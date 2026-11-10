-- Executed READ ONLY; snapshot time: 2026-11-01 00:44:42.605385-04

-- inventory_missing_identity
SELECT count(*) FROM t_inventario WHERE id_sucursal IS NULL OR id_variante IS NULL;

-- inventory_missing_quantities
SELECT count(*) FROM t_inventario WHERE stock_actual IS NULL OR stock_reservado IS NULL OR stock_disponible IS NULL;

-- inventory_negative_or_overreserved
SELECT count(*) FROM t_inventario WHERE stock_actual<0 OR stock_reservado<0 OR stock_disponible<0 OR stock_reservado>stock_actual;

-- inventory_available_mismatch
SELECT count(*) FROM t_inventario WHERE stock_disponible IS DISTINCT FROM stock_actual-stock_reservado;

-- inventory_duplicate_branch_variant_groups
SELECT count(*) FROM (SELECT id_sucursal,id_variante FROM t_inventario WHERE id_sucursal IS NOT NULL AND id_variante IS NOT NULL GROUP BY 1,2 HAVING count(*)>1) x;

-- inventory_nonnull_season
SELECT count(*) FROM t_inventario WHERE id_temporada IS NOT NULL;

-- inventory_cross_company
SELECT count(*) FROM t_inventario i JOIN t_sucursal s USING(id_sucursal) JOIN t_producto_talla_color v USING(id_variante) JOIN t_producto p USING(id_producto) WHERE s.id_empresa IS DISTINCT FROM p.id_empresa;

-- variant_duplicate_product_size_color_groups
SELECT count(*) FROM (SELECT id_producto,id_talla,id_color FROM t_producto_talla_color GROUP BY 1,2,3 HAVING count(*)>1) x;

-- variant_missing_identity
SELECT count(*) FROM t_producto_talla_color WHERE id_producto IS NULL OR id_talla IS NULL OR id_color IS NULL;

-- variant_cross_company_or_global_size_color
SELECT count(*) FROM t_producto_talla_color v JOIN t_producto p USING(id_producto) JOIN t_talla t USING(id_talla) JOIN t_color c USING(id_color) WHERE p.id_empresa IS DISTINCT FROM t.id_empresa OR p.id_empresa IS DISTINCT FROM c.id_empresa;

-- variant_cross_known_company_size_color
SELECT count(*) FROM t_producto_talla_color v JOIN t_producto p USING(id_producto) JOIN t_talla t USING(id_talla) JOIN t_color c USING(id_color) WHERE (p.id_empresa IS NOT NULL AND t.id_empresa IS NOT NULL AND p.id_empresa<>t.id_empresa) OR (p.id_empresa IS NOT NULL AND c.id_empresa IS NOT NULL AND p.id_empresa<>c.id_empresa);

-- variant_duplicate_sku_per_company_groups
SELECT count(*) FROM (SELECT p.id_empresa,lower(trim(v.sku)) FROM t_producto_talla_color v JOIN t_producto p USING(id_producto) WHERE nullif(trim(v.sku),'') IS NOT NULL GROUP BY 1,2 HAVING count(*)>1) x;

-- cash_session_incoherent
SELECT count(*) FROM t_caja_sesion cs JOIN t_caja c USING(id_caja) JOIN t_sucursal s ON s.id_sucursal=c.id_sucursal WHERE cs.id_sucursal IS DISTINCT FROM c.id_sucursal OR cs.id_empresa IS DISTINCT FROM c.id_empresa OR c.id_empresa IS DISTINCT FROM s.id_empresa;

-- cash_duplicate_open_session_groups
SELECT count(*) FROM (SELECT id_caja FROM t_caja_sesion WHERE estado='ABIERTA' GROUP BY 1 HAVING count(*)>1) x;

-- cash_duplicate_code_per_company_groups
SELECT count(*) FROM (SELECT id_empresa,codigo_caja FROM t_caja GROUP BY 1,2 HAVING count(*)>1) x;

-- user_branch_cross_known_company
SELECT count(*) FROM t_usuario_sucursal us JOIN t_usuario u USING(id_usuario) JOIN t_sucursal s USING(id_sucursal) WHERE u.id_empresa IS NOT NULL AND u.id_empresa IS DISTINCT FROM s.id_empresa;

-- client_duplicate_user_groups
SELECT count(*) FROM (SELECT id_usuario FROM t_cliente WHERE id_usuario IS NOT NULL GROUP BY 1 HAVING count(*)>1) x;

-- client_guest_or_missing_user
SELECT count(*) FROM t_cliente WHERE id_usuario IS NULL;

-- users_with_multiple_roles
SELECT count(*) FROM (SELECT id_usuario FROM t_usuario_rol GROUP BY 1 HAVING count(*)>1) x;

-- user_primary_role_missing_from_bridge
SELECT count(*) FROM t_usuario u WHERE u.id_rol IS NOT NULL AND NOT EXISTS (SELECT 1 FROM t_usuario_rol ur WHERE ur.id_usuario=u.id_usuario AND ur.id_rol=u.id_rol);

-- sales_missing_company
SELECT count(*) FROM t_venta WHERE id_empresa IS NULL;

-- sales_company_branch_mismatch
SELECT count(*) FROM t_venta v JOIN t_sucursal s USING(id_sucursal) WHERE v.id_empresa IS DISTINCT FROM s.id_empresa;

-- sale_details_missing_identity_or_nonpositive_quantity
SELECT count(*) FROM t_detalle_venta WHERE id_venta IS NULL OR id_variante IS NULL OR cantidad IS NULL OR cantidad<=0;

-- sale_detail_product_company_mismatch
SELECT count(*) FROM t_detalle_venta d JOIN t_venta ve USING(id_venta) JOIN t_producto_talla_color v USING(id_variante) JOIN t_producto p USING(id_producto) WHERE ve.id_empresa IS DISTINCT FROM p.id_empresa;

-- payments_missing_sale_or_method_or_amount
SELECT count(*) FROM t_pago WHERE id_venta IS NULL OR id_metodo_pago IS NULL OR monto IS NULL;

-- payments_nonpositive_amount
SELECT count(*) FROM t_pago WHERE monto<=0;

-- sales_with_multiple_approved_payments
SELECT count(*) FROM (SELECT id_venta FROM t_pago WHERE estado='APROBADO' AND id_venta IS NOT NULL GROUP BY 1 HAVING count(*)>1) x;

-- denomination_payment_sale_mismatch
SELECT count(*) FROM t_pago_denominacion d JOIN t_pago p USING(id_pago) WHERE d.id_venta IS DISTINCT FROM p.id_venta;

-- products_category_cross_known_company
SELECT count(*) FROM t_producto p JOIN t_categoria c USING(id_categoria) WHERE p.id_empresa IS NOT NULL AND c.id_empresa IS NOT NULL AND p.id_empresa<>c.id_empresa;

-- products_state_disagreement
SELECT count(*) FROM t_producto WHERE estado IS DISTINCT FROM activo;

-- sizes_state_disagreement
SELECT count(*) FROM t_talla WHERE estado IS DISTINCT FROM activo;

-- colors_state_disagreement
SELECT count(*) FROM t_color WHERE estado IS DISTINCT FROM activo;

-- categories_state_disagreement
SELECT count(*) FROM t_categoria WHERE estado IS DISTINCT FROM activo;

-- subscriptions_overlaps
SELECT count(*) FROM t_suscripcion a JOIN t_suscripcion b ON a.id_empresa=b.id_empresa AND a.id_suscripcion<b.id_suscripcion WHERE a.estado='ACTIVA' AND b.estado='ACTIVA' AND a.inicio<b.fin AND b.inicio<a.fin;

-- inventory_mismatch_available_zero
SELECT count(*) FROM t_inventario WHERE stock_disponible IS DISTINCT FROM stock_actual-stock_reservado AND stock_disponible=0;

-- inventory_mismatch_available_exceeds_free
SELECT count(*) FROM t_inventario WHERE stock_disponible>stock_actual-stock_reservado;

-- inventory_mismatch_available_below_free
SELECT count(*) FROM t_inventario WHERE stock_disponible<stock_actual-stock_reservado;

-- variant_wrong_size_company
SELECT count(*) FROM t_producto_talla_color v JOIN t_producto p USING(id_producto) JOIN t_talla t USING(id_talla) WHERE p.id_empresa<>t.id_empresa;

-- variant_wrong_color_company
SELECT count(*) FROM t_producto_talla_color v JOIN t_producto p USING(id_producto) JOIN t_color c USING(id_color) WHERE p.id_empresa<>c.id_empresa;

-- client_duplicate_profile_excess
SELECT COALESCE(sum(n-1),0)::int FROM (SELECT count(*) n FROM t_cliente WHERE id_usuario IS NOT NULL GROUP BY id_usuario HAVING count(*)>1) x;

-- products_missing_company
SELECT count(*) FROM t_producto WHERE id_empresa IS NULL;

-- branches_missing_company
SELECT count(*) FROM t_sucursal WHERE id_empresa IS NULL;

-- products_multiple_main_images_groups
SELECT count(*) FROM (SELECT id_producto FROM t_producto_imagen WHERE es_principal IS TRUE GROUP BY 1 HAVING count(*)>1) x;

-- paid_sales_with_header_discount
SELECT count(*) FROM t_venta WHERE descuento>0 AND estado IN ('PAGADO','COMPLETADA','ENTREGADO');

-- legacy_notification_dependent_views
SELECT count(DISTINCT v.oid) FROM pg_depend d JOIN pg_rewrite r ON r.oid=d.objid JOIN pg_class v ON v.oid=r.ev_class WHERE d.refobjid='notificacion'::regclass AND v.relkind IN ('v','m');

-- active_subscriptions_count
SELECT count(*) FROM t_suscripcion WHERE estado='ACTIVA';

-- missing_canonical_primary_role
SELECT count(*) FROM t_usuario WHERE id_rol IS NULL;

-- reservations_with_declared_payment
SELECT count(*) FROM t_reserva WHERE con_pago IS TRUE OR COALESCE(monto_pagado,0)>0;

-- reservations_with_declared_payment_without_sale
SELECT count(*) FROM t_reserva WHERE (con_pago IS TRUE OR COALESCE(monto_pagado,0)>0) AND id_venta IS NULL;

-- paid_orders_without_sale
SELECT count(*) FROM t_pedido WHERE estado_pago='PAGADO' AND id_venta IS NULL;

-- suppliers_used_in_multiple_companies_by_lots
SELECT count(*) FROM (SELECT id_proveedor FROM t_lote WHERE id_proveedor IS NOT NULL GROUP BY 1 HAVING count(DISTINCT id_empresa)>1) x;