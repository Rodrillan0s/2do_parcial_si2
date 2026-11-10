"""
Script de Población de Datos Bolivianos y Calibración de Precios de Variantes
AuroraStore Multi-Tenant SaaS:
1. Actualización de Tenants y Sucursales con NITs, ciudades y direcciones reales de Bolivia.
2. Población y estandarización de Tallas y Colores para todos los Tenants.
3. Creación y asignación de Categorías textiles y de confección.
4. Población de catálogo textil y prendas para Tenant 3 (URBAN STORE BOLIVIA).
5. Calibración y actualización de precios de TODAS las variantes (t_producto_talla_color) a precios en Bolivianos (Bs).
6. Asociación de imágenes HTTPS de alta calidad para productos y galerías (t_producto, t_producto_imagen).
7. Creación de usuarios bolivianos (Administradores, Cajeros y Clientes con CI de Bolivia) con contraseña 'Bolivia2026!'.
"""

import json
import logging
import random
from decimal import Decimal
from uuid import uuid4
from werkzeug.security import generate_password_hash
from app.core.postgres import PostgreSQL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("poblador_bolivia")

SCHEMA = "comercio"
PASSWORD_DEFAULT = "Bolivia2026!"
PASSWORD_HASH = generate_password_hash(PASSWORD_DEFAULT)

# Galería de imágenes de alta resolución curadas de moda (Unsplash Fashion CDN)
FASHION_IMAGES = {
    "vestidos": [
        "https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1585487000160-6ebcfceb0d03?auto=format&fit=crop&w=900&q=80"
    ],
    "blazers": [
        "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1487222477894-8943e31ef7b2?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=900&q=80"
    ],
    "abrigos": [
        "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1544022613-e87ca75a784a?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1516762689617-e1cffcef479d?auto=format&fit=crop&w=900&q=80"
    ],
    "blusas_camisas": [
        "https://images.unsplash.com/photo-1604014237800-1c9102c219da?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1598554747436-c9293d6a588f?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1589310243389-96a5483213a8?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=900&q=80"
    ],
    "pantalones": [
        "https://images.unsplash.com/photo-1509631179647-0177331693ae?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=900&q=80"
    ],
    "urbano": [
        "https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1509551388413-e18d0ac5d495?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1485230895905-ec40ba36b9bc?auto=format&fit=crop&w=900&q=80"
    ],
    "accesorios": [
        "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?auto=format&fit=crop&w=900&q=80"
    ]
}


def obtener_imagen_por_nombre(nombre_producto: str) -> str:
    nombre_low = nombre_producto.lower()
    if any(k in nombre_low for k in ["vestido", "gala", "sirena", "coctel", "fiesta"]):
        return random.choice(FASHION_IMAGES["vestidos"])
    elif any(k in nombre_low for k in ["blazer", "sastre", "traje", "chaqueta", "chaleco"]):
        return random.choice(FASHION_IMAGES["blazers"])
    elif any(k in nombre_low for k in ["abrigo", "alpaca", "lana", "cachemira", "capa", "buzo"]):
        return random.choice(FASHION_IMAGES["abrigos"])
    elif any(k in nombre_low for k in ["camisa", "blusa", "seda", "top", "polo"]):
        return random.choice(FASHION_IMAGES["blusas_camisas"])
    elif any(k in nombre_low for k in ["pantalón", "pantalon", "palazzo", "falda", "jean", "cargo", "chino"]):
        return random.choice(FASHION_IMAGES["pantalones"])
    elif any(k in nombre_low for k in ["cartera", "cinturón", "cinturon", "tote", "joya", "perlas"]):
        return random.choice(FASHION_IMAGES["accesorios"])
    else:
        return random.choice(FASHION_IMAGES["urbano"])


def calcular_precio_boliviano_coherente(nombre_producto: str, precio_actual: Decimal = None) -> Decimal:
    """
    Retorna un precio comercial boliviano calibrado (en Bs).
    Si el precio actual ya es realista (entre Bs. 70 y Bs. 950), lo preserva o calibra a múltiplo de 5.
    Si es 0, NULL o excesivo (>1500), calcula un valor equilibrado según la categoría.
    """
    if precio_actual and 70.0 <= float(precio_actual) <= 950.0:
        val = round(float(precio_actual) / 5.0) * 5.0
        return Decimal(f"{val:.2f}")

    nombre_low = nombre_producto.lower()
    if any(k in nombre_low for k in ["gala", "alpaca", "sastre", "abrigo", "capa"]):
        val = random.choice([480.0, 520.0, 580.0, 650.0, 720.0, 790.0, 850.0])
    elif any(k in nombre_low for k in ["blazer", "traje", "vestido"]):
        val = random.choice([320.0, 360.0, 390.0, 420.0, 450.0, 480.0])
    elif any(k in nombre_low for k in ["pantalón", "pantalon", "palazzo", "cargo", "falda"]):
        val = random.choice([210.0, 230.0, 250.0, 270.0, 290.0])
    elif any(k in nombre_low for k in ["camisa", "blusa", "seda", "hoodie", "buzo"]):
        val = random.choice([160.0, 180.0, 210.0, 240.0, 260.0])
    elif any(k in nombre_low for k in ["cartera", "cinturón", "cinturon", "tote"]):
        val = random.choice([120.0, 150.0, 180.0, 220.0])
    else:
        val = random.choice([95.0, 120.0, 150.0, 180.0])
    return Decimal(f"{val:.2f}")


def ejecutar_poblacion():
    db = PostgreSQL()
    db.create_connection()
    try:
        logger.info("=== 1. Actualizando Datos de Tenants y Sucursales Bolivianas ===")
        # Empresa 1
        db.execute_query(f"""
            UPDATE {SCHEMA}.empresa 
            SET nombre_empresa = 'SHOPPING BOLIVIA',
                razon_social = 'Shopping Bolivia S.R.L.',
                nit = '4045127018',
                direccion_fiscal = 'Av. Cristo Redentor #2340, entre 2do y 3er Anillo',
                ciudad = 'Santa Cruz de la Sierra',
                telefono = '+591 3 3428900',
                correo = 'contacto@shoppingbolivia.com.bo',
                estado = 'ACTIVO'
            WHERE id_empresa = 1;
        """, commit=True)

        # Empresa 2
        db.execute_query(f"""
            UPDATE {SCHEMA}.empresa 
            SET nombre_empresa = 'FASHIONWORLD BOLIVIA',
                razon_social = 'FashionWorld Bolivia S.A.',
                nit = '8594021014',
                direccion_fiscal = 'Av. San Martín #800, Barrio Equipetrol',
                ciudad = 'Santa Cruz de la Sierra',
                telefono = '+591 3 3881240',
                correo = 'ventas@fashionworld.bo',
                estado = 'ACTIVO'
            WHERE id_empresa = 2;
        """, commit=True)

        # Empresa 3
        db.execute_query(f"""
            UPDATE {SCHEMA}.empresa 
            SET nombre_empresa = 'URBAN STORE BOLIVIA',
                razon_social = 'Urban Store Bolivia S.R.L.',
                nit = '7042654018',
                direccion_fiscal = 'Av. Ballivián #1420, El Prado',
                ciudad = 'La Paz',
                telefono = '+591 2 2445890',
                correo = 'contacto@urbanstore.bo',
                estado = 'ACTIVO'
            WHERE id_empresa = 3;
        """, commit=True)

        # Sucursal 9 (Empresa 3)
        db.execute_query(f"""
            UPDATE {SCHEMA}.t_sucursal
            SET nombre = 'Urban Store Central El Prado',
                codigo_sucursal = 'SUC-URB-01',
                direccion = 'Av. 16 de Julio #1440, El Prado',
                id_ciudad = 6,
                telefono = '+591 2 2445890',
                correo = 'elprado@urbanstore.bo',
                horario_apertura = '09:00:00',
                horario_cierre = '21:00:00',
                estado = TRUE,
                activo = TRUE
            WHERE id_sucursal = 9;
        """, commit=True)

        # Crear Sucursal 10 para Empresa 3 en Cochabamba si no existe
        row_suc10 = db.execute_query(f"SELECT id_sucursal FROM {SCHEMA}.t_sucursal WHERE id_empresa = 3 AND codigo_sucursal = 'SUC-URB-02' LIMIT 1;", fetchone=True)
        id_sucursal_e3_cbba = None
        if not row_suc10:
            ins_suc = db.execute_query(f"""
                INSERT INTO {SCHEMA}.t_sucursal (
                    id_ciudad, nombre, codigo_sucursal, direccion, telefono, correo, 
                    horario_apertura, horario_cierre, estado, id_empresa, activo
                ) VALUES (
                    10, 'Urban Store Cala Cala', 'SUC-URB-02', 'Av. Libertador Bolívar #1250, Cala Cala',
                    '+591 4 4458920', 'calacala@urbanstore.bo', '09:00:00', '21:00:00', TRUE, 3, TRUE
                ) RETURNING id_sucursal;
            """, fetchone=True, commit=True)
            id_sucursal_e3_cbba = ins_suc[0] if ins_suc else 10
            logger.info(f"Sucursal Cochabamba creada para Empresa 3 (ID: {id_sucursal_e3_cbba})")
        else:
            id_sucursal_e3_cbba = row_suc10[0]

        logger.info("=== 2. Estandarizando Tallas y Colores para todos los Tenants ===")
        tallas_estandar = [
            ("XS", "Talla Extra Small / 34"),
            ("S", "Talla Small / 36"),
            ("M", "Talla Medium / 38"),
            ("L", "Talla Large / 40"),
            ("XL", "Talla Extra Large / 42"),
            ("XXL", "Talla Doble Extra Large / 44"),
            ("38", "Talla Numérica 38"),
            ("40", "Talla Numérica 40"),
            ("ÚNICA", "Talla Estándar / Ajustable")
        ]

        colores_estandar = [
            ("Negro Azabache", "#111111"),
            ("Blanco Nieve", "#FFFFFF"),
            ("Azul Marino", "#0B1D3A"),
            ("Rojo Borgoña", "#6B1124"),
            ("Verde Esmeralda", "#1B4D3E"),
            ("Beige Arena", "#D7C4A5"),
            ("Gris Oxford", "#464E56"),
            ("Terracota Andino", "#C15C3D"),
            ("Rosa Pastel", "#E8C5C8"),
            ("Camel Dorado", "#C19A6B")
        ]

        for id_emp in [1, 2, 3]:
            for nom, desc in tallas_estandar:
                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_talla (nombre, descripcion, estado, id_empresa, activo)
                    SELECT %s, %s, TRUE, %s, TRUE
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {SCHEMA}.t_talla WHERE id_empresa = %s AND UPPER(nombre) = UPPER(%s)
                    );
                """, (nom, desc, id_emp, id_emp, nom), commit=True)

            for nom, hex_col in colores_estandar:
                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_color (nombre, codigo_hex, estado, id_empresa, activo)
                    SELECT %s, %s, TRUE, %s, TRUE
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {SCHEMA}.t_color WHERE id_empresa = %s AND UPPER(nombre) = UPPER(%s)
                    );
                """, (nom, hex_col, id_emp, id_emp, nom), commit=True)

        logger.info("=== 3. Creando Categorías Textiles para cada Empresa ===")
        categorias_catalogo = [
            ("Vestidos & Gala", "Alta costura, vestidos de fiesta, noche y cóctel"),
            ("Sastrería & Blazers", "Blazers entallados, trajes ejecutivos dos piezas y chalecos"),
            ("Camisería & Blusas", "Camisas finas de lino, blusas de seda y tops formales"),
            ("Pantalones & Palazzos", "Pantalones pinzados, palazzos elegantes y corte recto"),
            ("Abrigos & Alpaca", "Prendas de abrigo en lana de alpaca boliviana y cachemira"),
            ("Moda Urbana & Casual", "Streetwear contemporáneo, prendas oversize y básicos de calidad"),
            ("Accesorios & Marroquinería", "Carteras de cuero genuino, cinturones y accesorios de autor")
        ]

        for id_emp in [1, 2, 3]:
            for nom, desc in categorias_catalogo:
                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_categoria (nombre, descripcion, estado, id_empresa, activo)
                    SELECT %s, %s, TRUE, %s, TRUE
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {SCHEMA}.t_categoria WHERE id_empresa = %s AND UPPER(nombre) = UPPER(%s)
                    );
                """, (nom, desc, id_emp, id_emp, nom), commit=True)

        logger.info("=== 4. Calibrando Precios de TODAS las Variantes Existentes ===")
        # Traer variantes que requieran calibración (nulas, cero o descalibradas)
        q_vars = f"""
            SELECT v.id_variante, v.id_producto, v.precio, p.nombre, p.precio AS precio_prod
            FROM {SCHEMA}.t_producto_talla_color v
            JOIN {SCHEMA}.t_producto p ON p.id_producto = v.id_producto
            WHERE v.precio IS NULL OR v.precio <= 0 OR v.precio > 1200.0
            ORDER BY v.id_variante ASC;
        """
        variantes = db.execute_query(q_vars, fetchall=True) or []
        count_actualizadas = 0

        for r in variantes:
            id_var = r[0]
            id_prod = r[1]
            precio_var = r[2]
            nombre_prod = r[3] or "Prenda de Moda"
            precio_prod = r[4]

            # Si precio es nulo, cero o exorbitante (>1500), calibrar
            needs_update = False
            if precio_var is None or float(precio_var) <= 0:
                needs_update = True
                nuevo_precio = calcular_precio_boliviano_coherente(nombre_prod, precio_prod)
            elif float(precio_var) > 1200.0:
                needs_update = True
                nuevo_precio = calcular_precio_boliviano_coherente(nombre_prod, None)
            else:
                # Redondear a múltiplo de 5 para prolijidad comercial
                val_calibrado = round(float(precio_var) / 5.0) * 5.0
                if abs(float(precio_var) - val_calibrado) > 0.01:
                    needs_update = True
                    nuevo_precio = Decimal(f"{val_calibrado:.2f}")

            if needs_update:
                db.execute_query(
                    f"UPDATE {SCHEMA}.t_producto_talla_color SET precio = %s WHERE id_variante = %s;",
                    (nuevo_precio, id_var),
                    commit=True
                )
                count_actualizadas += 1

        logger.info(f"Variantes calibradas a precios comerciales en Bs: {count_actualizadas} de {len(variantes)}")

        logger.info("=== 5. Calibrando Precios e Imágenes de t_producto y t_producto_imagen ===")
        q_prods = f"SELECT id_producto, nombre, precio, imagen_url FROM {SCHEMA}.t_producto ORDER BY id_producto ASC;"
        productos = db.execute_query(q_prods, fetchall=True) or []

        for p in productos:
            id_prod = p[0]
            nom = p[1] or "Prenda Exclusiva"
            prec = p[2]
            img = p[3]

            nuevo_prec = prec
            if prec is None or float(prec) <= 0 or float(prec) > 1200.0:
                nuevo_prec = calcular_precio_boliviano_coherente(nom, prec)

            nueva_img = img
            if not img or len(img.strip()) == 0 or "placeholder" in img.lower():
                nueva_img = obtener_imagen_por_nombre(nom)

            db.execute_query(f"""
                UPDATE {SCHEMA}.t_producto 
                SET precio = %s, imagen_url = %s, estado = TRUE, activo = TRUE 
                WHERE id_producto = %s;
            """, (nuevo_prec, nueva_img, id_prod), commit=True)

            # Asegurar al menos una imagen en t_producto_imagen
            has_img_galeria = db.execute_query(f"SELECT 1 FROM {SCHEMA}.t_producto_imagen WHERE id_producto = %s LIMIT 1;", (id_prod,), fetchone=True)
            if not has_img_galeria:
                pub_id = f"aurora_store/productos/prod_{id_prod}_{uuid4().hex[:6]}"
                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_producto_imagen (id_producto, imagen_url, public_id, es_principal, orden)
                    VALUES (%s, %s, %s, TRUE, 1);
                """, (id_prod, nueva_img, pub_id), commit=True)

        logger.info("=== 6. Poblando Catálogo Textil para Empresa 3 (URBAN STORE BOLIVIA) ===")
        # Traer categorías de Empresa 3
        cat_e3 = db.execute_query(f"SELECT id_categoria, nombre FROM {SCHEMA}.t_categoria WHERE id_empresa = 3;", fetchall=True)
        cat_map_e3 = {r[1]: r[0] for r in cat_e3}

        # Traer tallas y colores de Empresa 3
        tallas_e3 = db.execute_query(f"SELECT id_talla, nombre FROM {SCHEMA}.t_talla WHERE id_empresa = 3;", fetchall=True)
        colores_e3 = db.execute_query(f"SELECT id_color, nombre FROM {SCHEMA}.t_color WHERE id_empresa = 3;", fetchall=True)

        talla_s = next((r[0] for r in tallas_e3 if r[1] == "S"), tallas_e3[0][0])
        talla_m = next((r[0] for r in tallas_e3 if r[1] == "M"), tallas_e3[0][0])
        talla_l = next((r[0] for r in tallas_e3 if r[1] == "L"), tallas_e3[0][0])
        talla_xl = next((r[0] for r in tallas_e3 if r[1] == "XL"), tallas_e3[0][0])

        col_negro = next((r[0] for r in colores_e3 if "Negro" in r[1]), colores_e3[0][0])
        col_blanco = next((r[0] for r in colores_e3 if "Blanco" in r[1]), colores_e3[0][0])
        col_azul = next((r[0] for r in colores_e3 if "Azul" in r[1]), colores_e3[0][0])
        col_terra = next((r[0] for r in colores_e3 if "Terracota" in r[1]), colores_e3[0][0])
        col_camel = next((r[0] for r in colores_e3 if "Camel" in r[1]), colores_e3[0][0])

        cat_urbana_id = cat_map_e3.get("Moda Urbana & Casual") or cat_e3[0][0]
        cat_sastre_id = cat_map_e3.get("Sastrería & Blazers") or cat_urbana_id
        cat_camisas_id = cat_map_e3.get("Camisería & Blusas") or cat_urbana_id
        cat_abrigos_id = cat_map_e3.get("Abrigos & Alpaca") or cat_urbana_id
        cat_pantalones_id = cat_map_e3.get("Pantalones & Palazzos") or cat_urbana_id
        cat_vestidos_id = cat_map_e3.get("Vestidos & Gala") or cat_urbana_id
        cat_accesorios_id = cat_map_e3.get("Accesorios & Marroquinería") or cat_urbana_id

        productos_urban = [
            ("Hoodie Oversize Alpaca Blend 'Illimani'", "Buzo con capucha tejido en mezcla de alpaca y algodón boliviano", cat_abrigos_id, Decimal("320.00"), "UNISEX", "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=900&q=80"),
            ("Chaqueta Bomber Denim Vintage Santa Cruz", "Chaqueta denim estilo aviador lavado a la piedra", cat_urbana_id, Decimal("380.00"), "UNISEX", "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?auto=format&fit=crop&w=900&q=80"),
            ("Pantalón Cargo Urbano Ripstop Khaki", "Pantalón técnico con bolsillos laterales y calce relajado", cat_pantalones_id, Decimal("260.00"), "HOMBRE", "https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?auto=format&fit=crop&w=900&q=80"),
            ("Camisa Oversize Lino Andino Natural", "Camisa fresca con botones de madera y caída holgada", cat_camisas_id, Decimal("240.00"), "UNISEX", "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?auto=format&fit=crop&w=900&q=80"),
            ("Vestido Midi Casual Algodón Pima", "Vestido de día con corte evasé y textura liviana", cat_vestidos_id, Decimal("290.00"), "MUJER", "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?auto=format&fit=crop&w=900&q=80"),
            ("Blazer Casual Desestructurado Marengo", "Saco formal liviano sin forro interior ideal para media estación", cat_sastre_id, Decimal("420.00"), "UNISEX", "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=900&q=80"),
            ("Tote Bag Cuero Genuino Chiquitano", "Bolso amplio elaborado artesanalmente en cuero curtido vegetal", cat_accesorios_id, Decimal("190.00"), "UNISEX", "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=900&q=80"),
            ("Polera Gráfica Edición Chuquisaca", "Camiseta estampada serigrafiada en algodón peinado 24/1", cat_urbana_id, Decimal("140.00"), "UNISEX", "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=900&q=80"),
            ("Jogger Minimalista Algodón Orgánico", "Pantalón de descanso con puños ajustables y cordón interior", cat_pantalones_id, Decimal("210.00"), "UNISEX", "https://images.unsplash.com/photo-1552902865-b72c031ac5ea?auto=format&fit=crop&w=900&q=80"),
            ("Saco Corto Cruzado Lana Merino", "Saco femenino entallado con solapa ancha y botones carey", cat_sastre_id, Decimal("520.00"), "MUJER", "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?auto=format&fit=crop&w=900&q=80"),
            ("Falda Plisada Asimétrica Esmeralda", "Falda midi con pretina alta y movimiento fluido", cat_pantalones_id, Decimal("230.00"), "MUJER", "https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?auto=format&fit=crop&w=900&q=80"),
            ("Sobrecamisa de Corderoy Mostaza", "Chaqueta liviana de pana acanalada estilo leñador", cat_urbana_id, Decimal("270.00"), "HOMBRE", "https://images.unsplash.com/photo-1617137984095-74e4e5e3613f?auto=format&fit=crop&w=900&q=80"),
            ("Pantalón Chino Slim Fit Terracota", "Pantalón casual elegante confeccionado en sarga de algodón", cat_pantalones_id, Decimal("250.00"), "HOMBRE", "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?auto=format&fit=crop&w=900&q=80"),
            ("Buzo Cuello Tortuga Tejido a Mano", "Suéter abrigado tejido por artesanas del Altiplano", cat_abrigos_id, Decimal("340.00"), "UNISEX", "https://images.unsplash.com/photo-1576871337632-b9aef4c17ab9?auto=format&fit=crop&w=900&q=80"),
            ("Cinturón Reversible Cuero de Exportación", "Cinturón de vestir con hebilla giratoria níquel mate", cat_accesorios_id, Decimal("120.00"), "UNISEX", "https://images.unsplash.com/photo-1624222247344-550fb60583dc?auto=format&fit=crop&w=900&q=80")
        ]

        prods_creados_e3 = 0
        for idx, (p_nom, p_desc, p_cat, p_precio, p_gen, p_img) in enumerate(productos_urban, start=1):
            cod_prod = f"URB-PRD-{idx:03d}"
            # Comprobar si ya existe
            row_p = db.execute_query(f"SELECT id_producto FROM {SCHEMA}.t_producto WHERE codigo_producto = %s LIMIT 1;", (cod_prod,), fetchone=True)
            if not row_p:
                ins_prod = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_producto (
                        id_categoria, codigo_producto, nombre, descripcion, marca, genero, 
                        precio, imagen_url, estado, id_empresa, temporada, coleccion, activo
                    ) VALUES (
                        %s, %s, %s, %s, 'Urban Store Bolivia', %s,
                        %s, %s, TRUE, 3, 'Otoño - Invierno 2026', 'Colección Altura', TRUE
                    ) RETURNING id_producto;
                """, (p_cat, cod_prod, p_nom, p_desc, p_gen, p_precio, p_img), fetchone=True, commit=True)
                id_nuevo_prod = ins_prod[0]
                prods_creados_e3 += 1

                # Galería
                pub_id_new = f"aurora_store/productos/prod_{id_nuevo_prod}_{uuid4().hex[:6]}"
                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_producto_imagen (id_producto, imagen_url, public_id, es_principal, orden)
                    VALUES (%s, %s, %s, TRUE, 1);
                """, (id_nuevo_prod, p_img, pub_id_new), commit=True)

                # Crear variantes (S, M, L, XL) con combinaciones de color
                combo_variantes = [
                    (talla_s, col_negro, "S-NEG"),
                    (talla_m, col_negro, "M-NEG"),
                    (talla_l, col_negro, "L-NEG"),
                    (talla_m, col_azul, "M-AZU"),
                    (talla_l, col_terra, "L-TER"),
                    (talla_xl, col_camel, "XL-CAM")
                ]

                for id_t, id_c, cod_sufijo in combo_variantes:
                    sku = f"{cod_prod}-{cod_sufijo}"
                    ins_var = db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_producto_talla_color (
                            id_producto, id_talla, id_color, sku, precio, estado, activo
                        ) VALUES (%s, %s, %s, %s, %s, TRUE, TRUE)
                        RETURNING id_variante;
                    """, (id_nuevo_prod, id_t, id_c, sku, p_precio), fetchone=True, commit=True)

                    if ins_var:
                        id_var_nueva = ins_var[0]
                        # Asignar stock en Sucursal 9 (La Paz) y Sucursal 10 (Cochabamba)
                        for id_suc_stock in [9, id_sucursal_e3_cbba]:
                            stock_cant = random.randint(12, 35)
                            db.execute_query(f"""
                                INSERT INTO {SCHEMA}.t_inventario (
                                    id_sucursal, id_variante, stock_actual, stock_reservado, stock_disponible, stock_minimo, estado
                                ) VALUES (%s, %s, %s, 0, %s, 3, TRUE);
                            """, (id_suc_stock, id_var_nueva, stock_cant, stock_cant), commit=True)

        logger.info(f"Productos nuevos creados para Urban Store (Empresa 3): {prods_creados_e3}")

        logger.info("=== 7. Poblando Usuarios, Cajeros y Clientes Bolivianos ===")
        # Roles: 1=ADMINISTRADOR, 2=CLIENTE, 3=ADMINISTRADOR_TIENDA, 5=CAJERO
        usuarios_personal = [
            # Shopping Bolivia (Empresa 1)
            ("admin.shopping@aurora.bo", "Carlos", "Vargas Mamani", "+591 71025890", 1, 1, 3, "ADMINISTRADOR_TIENDA", "Av. Cristo Redentor #2340", "Santa Cruz"),
            ("cajero.shopping@aurora.bo", "Lucía", "Flores Quispe", "+591 72154890", 1, 1, 5, "CAJERO", "Barrio Equipetrol Calle 4", "Santa Cruz"),
            ("vendedor.shopping@aurora.bo", "Miguel Ángel", "Rojas Justiniano", "+591 73652140", 1, 1, 5, "CAJERO", "Av. Melchor Pinto #450", "Santa Cruz"),
            
            # FashionWorld Bolivia (Empresa 2)
            ("admin.fashion@aurora.bo", "Patricia", "Suárez Cuéllar", "+591 75841230", 2, 3, 3, "ADMINISTRADOR_TIENDA", "Av. San Martín #800", "Santa Cruz"),
            ("cajero.fashion@aurora.bo", "Mateo", "Fernández Terrazas", "+591 76952140", 2, 3, 5, "CAJERO", "Avenida Cristo Redentor #850", "Santa Cruz"),
            
            # Urban Store Bolivia (Empresa 3)
            ("admin.urban@aurora.bo", "Álvaro", "Choque Condori", "+591 78451200", 3, 9, 3, "ADMINISTRADOR_TIENDA", "Av. 16 de Julio #1440, El Prado", "La Paz"),
            ("cajero.urban@aurora.bo", "Camila", "Gutiérrez Peñaranda", "+591 79654120", 3, 9, 5, "CAJERO", "Calle 21 de Calacoto #500", "La Paz")
        ]

        for correo, nom, ape, telf, id_emp, id_suc, id_rol, cargo, dir_u, ciudad_u in usuarios_personal:
            usr = db.execute_query(f"SELECT id_usuario FROM {SCHEMA}.t_usuario WHERE correo = %s LIMIT 1;", (correo,), fetchone=True)
            if not usr:
                username = correo.split("@")[0]
                ins_u = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_usuario (
                        id_rol, username, password_hash, correo, nombre, apellido, telefono,
                        estado, id_empresa, direccion, ciudad
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s)
                    RETURNING id_usuario;
                """, (id_rol, username, PASSWORD_HASH, correo, nom, ape, telf, id_emp, dir_u, ciudad_u), fetchone=True, commit=True)
                id_usr = ins_u[0]
            else:
                id_usr = usr[0]
                db.execute_query(f"UPDATE {SCHEMA}.t_usuario SET id_empresa = %s, id_rol = %s WHERE id_usuario = %s;", (id_emp, id_rol, id_usr), commit=True)

            # Rol secundario en t_usuario_rol
            db.execute_query(f"""
                INSERT INTO {SCHEMA}.t_usuario_rol (id_usuario, id_rol)
                SELECT %s, %s
                WHERE NOT EXISTS (SELECT 1 FROM {SCHEMA}.t_usuario_rol WHERE id_usuario = %s AND id_rol = %s);
            """, (id_usr, id_rol, id_usr, id_rol), commit=True)

            # Sucursal en t_usuario_sucursal
            db.execute_query(f"""
                INSERT INTO {SCHEMA}.t_usuario_sucursal (id_usuario, id_sucursal)
                SELECT %s, %s
                WHERE NOT EXISTS (SELECT 1 FROM {SCHEMA}.t_usuario_sucursal WHERE id_usuario = %s AND id_sucursal = %s);
            """, (id_usr, id_suc, id_usr, id_suc), commit=True)

            # Ficha de empleado
            cod_emp = f"EMP-{id_emp}-{id_usr:04d}"
            db.execute_query(f"""
                INSERT INTO {SCHEMA}.t_empleado (id_usuario, id_sucursal, codigo_empleado, cargo, fecha_contratacion, estado)
                SELECT %s, %s, %s, %s, CURRENT_DATE, TRUE
                WHERE NOT EXISTS (SELECT 1 FROM {SCHEMA}.t_empleado WHERE id_usuario = %s);
            """, (id_usr, id_suc, cod_emp, cargo, id_usr), commit=True)

        # Clientes bolivianos
        clientes_bolivia = [
            ("valeria.montenegro@gmail.com", "Valeria", "Montenegro Siles", "+591 77012458", "5412369 SCZ", "Barrio Sirari Calle 3 #120", "Santa Cruz de la Sierra"),
            ("rodrigo.mamani@gmail.com", "Rodrigo", "Mamani Yujra", "+591 76541239", "6985412 LPZ", "Sopocachi Calle Guachalla #450", "La Paz"),
            ("gabriela.arce@hotmail.com", "Gabriela", "Arce Baldivieso", "+591 70745896", "4578123 CBBA", "Av. América Oeste #890", "Cochabamba"),
            ("daniel.justiniano@gmail.com", "Daniel", "Justiniano Pinto", "+591 78021456", "8741256 SCZ", "Condominio La Riviera Dpto 4B", "Santa Cruz de la Sierra"),
            ("natalia.torrico@gmail.com", "Natalia", "Torrico Quiroga", "+591 72985412", "6325418 TJA", "Barrio El Molino Calle 15 de Abril", "Tarija"),
            ("alejandro.vaca@gmail.com", "Alejandro", "Vaca Diez", "+591 74698521", "5896321 BENI", "Av. Pedro Ignacio Muiba #320", "Trinidad")
        ]

        for correo, nom, ape, telf, ci, direc, ciudad_c in clientes_bolivia:
            usr = db.execute_query(f"SELECT id_usuario FROM {SCHEMA}.t_usuario WHERE correo = %s LIMIT 1;", (correo,), fetchone=True)
            if not usr:
                username = correo.split("@")[0]
                ins_u = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_usuario (
                        id_rol, username, password_hash, correo, nombre, apellido, telefono,
                        estado, id_empresa, direccion, ciudad
                    ) VALUES (2, %s, %s, %s, %s, %s, %s, TRUE, 1, %s, %s)
                    RETURNING id_usuario;
                """, (username, PASSWORD_HASH, correo, nom, ape, telf, direc, ciudad_c), fetchone=True, commit=True)
                id_usr = ins_u[0]
            else:
                id_usr = usr[0]

            # Registro en t_cliente
            db.execute_query(f"""
                INSERT INTO {SCHEMA}.t_cliente (id_usuario, ci, direccion, ciudad)
                SELECT %s, %s, %s, %s
                WHERE NOT EXISTS (SELECT 1 FROM {SCHEMA}.t_cliente WHERE id_usuario = %s);
            """, (id_usr, ci, direc, ciudad_c, id_usr), commit=True)

        logger.info("Población boliviana y calibración de precios completada con éxito.")

    finally:
        db.close_connection()


if __name__ == "__main__":
    ejecutar_poblacion()
