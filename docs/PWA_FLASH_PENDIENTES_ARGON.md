# AuroraStore — Tareas Pendientes para Argon (Iteración 2 Avanzada)
**Fecha:** 28 de Octubre de 2026  
**Entregado por:** Antigravity (Gemini Flash 3.8)  
**Destinatario:** Modelo de Razonamiento Avanzado (Argon / Gemini Pro)  
**Propósito:** Delimitar con precisión las operaciones comerciales transaccionales de alto riesgo, los casos de uso offline pendientes y la sincronización profunda que quedaron expresamente fuera del alcance de Flash 3.8.

---

## 1. Estado de Entrada para Argon
La aplicación cuenta ahora con:
- Infraestructura base de PWA y Service Worker (`sw.js`) funcional, con aislamiento riguroso de `CacheStorage` (solo App Shell, assets estáticos e imágenes acotadas).
- Base de datos IndexedDB (`aurora_store_pwa_db`) con todos los stores creados (`products`, `product_details`, `catalog_filters`, `branches`, `stock_snapshots`, `cart_drafts`, `pending_operations`, `sync_attempts`, `metadata`).
- Sesión y navegación seguras ante desconexiones de red, timeouts o caídas de servidor (sin deslogueos erróneos).
- Precarga selectiva de lectura de catálogo y filtros para navegación offline de consulta (`CU04W` / `CU05W`).
- 40 pruebas automatizadas pasando al 100%.

---

## 2. Tareas Transaccionales Críticas Reservadas para Argon

### 2.1. CU24W — Ventas de Contado Offline (POS / Terminal de Caja)
- **Alcance pendiente:**
  - Registro de ventas de contado en la terminal POS (`/admin/caja`) cuando no hay conexión.
  - Generación de numeración provisional o correlativo local offline (ej. `OFFLINE-E{tenant}-S{sucursal}-{timestamp}`).
  - Descuento de stock provisional en `stock_snapshots` local de IndexedDB con bandera de `stock_descontado_localmente: true`.
  - Encolado seguro en el store `pending_operations` con payload canónico:
    - `id_operacion_local` (UUID v4)
    - `tipo: 'VENTA_CONTADO'`
    - `id_empresa`, `id_sucursal`, `id_usuario`
    - Items con `id_inventario`, `id_producto`, `cantidad`, `precio_unitario`
    - `monto_total`, `metodo_pago: 'EFECTIVO'`
    - `creado_el_cliente` (marca ISO)
  - **Restricción no negociable:** Pagos electrónicos con tarjeta o QR NO están permitidos offline; únicamente ventas de contado en efectivo.
  - Sincronización transaccional definitiva con el endpoint online correspondiente en FastAPI cuando se recupere la conexión, confirmando el comprobante oficial.

### 2.2. CU10W — Reservas Offline
- **Alcance pendiente:**
  - Permitir al cliente o cajero registrar solicitudes de reserva cuando se pierde la conexión.
  - **Restricción no negociable:** Una reserva offline solo puede registrarse como **pendiente de confirmación**, NUNCA como confirmada ni con stock asegurado en el servidor antes de conectar.
  - Al sincronizar con el backend, comprobar disponibilidad en tiempo real en PostgreSQL:
    - Si hay stock: confirmar reserva y generar folio oficial.
    - Si se agotó el stock durante el periodo offline: notificar conflicto al usuario para que seleccione otra fecha, talla o sucursal.

### 2.3. CU38W y CU39W — Motor de Sincronización Transaccional y Resolución de Conflictos
- **Alcance pendiente:**
  - Mecanismo de reintento con retroceso exponencial (exponential backoff) para fallos transitorios de red.
  - Protocolo de detección de conflictos en el servidor:
    - Discrepancia de precios durante el periodo offline.
    - Sobreventa (stock insuficiente al momento de la sincronización).
    - Desactivación de sucursal o revocación de permisos de empleado durante el periodo offline.
  - Interfaz interactiva de resolución en `PwaStatusBarComponent` / drawer de sincronización para que el usuario o cajero elija:
    - Aceptar precio actualizado.
    - Ajustar cantidad disponible.
    - Descartar o cancelar operación en conflicto.

### 2.4. Integración y Contratos para la App Móvil Flutter (SQLite)
- **Alcance pendiente:**
  - Mantener paridad con los esquemas de sincronización definidos en `docs/ITER1_CONTEXT.md` y `docs/API_CONTRACTS.md`.
  - Asegurar que la estructura de la cola local en SQLite de Flutter coincida con los contratos JSON de `pending_operations` que procesa el backend FastAPI en `/api/sync/lote` y `/api/sync/ping`.
  - Verificar que las pruebas de compatibilidad de la API pública sigan respetando a Flutter sin romper rutas ni parámetros.

---

## 3. Checklist de Verificación Recomendado para Argon

1. [ ] Implementar la persistencia de borradores de venta de contado en `pending_operations` desde `caja.ts`.
2. [ ] Validar que las ventas de contado offline decrementen el stock local para evitar doble venta en la misma terminal.
3. [ ] Probar la sincronización en lote contra `/api/sync/lote` simulando cortes y reconexiones de red.
4. [ ] Probar el escenario de conflicto de concurrencia donde dos clientes intentan reservar la última prenda mientras uno estaba offline.
5. [ ] Ejecutar la suite completa de 40 pruebas e incorporar nuevos tests específicos de integración para CU24W y CU10W.

