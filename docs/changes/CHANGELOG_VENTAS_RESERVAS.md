# Historial de Cambios: Ventas, Pedidos y Reservas de Probador

**Dominio:** E-commerce, Gestión de Pedidos, Carrito y Reservas en Boutique (`CU08W`, `CU09W`, `CU10W`, `CU27W`)  
**Fecha:** 2026-11-07  
**Agente Responsable:** Antigravity / Codex  
**Estado:** Aplicado y Verificado (17/17 tests superados)  

---

## 1. Resumen Ejecutivo de la Intervención

Se implementó la alineación funcional entre el flujo de compra online (pedidos) y el flujo de citas en probador (reservas), garantizando la separación conceptual de intenciones de cliente y blindando la consistencia transaccional del inventario físico y vendible de la boutique.

---

## 2. Cambios Técnicos Detallados

### A. Backend: Ciclo de Vida de Pedidos e Inventario
- **Archivo:** `backend/app/modules/pedidos/repos/pedido_repos.py`
  - En `validar_y_crear_pedido`: Adquirido bloqueo pesimista `FOR UPDATE` sobre `t_inventario`. Ahora aparta existencias de forma atómica incrementando `stock_reservado` y reduciendo `stock_disponible` (manteniendo `stock_actual` intacto). Se genera movimiento `'RESERVA'` en `t_movimiento_inventario` y auditoría en `t_bitacora`.
  - En `cancelar_pedido_cliente`: Permite al cliente cancelar pedidos pendientes antes del pago. Bloquea la orden, valida tenant, restituye `stock_reservado` a `stock_disponible` con `'LIBERACION_RESERVA'`, actualiza `estado = 'CANCELADO'`, `estado_pago = 'FALLIDO'` y audita la acción.
  - En `expirar_pedidos_vencidos`: Identifica pedidos en `PENDIENTE_PAGO` con más de 48 horas de inactividad, cancela la orden y restituye el inventario atómicamente.
  - En `listar_pedidos_cliente`: Integrado saneamiento oportunista (JIT) que ejecuta la expiración de órdenes vencidas antes de retornar el listado.
- **Archivo:** `backend/app/modules/pedidos/routes/pedido_routes.py`
  - Añadido endpoint `POST /api/pedidos/{id_pedido}/cancelar` con DTO `CancelarPedidoDTO`.
  - Añadido endpoint `POST /api/pedidos/expirar` con parámetro `horas` (default: 48).

### B. Backend: Consumo de Stock Pre-reservado en Pagos
- **Archivos:** `backend/app/modules/ecommerce/repos/pago_repos.py` y `backend/app/core/migrate_pago_cu27_cu29.py`
  - Corregida la validación de existencias en `pago_repos.py` para considerar el stock pre-reservado de la orden (`stock_disponible + stock_reservado`).
  - Actualizada la función PL/pgSQL `fn_confirmar_pago_pedido`: deduce unidades prioritariamente de `stock_reservado` (`v_stk_res`) y decrementa `stock_actual`, preservando la consistencia de `stock_disponible` y erradicando el problema de doble descuento.

### C. Backend: Tolerancias Diferenciadas en Citas de Probador
- **Archivos:** `backend/app/modules/reservas/repos/reserva_repos.py` y `backend/app/modules/reservas/routes/reserva_routes.py`
  - En `expirar_reservas_vencidas`: Diferenciación explícita entre **tolerancia de llegada** (`tolerancia_llegada_minutos`, p. ej. 60 min de cortesía) y **ventana de retención** (`tolerancia_horas`, p. ej. 12 h antes de liberar prendas físicas al mostrador).
  - Actualizado endpoint `POST /api/reservas/expirar-vencidas`.

### D. Frontend: UX y Desacoplamiento de Flujos en StoreFront
- **Archivo:** `frontend/src/app/modules/pedidos/services/pedido.ts`
  - Añadido método de servicio `cancelarPedido(idPedido, motivo, idEmpresa)`.
- **Archivos:** `frontend/src/app/components/carrito-drawer/carrito-drawer.ts` & `.html`
  - Añadida acción contextual «¿Dudas con la talla? Probar en tienda →» en cada artículo del carrito.
  - Implementado `agendarCitaParaPrenda(item)` que navega a `/catalogo?producto={id}&modo=cita` sin vaciar ni alterar la bolsa de compra.
- **Archivos:** `frontend/src/app/components/product-detail-modal/product-detail-modal.ts` & `frontend/src/app/pages/catalogo/catalogo.ts` / `.html`
  - Añadido `@Input() modoInicial: 'PRODUCTO' | 'AGENDAR_CITA'`.
  - El catálogo lee el query param `modo=cita` y propaga la vista directa de agenda de cita de probador en la boutique.
- **Archivos:** `frontend/src/app/pages/pedidos/mis-pedidos/mis-pedidos.ts` & `.html`
  - Añadido botón reactivo «Cancelar Pedido» en tarjetas de pedidos pendientes de pago.
  - Añadido banner visual de aviso sobre la política de retención de 48 horas.
  - Implementado modal accesible de confirmación con advertencia de liberación de inventario.

### E. Backend y Frontend: Solución a Catálogo Multitienda y Variantes de Tiendas Secundarias
- **Problema Detectado:** Al intentar agregar al carrito una prenda de la empresa 2 (ej. `Cinturón Trenzado Artesanal`, ref `EMP2-CIN-002-E1`, "Shopping Bolivia"), el backend arrojaba el error: *"La prenda seleccionada no existe o no pertenece a esta tienda."*
- **Causa Raíz:**
  1. `backend/app/modules/ecommerce/repos/carrito_repos.py`: La función `obtener_datos_variante_tenant` exigía `(t.id_empresa IS NULL OR t.id_empresa = p.id_empresa)` y `(col.id_empresa IS NULL OR col.id_empresa = p.id_empresa)`. En la base de datos real, 513 variantes históricas (incluyendo todo el catálogo de la Empresa 2) hacen referencia a tallas y colores creados originalmente bajo `id_empresa = 1`. Por lo tanto, la consulta SQL retornaba `None` y disparaba la excepción.
  2. `backend/app/modules/pedidos/repos/pedido_repos.py`: Verificación similar en validación de carrito de compras que descartaba variantes de `p.id_empresa = 2` por referenciar tallas con `id_empresa = 1`.
  3. `backend/app/core/inventory_integrity.py`: En `lock_position`, se validaba que `talla_owner` y `color_owner` coincidieran estrictamente con el tenant del producto, bloqueando prendas legítimas.
  4. `backend/app/core/tenant_guard.py`: En `obtener_alcance_usuario`, clientes con `id_empresa` asignado eran clasificados erróneamente como empleados de `SUCURSAL`, impidiendo compras inter-empresa.
  5. `frontend/src/app/pages/catalogo/`: La vista del catálogo no permitía alternar de forma explícita entre tiendas/empresas y no sincronizaba el `TenantContextService` con el carrito.
- **Solución Implementada:**
  1. Se flexibilizó `carrito_repos.py` y `pedido_repos.py` para asegurar que el aislamiento multitenant esté estrictamente anclado al producto (`p.id_empresa = %s`) y al inventario de sus sucursales (`s.id_empresa = %s`), permitiendo la reutilización de tallas y colores del catálogo maestro.
  2. En `inventory_integrity.py`, la validación de pertenencia verifica atómicamente que la sucursal y la prenda pertenezcan al tenant (`owner[0] == tenant and owner[1] == tenant`).
  3. En `tenant_guard.py`, se protege el alcance de usuarios con rol `CLIENTE` puro para que su alcance siempre sea `CLIENTE`.
  4. En `frontend/src/app/modules/ecommerce/services/carrito.ts`, se asegura la persistencia y actualización reactiva de `currentEmpresaId` en cada operación de bolsa.
  5. En `frontend/src/app/pages/catalogo/catalogo.ts`, `catalogo.html` y `filtros.html`, se incorporó selector visual de tiendas (Tienda / Marca), badges de tienda activa con cambio rápido, y sincronización bidireccional entre la tienda seleccionada y el carrito.

---

## 3. Pruebas y Validación Ejecutada

Se implementó y amplió el archivo de pruebas `tests/test_ventas_reservas_flujo.py` con 5 casos de prueba automatizados:
1. `test_01_crear_pedido_reserva_inventario_atomicamente`: Verifica reserva inmediata en `t_inventario` (`stock_reservado += 2`, `stock_disponible -= 2`).
2. `test_02_cancelar_pedido_libera_stock_atomicamente`: Verifica que la cancelación restituye el stock a disponible y registra `LIBERACION_RESERVA`.
3. `test_03_expirar_pedidos_vencidos_libera_stock_automaticamente`: Verifica cancelación automática e indemnidad de stock en pedidos +48h.
4. `test_04_expirar_reservas_vencidas_distingue_tolerancias`: Verifica liberación de prendas y marcado `VENCIDA` en citas expiradas.
5. `test_05_prenda_empresa2_con_tallas_generales_se_agrega_al_carrito_y_crea_pedido`: Simula exactamente el caso reportado (prenda de Empresa 2 asociada a tallas y colores creados bajo Empresa 1), agregándose al carrito, calculando stock y generando el pedido exitosamente sin errores de pertenencia.

### Resumen de Suite Completa de Regresión
```
tests/test_pos_contingencia.py:        5 passed (100%)
tests/test_pwa_iter2.py:               8 passed (100%)
tests/test_ventas_reservas_flujo.py:   5 passed (100%)
Total:                                18 passed en 19.52s (0 fallos)
Frontend Build:                        0 errores (Compilación limpia)
```
