from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, ConfigDict
from psycopg2.errors import UndefinedTable
from app.modules.saas.services import saas_services as service
from app.core.security import require_permission, require_platform_admin
from app.core.tenant_guard import resolver_tenant_operacion, validar_acceso_recurso_tenant

router = APIRouter(tags=['SaaS — Planes, Suscripciones, Contratación Autónoma y Storefront'])


class PlanIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    nombre: str = Field(min_length=2, max_length=80)
    activo: bool
    precio_mensual: Optional[float] = Field(default=None, gt=0)
    precio_anual: Optional[float] = Field(default=None, gt=0)
    descripcion: Optional[str] = Field(default=None, max_length=500)


class SuscripcionIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    codigo_plan: Literal['BASICO', 'PROFESIONAL']
    inicio: datetime
    fin: datetime
    motivo: str = Field(min_length=3, max_length=500)


class CancelacionIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    motivo: str = Field(min_length=3, max_length=500)
    confirmar: Literal[True]


class RegistroContratacionIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    nombre: str = Field(min_length=2, max_length=80)
    apellido: str = Field(min_length=2, max_length=80)
    correo: str = Field(min_length=5, max_length=120)
    telefono: Optional[str] = Field(default='', max_length=30)
    password: str = Field(min_length=8, max_length=120)
    confirm_password: str = Field(min_length=8, max_length=120)
    nombre_comercial: str = Field(min_length=2, max_length=100)
    razon_social: Optional[str] = Field(default=None, max_length=120)
    nit: Optional[str] = Field(default='', max_length=40)
    ciudad: Optional[str] = Field(default='Santa Cruz', max_length=60)
    direccion_fiscal: Optional[str] = Field(default='', max_length=200)
    slug: str = Field(min_length=3, max_length=70)
    codigo_plan: Literal['BASICO', 'PROFESIONAL'] = 'BASICO'
    periodicidad: Literal['MENSUAL', 'ANUAL'] = 'MENSUAL'
    publicos_objetivo: Optional[List[str]] = Field(default=None)


class VerificarCorreoIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    codigo_seguimiento: str = Field(min_length=4, max_length=50)
    token: str = Field(min_length=8, max_length=200)


class CapturarPayPalContratacionIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    order_id: str = Field(min_length=4, max_length=120)


class ComprobanteContratacionIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    comprobante_url: str = Field(min_length=5, max_length=800)
    referencia_pago: Optional[str] = Field(default='QR-TRANSFERENCIA', max_length=150)


class SolicitarPlanIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    codigo_plan: Literal['BASICO', 'PROFESIONAL']
    periodicidad: Literal['MENSUAL', 'ANUAL'] = 'MENSUAL'
    momento_cambio: Literal['SIGUIENTE_CICLO', 'INMEDIATO'] = 'SIGUIENTE_CICLO'
    motivo: Optional[str] = Field(default=None, max_length=250)


class CrearOrdenPayPalIn(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    origen: Optional[str] = 'comercial'
    retorno_url: Optional[str] = None


class CancelacionComercialIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    tipo_cancelacion: Literal['FIN_DE_CICLO', 'REEMBOLSO_INMEDIATO'] = 'FIN_DE_CICLO'
    motivo: Optional[str] = Field(default=None, max_length=250)


class ResolverContratacionIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    accion: Literal['APROBAR', 'RECHAZAR']
    observaciones: str = Field(min_length=3, max_length=500)


class SeccionStorefrontIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    codigo: Literal['banner', 'publicos', 'categorias', 'colecciones', 'destacados', 'novedades', 'recomendaciones']
    visible: bool = True
    orden: int = Field(ge=1, le=20)


class StorefrontConfigIn(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    nombre_comercial: Optional[str] = Field(default=None, max_length=100)
    slug: Optional[str] = Field(default=None, max_length=70)
    logo: Optional[str] = Field(default=None, max_length=500)
    eslogan: Optional[str] = Field(default=None, max_length=160)
    color_primario: Optional[str] = Field(default=None, max_length=10)
    color_secundario: Optional[str] = Field(default=None, max_length=10)
    tipografia: Optional[Literal['editorial', 'moderna', 'clasica', 'minimal']] = None
    estilo_tarjetas: Optional[Literal['editorial', 'minimal', 'borde_suave']] = None
    banner_titulo: Optional[str] = Field(default=None, max_length=120)
    banner_subtitulo: Optional[str] = Field(default=None, max_length=280)
    banner_imagen_url: Optional[str] = Field(default=None, max_length=500)
    banner_cta_texto: Optional[str] = Field(default=None, max_length=40)
    publicos_habilitados: Optional[List[str]] = None
    colecciones_destacadas: Optional[List[str]] = None
    secciones: Optional[List[SeccionStorefrontIn]] = None
    onboarding_completado: Optional[bool] = None


# ==============================================================================
# ENDPOINTS PÚBLICOS DEL SITIO COMERCIAL DE AURORASTORE
# ==============================================================================

@router.get('/api/public/planes')
def planes_publicos():
    """Catálogo público de planes activos y contratables (con precio, periodicidad, límites y beneficios)."""
    return {'success': True, 'data': service.listar_planes(solo_activos=True)}


@router.get('/api/public/tenant/check-slug')
def check_slug_disponible(
    slug: str = Query(..., min_length=2, max_length=80),
    exclude_id_empresa: Optional[int] = Query(None, gt=0)
):
    """Valida en tiempo real si un slug para subdominio/tienda está disponible."""
    return {'success': True, 'data': service.verificar_disponibilidad_slug(slug, exclude_id_empresa)}


@router.post('/api/public/contratacion/registro', status_code=201)
def registrar_contratacion(data: RegistroContratacionIn):
    """Registro autónomo de empresa y propietario (ADMINISTRADOR_TIENDA) con envío de verificación de correo."""
    res = service.registrar_contratacion_autonoma(data.model_dump())
    return {'success': True, 'data': res}


@router.post('/api/public/contratacion/verificar-correo')
def verificar_correo(data: VerificarCorreoIn):
    """Verifica el token criptográfico de un solo uso y habilita la etapa de pago."""
    res = service.verificar_correo_contratacion(data.codigo_seguimiento, data.token)
    return {'success': True, 'data': res}


@router.post('/api/public/contratacion/{codigo_seguimiento}/reenviar-verificacion')
def reenviar_verificacion(codigo_seguimiento: str):
    """Genera un nuevo token criptográfico de verificación y reenvía el correo."""
    res = service.reenviar_verificacion_correo(codigo_seguimiento)
    return {'success': True, 'data': res}


@router.get('/api/public/contratacion/{codigo_seguimiento}')
def estado_contratacion(codigo_seguimiento: str):
    """Consulta el resumen y estado actual de una contratación por su código de seguimiento."""
    res = service.obtener_estado_contratacion_por_codigo(codigo_seguimiento)
    return {'success': True, 'data': res}


@router.post('/api/public/contratacion/{codigo_seguimiento}/paypal/crear-orden')
def crear_orden_paypal(codigo_seguimiento: str, data: Optional[CrearOrdenPayPalIn] = None):
    """Crea una orden en PayPal Sandbox para la solicitud de contratación verificada."""
    origen = data.origen if data else 'comercial'
    retorno_url = data.retorno_url if data else None
    res = service.crear_orden_paypal_contratacion(codigo_seguimiento, origen=origen, retorno_url=retorno_url)
    return {'success': True, 'data': res}


@router.post('/api/public/contratacion/{codigo_seguimiento}/paypal/capturar')
def capturar_orden_paypal(codigo_seguimiento: str, data: CapturarPayPalContratacionIn):
    """Valida server-to-server la captura en PayPal y activa automáticamente la empresa y suscripción."""
    res = service.capturar_pago_paypal_contratacion(codigo_seguimiento, data.order_id)
    return {'success': True, 'data': res}


@router.post('/api/public/contratacion/{codigo_seguimiento}/pago-comprobante')
def enviar_comprobante_json(codigo_seguimiento: str, data: ComprobanteContratacionIn):
    """Registra el comprobante de pago por QR/Transferencia quedando pendiente de verificación administrativa."""
    res = service.registrar_comprobante_pago_contratacion(
        codigo_seguimiento=codigo_seguimiento,
        comprobante_url=data.comprobante_url,
        referencia_pago=data.referencia_pago or 'QR-TRANSFERENCIA'
    )
    return {'success': True, 'data': res}


@router.post('/api/public/contratacion/{codigo_seguimiento}/subir-comprobante')
async def subir_comprobante_archivo(
    codigo_seguimiento: str,
    archivo: UploadFile = File(...),
    referencia_pago: str = Form('QR-TRANSFERENCIA')
):
    """Sube la imagen del comprobante a Cloudinary y registra la solicitud en PENDIENTE_VERIFICACION_PAGO."""
    from app.shared import cloudinary_service
    try:
        contenido = await archivo.read()
        if not contenido:
            raise HTTPException(400, detail='El archivo del comprobante está vacío.')
        upload_res = cloudinary_service.upload_image(
            file_bytes=contenido,
            folder='aurorastore/comprobantes_saas',
            public_id=f"comprobante_{codigo_seguimiento.lower()}"
        )
        url = upload_res.get('secure_url') or upload_res.get('url')
        if not url:
            raise HTTPException(502, detail='No se pudo obtener la URL del comprobante subido.')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, detail=f'Error al subir comprobante: {str(e)}')

    res = service.registrar_comprobante_pago_contratacion(
        codigo_seguimiento=codigo_seguimiento,
        comprobante_url=url,
        referencia_pago=referencia_pago
    )
    return {'success': True, 'data': res}


# ==============================================================================
# ENDPOINTS DE ADMINISTRACIÓN DE PLANES, SUSCRIPCIONES Y CONTRATACIONES
# ==============================================================================

@router.get('/api/planes')
def planes(payload=Depends(require_permission('planes.ver'))):
    return {'success': True, 'data': service.listar_planes()}


@router.put('/api/planes/{codigo}', dependencies=[Depends(require_platform_admin)])
def actualizar_plan(
    codigo: Literal['BASICO', 'PROFESIONAL'],
    data: PlanIn,
    payload=Depends(require_permission('planes.gestionar'))
):
    return {
        'success': True,
        'data': service.actualizar_plan(
            codigo,
            data.nombre,
            data.activo,
            payload,
            precio_mensual=data.precio_mensual,
            precio_anual=data.precio_anual,
            descripcion=data.descripcion
        )
    }


@router.get('/api/contrataciones', dependencies=[Depends(require_platform_admin)])
def listar_contrataciones(
    estado: Optional[str] = Query(None),
    payload=Depends(require_permission('suscripciones.gestionar'))
):
    """Lista las solicitudes de contratación autónoma para verificación por SuperAdmin."""
    return {'success': True, 'data': service.listar_solicitudes_contratacion(estado)}


@router.post('/api/contrataciones/{id_solicitud}/resolver', dependencies=[Depends(require_platform_admin)])
def resolver_contratacion(
    id_solicitud: int,
    data: ResolverContratacionIn,
    payload=Depends(require_permission('suscripciones.gestionar'))
):
    """Aprueba o rechaza una solicitud de contratación pendiente de verificación de comprobante."""
    return {
        'success': True,
        'data': service.resolver_solicitud_contratacion(
            id_solicitud=id_solicitud,
            accion=data.accion,
            observaciones=data.observaciones,
            actor=payload
        )
    }


@router.get('/api/mi-empresa/plan')
def mi_plan(id_empresa: int | None = Query(None, gt=0), payload=Depends(require_permission('suscripciones.ver'))):
    empresa = id_empresa or payload.get('id_empresa')
    if not empresa:
        raise HTTPException(400, detail='Seleccione una empresa.')
    validar_acceso_recurso_tenant(payload, empresa, 'plan')
    return {'success': True, 'data': service.consultar_plan(empresa)}


@router.get('/api/mi-empresa/contratacion-activa')
def obtener_mi_contratacion_activa(
    id_empresa: int | None = Query(None, gt=0),
    payload=Depends(require_permission('suscripciones.ver'))
):
    """Obtiene la solicitud de contratación más reciente (activa o pendiente de pago) de la empresa."""
    empresa = id_empresa or payload.get('id_empresa')
    if not empresa:
        raise HTTPException(400, detail='Seleccione una empresa.')
    validar_acceso_recurso_tenant(payload, empresa, 'contratacion')
    res = service.obtener_contratacion_activa_empresa(empresa)
    return {'success': True, 'data': res}


@router.post('/api/mi-empresa/suscripcion/solicitar', status_code=201)
def solicitar_suscripcion_tenant(
    data: SolicitarPlanIn,
    id_empresa: int | None = Query(None, gt=0),
    payload=Depends(require_permission('suscripciones.ver'))
):
    """Permite al administrador del tenant solicitar una renovación o cambio de plan (Upgrade/Downgrade)."""
    empresa = id_empresa or payload.get('id_empresa')
    if not empresa:
        raise HTTPException(400, detail='Seleccione una empresa.')
    validar_acceso_recurso_tenant(payload, empresa, 'suscripcion')
    id_usuario = payload.get('id_usuario') or payload.get('nro_usuario') or 1
    res = service.solicitar_renovacion_o_cambio_plan(
        id_empresa=empresa,
        id_usuario=id_usuario,
        datos=data.model_dump(exclude_none=True)
    )
    return {'success': True, 'data': res}


@router.get('/api/mi-empresa/suscripcion/opciones-cancelacion')
def opciones_cancelacion_tenant(
    id_empresa: int | None = Query(None, gt=0),
    payload=Depends(require_permission('suscripciones.ver'))
):
    """Calcula las opciones comerciales de cancelación y reembolso disponibles para la suscripción activa."""
    empresa = id_empresa or payload.get('id_empresa')
    if not empresa:
        raise HTTPException(400, detail='Seleccione una empresa.')
    validar_acceso_recurso_tenant(payload, empresa, 'suscripcion')
    res = service.obtener_opciones_cancelacion_suscripcion(empresa)
    return {'success': True, 'data': res}


@router.post('/api/mi-empresa/suscripcion/cancelar')
def cancelar_suscripcion_tenant(
    data: CancelacionComercialIn,
    id_empresa: int | None = Query(None, gt=0),
    payload=Depends(require_permission('suscripciones.ver'))
):
    """Permite al propietario cancelar su suscripción al término del ciclo o con reembolso si <= 10% consumido."""
    empresa = id_empresa or payload.get('id_empresa')
    if not empresa:
        raise HTTPException(400, detail='Seleccione una empresa.')
    validar_acceso_recurso_tenant(payload, empresa, 'suscripcion')
    id_usuario = payload.get('id_usuario') or payload.get('nro_usuario') or 1
    res = service.procesar_cancelacion_comercial_tenant(
        id_empresa=empresa,
        id_usuario=id_usuario,
        datos=data.model_dump(exclude_none=True)
    )
    return {'success': True, 'data': res}


@router.get('/api/mi-empresa/storefront')
def obtener_mi_storefront(
    id_empresa: int | None = Query(None, gt=0),
    payload=Depends(require_permission('storefront.configurar'))
):
    """Obtiene la configuración actual del storefront y el progreso de onboarding de la empresa."""
    empresa = id_empresa or payload.get('id_empresa')
    if not empresa:
        raise HTTPException(400, detail='Seleccione una empresa.')
    validar_acceso_recurso_tenant(payload, empresa, 'storefront')
    return {'success': True, 'data': service.obtener_configuracion_storefront_empresa(empresa)}


@router.put('/api/mi-empresa/storefront')
def actualizar_mi_storefront(
    data: StorefrontConfigIn,
    id_empresa: int | None = Query(None, gt=0),
    payload=Depends(require_permission('storefront.configurar'))
):
    """Actualiza las opciones controladas de personalización visual, públicos y secciones del storefront."""
    empresa = id_empresa or payload.get('id_empresa')
    if not empresa:
        raise HTTPException(400, detail='Seleccione una empresa.')
    validar_acceso_recurso_tenant(payload, empresa, 'storefront')
    res = service.actualizar_configuracion_storefront_empresa(
        id_empresa=empresa,
        datos=data.model_dump(exclude_none=True),
        actor=payload
    )
    return {'success': True, 'data': res}


@router.get('/api/empresas/{id_empresa}/suscripciones')
def suscripciones(id_empresa: int, payload=Depends(require_permission('suscripciones.ver'))):
    validar_acceso_recurso_tenant(payload, id_empresa, 'suscripciones')
    try:
        return {'success': True, 'data': service.historial(id_empresa)}
    except UndefinedTable:
        raise HTTPException(503, detail={'code': 'MIGRACION_PENDIENTE', 'message': 'Aplique la migración SaaS.'})


@router.post('/api/empresas/{id_empresa}/suscripciones', status_code=201, dependencies=[Depends(require_platform_admin)])
def asignar_suscripcion(id_empresa: int, data: SuscripcionIn, payload=Depends(require_permission('suscripciones.gestionar'))):
    return {'success': True, 'data': service.crear_suscripcion(id_empresa, data.model_dump(), payload)}


@router.post('/api/empresas/{id_empresa}/suscripciones/{id_suscripcion}/cancelar', dependencies=[Depends(require_platform_admin)])
def cancelar_suscripcion(id_empresa: int, id_suscripcion: int, data: CancelacionIn, payload=Depends(require_permission('suscripciones.gestionar'))):
    return {'success': True, 'data': service.cancelar_suscripcion(id_empresa, id_suscripcion, data.motivo, payload)}
