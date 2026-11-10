import json
import logging
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.core.config import Config
from app.core.postgres import iniciar_metricas_db_request, obtener_metricas_db_request
from app.core.saas_errors import install_handlers

# Modular routers from UML packages
from app.modules.auth.routes import (
    auth_routes, users_routes, roles_routes, rbac_routes, profile_routes
)
from app.modules.saas.routes import saas_routes, tenant_routes
from app.modules.catalogo.routes import (
    productos_routes, categorias_routes, tallas_colores_routes,
    catalogo_routes, media_routes
)
from app.modules.inventario.routes import (
    sucursales_routes, ciudades_routes, inventario_routes,
    proveedores_routes, compras_lotes_routes
)
from app.modules.ecommerce.routes import carrito_routes, pago_routes, sync_routes
from app.modules.reservas.routes import reserva_routes, atender_reserva_routes
from app.modules.pos.routes import (
    pos_routes, caja_routes, caja_pago_routes, comprobante_routes
)
from app.modules.pedidos.routes import (
    pedido_routes, reportes_routes, kpis_routes, motor_reportes_routes, devoluciones_routes
)
from app.modules.ia.routes import asistente_routes, recomendaciones_routes, predicciones_routes
from app.modules.valoraciones.routes import valoracion_routes
from app.modules.admin.routes import (
    backup_routes, bitacora_routes, main_routes, notificaciones_routes
)

perf_logger = logging.getLogger("aurora.perf")


def create_app() -> FastAPI:
    app = FastAPI(
        title="API E-Commerce Multi-Tenant de Ropa",
        version="2.0.0",
        description="Backend FastAPI para plataforma E-Commerce Multi-Tenant"
    )

    # Schema changes and RBAC seeds are explicit deployment operations.
    install_handlers(app)
    app.include_router(saas_routes.router)

    @app.middleware("http")
    async def performance_instrumentation_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        iniciar_metricas_db_request()
        t_start = time.perf_counter()
        response = await call_next(request)
        total_ms = (time.perf_counter() - t_start) * 1000.0
        db_metrics = obtener_metricas_db_request()
        db_ms = float(db_metrics.get("db_ms", 0.0))
        pool_ms = float(db_metrics.get("pool_ms", 0.0))
        db_queries = int(db_metrics.get("queries", 0))
        app_ms = max(0.0, total_ms - db_ms - pool_ms)

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-Ms"] = f"{total_ms:.2f}"
        response.headers["X-DB-Query-Count"] = str(db_queries)
        response.headers["Server-Timing"] = (
            f"total;dur={total_ms:.2f}, db;dur={db_ms:.2f};desc=\"queries={db_queries}\", "
            f"pool;dur={pool_ms:.2f}, app;dur={app_ms:.2f}"
        )

        if request.url.path.startswith("/api/"):
            perf_logger.info(
                json.dumps(
                    {
                        "event": "http_request_perf",
                        "request_id": req_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "total_ms": round(total_ms, 2),
                        "db_ms": round(db_ms, 2),
                        "pool_ms": round(pool_ms, 2),
                        "app_ms": round(app_ms, 2),
                        "db_queries": db_queries,
                    }
                )
            )
        return response

    app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:4200",
            "http://127.0.0.1:4200",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://aurora-store-d20q.onrender.com",
            ""
        ],
        allow_origin_regex=r"https?://([a-zA-Z0-9-]+\.)?(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms", "X-DB-Query-Count", "Server-Timing"],
    )

    # Registro de rutas activas e-commerce (preservando el orden y prefijos exactos)
    app.include_router(main_routes.router)
    app.include_router(auth_routes.router, prefix='/api/auth')
    app.include_router(users_routes.router, prefix='/api/usuarios')
    app.include_router(tenant_routes.router, prefix='/api/empresas')
    app.include_router(sucursales_routes.router, prefix='/api/sucursales')
    app.include_router(roles_routes.router, prefix='/api/roles')
    app.include_router(rbac_routes.router, prefix='/api/rbac')
    app.include_router(bitacora_routes.router, prefix='/api/bitacora')
    app.include_router(notificaciones_routes.router, prefix='/api/ws')
    app.include_router(kpis_routes.router)
    app.include_router(kpis_routes.kpis_router)
    app.include_router(reportes_routes.router)
    app.include_router(backup_routes.router, prefix='/api/backup')
    app.include_router(profile_routes.router, prefix='/api/perfil')
    app.include_router(ciudades_routes.router, prefix='/api/ciudades')
    app.include_router(media_routes.router)
    app.include_router(categorias_routes.router, prefix='/api/categorias')
    app.include_router(tallas_colores_routes.tallas_router, prefix='/api/tallas')
    app.include_router(tallas_colores_routes.colores_router, prefix='/api/colores')
    app.include_router(productos_routes.router)
    app.include_router(catalogo_routes.router)
    app.include_router(carrito_routes.router)
    app.include_router(sync_routes.router)
    app.include_router(pedido_routes.router)
    app.include_router(devoluciones_routes.router)
    app.include_router(reserva_routes.router)
    app.include_router(proveedores_routes.router, prefix='/api/proveedores')
    app.include_router(inventario_routes.router)
    app.include_router(pago_routes.router)

    app.include_router(comprobante_routes.router, prefix='/api/comprobantes')
    app.include_router(caja_routes.router)
    app.include_router(pos_routes.router)
    app.include_router(caja_pago_routes.router)
    app.include_router(compras_lotes_routes.router)
    app.include_router(asistente_routes.router)
    app.include_router(recomendaciones_routes.router)
    app.include_router(predicciones_routes.router)
    app.include_router(motor_reportes_routes.router)
    app.include_router(atender_reserva_routes.router)
    app.include_router(valoracion_routes.router)

    return app


app = create_app()

