# Changelog — Módulo SaaS, Storefront y Suscripciones (AuroraStore)

**Módulo:** Gestión de Suscripciones SaaS, Contratación Autónoma y Pasarela de Pago  
**Ubicación:** `backend/app/modules/saas/` & `frontend/src/app/pages/suscripciones/`  
**Base de Datos:** PostgreSQL (`empresa`, `t_plan`, `t_suscripcion`, `t_solicitud_contratacion`, `t_permiso`)  
**Estado:** Estable / Pasarela PayPal Sandbox y Ciclo de Planes Operativos  

---

## [2026-11-06] — Experiencia de Cambio de Plan, Políticas de Cancelación y Pasarela de Pagos

### 1. Diagnóstico de la Experiencia de Usuario
- **Mensaje confuso de inmutabilidad:** El usuario recibía un mensaje agresivo: *"El historial de suscripciones es inmutable"* al intentar cambiar de suscripción, mostrándose además banners simultáneos de éxito (verde) y error (rojo).
- **Falta de opciones comerciales estándar:** En una plataforma SaaS comercial, el cliente espera opciones claras:
  - Cancelar suscripción conservando el servicio activo hasta el fin del periodo contratado.
  - Solicitar reembolso y cancelación inmediata si no ha transcurrido más del 10% del periodo de suscripción.
  - Programar cambio de plan (upgrade o downgrade) efectivo al iniciar el siguiente ciclo de facturación.
- **Flujo de pago tras redirección:** Al completar el pago en PayPal, el usuario no debía ser conducido a un panel intermediario confuso; el sistema debía verificar y aprobar el pago de inmediato, o presentar un botón de comprobación con feedback transparente.

### 2. Cambios Implementados

#### A. Limpieza Visual y Banners Excluyentes (`suscripciones.ts`)
- En `frontend/src/app/pages/suscripciones/suscripciones.ts`, se ajustó la lógica para que las señales `errorModalCambio` y `exitoModalCambio` sean mutuamente excluyentes:
  - Al desencadenar una acción, se limpian ambos estados de error y éxito previos.
  - La visualización en el modal presenta un mensaje contextual único, evitando advertencias contradictorias.

#### B. Políticas de Ciclo de Vida de Suscripción
1. **Conservación de Suscripción hasta Fin de Periodo:**
   - La cancelación no interrumpe el acceso de forma abrupta si el periodo ya fue abonado; el estado se marca para no renovación automática y la tienda conserva sus límites operativos hasta la fecha `fin`.
2. **Reembolso por Cancelación Temprana (<= 10% del Periodo):**
   - Si la solicitud de cancelación se realiza durante el primer 10% del tiempo de suscripción (ej. primeros 3 días en un plan mensual de 30 días), se habilita la opción de reembolso administrativo total y reversión del plan.
3. **Cambio de Plan Programado:**
   - El cambio de plan (p. ej. de BÁSICO a PROFESIONAL o viceversa) se programa como una suscripción futura vinculada al fin del periodo actual, preservando la inmutabilidad histórica contable sin bloquear al cliente.

#### C. Pasarela de Pago PayPal Sandbox y Verificación Directa
- Verificados los endpoints:
  - `POST /api/saas/pagos/paypal/orden`: Crea la orden oficial en PayPal Sandbox con el monto y moneda correctos (BOB o USD equivalente).
  - `POST /api/saas/pagos/paypal/capturar`: Captura la orden, verifica el estado `COMPLETED` directamente contra la API de PayPal, activa la suscripción y genera el registro en `t_suscripcion` y `t_solicitud_contratacion`.

---

## [2026-11-05] — Migración 006: Storefront Multitenant y Contratación Autónoma
- Creación de tabla `t_solicitud_contratacion` para registro público y flujo de onboarding.
- Adición de `slug` y `configuracion_storefront` JSONB en `empresa`.
- Extensión de `t_plan` con precios mensual/anual y beneficios comerciales.
- Verificación criptográfica de correos mediante hash de un solo uso.
