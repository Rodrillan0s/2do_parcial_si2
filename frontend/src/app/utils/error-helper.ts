/**
 * Utilidad unificada para extraer y formatear mensajes de error provenientes del backend FastAPI.
 * Soporta:
 * - detail como texto plano (string).
 * - detail como objeto estructurado { code?: string; message?: string }.
 * - detail como array de validación Pydantic [{ loc?: any[]; msg?: string; type?: string }].
 * - Códigos específicos de SaaS (LIMITE_SUCURSALES, PLAN_NO_HABILITA_REPORTES, MIGRACION_PENDIENTE, etc.).
 * - Respuestas estándar HTTP.
 */
export function extraerMensajeError(err: any, mensajePorDefecto: string = 'Ocurrió un error inesperado al procesar la solicitud.'): string {
  if (!err) return mensajePorDefecto;

  // Si err es directamente una cadena
  if (typeof err === 'string') return err;

  // Manejo de error 503 por migración pendiente
  if (err.status === 503) {
    const detail = err.error?.detail;
    if (detail && typeof detail === 'object' && detail.code === 'MIGRACION_PENDIENTE') {
      return detail.message || 'El servicio requiere aplicar la migración de base de datos pendiente (MIGRACION_PENDIENTE).';
    }
    return 'Servicio temporalmente no disponible por tareas de mantenimiento o base de datos.';
  }

  // Si viene dentro de err.error
  const errorBody = err.error !== undefined ? err.error : err;

  if (errorBody) {
    // Si errorBody tiene propiedad detail
    if (errorBody.detail !== undefined && errorBody.detail !== null) {
      const detail = errorBody.detail;

      // 1. detail es string directo
      if (typeof detail === 'string') {
        return detail.trim() || mensajePorDefecto;
      }

      // 2. detail es objeto con code y message
      if (typeof detail === 'object' && !Array.isArray(detail)) {
        if (detail.message) {
          return detail.message;
        }
        if (detail.msg) {
          return detail.msg;
        }
        if (detail.code) {
          return `Error (${detail.code}): ${JSON.stringify(detail)}`;
        }
      }

      // 3. detail es array de errores de validación (Pydantic / FastAPI 422)
      if (Array.isArray(detail)) {
        const mensajes = detail.map((item: any) => {
          if (typeof item === 'string') return item;
          if (item && item.msg) {
            const campo = Array.isArray(item.loc) ? item.loc.filter((l: any) => l !== 'body').join('.') : '';
            return campo ? `${campo}: ${item.msg}` : item.msg;
          }
          return JSON.stringify(item);
        });
        if (mensajes.length > 0) {
          return mensajes.join(' | ');
        }
      }
    }

    // Si viene en message
    if (typeof errorBody.message === 'string' && errorBody.message.trim().length > 0) {
      return errorBody.message;
    }

    // Si errorBody es string directo
    if (typeof errorBody === 'string' && errorBody.trim().length > 0) {
      return errorBody;
    }
  }

  // Fallback al message nativo de Javascript / Error
  if (err.message && typeof err.message === 'string') {
    return err.message;
  }

  return mensajePorDefecto;
}
