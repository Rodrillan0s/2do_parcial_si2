from fastapi import HTTPException
from fastapi.responses import JSONResponse
from psycopg2 import errors

BUSINESS_ERRORS = {
    'LIMITE_SUCURSALES': (409, 'El plan no permite más sucursales activas.'),
    'LIMITE_PLAN_PROGRAMADO': (409, 'La activación excedería un plan programado.'),
    'SUSCRIPCION_NO_VIGENTE': (403, 'La empresa no tiene una suscripción vigente.'),
    'EMPRESA_INACTIVA': (403, 'La empresa está inactiva.'),
    'TRASLADO_EMPRESA_NO_PERMITIDO': (409, 'No se permite trasladar una entidad entre empresas.'),
    'ASIGNACION_SUCURSAL_NO_AUTORIZADA': (403, 'Usuario y sucursales deben pertenecer a la misma empresa activa.'),
    'PERIODO_SOLAPADO': (409, 'Ya existe una suscripción para ese periodo. Puedes programar el cambio para el siguiente ciclo.'),
    'SUSCRIPCION_INMUTABLE': (409, 'El historial de suscripciones está protegido y no permite modificaciones retroactivas. Si deseas cambiar de plan, puedes programarlo para el siguiente ciclo o cancelarlo conforme a las políticas comerciales.'),
    'PLAN_INACTIVO': (409, 'El plan está inactivo.'),
}


def translate_database_error(exc):
    """Called before legacy broad except blocks can turn business errors into 500."""
    if isinstance(exc, errors.CheckViolation):
        code = exc.diag.message_primary
        if code in BUSINESS_ERRORS:
            status, message = BUSINESS_ERRORS[code]
            raise HTTPException(status, detail={'code': code, 'message': message}) from exc


def install_handlers(app):
    @app.exception_handler(errors.UndefinedTable)
    async def missing_migration(request, exc):
        return JSONResponse(status_code=503, content={'detail': {'code': 'MIGRACION_PENDIENTE', 'message': 'Esquema no disponible; consulte al administrador.'}})

    @app.exception_handler(errors.CheckViolation)
    async def constraint_error(request, exc):
        code = exc.diag.message_primary
        status, message = BUSINESS_ERRORS.get(code, (409, 'La operación incumple una regla de integridad.'))
        return JSONResponse(status_code=status, content={'detail': {'code': code if code in BUSINESS_ERRORS else 'INTEGRIDAD', 'message': message}})
