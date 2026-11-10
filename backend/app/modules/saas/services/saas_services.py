"""SaaS Services: Plans, Subscriptions, Autonomous Contracting, Payment Verification, and Storefront Configuration."""
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from psycopg2.errors import UndefinedTable
from psycopg2.extras import Json
from app.core.postgres import transaction
from app.core.config import Config
from app.core import security
from app.shared import email_service
from app.modules.catalogo.repos.catalogo_repos import _normalizar_config_storefront
from app.modules.catalogo.routes.catalogo_routes import invalidar_cache_catalogo_publico

SLUGS_RESERVADOS = {
    'admin', 'administracion', 'saas', 'api', 'auth', 'login', 'registro',
    'planes', 'catalogo', 'explorar', 'carrito', 'checkout', 'perfil',
    'reservas', 'devoluciones', 'www', 'aurora', 'aurorastore', 'static',
    'assets', 'public', 'support', 'soporte', 'billing', 'pagos'
}

PUBLICOS_PERMITIDOS = {'Mujer', 'Hombre', 'Unisex', 'Niños', 'Niñas', 'Bebés'}
TIPOGRAFIAS_PERMITIDAS = {'editorial', 'moderna', 'clasica', 'minimal'}
ESTILOS_TARJETA_PERMITIDOS = {'editorial', 'minimal', 'borde_suave'}
SECCIONES_PERMITIDAS = {'banner', 'publicos', 'categorias', 'colecciones', 'destacados', 'novedades', 'recomendaciones'}


def _schema():
    return Config.SCHEMA or 'comercio'


def _generar_codigo_seguimiento() -> str:
    return f"AUR-{datetime.now(timezone.utc).strftime('%y%m')}-{secrets.token_hex(3).upper()}"


def _error(status, code, message):
    raise HTTPException(status_code=status, detail={'code': code, 'message': message})


def auditar(db, actor, empresa, accion, datos):
    actor_id = None
    if isinstance(actor, dict):
        actor_id = actor.get('id_usuario') or actor.get('nro_usuario')
    elif isinstance(actor, int):
        actor_id = actor
    db.execute_query(
        f'''INSERT INTO {_schema()}.t_bitacora
        (id_usuario,id_empresa,modulo,accion,entidad,resultado,nivel,descripcion,datos_nuevos)
        VALUES (%s,%s,'SAAS',%s,'empresa','EXITO','INFO',%s,%s)''',
        (actor_id, empresa, accion, accion, Json(datos))
    )


def _limpiar_slug(valor: str) -> str:
    if not valor:
        return ''
    s = re.sub(r'[^a-z0-9]+', '-', valor.strip().lower()).strip('-')
    return s[:70]


def verificar_disponibilidad_slug(slug_raw: str, exclude_id_empresa: Optional[int] = None) -> Dict[str, Any]:
    slug = _limpiar_slug(slug_raw)
    if len(slug) < 3:
        return {
            'disponible': False,
            'slug_normalizado': slug,
            'motivo': 'El identificador (slug) debe tener al menos 3 caracteres alfanuméricos.'
        }
    if slug in SLUGS_RESERVADOS:
        sugerencia = f'{slug}-tienda'
        return {
            'disponible': False,
            'slug_normalizado': slug,
            'sugerencia': sugerencia,
            'motivo': 'Este identificador está reservado por la plataforma.'
        }
    with transaction() as db:
        if exclude_id_empresa:
            row = db.execute_query(
                f'SELECT 1 FROM {_schema()}.empresa WHERE LOWER(slug) = %s AND id_empresa != %s LIMIT 1',
                (slug, exclude_id_empresa),
                fetchone=True
            )
        else:
            row = db.execute_query(
                f'SELECT 1 FROM {_schema()}.empresa WHERE LOWER(slug) = %s LIMIT 1',
                (slug,),
                fetchone=True
            )
        if row:
            sufijo = secrets.token_hex(2)
            return {
                'disponible': False,
                'slug_normalizado': slug,
                'sugerencia': f'{slug}-{sufijo}',
                'motivo': 'Ya existe una tienda registrada con este subdominio/slug.'
            }
        return {
            'disponible': True,
            'slug_normalizado': slug,
            'motivo': 'Disponible'
        }


def listar_planes(solo_activos: bool = False) -> List[Dict[str, Any]]:
    try:
        with transaction() as db:
            cond = 'WHERE activo = TRUE' if solo_activos else ''
            rows = db.execute_query(
                f'''SELECT codigo, nombre, max_sucursales, reportes_generativos, activo,
                           COALESCE(precio_mensual, 199.00) AS precio_mensual,
                           COALESCE(precio_anual, 1990.00) AS precio_anual,
                           COALESCE(moneda, 'BOB') AS moneda,
                           COALESCE(descripcion, '') AS descripcion,
                           COALESCE(beneficios, '[]'::jsonb) AS beneficios
                    FROM {_schema()}.t_plan
                    {cond}
                    ORDER BY max_sucursales''',
                fetchall=True
            )
            planes = []
            for r in rows or []:
                planes.append({
                    'codigo': r[0],
                    'nombre': r[1],
                    'max_sucursales': int(r[2]),
                    'reportes_generativos': bool(r[3]),
                    'activo': bool(r[4]),
                    'precio_mensual': float(r[5]),
                    'precio_anual': float(r[6]),
                    'moneda': r[7] or 'BOB',
                    'descripcion': r[8] or '',
                    'beneficios': r[9] if isinstance(r[9], list) else []
                })
            return planes
    except UndefinedTable:
        _error(503, 'MIGRACION_PENDIENTE', 'La migración SaaS todavía no fue aplicada.')


def actualizar_plan(codigo, nombre, activo, actor, precio_mensual=None, precio_anual=None, descripcion=None):
    with transaction() as db:
        campos = ['nombre=%s', 'activo=%s']
        params = [nombre, activo]
        if precio_mensual is not None:
            campos.append('precio_mensual=%s')
            params.append(precio_mensual)
        if precio_anual is not None:
            campos.append('precio_anual=%s')
            params.append(precio_anual)
        if descripcion is not None:
            campos.append('descripcion=%s')
            params.append(descripcion)
        params.append(codigo)
        row = db.execute_query(
            f"UPDATE {_schema()}.t_plan SET {', '.join(campos)} WHERE codigo=%s RETURNING codigo",
            tuple(params),
            fetchone=True
        )
        if not row:
            _error(404, 'PLAN_NO_ENCONTRADO', 'Plan inexistente.')
        auditar(db, actor, None, 'PLAN_ACTUALIZADO', {'codigo': codigo, 'nombre': nombre, 'activo': activo})
    return next(p for p in listar_planes() if p['codigo'] == codigo)


def _empresa(db, empresa, lock=False):
    row = db.execute_query(
        f'SELECT estado FROM {_schema()}.empresa WHERE id_empresa=%s' + (' FOR UPDATE' if lock else ''),
        (empresa,),
        fetchone=True
    )
    if not row:
        _error(404, 'EMPRESA_NO_ENCONTRADA', 'Empresa inexistente.')
    return row[0]


def historial(empresa):
    with transaction() as db:
        _empresa(db, empresa)
        rows = db.execute_query(
            f'''SELECT id_suscripcion,id_empresa,codigo_plan,inicio,fin,estado,motivo,creado_por,creado_en
            FROM {_schema()}.t_suscripcion WHERE id_empresa=%s ORDER BY inicio DESC,id_suscripcion DESC''',
            (empresa,),
            fetchall=True
        )
        return [
            dict(zip(('id_suscripcion', 'id_empresa', 'codigo_plan', 'inicio', 'fin', 'estado', 'motivo', 'creado_por', 'creado_en'), row))
            for row in rows
        ]


def consultar_plan(empresa):
    try:
        with transaction() as db:
            estado_empresa = _empresa(db, empresa)
            row = db.execute_query(
                f'''SELECT s.id_suscripcion,s.codigo_plan,s.inicio,s.fin,p.max_sucursales,p.reportes_generativos
                FROM {_schema()}.t_suscripcion s JOIN {_schema()}.t_plan p ON p.codigo=s.codigo_plan
                WHERE s.id_empresa=%s AND s.estado='ACTIVA' AND s.inicio<=now() AND s.fin>now()''',
                (empresa,),
                fetchone=True
            )
            usadas = db.execute_query(
                f'SELECT COUNT(*) FROM {_schema()}.t_sucursal WHERE id_empresa=%s AND COALESCE(activo,estado,FALSE)',
                (empresa,),
                fetchone=True
            )[0]
            estado = 'VIGENTE' if row else 'SIN_SUSCRIPCION'
            if not row:
                ultima = db.execute_query(
                    f'''SELECT estado,fin,inicio FROM {_schema()}.t_suscripcion
                    WHERE id_empresa=%s ORDER BY fin DESC LIMIT 1''',
                    (empresa,),
                    fetchone=True
                )
                if ultima:
                    estado = 'CANCELADA' if ultima[0] == 'CANCELADA' else ('PROGRAMADA' if ultima[2] > datetime.now(timezone.utc) else 'VENCIDA')
            if estado_empresa == 'PENDIENTE':
                estado = 'PENDIENTE_ACTIVACION'
            elif estado_empresa != 'ACTIVO':
                estado = 'EMPRESA_INACTIVA'

            # Consultar última solicitud de contratación para advertir estados de pago / activación
            solicitud_contratacion = None
            try:
                sol_row = db.execute_query(
                    f'''SELECT s.id_solicitud, s.codigo_seguimiento, s.estado_contratacion, s.codigo_plan,
                               s.periodicidad, s.monto, s.moneda, s.metodo_pago, s.correo_verificado,
                               p.nombre AS nombre_plan, s.paypal_order_id, s.comprobante_url
                        FROM {_schema()}.t_solicitud_contratacion s
                        LEFT JOIN {_schema()}.t_plan p ON p.codigo = s.codigo_plan
                        WHERE s.id_empresa = %s
                        ORDER BY s.id_solicitud DESC LIMIT 1''',
                    (empresa,),
                    fetchone=True
                )
                if sol_row:
                    solicitud_contratacion = {
                        'id_solicitud': sol_row[0],
                        'codigo_seguimiento': sol_row[1],
                        'estado_contratacion': sol_row[2],
                        'codigo_plan': sol_row[3],
                        'periodicidad': sol_row[4],
                        'monto': float(sol_row[5]) if sol_row[5] is not None else 0.0,
                        'moneda': sol_row[6] or 'BOB',
                        'metodo_pago': sol_row[7],
                        'correo_verificado': bool(sol_row[8]),
                        'nombre_plan': sol_row[9] or sol_row[3],
                        'paypal_order_id': sol_row[10],
                        'comprobante_url': sol_row[11]
                    }
                    if estado in ('EMPRESA_INACTIVA', 'SIN_SUSCRIPCION') and sol_row[2] in ('PENDIENTE_PAGO', 'PENDIENTE_VERIFICACION_CORREO', 'PENDIENTE_VERIFICACION_PAGO'):
                        estado = 'PENDIENTE_ACTIVACION'
            except Exception:
                pass

            vigente = estado == 'VIGENTE'
            return {
                'id_empresa': empresa,
                'estado': estado,
                'vigente': vigente,
                'id_suscripcion': row[0] if row else None,
                'codigo_plan': row[1] if row else None,
                'inicio': row[2] if row else None,
                'fin': row[3] if row else None,
                'limites': {'sucursales_activas': row[4] if row else None},
                'uso': {'sucursales_activas': usadas},
                'disponibles': max(0, row[4] - usadas) if vigente else 0,
                'capacidades': {'reportes_generativos': bool(vigente and row[5]) if row else False},
                'solicitud_contratacion': solicitud_contratacion
            }
    except UndefinedTable:
        _error(503, 'MIGRACION_PENDIENTE', 'La migración SaaS todavía no fue aplicada.')


def exigir_vigencia(empresa, reportes=False):
    estado = consultar_plan(empresa)
    if not estado['vigente']:
        _error(403, 'SUSCRIPCION_NO_VIGENTE', 'La empresa no tiene una suscripción vigente.')
    if reportes and not estado['capacidades']['reportes_generativos']:
        _error(403, 'PLAN_NO_HABILITA_REPORTES', 'El motor de reportes requiere el plan Profesional.')
    return estado


def crear_suscripcion(empresa, datos, actor):
    inicio, fin = datos['inicio'], datos['fin']
    now = datetime.now(timezone.utc)
    if inicio.tzinfo is None or fin.tzinfo is None or fin <= inicio or fin <= now:
        _error(422, 'PERIODO_INVALIDO', 'Indique fechas con zona horaria, fin futuro y posterior al inicio.')
    with transaction() as db:
        if _empresa(db, empresa, lock=True) != 'ACTIVO':
            _error(409, 'EMPRESA_INACTIVA', 'Active la empresa antes de asignar la suscripción.')
        plan = db.execute_query(
            f'SELECT max_sucursales FROM {_schema()}.t_plan WHERE codigo=%s AND activo FOR SHARE',
            (datos['codigo_plan'],),
            fetchone=True
        )
        if not plan:
            _error(404, 'PLAN_NO_ENCONTRADO', 'El plan no existe o está inactivo.')
        usadas = db.execute_query(
            f'SELECT COUNT(*) FROM {_schema()}.t_sucursal WHERE id_empresa=%s AND COALESCE(activo,estado,FALSE)',
            (empresa,),
            fetchone=True
        )[0]
        if usadas > plan[0]:
            _error(409, 'LIMITE_SUCURSALES', 'Reduzca las sucursales activas antes de asignar este plan.')
        overlap = db.execute_query(
            f"SELECT 1 FROM {_schema()}.t_suscripcion WHERE id_empresa=%s AND estado='ACTIVA' AND inicio<%s AND fin>%s",
            (empresa, fin, inicio),
            fetchone=True
        )
        if overlap:
            _error(409, 'PERIODO_SOLAPADO', 'El periodo se superpone con otra suscripción activa.')
        row = db.execute_query(
            f'''INSERT INTO {_schema()}.t_suscripcion(id_empresa,codigo_plan,inicio,fin,motivo,creado_por)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_suscripcion''',
            (empresa, datos['codigo_plan'], inicio, fin, datos['motivo'], actor['id_usuario']),
            fetchone=True
        )
        auditar(db, actor, empresa, 'SUSCRIPCION_CREADA', {
            'id_suscripcion': row[0],
            'codigo_plan': datos['codigo_plan'],
            'inicio': inicio.isoformat(),
            'fin': fin.isoformat(),
            'motivo': datos['motivo']
        })
    return next(s for s in historial(empresa) if s['id_suscripcion'] == row[0])


def cancelar_suscripcion(empresa, suscripcion, motivo, actor):
    with transaction() as db:
        _empresa(db, empresa, lock=True)
        row = db.execute_query(
            f'''UPDATE {_schema()}.t_suscripcion SET estado='CANCELADA'
            WHERE id_suscripcion=%s AND id_empresa=%s AND estado='ACTIVA' RETURNING id_suscripcion''',
            (suscripcion, empresa),
            fetchone=True
        )
        if not row:
            _error(404, 'SUSCRIPCION_NO_ENCONTRADA', 'Suscripción inexistente o ya cancelada.')
        auditar(db, actor, empresa, 'SUSCRIPCION_CANCELADA', {'id_suscripcion': suscripcion, 'motivo': motivo})
    return {'id_suscripcion': suscripcion, 'estado': 'CANCELADA'}


# ==============================================================================
# CONTRATACIÓN SAAS AUTÓNOMA Y VERIFICACIÓN DE CORREO / PAGO
# ==============================================================================

def _enviar_correo_verificacion_saas(
    destinatario: str,
    nombre_propietario: str,
    nombre_empresa: str,
    codigo_seguimiento: str,
    raw_token: str,
    nombre_plan: str,
    monto: float,
    moneda: str
) -> bool:
    asunto = f"Verifica tu correo — Contratación AuroraStore ({nombre_empresa})"
    frontend_base = getattr(Config, 'FRONTEND_URL', None) or 'http://localhost:4200'
    url_verificacion = f"{frontend_base.rstrip('/')}/saas/contratacion/{codigo_seguimiento}?token={raw_token}"
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <body style="margin:0;padding:24px;background:#f8fafc;font-family:'Segoe UI',Arial,sans-serif;color:#0f172a;">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:580px;margin:0 auto;background:#ffffff;border-radius:16px;border:1px solid #e2e8f0;overflow:hidden;">
        <tr>
          <td style="background:#0f172a;padding:28px 32px;color:#ffffff;">
            <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#94a3b8;font-weight:700;">AuroraStore Cloud SaaS</div>
            <h1 style="margin:8px 0 0;font-size:22px;font-weight:800;">Confirma la titularidad de tu correo</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <p style="margin:0 0 16px;font-size:15px;line-height:1.6;">Hola <strong>{nombre_propietario}</strong>,</p>
            <p style="margin:0 0 16px;font-size:14px;line-height:1.6;color:#334155;">
              Recibimos tu solicitud de contratación para la tienda <strong>{nombre_empresa}</strong> en el plan
              <strong>{nombre_plan}</strong> ({moneda} {monto:.2f}).
            </p>
            <p style="margin:0 0 24px;font-size:14px;line-height:1.6;color:#334155;">
              Haz clic en el siguiente botón para verificar tu correo electrónico y continuar con el pago de activación:
            </p>
            <div style="text-align:center;margin:28px 0;">
              <a href="{url_verificacion}" style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:12px;font-weight:700;font-size:14px;">
                Verificar mi correo y continuar
              </a>
            </div>
            <div style="background:#f1f5f9;border-radius:12px;padding:16px;margin-top:20px;font-size:12px;color:#475569;">
              <div><strong>Código de seguimiento:</strong> {codigo_seguimiento}</div>
              <div style="margin-top:6px;word-break:break-all;"><strong>Token de verificación:</strong> {raw_token}</div>
              <div style="margin-top:6px;color:#64748b;">Este enlace es de un solo uso y expira en 24 horas.</div>
            </div>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    try:
        return email_service.enviar_correo_html_brevo(
            destinatario_email=destinatario,
            destinatario_nombre=nombre_propietario,
            asunto=asunto,
            html_content=html,
            sender_name="AuroraStore Cloud SaaS"
        )
    except Exception as e:
        print(f"[SAAS CORREO ERROR] Fallo al despachar correo de verificación: {e}")
        return False


def registrar_contratacion_autonoma(datos: Dict[str, Any]) -> Dict[str, Any]:
    correo = (datos.get('correo') or '').strip().lower()
    password = datos.get('password') or ''
    confirm_password = datos.get('confirm_password') or ''
    nombre = (datos.get('nombre') or '').strip()
    apellido = (datos.get('apellido') or '').strip()
    telefono = (datos.get('telefono') or '').strip()
    nombre_comercial = (datos.get('nombre_comercial') or '').strip()
    razon_social = (datos.get('razon_social') or nombre_comercial).strip()
    nit = (datos.get('nit') or '').strip()
    ciudad = (datos.get('ciudad') or 'Santa Cruz').strip()
    direccion_fiscal = (datos.get('direccion_fiscal') or '').strip()
    slug_deseado = _limpiar_slug(datos.get('slug') or nombre_comercial)
    codigo_plan = (datos.get('codigo_plan') or 'BASICO').strip().upper()
    periodicidad = (datos.get('periodicidad') or 'MENSUAL').strip().upper()
    publicos_iniciales = [p for p in (datos.get('publicos_objetivo') or []) if p in PUBLICOS_PERMITIDOS]

    if password != confirm_password:
        _error(422, 'PASSWORD_MISMATCH', 'Las contraseñas ingresadas no coinciden.')
    if not security.validar_password(password):
        _error(422, 'PASSWORD_WEAK', 'La contraseña debe tener al menos 8 caracteres e incluir un carácter especial.')

    disp_slug = verificar_disponibilidad_slug(slug_deseado)
    if not disp_slug['disponible']:
        _error(409, 'SLUG_NO_DISPONIBLE', disp_slug['motivo'])

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    expira_en = datetime.now(timezone.utc) + timedelta(hours=24)
    codigo_seguimiento = f"AUR-{datetime.now(timezone.utc).strftime('%y%m')}-{secrets.token_hex(3).upper()}"

    with transaction() as db:
        # 1. Validar plan activo y obtener precio oficial desde BD
        plan_row = db.execute_query(
            f'''SELECT codigo, nombre, max_sucursales, reportes_generativos,
                       COALESCE(precio_mensual, 199.00), COALESCE(precio_anual, 1990.00), COALESCE(moneda, 'BOB')
                FROM {_schema()}.t_plan
                WHERE codigo = %s AND activo = TRUE''',
            (codigo_plan,),
            fetchone=True
        )
        if not plan_row:
            _error(404, 'PLAN_NO_DISPONIBLE', 'El plan seleccionado no existe o no está disponible para contratación.')

        monto = float(plan_row[5]) if periodicidad == 'ANUAL' else float(plan_row[4])
        moneda = plan_row[6] or 'BOB'

        # 2. Validar unicidad de correo / username
        base_username = re.sub(r'[^a-zA-Z0-9_.]', '', correo.split('@')[0])[:24] or 'propietario'
        existe_correo = db.execute_query(
            f'SELECT 1 FROM {_schema()}.t_usuario WHERE LOWER(correo) = LOWER(%s) LIMIT 1',
            (correo,),
            fetchone=True
        )
        if existe_correo:
            _error(409, 'CORREO_DUPLICADO', 'Ya existe una cuenta registrada con este correo electrónico. Inicia sesión para gestionar tu suscripción.')

        username = base_username
        existe_user = db.execute_query(
            f'SELECT 1 FROM {_schema()}.t_usuario WHERE LOWER(username) = LOWER(%s) LIMIT 1',
            (username,),
            fetchone=True
        )
        if existe_user:
            username = f"{base_username}_{secrets.token_hex(2)}"

        # 3. Validar NIT si fue provisto
        if nit:
            existe_nit = db.execute_query(
                f'SELECT 1 FROM {_schema()}.empresa WHERE LOWER(nit) = LOWER(%s) LIMIT 1',
                (nit,),
                fetchone=True
            )
            if existe_nit:
                _error(409, 'NIT_DUPLICADO', 'Ya existe una empresa registrada con ese NIT.')
        else:
            nit = f"PEND-{secrets.token_hex(4).upper()}"

        # 4. Configuración inicial del storefront para el nuevo tenant
        config_inicial = _normalizar_config_storefront(
            {
                'nombre_comercial': nombre_comercial,
                'publicos_habilitados': publicos_iniciales or ['Mujer', 'Hombre', 'Unisex'],
                'onboarding_completado': False
            },
            nombre_comercial
        )

        # 5. Crear empresa en estado PENDIENTE (no activa hasta confirmar pago)
        emp_row = db.execute_query(
            f'''INSERT INTO {_schema()}.empresa
                (nombre_empresa, razon_social, nit, correo, telefono, direccion_fiscal, ciudad, slug, estado, configuracion_storefront, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PENDIENTE', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id_empresa''',
            (
                nombre_comercial.upper(),
                razon_social.upper(),
                nit,
                correo,
                telefono,
                direccion_fiscal,
                ciudad,
                slug_deseado,
                Json(config_inicial)
            ),
            fetchone=True
        )
        id_empresa = emp_row[0]

        # 6. Obtener rol ADMINISTRADOR_TIENDA (nunca ADMINISTRADOR global)
        rol_row = db.execute_query(
            f"SELECT id_rol FROM {_schema()}.t_rol WHERE nombre = 'ADMINISTRADOR_TIENDA' LIMIT 1",
            fetchone=True
        )
        id_rol_tienda = rol_row[0] if rol_row else 3

        password_hash = security.hash_password(password)
        user_row = db.execute_query(
            f'''INSERT INTO {_schema()}.t_usuario
                (id_rol, username, password_hash, correo, nombre, apellido, telefono, estado, fecha_registro, id_empresa, ciudad)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, %s, %s)
                RETURNING id_usuario''',
            (id_rol_tienda, username, password_hash, correo, nombre, apellido, telefono, id_empresa, ciudad),
            fetchone=True
        )
        id_usuario = user_row[0]

        db.execute_query(
            f'''INSERT INTO {_schema()}.t_usuario_rol (id_usuario, id_rol)
                VALUES (%s, %s) ON CONFLICT DO NOTHING''',
            (id_usuario, id_rol_tienda)
        )
        db.execute_query(
            f'''INSERT INTO {_schema()}.t_seguridad_usuario (id_usuario, intentos_fallidos)
                VALUES (%s, 0) ON CONFLICT DO NOTHING''',
            (id_usuario,)
        )

        # 7. Crear solicitud de contratación
        sol_row = db.execute_query(
            f'''INSERT INTO {_schema()}.t_solicitud_contratacion
                (codigo_seguimiento, id_empresa, id_usuario_propietario, codigo_plan, periodicidad,
                 monto, moneda, estado_contratacion, token_verificacion_hash, token_expira_en, correo_verificado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDIENTE_VERIFICACION_CORREO', %s, %s, FALSE)
                RETURNING id_solicitud''',
            (
                codigo_seguimiento,
                id_empresa,
                id_usuario,
                codigo_plan,
                periodicidad,
                monto,
                moneda,
                token_hash,
                expira_en
            ),
            fetchone=True
        )
        id_solicitud = sol_row[0]

        auditar(db, id_usuario, id_empresa, 'CONTRATACION_REGISTRADA', {
            'id_solicitud': id_solicitud,
            'codigo_seguimiento': codigo_seguimiento,
            'slug': slug_deseado,
            'codigo_plan': codigo_plan,
            'periodicidad': periodicidad,
            'monto': monto,
            'moneda': moneda
        })

    email_enviado = _enviar_correo_verificacion_saas(
        destinatario=correo,
        nombre_propietario=f"{nombre} {apellido}".strip(),
        nombre_empresa=nombre_comercial,
        codigo_seguimiento=codigo_seguimiento,
        raw_token=raw_token,
        nombre_plan=plan_row[1],
        monto=monto,
        moneda=moneda
    )

    detalle = obtener_estado_contratacion_por_codigo(codigo_seguimiento)
    detalle['email_enviado'] = email_enviado
    # En entorno de desarrollo / pruebas se incluye el token generado para facilitar la verificación si el buzón es de prueba
    detalle['token_verificacion_dev'] = raw_token
    return detalle


def verificar_correo_contratacion(codigo_seguimiento: str, token: str) -> Dict[str, Any]:
    if not codigo_seguimiento or not token:
        _error(400, 'DATOS_INCOMPLETOS', 'El código de seguimiento y el token de verificación son obligatorios.')
    token_hash = hashlib.sha256(token.strip().encode('utf-8')).hexdigest()
    now = datetime.now(timezone.utc)

    with transaction() as db:
        row = db.execute_query(
            f'''SELECT id_solicitud, id_empresa, id_usuario_propietario, estado_contratacion,
                       token_verificacion_hash, token_expira_en, token_usado_en, correo_verificado
                FROM {_schema()}.t_solicitud_contratacion
                WHERE UPPER(codigo_seguimiento) = UPPER(%s)
                FOR UPDATE''',
            (codigo_seguimiento.strip(),),
            fetchone=True
        )
        if not row:
            _error(404, 'CONTRATACION_NO_ENCONTRADA', 'No se encontró la solicitud de contratación indicada.')

        id_solicitud, id_empresa, id_usuario, estado_actual, db_hash, expira_en, usado_en, verificado = row

        if verificado and usado_en is not None:
            _error(409, 'TOKEN_YA_UTILIZADO', 'Este enlace de verificación ya fue utilizado anteriormente.')

        if not db_hash or not secrets.compare_digest(db_hash, token_hash):
            _error(400, 'TOKEN_INVALIDO', 'El token de verificación de correo no es válido.')

        if expira_en and expira_en < now:
            _error(410, 'TOKEN_EXPIRADO', 'El enlace de verificación ha expirado. Solicita un nuevo enlace.')

        nuevo_estado = 'PENDIENTE_PAGO' if estado_actual == 'PENDIENTE_VERIFICACION_CORREO' else estado_actual
        db.execute_query(
            f'''UPDATE {_schema()}.t_solicitud_contratacion
                SET correo_verificado = TRUE,
                    token_usado_en = CURRENT_TIMESTAMP,
                    token_verificacion_hash = NULL,
                    estado_contratacion = %s,
                    actualizado_en = CURRENT_TIMESTAMP
                WHERE id_solicitud = %s''',
            (nuevo_estado, id_solicitud)
        )
        auditar(db, id_usuario, id_empresa, 'CORREO_CONTRATACION_VERIFICADO', {
            'id_solicitud': id_solicitud,
            'codigo_seguimiento': codigo_seguimiento
        })

    return obtener_estado_contratacion_por_codigo(codigo_seguimiento)


def reenviar_verificacion_correo(codigo_seguimiento: str) -> Dict[str, Any]:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    expira_en = datetime.now(timezone.utc) + timedelta(hours=24)

    with transaction() as db:
        row = db.execute_query(
            f'''SELECT s.id_solicitud, s.id_empresa, s.id_usuario_propietario, s.correo_verificado,
                       s.monto, s.moneda, p.nombre, e.nombre_empresa, u.correo, u.nombre, u.apellido
                FROM {_schema()}.t_solicitud_contratacion s
                JOIN {_schema()}.t_plan p ON p.codigo = s.codigo_plan
                JOIN {_schema()}.empresa e ON e.id_empresa = s.id_empresa
                JOIN {_schema()}.t_usuario u ON u.id_usuario = s.id_usuario_propietario
                WHERE UPPER(s.codigo_seguimiento) = UPPER(%s)
                FOR UPDATE OF s''',
            (codigo_seguimiento.strip(),),
            fetchone=True
        )
        if not row:
            _error(404, 'CONTRATACION_NO_ENCONTRADA', 'No se encontró la solicitud de contratación.')
        if row[3]:
            _error(409, 'CORREO_YA_VERIFICADO', 'El correo electrónico de esta solicitud ya fue verificado.')

        db.execute_query(
            f'''UPDATE {_schema()}.t_solicitud_contratacion
                SET token_verificacion_hash = %s,
                    token_expira_en = %s,
                    token_usado_en = NULL,
                    actualizado_en = CURRENT_TIMESTAMP
                WHERE id_solicitud = %s''',
            (token_hash, expira_en, row[0])
        )

    enviado = _enviar_correo_verificacion_saas(
        destinatario=row[8],
        nombre_propietario=f"{row[9]} {row[10]}".strip(),
        nombre_empresa=row[7],
        codigo_seguimiento=codigo_seguimiento,
        raw_token=raw_token,
        nombre_plan=row[6],
        monto=float(row[4]),
        moneda=row[5]
    )
    return {
        'codigo_seguimiento': codigo_seguimiento,
        'email_enviado': enviado,
        'token_verificacion_dev': raw_token
    }


def obtener_estado_contratacion_por_codigo(codigo_seguimiento: str) -> Dict[str, Any]:
    with transaction() as db:
        row = db.execute_query(
            f'''SELECT s.id_solicitud, s.codigo_seguimiento, s.id_empresa, e.nombre_empresa, e.slug, e.estado AS estado_empresa,
                       s.id_usuario_propietario, u.nombre, u.apellido, u.correo,
                       s.codigo_plan, p.nombre AS nombre_plan, p.max_sucursales, p.reportes_generativos,
                       s.periodicidad, s.monto, s.moneda, s.estado_contratacion, s.correo_verificado,
                       s.metodo_pago, s.referencia_pago, s.paypal_order_id, s.comprobante_url,
                       s.id_suscripcion_generada, s.observaciones_revision,
                       s.creado_en, s.actualizado_en
                FROM {_schema()}.t_solicitud_contratacion s
                JOIN {_schema()}.empresa e ON e.id_empresa = s.id_empresa
                JOIN {_schema()}.t_usuario u ON u.id_usuario = s.id_usuario_propietario
                JOIN {_schema()}.t_plan p ON p.codigo = s.codigo_plan
                WHERE UPPER(s.codigo_seguimiento) = UPPER(%s)''',
            (codigo_seguimiento.strip(),),
            fetchone=True
        )
        if not row:
            _error(404, 'CONTRATACION_NO_ENCONTRADA', 'No se encontró una contratación con ese código.')

        return {
            'id_solicitud': row[0],
            'codigo_seguimiento': row[1],
            'id_empresa': row[2],
            'nombre_empresa': row[3],
            'slug': row[4],
            'estado_empresa': row[5],
            'id_usuario_propietario': row[6],
            'nombre_propietario': f"{row[7] or ''} {row[8] or ''}".strip(),
            'correo_propietario': row[9],
            'codigo_plan': row[10],
            'nombre_plan': row[11],
            'max_sucursales': int(row[12]),
            'reportes_generativos': bool(row[13]),
            'periodicidad': row[14],
            'monto': float(row[15]),
            'moneda': row[16],
            'estado_contratacion': row[17],
            'correo_verificado': bool(row[18]),
            'metodo_pago': row[19],
            'referencia_pago': row[20],
            'paypal_order_id': row[21],
            'comprobante_url': row[22],
            'id_suscripcion_generada': row[23],
            'observaciones_revision': row[24],
            'creado_en': row[25].isoformat() if row[25] else None,
            'actualizado_en': row[26].isoformat() if row[26] else None,
        }


def _activar_contratacion_en_tx(
    db,
    id_solicitud: int,
    metodo_pago: str,
    referencia_pago: str,
    actor_id: int,
    observaciones: Optional[str] = None
) -> int:
    row = db.execute_query(
        f'''SELECT id_empresa, id_usuario_propietario, codigo_plan, periodicidad, estado_contratacion, codigo_seguimiento
            FROM {_schema()}.t_solicitud_contratacion
            WHERE id_solicitud = %s FOR UPDATE''',
        (id_solicitud,),
        fetchone=True
    )
    if not row:
        _error(404, 'CONTRATACION_NO_ENCONTRADA', 'Solicitud de contratación no encontrada.')

    id_empresa, id_propietario, codigo_plan, periodicidad, estado_actual, codigo_seguimiento = row
    if estado_actual == 'ACTIVA':
        _error(409, 'CONTRATACION_YA_ACTIVA', 'Esta solicitud de contratación ya fue activada previamente.')

    # 1. Activar empresa
    db.execute_query(
        f"UPDATE {_schema()}.empresa SET estado = 'ACTIVO', updated_at = CURRENT_TIMESTAMP WHERE id_empresa = %s",
        (id_empresa,)
    )

    # 2. Calcular periodo de suscripción
    inicio = datetime.now(timezone.utc)
    dias = 365 if periodicidad == 'ANUAL' else 30
    fin = inicio + timedelta(days=dias)
    motivo = f"Contratación SaaS autónoma {codigo_seguimiento} ({metodo_pago} ref: {referencia_pago or 'N/A'})"

    # Comprobar si la solicitud especificó cambio programado para el siguiente ciclo
    sol_obs = db.execute_query(
        f'''SELECT observaciones_revision FROM {_schema()}.t_solicitud_contratacion WHERE id_solicitud = %s''',
        (id_solicitud,),
        fetchone=True
    )
    obs_texto = (sol_obs[0] or '') if sol_obs else ''
    es_siguiente_ciclo = ('[MOMENTO:SIGUIENTE_CICLO]' in obs_texto)

    # Si existe una suscripción activa solapada:
    ult_row = db.execute_query(
        f'''SELECT id_suscripcion, codigo_plan, fin FROM {_schema()}.t_suscripcion
            WHERE id_empresa = %s AND estado = 'ACTIVA' AND fin > %s
            ORDER BY fin DESC LIMIT 1''',
        (id_empresa, inicio),
        fetchone=True
    )
    if ult_row and ult_row[2]:
        if ult_row[1] == codigo_plan or es_siguiente_ciclo:
            # Renovación del mismo plan O cambio programado para el siguiente ciclo:
            # Extender contiguamente sin alterar la suscripción actual (inicio = fin_actual + 1s)
            inicio = ult_row[2] + timedelta(seconds=1)
            fin = inicio + timedelta(days=dias)
            if ult_row[1] == codigo_plan:
                motivo = f"Renovación SaaS {codigo_seguimiento} ({metodo_pago} ref: {referencia_pago or 'N/A'})"
            else:
                motivo = f"Cambio programado a {codigo_plan} para el próximo ciclo ({codigo_seguimiento})"
        else:
            # Cambio de plan Inmediato (Upgrade/Downgrade):
            # Desactivar la suscripción anterior actualizando ÚNICAMENTE 'estado' a 'CANCELADA'
            # para no violar la inmutabilidad histórica requerida por la base de datos
            db.execute_query(
                f'''UPDATE {_schema()}.t_suscripcion
                    SET estado = 'CANCELADA'
                    WHERE id_suscripcion = %s''',
                (ult_row[0],)
            )
            inicio = datetime.now(timezone.utc)
            fin = inicio + timedelta(days=dias)
            motivo = f"Cambio inmediato a {codigo_plan} ({codigo_seguimiento}, {metodo_pago})"

    susc_row = db.execute_query(
        f'''INSERT INTO {_schema()}.t_suscripcion
            (id_empresa, codigo_plan, inicio, fin, estado, motivo, creado_por)
            VALUES (%s, %s, %s, %s, 'ACTIVA', %s, %s)
            RETURNING id_suscripcion''',
        (id_empresa, codigo_plan, inicio, fin, motivo[:490], actor_id or id_propietario),
        fetchone=True
    )
    id_suscripcion = susc_row[0]

    # 3. Actualizar solicitud de contratación
    db.execute_query(
        f'''UPDATE {_schema()}.t_solicitud_contratacion
            SET estado_contratacion = 'ACTIVA',
                metodo_pago = %s,
                referencia_pago = COALESCE(%s, referencia_pago),
                id_suscripcion_generada = %s,
                revisado_por = %s,
                revisado_en = CURRENT_TIMESTAMP,
                observaciones_revision = COALESCE(%s, observaciones_revision),
                actualizado_en = CURRENT_TIMESTAMP
            WHERE id_solicitud = %s''',
        (metodo_pago, referencia_pago, id_suscripcion, actor_id, observaciones, id_solicitud)
    )

    auditar(db, actor_id or id_propietario, id_empresa, 'CONTRATACION_ACTIVADA', {
        'id_solicitud': id_solicitud,
        'codigo_seguimiento': codigo_seguimiento,
        'id_suscripcion': id_suscripcion,
        'metodo_pago': metodo_pago,
        'referencia_pago': referencia_pago
    })
    invalidar_cache_catalogo_publico()
    return id_suscripcion


def crear_orden_paypal_contratacion(
    codigo_seguimiento: str,
    origen: Optional[str] = None,
    retorno_url: Optional[str] = None
) -> Dict[str, Any]:
    from app.modules.ecommerce.services import paypal_service

    estado = obtener_estado_contratacion_por_codigo(codigo_seguimiento)
    if not estado['correo_verificado']:
        _error(403, 'CORREO_NO_VERIFICADO', 'Debes verificar tu correo electrónico antes de procesar el pago.')
    if estado['estado_contratacion'] == 'ACTIVA':
        _error(409, 'CONTRATACION_YA_ACTIVA', 'La suscripción ya se encuentra activa.')

    frontend_base = getattr(Config, 'FRONTEND_URL', None) or 'http://localhost:4200'
    if retorno_url and retorno_url.strip():
        sep = '&' if '?' in retorno_url else '?'
        ret_url = f"{retorno_url.strip()}{sep}codigo={codigo_seguimiento}&paypal=success"
        canc_url = f"{retorno_url.strip()}{sep}codigo={codigo_seguimiento}&paypal=cancel"
    elif origen == 'admin':
        ret_url = f"{frontend_base.rstrip('/')}/admin/suscripciones?codigo={codigo_seguimiento}&paypal=success"
        canc_url = f"{frontend_base.rstrip('/')}/admin/suscripciones?codigo={codigo_seguimiento}&paypal=cancel"
    else:
        ret_url = f"{frontend_base.rstrip('/')}/saas/contratacion/{codigo_seguimiento}?paypal=success"
        canc_url = f"{frontend_base.rstrip('/')}/saas/contratacion/{codigo_seguimiento}?paypal=cancel"

    try:
        orden = paypal_service.crear_orden_paypal(
            codigo_pedido=estado['codigo_seguimiento'],
            monto_bob=float(estado['monto']),
            nombre_tienda=f"AuroraStore - {estado.get('nombre_empresa', 'Suscripción')}",
            return_url=ret_url,
            cancel_url=canc_url,
            descripcion=f"Suscripción {estado.get('nombre_plan', 'SaaS')} — {estado.get('nombre_empresa')}"
        )
    except Exception as e:
        _error(502, 'PAYPAL_ERROR', str(e))

    with transaction() as db:
        db.execute_query(
            f'''UPDATE {_schema()}.t_solicitud_contratacion
                SET metodo_pago = 'PAYPAL',
                    paypal_order_id = %s,
                    actualizado_en = CURRENT_TIMESTAMP
                WHERE id_solicitud = %s''',
            (orden['order_id'], estado['id_solicitud'])
        )

    return {
        'codigo_seguimiento': codigo_seguimiento,
        'paypal_order_id': orden['order_id'],
        'approve_url': orden.get('approve_url'),
        'monto_bs': orden.get('monto_bob') or orden.get('monto_bs'),
        'monto_usd': orden.get('monto_usd'),
        'client_id': Config.PAYPAL_CLIENT_ID
    }


def capturar_pago_paypal_contratacion(codigo_seguimiento: str, order_id: str) -> Dict[str, Any]:
    from app.modules.ecommerce.services import paypal_service

    estado = obtener_estado_contratacion_por_codigo(codigo_seguimiento)
    if not estado['correo_verificado']:
        _error(403, 'CORREO_NO_VERIFICADO', 'Debes verificar tu correo electrónico antes de confirmar el pago.')
    if estado['estado_contratacion'] == 'ACTIVA':
        return estado

    try:
        captura = paypal_service.capturar_orden_paypal(order_id)
    except Exception as e:
        _error(502, 'PAYPAL_CAPTURE_ERROR', str(e))

    if not captura.get('success') or captura.get('status') != 'COMPLETED':
        msg = captura.get('message') or f"PayPal reportó estado {captura.get('status')}. La suscripción no fue activada."
        _error(400, 'PAGO_NO_COMPLETADO', msg)

    referencia = captura.get('capture_id') or order_id
    with transaction() as db:
        _activar_contratacion_en_tx(
            db=db,
            id_solicitud=estado['id_solicitud'],
            metodo_pago='PAYPAL',
            referencia_pago=referencia,
            actor_id=estado['id_usuario_propietario'],
            observaciones=f"Confirmado automáticamente vía PayPal REST API (Order: {order_id}, Capture: {referencia})"
        )

    return obtener_estado_contratacion_por_codigo(codigo_seguimiento)


def registrar_comprobante_pago_contratacion(
    codigo_seguimiento: str,
    comprobante_url: str,
    referencia_pago: str
) -> Dict[str, Any]:
    if not comprobante_url or not comprobante_url.strip():
        _error(422, 'COMPROBANTE_REQUERIDO', 'Debes adjuntar la imagen o documento del comprobante de transferencia/QR.')

    estado = obtener_estado_contratacion_por_codigo(codigo_seguimiento)
    if not estado['correo_verificado']:
        _error(403, 'CORREO_NO_VERIFICADO', 'Debes verificar tu correo electrónico antes de adjuntar el comprobante.')
    if estado['estado_contratacion'] == 'ACTIVA':
        _error(409, 'CONTRATACION_YA_ACTIVA', 'Esta contratación ya se encuentra activa.')

    with transaction() as db:
        db.execute_query(
            f'''UPDATE {_schema()}.t_solicitud_contratacion
                SET metodo_pago = 'QR_TRANSFERENCIA',
                    comprobante_url = %s,
                    referencia_pago = %s,
                    estado_contratacion = 'PENDIENTE_VERIFICACION_PAGO',
                    actualizado_en = CURRENT_TIMESTAMP
                WHERE id_solicitud = %s''',
            (comprobante_url.strip(), (referencia_pago or '').strip() or 'QR-TRANSF', estado['id_solicitud'])
        )
        auditar(db, estado['id_usuario_propietario'], estado['id_empresa'], 'COMPROBANTE_CONTRATACION_ENVIADO', {
            'id_solicitud': estado['id_solicitud'],
            'codigo_seguimiento': codigo_seguimiento,
            'referencia_pago': referencia_pago
        })

    return obtener_estado_contratacion_por_codigo(codigo_seguimiento)


def listar_solicitudes_contratacion(estado_filtro: Optional[str] = None) -> List[Dict[str, Any]]:
    with transaction() as db:
        cond = ''
        params: list = []
        if estado_filtro and estado_filtro.strip():
            cond = 'WHERE s.estado_contratacion = %s'
            params.append(estado_filtro.strip().upper())

        rows = db.execute_query(
            f'''SELECT s.id_solicitud, s.codigo_seguimiento, s.id_empresa, e.nombre_empresa, e.slug, e.estado AS estado_empresa,
                       s.id_usuario_propietario, u.nombre, u.apellido, u.correo,
                       s.codigo_plan, p.nombre AS nombre_plan, s.periodicidad, s.monto, s.moneda,
                       s.estado_contratacion, s.correo_verificado, s.metodo_pago, s.referencia_pago,
                       s.comprobante_url, s.id_suscripcion_generada, s.observaciones_revision,
                       s.creado_en, s.actualizado_en
                FROM {_schema()}.t_solicitud_contratacion s
                JOIN {_schema()}.empresa e ON e.id_empresa = s.id_empresa
                JOIN {_schema()}.t_usuario u ON u.id_usuario = s.id_usuario_propietario
                JOIN {_schema()}.t_plan p ON p.codigo = s.codigo_plan
                {cond}
                ORDER BY s.creado_en DESC''',
            tuple(params),
            fetchall=True
        )
        resultado = []
        for row in rows or []:
            resultado.append({
                'id_solicitud': row[0],
                'codigo_seguimiento': row[1],
                'id_empresa': row[2],
                'nombre_empresa': row[3],
                'slug': row[4],
                'estado_empresa': row[5],
                'id_usuario_propietario': row[6],
                'nombre_propietario': f"{row[7] or ''} {row[8] or ''}".strip(),
                'correo_propietario': row[9],
                'codigo_plan': row[10],
                'nombre_plan': row[11],
                'periodicidad': row[12],
                'monto': float(row[13]),
                'moneda': row[14],
                'estado_contratacion': row[15],
                'correo_verificado': bool(row[16]),
                'metodo_pago': row[17],
                'referencia_pago': row[18],
                'comprobante_url': row[19],
                'id_suscripcion_generada': row[20],
                'observaciones_revision': row[21],
                'creado_en': row[22].isoformat() if row[22] else None,
                'actualizado_en': row[23].isoformat() if row[23] else None,
            })
        return resultado


def resolver_solicitud_contratacion(
    id_solicitud: int,
    accion: str,
    observaciones: str,
    actor: Dict[str, Any]
) -> Dict[str, Any]:
    accion_norm = (accion or '').strip().upper()
    actor_id = actor.get('id_usuario') or actor.get('nro_usuario')
    with transaction() as db:
        row = db.execute_query(
            f'''SELECT codigo_seguimiento, id_empresa, metodo_pago, referencia_pago, estado_contratacion
                FROM {_schema()}.t_solicitud_contratacion
                WHERE id_solicitud = %s FOR UPDATE''',
            (id_solicitud,),
            fetchone=True
        )
        if not row:
            _error(404, 'CONTRATACION_NO_ENCONTRADA', 'La solicitud de contratación no existe.')

        codigo_seguimiento, id_empresa, metodo_pago, referencia_pago, estado_actual = row
        if accion_norm == 'APROBAR':
            _activar_contratacion_en_tx(
                db=db,
                id_solicitud=id_solicitud,
                metodo_pago=metodo_pago or 'QR_TRANSFERENCIA',
                referencia_pago=referencia_pago or 'VERIFICADO_ADMIN',
                actor_id=actor_id,
                observaciones=observaciones
            )
        elif accion_norm == 'RECHAZAR':
            if estado_actual == 'ACTIVA':
                _error(409, 'CONTRATACION_YA_ACTIVA', 'No se puede rechazar una contratación que ya fue activada.')
            db.execute_query(
                f'''UPDATE {_schema()}.t_solicitud_contratacion
                    SET estado_contratacion = 'RECHAZADO',
                        revisado_por = %s,
                        revisado_en = CURRENT_TIMESTAMP,
                        observaciones_revision = %s,
                        actualizado_en = CURRENT_TIMESTAMP
                    WHERE id_solicitud = %s''',
                (actor_id, observaciones, id_solicitud)
            )
            auditar(db, actor, id_empresa, 'CONTRATACION_RECHAZADA', {
                'id_solicitud': id_solicitud,
                'codigo_seguimiento': codigo_seguimiento,
                'motivo': observaciones
            })
        else:
            _error(422, 'ACCION_INVALIDA', 'La acción debe ser APROBAR o RECHAZAR.')

    return obtener_estado_contratacion_por_codigo(codigo_seguimiento)


# ==============================================================================
# CONFIGURACIÓN DEL STOREFRONT Y ASISTENTE DE ONBOARDING DEL TENANT
# ==============================================================================

def obtener_configuracion_storefront_empresa(id_empresa: int) -> Dict[str, Any]:
    with transaction() as db:
        row = db.execute_query(
            f'''SELECT id_empresa, nombre_empresa, razon_social, nit, correo, telefono,
                       direccion_fiscal, ciudad, logo, estado,
                       COALESCE(slug, LOWER(REGEXP_REPLACE(TRIM(nombre_empresa), '[^a-zA-Z0-9]+', '-', 'g'))) AS slug,
                       COALESCE(configuracion_storefront, '{{}}'::jsonb) AS configuracion_storefront
                FROM {_schema()}.empresa
                WHERE id_empresa = %s''',
            (id_empresa,),
            fetchone=True
        )
        if not row:
            _error(404, 'EMPRESA_NO_ENCONTRADA', 'Empresa no encontrada.')

        sucursales = db.execute_query(
            f'SELECT COUNT(*) FROM {_schema()}.t_sucursal WHERE id_empresa = %s AND COALESCE(activo, estado, FALSE)',
            (id_empresa,),
            fetchone=True
        )[0]
        productos = db.execute_query(
            f'SELECT COUNT(*) FROM {_schema()}.t_producto WHERE id_empresa = %s AND activo = TRUE',
            (id_empresa,),
            fetchone=True
        )[0]

        cfg = _normalizar_config_storefront(row[11], row[1])
        return {
            'id_empresa': row[0],
            'nombre_empresa': row[1],
            'razon_social': row[2],
            'nit': row[3],
            'correo': row[4],
            'telefono': row[5],
            'direccion_fiscal': row[6],
            'ciudad': row[7],
            'logo': row[8] or '',
            'estado': row[9],
            'slug': row[10],
            'configuracion_storefront': cfg,
            'progreso_onboarding': {
                'identidad_configurada': bool(cfg.get('nombre_comercial') and cfg.get('color_primario')),
                'publicos_definidos': len(cfg.get('publicos_habilitados') or []) > 0,
                'tiene_sucursal_activa': sucursales > 0,
                'tiene_productos_activos': productos > 0,
                'sucursales_activas': int(sucursales),
                'productos_activos': int(productos),
                'onboarding_completado': bool(cfg.get('onboarding_completado'))
            }
        }


def actualizar_configuracion_storefront_empresa(
    id_empresa: int,
    datos: Dict[str, Any],
    actor: Dict[str, Any]
) -> Dict[str, Any]:
    actual = obtener_configuracion_storefront_empresa(id_empresa)
    cfg_prev = actual['configuracion_storefront']

    nuevo_slug = actual['slug']
    if datos.get('slug') and _limpiar_slug(datos['slug']) != actual['slug']:
        disp = verificar_disponibilidad_slug(datos['slug'], exclude_id_empresa=id_empresa)
        if not disp['disponible']:
            _error(409, 'SLUG_NO_DISPONIBLE', disp['motivo'])
        nuevo_slug = disp['slug_normalizado']

    color_primario = (datos.get('color_primario') or cfg_prev.get('color_primario') or '#18181b').strip()
    color_secundario = (datos.get('color_secundario') or cfg_prev.get('color_secundario') or '#c2410c').strip()
    if not re.match(r'^#[0-9a-fA-F]{6}$', color_primario):
        _error(422, 'COLOR_INVALIDO', 'El color primario debe tener formato hexadecimal (#RRGGBB).')
    if not re.match(r'^#[0-9a-fA-F]{6}$', color_secundario):
        _error(422, 'COLOR_INVALIDO', 'El color secundario debe tener formato hexadecimal (#RRGGBB).')

    tipografia = (datos.get('tipografia') or cfg_prev.get('tipografia') or 'editorial').strip().lower()
    if tipografia not in TIPOGRAFIAS_PERMITIDAS:
        _error(422, 'TIPOGRAFIA_NO_PERMITIDA', f'Tipografía no permitida. Opciones: {sorted(TIPOGRAFIAS_PERMITIDAS)}')

    estilo_tarjetas = (datos.get('estilo_tarjetas') or cfg_prev.get('estilo_tarjetas') or 'editorial').strip().lower()
    if estilo_tarjetas not in ESTILOS_TARJETA_PERMITIDOS:
        _error(422, 'ESTILO_TARJETA_NO_PERMITIDO', f'Estilo de tarjeta no permitido. Opciones: {sorted(ESTILOS_TARJETA_PERMITIDOS)}')

    publicos_raw = datos.get('publicos_habilitados')
    if isinstance(publicos_raw, list):
        publicos = [p for p in publicos_raw if p in PUBLICOS_PERMITIDOS]
    else:
        publicos = cfg_prev.get('publicos_habilitados', [])

    secciones_raw = datos.get('secciones')
    if isinstance(secciones_raw, list) and len(secciones_raw) > 0:
        secciones = []
        for idx, s in enumerate(secciones_raw, start=1):
            if isinstance(s, dict) and s.get('codigo') in SECCIONES_PERMITIDAS:
                secciones.append({
                    'codigo': s['codigo'],
                    'visible': bool(s.get('visible', True)),
                    'orden': int(s.get('orden', idx))
                })
        secciones.sort(key=lambda x: x['orden'])
    else:
        secciones = cfg_prev.get('secciones', [])

    colecciones_raw = datos.get('colecciones_destacadas')
    if isinstance(colecciones_raw, list):
        colecciones = [str(c).strip()[:60] for c in colecciones_raw if str(c).strip()][:8]
    else:
        colecciones = cfg_prev.get('colecciones_destacadas', [])

    nombre_comercial = (datos.get('nombre_comercial') or cfg_prev.get('nombre_comercial') or actual['nombre_empresa']).strip()[:100]
    nuevo_logo = datos.get('logo') if datos.get('logo') is not None else actual['logo']

    nueva_cfg = _normalizar_config_storefront({
        'nombre_comercial': nombre_comercial,
        'eslogan': (datos.get('eslogan') if datos.get('eslogan') is not None else cfg_prev.get('eslogan', '')).strip()[:160],
        'color_primario': color_primario,
        'color_secundario': color_secundario,
        'tipografia': tipografia,
        'estilo_tarjetas': estilo_tarjetas,
        'banner_titulo': (datos.get('banner_titulo') if datos.get('banner_titulo') is not None else cfg_prev.get('banner_titulo', '')).strip()[:120],
        'banner_subtitulo': (datos.get('banner_subtitulo') if datos.get('banner_subtitulo') is not None else cfg_prev.get('banner_subtitulo', '')).strip()[:280],
        'banner_imagen_url': (datos.get('banner_imagen_url') if datos.get('banner_imagen_url') is not None else cfg_prev.get('banner_imagen_url', '')).strip()[:500],
        'banner_cta_texto': (datos.get('banner_cta_texto') if datos.get('banner_cta_texto') is not None else cfg_prev.get('banner_cta_texto', 'Explorar catálogo')).strip()[:40],
        'publicos_habilitados': publicos,
        'colecciones_destacadas': colecciones,
        'secciones': secciones,
        'onboarding_completado': bool(datos.get('onboarding_completado', cfg_prev.get('onboarding_completado', False)))
    }, actual['nombre_empresa'])

    with transaction() as db:
        db.execute_query(
            f'''UPDATE {_schema()}.empresa
                SET nombre_empresa = COALESCE(NULLIF(%s, ''), nombre_empresa),
                    logo = %s,
                    slug = %s,
                    configuracion_storefront = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id_empresa = %s''',
            (nombre_comercial.upper(), nuevo_logo, nuevo_slug, Json(nueva_cfg), id_empresa)
        )
        auditar(db, actor, id_empresa, 'STOREFRONT_CONFIGURADO', {
            'slug': nuevo_slug,
            'color_primario': color_primario,
            'color_secundario': color_secundario,
            'tipografia': tipografia,
            'publicos_habilitados': publicos,
            'onboarding_completado': nueva_cfg['onboarding_completado']
        })

    invalidar_cache_catalogo_publico()
    return obtener_configuracion_storefront_empresa(id_empresa)


def obtener_contratacion_activa_empresa(id_empresa: int) -> Optional[Dict[str, Any]]:
    """Obtiene la solicitud de contratación más reciente (activa o pendiente de pago) de la empresa."""
    with transaction() as db:
        sol_row = db.execute_query(
            f'''SELECT s.id_solicitud, s.codigo_seguimiento, s.estado_contratacion, s.codigo_plan,
                       s.periodicidad, s.monto, s.moneda, s.metodo_pago, s.correo_verificado,
                       p.nombre AS nombre_plan, s.paypal_order_id, s.comprobante_url,
                       e.nombre_empresa, e.estado AS estado_empresa
                FROM {_schema()}.t_solicitud_contratacion s
                LEFT JOIN {_schema()}.t_plan p ON p.codigo = s.codigo_plan
                LEFT JOIN {_schema()}.empresa e ON e.id_empresa = s.id_empresa
                WHERE s.id_empresa = %s
                ORDER BY s.id_solicitud DESC LIMIT 1''',
            (id_empresa,),
            fetchone=True
        )
        if not sol_row:
            return None
        return {
            'id_solicitud': sol_row[0],
            'codigo_seguimiento': sol_row[1],
            'estado_contratacion': sol_row[2],
            'codigo_plan': sol_row[3],
            'periodicidad': sol_row[4],
            'monto': float(sol_row[5]) if sol_row[5] is not None else 0.0,
            'moneda': sol_row[6] or 'BOB',
            'metodo_pago': sol_row[7],
            'correo_verificado': bool(sol_row[8]),
            'nombre_plan': sol_row[9] or sol_row[3],
            'paypal_order_id': sol_row[10],
            'comprobante_url': sol_row[11],
            'nombre_empresa': sol_row[12],
            'estado_empresa': sol_row[13]
        }


def solicitar_renovacion_o_cambio_plan(
    id_empresa: int,
    id_usuario: int,
    datos: Dict[str, Any]
) -> Dict[str, Any]:
    """Genera una nueva solicitud de contratación para renovar o cambiar de plan desde el panel administrativo."""
    codigo_plan = (datos.get('codigo_plan') or '').strip().upper()
    periodicidad = (datos.get('periodicidad') or 'MENSUAL').strip().upper()
    motivo = (datos.get('motivo') or '').strip()

    if codigo_plan not in ('BASICO', 'PROFESIONAL'):
        _error(400, 'PLAN_INVALIDO', 'El plan seleccionado no es válido. Debe ser BASICO o PROFESIONAL.')
    if periodicidad not in ('MENSUAL', 'ANUAL'):
        _error(400, 'PERIODICIDAD_INVALIDA', 'Periodicidad no válida. Debe ser MENSUAL o ANUAL.')

    with transaction() as db:
        emp_row = db.execute_query(
            f"SELECT id_empresa, nombre_empresa, estado FROM {_schema()}.empresa WHERE id_empresa = %s",
            (id_empresa,),
            fetchone=True
        )
        if not emp_row:
            _error(404, 'EMPRESA_NO_ENCONTRADA', 'Empresa no encontrada.')

        # Si el plan es BASICO, validar sucursales activas (máximo 2)
        if codigo_plan == 'BASICO':
            usadas = db.execute_query(
                f'SELECT COUNT(*) FROM {_schema()}.t_sucursal WHERE id_empresa=%s AND COALESCE(activo,estado,FALSE)',
                (id_empresa,),
                fetchone=True
            )[0]
            if usadas > 2:
                _error(400, 'LIMITE_SUCURSALES_EXCEDIDO', f'Tu empresa tiene {usadas} sucursales activas. El plan Básico admite un máximo de 2. Desactiva sucursales antes de solicitar este cambio.')

        # Obtener precio del plan
        plan_row = db.execute_query(
            f'SELECT codigo, nombre, precio_mensual, precio_anual, moneda FROM {_schema()}.t_plan WHERE codigo = %s',
            (codigo_plan,),
            fetchone=True
        )
        if not plan_row:
            _error(404, 'PLAN_NO_ENCONTRADO', f"Plan '{codigo_plan}' no encontrado.")

        monto = float(plan_row[3] if periodicidad == 'ANUAL' else plan_row[2])
        moneda = plan_row[4] or 'BOB'

        # Generar código de seguimiento
        codigo_seguimiento = _generar_codigo_seguimiento()

        # Token administrativo interno
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        expira_en = datetime.now(timezone.utc) + timedelta(hours=72)

        momento_cambio = (datos.get('momento_cambio') or 'SIGUIENTE_CICLO').strip().upper()
        if momento_cambio not in ('SIGUIENTE_CICLO', 'INMEDIATO'):
            momento_cambio = 'SIGUIENTE_CICLO'
        motivo_con_momento = f"[MOMENTO:{momento_cambio}] {motivo or ''}".strip()

        sol_row = db.execute_query(
            f'''INSERT INTO {_schema()}.t_solicitud_contratacion
                (codigo_seguimiento, id_empresa, id_usuario_propietario, codigo_plan, periodicidad,
                 monto, moneda, estado_contratacion, token_verificacion_hash, token_expira_en,
                 token_usado_en, correo_verificado, observaciones_revision, creado_en, actualizado_en)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDIENTE_PAGO', %s, %s, CURRENT_TIMESTAMP, TRUE, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id_solicitud''',
            (codigo_seguimiento, id_empresa, id_usuario, codigo_plan, periodicidad, monto, moneda, token_hash, expira_en, motivo_con_momento),
            fetchone=True
        )
        id_solicitud = sol_row[0]

        auditar(db, id_usuario, id_empresa, 'SOLICITUD_PLAN_CREADA', {
            'id_solicitud': id_solicitud,
            'codigo_seguimiento': codigo_seguimiento,
            'codigo_plan': codigo_plan,
            'periodicidad': periodicidad,
            'monto': monto,
            'momento_cambio': momento_cambio,
            'motivo': motivo
        })

        return {
            'id_solicitud': id_solicitud,
            'codigo_seguimiento': codigo_seguimiento,
            'codigo_plan': codigo_plan,
            'nombre_plan': plan_row[1],
            'periodicidad': periodicidad,
            'monto': monto,
            'moneda': moneda,
            'momento_cambio': momento_cambio,
            'estado_contratacion': 'PENDIENTE_PAGO',
            'correo_verificado': True
        }


def obtener_opciones_cancelacion_suscripcion(id_empresa: int) -> Dict[str, Any]:
    """Calcula las opciones comerciales de cancelación y reembolso según el tiempo transcurrido (regla del 10%)."""
    with transaction() as db:
        row = db.execute_query(
            f'''SELECT s.id_suscripcion, s.codigo_plan, s.inicio, s.fin, s.estado, p.nombre, p.precio_mensual, p.precio_anual
                FROM {_schema()}.t_suscripcion s
                JOIN {_schema()}.t_plan p ON p.codigo = s.codigo_plan
                WHERE s.id_empresa = %s AND s.estado = 'ACTIVA' AND s.fin > CURRENT_TIMESTAMP
                ORDER BY s.fin DESC LIMIT 1''',
            (id_empresa,),
            fetchone=True
        )
        if not row:
            return {'tiene_suscripcion_activa': False}

        id_suscripcion, codigo_plan, inicio, fin, estado, nombre_plan, p_mensual, p_anual = row
        ahora = datetime.now(timezone.utc)
        total_segundos = max(1.0, (fin - inicio).total_seconds())
        segundos_transcurridos = max(0.0, (ahora - inicio).total_seconds())
        dias_totales = int(round(total_segundos / 86400.0))
        dias_transcurridos = round(segundos_transcurridos / 86400.0, 1)
        porcentaje_consumido = min(100.0, round((segundos_transcurridos / total_segundos) * 100.0, 1))
        elegible_reembolso = (porcentaje_consumido <= 10.0)

        return {
            'tiene_suscripcion_activa': True,
            'id_suscripcion': id_suscripcion,
            'codigo_plan': codigo_plan,
            'nombre_plan': nombre_plan,
            'inicio': inicio.isoformat(),
            'fin': fin.isoformat(),
            'dias_totales': dias_totales,
            'dias_transcurridos': dias_transcurridos,
            'porcentaje_consumido': porcentaje_consumido,
            'elegible_reembolso': elegible_reembolso,
            'limite_porcentaje_reembolso': 10.0,
            'opcion_cancelar_fin_ciclo': {
                'disponible': True,
                'titulo': 'Cancelar al finalizar el período',
                'descripcion': f'Conserva el acceso completo a tu tienda y todas sus funciones hasta el {fin.strftime("%d/%m/%Y")}. No se realizarán renovaciones ni cobros posteriores.'
            },
            'opcion_reembolso_inmediato': {
                'disponible': elegible_reembolso,
                'titulo': 'Cancelar ahora con reembolso',
                'descripcion': (
                    f'Garantía comercial aplicable: ha transcurrido el {porcentaje_consumido}% del período (dentro del 10% permitido). Se cancelará el servicio de inmediato y se tramitará el reembolso.'
                    if elegible_reembolso else
                    f'No elegible para reembolso: han transcurrido {dias_transcurridos} días ({porcentaje_consumido}% del ciclo). La garantía con devolución aplica dentro del primer 10% del período.'
                )
            }
        }


def procesar_cancelacion_comercial_tenant(
    id_empresa: int,
    id_usuario: int,
    datos: Dict[str, Any]
) -> Dict[str, Any]:
    """Ejecuta la cancelación comercial elegida: fin de ciclo o reembolso inmediato (si <= 10% consumido)."""
    tipo_cancelacion = (datos.get('tipo_cancelacion') or 'FIN_DE_CICLO').strip().upper()
    motivo = (datos.get('motivo') or 'Solicitud de cancelación gestionada por el propietario').strip()

    opciones = obtener_opciones_cancelacion_suscripcion(id_empresa)
    if not opciones.get('tiene_suscripcion_activa'):
        _error(404, 'SIN_SUSCRIPCION_ACTIVA', 'La empresa no cuenta con una suscripción activa para cancelar.')

    id_suscripcion = opciones['id_suscripcion']
    fin_str = opciones['fin']
    porcentaje = opciones['porcentaje_consumido']

    with transaction() as db:
        if tipo_cancelacion == 'REEMBOLSO_INMEDIATO':
            if not opciones['elegible_reembolso']:
                _error(400, 'REEMBOLSO_NO_ELEGIBLE', f'No es posible emitir un reembolso inmediato porque ha transcurrido el {porcentaje}% del ciclo (límite comercial: 10%). Te sugerimos elegir la opción de conservar tu suscripción hasta el final del período.')

            # Consultar método de pago y referencia original de la suscripción
            sol_row = db.execute_query(
                f'''SELECT metodo_pago, referencia_pago, paypal_order_id, monto, moneda
                    FROM {_schema()}.t_solicitud_contratacion
                    WHERE id_suscripcion_generada = %s
                    ORDER BY id_solicitud DESC LIMIT 1''',
                (id_suscripcion,),
                fetchone=True
            )

            reembolso_resultado = {'metodo': 'DESCONOCIDO', 'procesado_en_pasarela': False}
            if sol_row:
                metodo_pago, ref_pago, paypal_order, monto, moneda = sol_row
                if metodo_pago == 'PAYPAL':
                    from app.modules.ecommerce.services import paypal_service
                    cap_id = ref_pago or ''
                    if cap_id:
                        res_ref = paypal_service.reembolsar_captura_paypal(
                            capture_id=cap_id,
                            nota=f"Garantía comercial 10% - Cancelación suscripción {opciones['codigo_plan']}"
                        )
                        reembolso_resultado = {
                            'metodo': 'PAYPAL',
                            'procesado_en_pasarela': res_ref.get('success', False),
                            'refund_id': res_ref.get('refund_id'),
                            'estado_paypal': res_ref.get('status')
                        }
                else:
                    reembolso_resultado = {
                        'metodo': 'QR_TRANSFERENCIA',
                        'procesado_en_pasarela': False,
                        'mensaje': 'Reintegro bancario manual registrado.'
                    }

            # Desactivar inmediatamente la suscripción respetando inmutabilidad (solo actualizamos estado)
            db.execute_query(
                f'''UPDATE {_schema()}.t_suscripcion SET estado = 'CANCELADA' WHERE id_suscripcion = %s''',
                (id_suscripcion,)
            )
            # Cancelar solicitudes de cobro pendientes
            db.execute_query(
                f'''UPDATE {_schema()}.t_solicitud_contratacion
                    SET estado_contratacion = 'CANCELADA', actualizado_en = CURRENT_TIMESTAMP
                    WHERE id_empresa = %s AND estado_contratacion IN ('PENDIENTE_PAGO', 'PENDIENTE_VERIFICACION_PAGO')''',
                (id_empresa,)
            )
            auditar(db, id_usuario, id_empresa, 'CANCELACION_CON_REEMBOLSO', {
                'id_suscripcion': id_suscripcion,
                'porcentaje_consumido': porcentaje,
                'motivo': motivo,
                'reembolso': reembolso_resultado
            })
            invalidar_cache_catalogo_publico()

            if reembolso_resultado.get('procesado_en_pasarela') and reembolso_resultado.get('refund_id'):
                msg = f"Suscripción cancelada bajo garantía comercial ({porcentaje}% transcurrido). PayPal ha procesado el reembolso exitosamente (ID: {reembolso_resultado['refund_id']}). Los fondos se reintegrarán automáticamente a tu cuenta/tarjeta."
            elif reembolso_resultado.get('metodo') == 'PAYPAL':
                msg = f"Suscripción cancelada bajo garantía comercial ({porcentaje}% transcurrido). La solicitud de reembolso ha sido registrada para confirmación en PayPal."
            else:
                msg = f"Suscripción cancelada bajo garantía comercial ({porcentaje}% transcurrido). La solicitud de reintegro bancario ha sido registrada para su acreditación."

            return {
                'exito': True,
                'tipo_cancelacion': 'REEMBOLSO_INMEDIATO',
                'reembolso': reembolso_resultado,
                'mensaje': msg
            }
        else: # FIN_DE_CICLO
            # Dejar la suscripción activa hasta fin, pero cancelar solicitudes de renovación pendientes
            db.execute_query(
                f'''UPDATE {_schema()}.t_solicitud_contratacion
                    SET estado_contratacion = 'CANCELADA', actualizado_en = CURRENT_TIMESTAMP
                    WHERE id_empresa = %s AND estado_contratacion IN ('PENDIENTE_PAGO', 'PENDIENTE_VERIFICACION_PAGO')''',
                (id_empresa,)
            )
            auditar(db, id_usuario, id_empresa, 'CANCELACION_FIN_DE_CICLO', {
                'id_suscripcion': id_suscripcion,
                'fecha_fin': fin_str,
                'motivo': motivo
            })
            return {
                'exito': True,
                'tipo_cancelacion': 'FIN_DE_CICLO',
                'fecha_fin_servicio': fin_str,
                'mensaje': 'Cancelación programada registrada. Tu tienda conservará todas sus funciones activas hasta el fin de ciclo acordado sin renovaciones automáticas.'
            }
