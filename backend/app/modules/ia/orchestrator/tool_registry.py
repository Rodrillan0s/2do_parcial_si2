"""
Registro Centralizado de Herramientas (ToolRegistry) y Ejecutor Seguro (ToolExecutor)
para Aurora Advisor.

Reglas críticas:
1. Lista blanca estricta de herramientas (solo lectura: read_only=True).
2. Prohibido ejecutar modificaciones de inventario, anulaciones, cambios de precios, roles o pagos.
3. Validación independiente de alcance (PUBLIC, CLIENTE, SUCURSAL, EMPRESA, PLATAFORMA) y RBAC
   ANTES de ejecutar cualquier herramienta, sin confiar jamás en el LLM.
4. Integración directa con el servicio oficial CU23W (demanda_forecast_services) y Motor de Reportes.
5. Sanitización de datos recuperados de PostgreSQL y límite estricto de registros por consulta.
"""

import time
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Tuple
from app.modules.ia.orchestrator.security_guard import (
    AssistantSecurityContext,
    verify_branch_access,
    sanitize_untrusted_db_content
)
from app.modules.ia.ai.exceptions.ai_exceptions import (
    AISecurityViolationError,
    AIToolExecutionError,
    AIDatabaseError
)

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    allowed_contexts: List[str]  # ["PUBLIC", "CLIENTE", "SUCURSAL", "EMPRESA", "PLATAFORMA"]
    required_permissions: List[str] = field(default_factory=list)
    read_only: bool = True
    max_results: int = 10
    timeout_seconds: float = 10.0
    widget_type: str = "texto"
    is_admin_tool: bool = False

    def to_openai_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


ALL_SCOPES = ["PUBLIC", "CLIENTE", "SUCURSAL", "EMPRESA", "PLATAFORMA"]
AUTH_CLIENT_SCOPES = ["CLIENTE", "SUCURSAL", "EMPRESA", "PLATAFORMA"]
ADMIN_SCOPES = ["SUCURSAL", "EMPRESA", "PLATAFORMA"]


TOOL_DEFINITIONS: Dict[str, ToolDefinition] = {
    # =========================================================================
    # 9.1 HERRAMIENTAS PARA CLIENTES Y VISITANTES (13 HERRAMIENTAS)
    # =========================================================================
    "buscar_prendas_catalogo": ToolDefinition(
        name="buscar_prendas_catalogo",
        description="Busca prendas y artículos disponibles en el catálogo de la tienda actual por término, categoría, género o precio máximo.",
        parameters={
            "type": "object",
            "properties": {
                "termino": {"type": "string", "description": "Término de búsqueda (ej. 'vestido', 'camisa', 'seda')"},
                "categoria": {"type": "string", "description": "Categoría (ej. 'Vestidos', 'Blusas', 'Pantalones', 'Chaquetas')"},
                "genero": {"type": "string", "enum": ["Damas", "Caballeros", "Unisex", "Niños"], "description": "Sección o público objetivo"},
                "precio_max": {"type": "number", "description": "Precio máximo en Bolivianos (Bs.)"}
            }
        },
        allowed_contexts=ALL_SCOPES,
        widget_type="productos",
        max_results=8
    ),
    "buscar_prendas_avanzada": ToolDefinition(
        name="buscar_prendas_avanzada",
        description="Búsqueda avanzada y multicriterio filtrando por categoría, talla, color preferido, colores excluidos, rango de precios y sucursal.",
        parameters={
            "type": "object",
            "properties": {
                "termino": {"type": "string", "description": "Palabra clave o modelo"},
                "categoria": {"type": "string", "description": "Categoría de la prenda"},
                "talla": {"type": "string", "description": "Talla buscada (ej. XS, S, M, L, XL)"},
                "color": {"type": "string", "description": "Color o gama deseada (ej. Blanco, Beige, Azul, colores claros)"},
                "colores_excluidos": {"type": "array", "items": {"type": "string"}, "description": "Colores que el usuario NO desea usar"},
                "precio_min": {"type": "number", "description": "Precio mínimo en Bs."},
                "precio_max": {"type": "number", "description": "Precio máximo en Bs."},
                "sucursal": {"type": "string", "description": "Nombre de la sucursal preferida"}
            }
        },
        allowed_contexts=ALL_SCOPES,
        widget_type="productos",
        max_results=10
    ),
    "consultar_detalle_prenda": ToolDefinition(
        name="consultar_detalle_prenda",
        description="Obtiene los detalles completos de una prenda: precio real, descripción, tallas, colores y stock desglosado por sucursal.",
        parameters={
            "type": "object",
            "properties": {
                "id_producto": {"type": "integer", "description": "ID del producto"},
                "nombre_prenda": {"type": "string", "description": "Nombre o código de la prenda"}
            }
        },
        allowed_contexts=ALL_SCOPES,
        widget_type="productos",
        max_results=10
    ),
    "comparar_productos": ToolDefinition(
        name="comparar_productos",
        description="Compara dos o más prendas lado a lado analizando precio, categoría, tallas disponibles, colores y existencias en tienda.",
        parameters={
            "type": "object",
            "properties": {
                "ids_productos": {"type": "array", "items": {"type": "integer"}, "description": "Lista de IDs de productos a comparar"},
                "nombres_productos": {"type": "array", "items": {"type": "string"}, "description": "Nombres aproximados de las prendas a comparar"},
                "categoria": {"type": "string", "description": "Categoría para comparar las mejores opciones disponibles"}
            }
        },
        allowed_contexts=ALL_SCOPES,
        widget_type="comparacion",
        max_results=5
    ),
    "buscar_productos_similares": ToolDefinition(
        name="buscar_productos_similares",
        description="Busca prendas similares o alternativas a un producto de referencia, permitiendo filtrar opciones más económicas o en una talla específica.",
        parameters={
            "type": "object",
            "properties": {
                "id_producto_referencia": {"type": "integer", "description": "ID de la prenda de referencia"},
                "nombre_referencia": {"type": "string", "description": "Nombre de la prenda de referencia"},
                "mas_economico": {"type": "boolean", "description": "Si es True, busca alternativas de menor precio que la referencia"},
                "precio_max": {"type": "number", "description": "Presupuesto máximo en Bs."},
                "talla": {"type": "string", "description": "Talla requerida"}
            }
        },
        allowed_contexts=ALL_SCOPES,
        widget_type="productos",
        max_results=6
    ),
    "recomendar_outfit_estilo": ToolDefinition(
        name="recomendar_outfit_estilo",
        description="Diseña combinaciones completas de prendas reales (prendas principales, calzado y accesorios) según ocasión, estilo, colores permitidos/excluidos y presupuesto.",
        parameters={
            "type": "object",
            "properties": {
                "ocasion": {"type": "string", "description": "Ocasión (ej. 'boda', 'cena formal', 'gala', 'coctel', 'oficina', 'casual', 'invierno')"},
                "genero": {"type": "string", "enum": ["Damas", "Caballeros", "Unisex"], "description": "Público objetivo"},
                "estilo_preferido": {"type": "string", "description": "Estilo (ej. 'elegante', 'minimalista', 'moderno', 'clasico')"},
                "talla": {"type": "string", "description": "Talla deseada"},
                "colores_preferidos": {"type": "array", "items": {"type": "string"}, "description": "Colores deseados"},
                "colores_excluidos": {"type": "array", "items": {"type": "string"}, "description": "Colores a evitar (ej. ['Negro'])"},
                "presupuesto_max": {"type": "number", "description": "Presupuesto total máximo en Bolivianos (Bs.)"}
            },
            "required": ["ocasion"]
        },
        allowed_contexts=ALL_SCOPES,
        widget_type="outfit",
        max_results=6
    ),
    "consultar_disponibilidad_sucursal": ToolDefinition(
        name="consultar_disponibilidad_sucursal",
        description="Consulta qué sucursales físicas tienen stock disponible de una prenda, categoría o talla específica.",
        parameters={
            "type": "object",
            "properties": {
                "id_producto": {"type": "integer", "description": "ID del producto"},
                "nombre_prenda": {"type": "string", "description": "Nombre de la prenda o categoría"},
                "talla": {"type": "string", "description": "Talla específica a verificar"},
                "sucursal": {"type": "string", "description": "Sucursal específica (opcional)"}
            }
        },
        allowed_contexts=ALL_SCOPES,
        widget_type="tabla",
        max_results=12
    ),
    "consultar_promociones": ToolDefinition(
        name="consultar_promociones",
        description="Consulta las prendas con mejor relación calidad-precio, colecciones de temporada y oportunidades vigentes en la tienda.",
        parameters={
            "type": "object",
            "properties": {
                "categoria": {"type": "string", "description": "Categoría opcional"},
                "presupuesto_max": {"type": "number", "description": "Presupuesto máximo en Bs."}
            }
        },
        allowed_contexts=ALL_SCOPES,
        widget_type="productos",
        max_results=6
    ),
    "consultar_politicas_devolucion": ToolDefinition(
        name="consultar_politicas_devolucion",
        description="Consulta las políticas comerciales de la tienda actual: cambios de talla, garantías (Ley 453), vigencia de reservas (48h), envíos y pagos.",
        parameters={
            "type": "object",
            "properties": {
                "tema": {
                    "type": "string",
                    "enum": ["cambios_talla", "garantias_devoluciones", "reservas_vigencia", "envios_tiempos", "cuidados_prendas", "metodos_pago", "general"],
                    "description": "Tema de la consulta"
                }
            }
        },
        allowed_contexts=ALL_SCOPES,
        widget_type="tabla",
        max_results=6
    ),
    "consultar_sucursales_tiendas": ToolDefinition(
        name="consultar_sucursales_tiendas",
        description="Lista las sucursales y boutiques físicas activas de la empresa con direcciones, ciudades, teléfonos y horarios.",
        parameters={"type": "object", "properties": {}},
        allowed_contexts=ALL_SCOPES,
        widget_type="tabla",
        max_results=10
    ),
    "consultar_mis_pedidos": ToolDefinition(
        name="consultar_mis_pedidos",
        description="Consulta el historial y seguimiento de pedidos online realizados por el cliente autenticado.",
        parameters={
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "description": "Cantidad de pedidos a mostrar (máx 10)"}
            }
        },
        allowed_contexts=AUTH_CLIENT_SCOPES,
        widget_type="seguimiento_pedido",
        max_results=10
    ),
    "consultar_mis_reservas": ToolDefinition(
        name="consultar_mis_reservas",
        description="Consulta las citas de probador y reservas de prendas activas del cliente autenticado.",
        parameters={
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "description": "Cantidad de reservas a mostrar (máx 10)"}
            }
        },
        allowed_contexts=AUTH_CLIENT_SCOPES,
        widget_type="tabla",
        max_results=10
    ),
    "consultar_mis_recomendaciones_personalizadas": ToolDefinition(
        name="consultar_mis_recomendaciones_personalizadas",
        description="Genera recomendaciones personalizadas para el cliente combinando su historial de compras, reservas, disponibilidad real y preferencias expresadas en la conversación.",
        parameters={
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "description": "Cantidad de recomendaciones (por defecto 4)"},
                "categoria": {"type": "string", "description": "Categoría preferida opcional"},
                "talla": {"type": "string", "description": "Talla preferida opcional"},
                "precio_max": {"type": "number", "description": "Presupuesto máximo opcional en Bs."}
            }
        },
        allowed_contexts=ALL_SCOPES,
        widget_type="recomendaciones",
        max_results=8
    ),

    # =========================================================================
    # 9.2 HERRAMIENTAS ADMINISTRATIVAS Y COMERCIALES (13 + ALIASES)
    # =========================================================================
    "consultar_ventas_empresa": ToolDefinition(
        name="consultar_ventas_empresa",
        description="Consulta las ventas confirmadas, facturación total en Bs., ticket promedio y transacciones de la empresa en un período.",
        parameters={
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": ["hoy", "ayer", "esta_semana", "semana_pasada", "este_mes", "mes_pasado", "ultimos_30_dias", "este_anio"],
                    "description": "Período temporal a consultar"
                },
                "sucursal": {"type": "string", "description": "Nombre de la sucursal (opcional)"}
            },
            "required": ["periodo"]
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["ventas.consultar", "reportes.consultar", "kpis.consultar", "admin.acceder"],
        widget_type="indicadores",
        is_admin_tool=True
    ),
    "consultar_kpis_empresa": ToolDefinition(
        name="consultar_kpis_empresa",
        description="Obtiene los indicadores clave de rendimiento (KPIs) ejecutivos de la empresa: ingresos netos, ventas confirmadas, ticket promedio, prendas activas y sucursales.",
        parameters={
            "type": "object",
            "properties": {
                "sucursal": {"type": "string", "description": "Sucursal opcional"}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["kpis.consultar", "reportes.consultar", "admin.acceder"],
        widget_type="indicadores",
        is_admin_tool=True
    ),
    "consultar_indicadores_kpi_generales": ToolDefinition(
        name="consultar_indicadores_kpi_generales",
        description="Alias compatible para consultar los principales indicadores KPI de la empresa.",
        parameters={"type": "object", "properties": {}},
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["kpis.consultar", "reportes.consultar", "admin.acceder"],
        widget_type="indicadores",
        is_admin_tool=True
    ),
    "consultar_ventas_por_periodo": ToolDefinition(
        name="consultar_ventas_por_periodo",
        description="Compara el desempeño de ventas e ingresos entre dos períodos (ej. este mes vs el mes anterior, o esta semana vs la semana pasada) calculando variaciones porcentuales reales.",
        parameters={
            "type": "object",
            "properties": {
                "periodo_actual": {"type": "string", "default": "este_mes", "description": "Período principal (ej. 'este_mes', 'esta_semana', 'hoy')"},
                "periodo_comparacion": {"type": "string", "default": "mes_pasado", "description": "Período de referencia (ej. 'mes_pasado', 'semana_pasada', 'ayer')"},
                "sucursal": {"type": "string", "description": "Sucursal opcional"}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["ventas.consultar", "reportes.consultar", "kpis.consultar", "admin.acceder"],
        widget_type="comparacion",
        is_admin_tool=True
    ),
    "consultar_productos_mas_vendidos": ToolDefinition(
        name="consultar_productos_mas_vendidos",
        description="Obtiene el ranking comercial de las prendas con mayor rotación, unidades vendidas, ingresos generados y su stock disponible actual.",
        parameters={
            "type": "object",
            "properties": {
                "periodo": {"type": "string", "default": "ultimos_30_dias", "description": "Período a analizar"},
                "sucursal": {"type": "string", "description": "Sucursal opcional"},
                "limite": {"type": "integer", "default": 8, "description": "Cantidad de productos"}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["ventas.consultar", "reportes.consultar", "inventario.consultar", "admin.acceder"],
        widget_type="tabla",
        max_results=10,
        is_admin_tool=True
    ),
    "consultar_productos_sin_rotacion": ToolDefinition(
        name="consultar_productos_sin_rotacion",
        description="Identifica prendas de baja rotación o stock inmovilizado que se están vendiendo menos de lo esperado, mostrando capital retenido y días sin movimiento.",
        parameters={
            "type": "object",
            "properties": {
                "sucursal": {"type": "string", "description": "Sucursal opcional"},
                "limite": {"type": "integer", "default": 8, "description": "Cantidad máxima de registros"}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["inventario.consultar", "reportes.consultar", "admin.acceder"],
        widget_type="alertas",
        max_results=10,
        is_admin_tool=True
    ),
    "consultar_inventario_alertas": ToolDefinition(
        name="consultar_inventario_alertas",
        description="Consulta el estado del inventario físico identificando prendas agotadas o con stock crítico por debajo del mínimo de seguridad.",
        parameters={
            "type": "object",
            "properties": {
                "filtro": {"type": "string", "enum": ["agotados", "bajo_stock", "todos"], "description": "Condición del stock"},
                "sucursal": {"type": "string", "description": "Nombre de la sucursal (opcional)"}
            },
            "required": ["filtro"]
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["inventario.consultar", "reportes.consultar", "admin.acceder"],
        widget_type="alertas",
        max_results=12,
        is_admin_tool=True
    ),
    "consultar_devoluciones_reclamos": ToolDefinition(
        name="consultar_devoluciones_reclamos",
        description="Audita y resume las devoluciones y reclamos registrados en la empresa por período, sucursal y motivo.",
        parameters={
            "type": "object",
            "properties": {
                "periodo": {"type": "string", "enum": ["hoy", "esta_semana", "este_mes", "ultimos_30_dias", "todos"]},
                "sucursal": {"type": "string"},
                "motivo": {"type": "string"}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["devoluciones.consultar", "reportes.consultar", "admin.acceder"],
        widget_type="tabla",
        max_results=10,
        is_admin_tool=True
    ),
    "consultar_recomendaciones_reposicion_stock": ToolDefinition(
        name="consultar_recomendaciones_reposicion_stock",
        description="Consulta el motor oficial CU23W para obtener recomendaciones de reposición de inventario basadas en ritmo diario de ventas, días de cobertura, lead time y stock de seguridad.",
        parameters={
            "type": "object",
            "properties": {
                "sucursal": {"type": "string", "description": "Nombre de la sucursal (opcional)"},
                "categoria": {"type": "string", "description": "Categoría opcional"},
                "lead_time_dias": {"type": "integer", "default": 7, "description": "Tiempo de reposición del proveedor en días"}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["inventario.consultar", "reportes.consultar", "kpis.consultar", "admin.acceder"],
        widget_type="recomendaciones",
        max_results=10,
        is_admin_tool=True
    ),
    "consultar_demanda_proyectada": ToolDefinition(
        name="consultar_demanda_proyectada",
        description="Consulta el servicio predictivo oficial CU23W (suavizamiento exponencial con tendencia Holt e intervalos de confianza al 95%) para proyectar la demanda futura y evaluar su precisión (MAE, RMSE, MAPE).",
        parameters={
            "type": "object",
            "properties": {
                "dias_proyeccion": {"type": "integer", "default": 14, "description": "Horizonte de proyección en días (7, 14 o 30)"},
                "dias_historia": {"type": "integer", "default": 60, "description": "Ventana histórica de análisis en días"},
                "sucursal": {"type": "string", "description": "Sucursal opcional"},
                "id_producto": {"type": "integer", "description": "ID de producto específico opcional"}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["reportes.consultar", "kpis.consultar", "admin.acceder"],
        widget_type="predicciones",
        max_results=14,
        is_admin_tool=True
    ),
    "consultar_riesgo_agotamiento": ToolDefinition(
        name="consultar_riesgo_agotamiento",
        description="Identifica las variantes y prendas con riesgo CRÍTICO o ALTO de quiebre de stock antes del tiempo de reposición según la velocidad de venta real (CU23W).",
        parameters={
            "type": "object",
            "properties": {
                "sucursal": {"type": "string", "description": "Sucursal opcional"},
                "lead_time_dias": {"type": "integer", "default": 7, "description": "Días de reposición"}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["inventario.consultar", "reportes.consultar", "admin.acceder"],
        widget_type="alertas",
        max_results=10,
        is_admin_tool=True
    ),
    "consultar_reporte_motor_analitico": ToolDefinition(
        name="consultar_reporte_motor_analitico",
        description="Ejecuta cualquiera de los 13 reportes canónicos del sistema (ventas, inventario, rentabilidad, rendimiento de cajeros, stock inmovilizado, sesiones de caja, pagos, devoluciones).",
        parameters={
            "type": "object",
            "properties": {
                "comando_o_reporte": {"type": "string", "description": "Consulta analítica (ej. 'rentabilidad por producto', 'rendimiento de cajeros', 'ventas pendientes')"}
            },
            "required": ["comando_o_reporte"]
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["reportes.consultar", "admin.acceder"],
        widget_type="reporte",
        max_results=10,
        is_admin_tool=True
    ),
    "generar_reporte_directo": ToolDefinition(
        name="generar_reporte_directo",
        description="Genera un resumen de reporte oficial de ventas, inventario, pagos, caja, devoluciones, rentabilidad o stock inmovilizado.",
        parameters={
            "type": "object",
            "properties": {
                "tipo_reporte": {
                    "type": "string",
                    "enum": ["ventas", "inventario", "pagos", "caja", "devoluciones", "rentabilidad", "rendimiento_personal", "stock_inmovilizado"]
                },
                "periodo": {"type": "string"}
            },
            "required": ["tipo_reporte"]
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["reportes.consultar", "admin.acceder"],
        widget_type="reporte",
        max_results=10,
        is_admin_tool=True
    ),
    "consultar_ventas_pendientes": ToolDefinition(
        name="consultar_ventas_pendientes",
        description="Consulta las ventas y pedidos pendientes de confirmación de pago en la empresa, mostrando antigüedad y montos por cobrar.",
        parameters={
            "type": "object",
            "properties": {
                "sucursal": {"type": "string"},
                "canal": {"type": "string", "enum": ["todos", "pos", "online"]}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["ventas.consultar", "reportes.consultar", "admin.acceder"],
        widget_type="tabla",
        max_results=10,
        is_admin_tool=True
    ),
    "consultar_auditoria_pos_errores": ToolDefinition(
        name="consultar_auditoria_pos_errores",
        description="Audita las ventas en mostrador/caja POS para detectar incidencias o descuadres de cobro.",
        parameters={
            "type": "object",
            "properties": {
                "sucursal": {"type": "string"},
                "solo_alertas": {"type": "boolean"}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["caja.consultar", "ventas.consultar", "reportes.consultar", "admin.acceder"],
        widget_type="tabla",
        max_results=10,
        is_admin_tool=True
    ),
    "consultar_reservas_prendas_empresa": ToolDefinition(
        name="consultar_reservas_prendas_empresa",
        description="Consulta las reservas de prendas apartadas en las sucursales de la empresa y su estado de vigencia.",
        parameters={
            "type": "object",
            "properties": {
                "sucursal": {"type": "string"},
                "vigencia": {"type": "string", "enum": ["vigente", "vencida", "todas"]}
            }
        },
        allowed_contexts=ADMIN_SCOPES,
        required_permissions=["reservas.consultar", "reportes.consultar", "admin.acceder"],
        widget_type="tabla",
        max_results=10,
        is_admin_tool=True
    ),
}


# Nombres de herramientas de escritura prohibidas explícitamente
FORBIDDEN_WRITE_TOOLS = {
    "modificar_inventario", "actualizar_stock", "eliminar_producto", "cambiar_precio",
    "anular_venta", "cancelar_venta", "eliminar_usuario", "cambiar_rol", "asignar_rol",
    "procesar_pago", "capturar_pago", "ejecutar_sql", "drop_table"
}


class ToolRegistry:
    @classmethod
    def get_tool(cls, name: str) -> Optional[ToolDefinition]:
        return TOOL_DEFINITIONS.get(name)

    @classmethod
    def get_tools_for_context(cls, ctx: AssistantSecurityContext) -> List[Dict[str, Any]]:
        """Retorna las especificaciones OpenAI/Function-Calling permitidas para el contexto actual."""
        available: List[Dict[str, Any]] = []
        for tool_def in TOOL_DEFINITIONS.values():
            if cls.is_authorized(tool_def, ctx):
                available.append(tool_def.to_openai_tool())
        return available

    @classmethod
    def is_authorized(cls, tool_def: ToolDefinition, ctx: AssistantSecurityContext) -> bool:
        """
        Verifica de forma independiente si el contexto de usuario tiene permiso para usar la herramienta.
        """
        if not tool_def.read_only:
            return False

        if ctx.alcance not in tool_def.allowed_contexts:
            return False

        if tool_def.is_admin_tool:
            if not ctx.es_admin or ctx.alcance in ("PUBLIC", "CLIENTE"):
                return False
            # Si es PLATAFORMA o ADMINISTRADOR_TIENDA o tiene al menos uno de los permisos requeridos
            if ctx.alcance in ("PLATAFORMA", "EMPRESA"):
                return True
            if tool_def.required_permissions and ctx.permisos:
                if any(p in ctx.permisos for p in tool_def.required_permissions):
                    return True
                # Para encargados/cajeros en sucursal permitir herramientas operativas de sucursal si su rol lo respalda
                roles_set = set(ctx.roles)
                if roles_set.intersection({"ENCARGADO", "ENCARGADO_SUCURSAL", "CAJERO", "EMPLEADO"}):
                    return True
                return False

        return True

    @classmethod
    def get_openai_tools_for_context(cls, ctx: AssistantSecurityContext) -> List[Dict[str, Any]]:
        return cls.get_tools_for_context(ctx)


GLOBAL_TOOL_REGISTRY = ToolRegistry

