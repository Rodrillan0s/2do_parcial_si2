"""
Script de Expansión de Catálogo, Normalización por Temporadas y Población Operativa
AuroraStore Multi-Tenant SaaS:
1. Normalización y corrección estricta de temporadas (PRIMAVERA, VERANO, OTOÑO, INVIERNO, PERMANENTE)
   en todos los productos existentes de los 3 Tenants.
2. Población de t_temporada y creación de promociones activas (t_promocion, t_promocion_producto)
   para que prendas de fuera de temporada (Verano, Otoño, Invierno) sean 100% visibles en el catálogo
   público con insignias y descuentos comerciales vigentes.
3. Expansión masiva de catálogo ("población grandecita"):
   - Tenant 3 (URBAN STORE BOLIVIA): +35 productos nuevos con 140+ variantes y stock en La Paz y Cochabamba.
   - Tenant 2 (FASHIONWORLD BOLIVIA): +25 productos nuevos con 100+ variantes y stock en Santa Cruz.
   - Tenant 1 (SHOPPING BOLIVIA): +20 productos nuevos con 80+ variantes y stock en sus 4 sucursales.
   Totalizando más de 225 productos y 2.700+ variantes en todo el sistema.
4. Generación masiva de operaciones transaccionales:
   - 120 nuevas ventas multicanal (POS y Ecommerce) con pagos en Efectivo, QR, Tarjeta y PayPal.
   - 36 nuevas reservas de probador en boutique.
   - 12 devoluciones (Cambio de Talla y Ley 453).
   - 60 valoraciones y opiniones verificadas de clientes.
5. Re-entrenamiento del motor Mini-ML vectorial de preferencias y recomendaciones.
"""

import json
import logging
import random
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import uuid4
from app.core.postgres import PostgreSQL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("expansion_temporadas")

SCHEMA = "comercio"

# Banco curado de imágenes de moda femenina, masculina y accesorios de alta resolución
IMAGENES_MODA = {
    "vestidos_gala": [
        "https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1585487000160-6ebcfceb0d03?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1539008835657-9e8e9680c956?auto=format&fit=crop&w=900&q=80"
    ],
    "sastreria": [
        "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1487222477894-8943e31ef7b2?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1552374196-1ab2a1c593e8?auto=format&fit=crop&w=900&q=80"
    ],
    "verano": [
        "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1509631179647-0177331693ae?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1469334031218-e382a71b716b?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1512436991641-6745cdb1723f?auto=format&fit=crop&w=900&q=80"
    ],
    "abrigos_invierno": [
        "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1544022613-e87ca75a784a?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1516762689617-e1cffcef479d?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1578587018452-892bacefd3f2?auto=format&fit=crop&w=900&q=80"
    ],
    "camisas_blusas": [
        "https://images.unsplash.com/photo-1604014237800-1c9102c219da?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1598554747436-c9293d6a588f?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1578932750294-f5075e85f44a?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1589310243389-96a5483213a8?auto=format&fit=crop&w=900&q=80"
    ],
    "pantalones": [
        "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1565084888279-aca607ecce0c?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1551854838-212c50b4c184?auto=format&fit=crop&w=900&q=80"
    ],
    "accesorios": [
        "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1608256246200-53e635b5b65f?auto=format&fit=crop&w=900&q=80",
        "https://images.unsplash.com/photo-1524498250077-390f9e378fc0?auto=format&fit=crop&w=900&q=80"
    ]
}

COMENTARIOS_EXPANSION = [
    (5, "Compré esta prenda en la sucursal de El Prado y la calidad de los acabados es soberbia. Muy recomendada."),
    (5, "Excelente diseño para la temporada. Llegó rápidamente a mi domicilio en Santa Cruz con empaque de lujo."),
    (5, "El tejido es sumamente fresco, perfecto para los días calurosos. El talleje coincide a la perfección."),
    (4, "Muy linda caída de la tela y color idéntico al catálogo web. Sin duda volveré a comprar."),
    (5, "Atención impecable en probadores y la prenda superó todas mis expectativas de calidad."),
    (4, "Prenda cómoda y elegante, el color es un tono ligeramente más intenso pero luce espectacular."),
    (5, "El abrigo de alpaca es ultra suave, abriga perfecto para las noches frías en La Paz."),
    (3, "El corte es bonito pero me quedó un poco ajustado en hombros; solicité cambio de talla en sucursal."),
    (5, "Gran experiencia de compra, factura electrónica emitida al instante y el pedido llegó en 24 horas.")
]


def ejecutar_expansion():
    db = PostgreSQL()
    db.create_connection()

    try:
        logger.info("=== 1. Normalizando y Corrigiendo Temporadas de Productos Existentes ===")
        # Traer todos los productos existentes
        prods_act = db.execute_query(f"""
            SELECT p.id_producto, p.nombre, p.id_categoria, p.temporada, p.id_empresa
            FROM {SCHEMA}.t_producto p
            ORDER BY p.id_producto;
        """, fetchall=True)

        seasons_pool = ["PRIMAVERA", "VERANO", "OTOÑO", "INVIERNO", "PERMANENTE"]

        count_updated_seasons = 0
        for p in prods_act:
            id_p = p[0]
            nom = (p[1] or "").lower()
            id_cat = p[2]
            temp_actual = (p[3] or "").strip().upper()
            id_emp = p[4]

            # Clasificación inteligente de temporada
            nueva_temp = None
            if temp_actual in ("PRIMAVERA", "VERANO", "OTOÑO", "INVIERNO", "PERMANENTE"):
                nueva_temp = temp_actual
            elif "invierno" in (p[3] or "").lower() or "otoño" in (p[3] or "").lower():
                nueva_temp = "INVIERNO" if "abrigo" in nom or "alpaca" in nom or "sweater" in nom else "OTOÑO"
            elif "permanente" in (p[3] or "").lower():
                nueva_temp = "PERMANENTE"
            else:
                # Deducir por nombre y categoría
                if any(k in nom for k in ["lino", "seda", "top", "blusa", "short", "vestido verano", "fresco"]):
                    nueva_temp = random.choice(["VERANO", "PRIMAVERA"])
                elif any(k in nom for k in ["abrigo", "alpaca", "lana", "parka", "saco pesado"]):
                    nueva_temp = "INVIERNO"
                elif any(k in nom for k in ["blazer", "traje", "chaleco", "palazzo", "trench"]):
                    nueva_temp = random.choice(["OTOÑO", "PRIMAVERA"])
                elif any(k in nom for k in ["denim", "jean", "cinturon", "zapato", "bolso", "cartera"]):
                    nueva_temp = "PERMANENTE"
                else:
                    nueva_temp = random.choice(["PRIMAVERA", "VERANO", "OTOÑO", "PERMANENTE"])

            if nueva_temp != p[3]:
                db.execute_query(f"""
                    UPDATE {SCHEMA}.t_producto 
                    SET temporada = %s, updated_at = NOW()
                    WHERE id_producto = %s;
                """, (nueva_temp, id_p), commit=True)
                count_updated_seasons += 1

        logger.info(f"Temporadas corregidas y normalizadas en {count_updated_seasons} productos existentes.")

        logger.info("=== 2. Poblando t_temporada y Promociones de Temporada (t_promocion) ===")
        # Poblar t_temporada si está vacía
        t_temps = db.execute_query(f"SELECT count(*) FROM {SCHEMA}.t_temporada;", fetchone=True)[0]
        if t_temps == 0:
            temps_data = [
                (1, "PRIMAVERA", "Temporada Oficial de Primavera Andina y Valles", date(2026, 9, 21), date(2026, 12, 20), True),
                (2, "VERANO", "Temporada de Verano, Playa y Festividades", date(2026, 12, 21), date(2027, 3, 20), True),
                (3, "OTOÑO", "Temporada de Otoño & Media Estación", date(2026, 3, 21), date(2026, 6, 20), True),
                (4, "INVIERNO", "Temporada de Invierno & Tejidos de Abrigo", date(2026, 6, 21), date(2026, 9, 20), True),
                (5, "PERMANENTE", "Colección Básicos Esenciales y Atemporales", date(2026, 1, 1), date(2030, 12, 31), True)
            ]
            for id_t, n, d, fi, ff, st in temps_data:
                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_temporada (id_temporada, nombre, descripcion, fecha_inicio, fecha_fin, estado)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id_temporada) DO NOTHING;
                """, (id_t, n, d, fi, ff, st), commit=True)
            logger.info("Tabla t_temporada poblada con 5 temporadas oficiales.")

        # Asegurar Promociones Activas que cubran la fecha actual (2026-11-10 hasta 2027-03-31)
        # Esto asegura que los productos VERANO, OTOÑO e INVIERNO se muestren en el catálogo público
        db.execute_query(f"""
            INSERT INTO {SCHEMA}.t_promocion (id_promocion, nombre, descripcion, fecha_inicio, fecha_fin, estado)
            VALUES (4, 'PREVENTA & LANZAMIENTO VERANO 2026/2027', 'Preventa exclusiva de temporada Verano con 15% OFF', '2026-10-01', '2027-03-31', TRUE)
            ON CONFLICT (id_promocion) DO UPDATE SET fecha_inicio='2026-10-01', fecha_fin='2027-03-31', estado=TRUE;
        """, commit=True)

        db.execute_query(f"""
            INSERT INTO {SCHEMA}.t_promocion (id_promocion, nombre, descripcion, fecha_inicio, fecha_fin, estado)
            VALUES (5, 'OUTLET DE TEMPORADA FRÍA (OTOÑO & INVIERNO)', 'Liquidación de prendas de abrigo y media estación con 20% OFF', '2026-10-01', '2027-03-31', TRUE)
            ON CONFLICT (id_promocion) DO UPDATE SET fecha_inicio='2026-10-01', fecha_fin='2027-03-31', estado=TRUE;
        """, commit=True)

        logger.info("Promociones de temporada creadas y activas (hasta marzo 2027).")

        logger.info("=== 3. Creando Nuevos Productos para Todos los Tenants (Población Grandecita) ===")
        # Traer sucursales activas
        sucursales = db.execute_query(f"SELECT id_sucursal, id_empresa, nombre FROM {SCHEMA}.t_sucursal WHERE estado = TRUE;", fetchall=True)

        # Definir nuevos productos por Tenant con diseño de alta costura y moda boliviana
        # Tenant 3 (Urban Store Bolivia): 35 nuevos productos
        # Tenant 2 (FashionWorld Bolivia): 25 nuevos productos
        # Tenant 1 (Shopping Bolivia): 20 nuevos productos

        nuevos_productos_config = [
            # -------------------------------------------------------------
            # TENANT 3: URBAN STORE BOLIVIA (La Paz y Cochabamba) - 35 productos
            # -------------------------------------------------------------
            (3, 49, "Vestido Gala Illimani en Terciopelo", "Vestido de gala en terciopelo azul noche con escote geométrico y mangas al codo, inspirado en las noches andinas.", 820.00, "vestidos_gala", "Mujer", "INVIERNO", "Colección Andina"),
            (3, 49, "Vestido Mururata en Crepe Seda", "Vestido largo con abertura lateral y detalle drapeado en la cintura, tela crepe de alta caída.", 760.00, "vestidos_gala", "Mujer", "PRIMAVERA", "Colección Andina"),
            (3, 49, "Vestido Cóctel Sopocachi", "Vestido a media pierna en tono esmeralda con corsetería suave y falda en línea A.", 540.00, "vestidos_gala", "Mujer", "VERANO", "Urbano Noche"),
            (3, 49, "Vestido Minimalista Cala Cala", "Vestido midi en satín color champagne, ideal para eventos de tarde y clima templado de valle.", 490.00, "vestidos_gala", "Mujer", "VERANO", "Valle Chic"),
            (3, 49, "Vestido Satinado Noche Paceña", "Prenda sofisticada con tirantes finos ajustables y espalda descubierta en tono rubí.", 650.00, "vestidos_gala", "Mujer", "PRIMAVERA", "Urbano Noche"),

            (3, 50, "Blazer Sastre Prado Andino", "Saco sastre entallado en lana fría boliviana con botones metálicos y forro de satén.", 680.00, "sastreria", "Unisex", "OTOÑO", "Sastrería Ejecutiva"),
            (3, 50, "Blazer Oversize Calle Sagárnaga", "Blazer holgado de corte contemporáneo en tono gris oxford, solapa clásica.", 590.00, "sastreria", "Mujer", "PRIMAVERA", "Urbano Vanguardia"),
            (3, 50, "Saco Estructurado Valle Alto", "Chaqueta estructurada con cinturón fajín a juego en paño de media estación.", 620.00, "sastreria", "Mujer", "INVIERNO", "Sastrería Ejecutiva"),
            (3, 50, "Blazer Casual Lino Sucre", "Blazer ligero en mezcla de lino y algodón color crudo con bolsillos de parche.", 480.00, "sastreria", "Hombre", "VERANO", "Lino Natural"),
            (3, 50, "Traje Sastre Ejecutivo Tunari", "Chaqueta formal confeccionada para clima de valle y oficina corporativa.", 710.00, "sastreria", "Hombre", "PERMANENTE", "Sastrería Ejecutiva"),

            (3, 51, "Camisa de Lino Blanco Huayna", "Camisa clásica en 100% lino puro transpirable, corte regular fit impecable.", 320.00, "camisas_blusas", "Hombre", "VERANO", "Esenciales"),
            (3, 51, "Blusa de Seda Estampada Kantuta", "Blusa fluida con estampado floral delicado y lazo al cuello en tonos cálidos.", 340.00, "camisas_blusas", "Mujer", "PRIMAVERA", "Flores de Primavera"),
            (3, 51, "Camisa Cuello Mao Copacabana", "Camisa veraniega con cuello mao en tejido liviano color azul cielo.", 290.00, "camisas_blusas", "Hombre", "VERANO", "Lino Natural"),
            (3, 51, "Blusa Manga Abullonada Tarija", "Blusa romántica con mangas bombachas y puño elástico en gasa suave.", 280.00, "camisas_blusas", "Mujer", "PRIMAVERA", "Flores de Primavera"),
            (3, 51, "Camisa Sastre Popelina San Miguel", "Camisa ejecutiva de popelina de algodón egipcio de planchado fácil.", 360.00, "camisas_blusas", "Unisex", "PERMANENTE", "Esenciales"),

            (3, 52, "Pantalón Palazzo Tiwanaku", "Pantalón de bota ancha en lino pesado con pinzas delanteras y pretina alta.", 410.00, "pantalones", "Mujer", "PRIMAVERA", "Pantalones Contemporáneos"),
            (3, 52, "Pantalón Chino Alameda", "Pantalón de gabardina suave en tono camel con bolsillos diagonales.", 350.00, "pantalones", "Hombre", "PERMANENTE", "Esenciales"),
            (3, 52, "Palazzo Plisado Achumani", "Pantalón fluido con plisado permanente y cintura elástica muy confortable.", 380.00, "pantalones", "Mujer", "VERANO", "Pantalones Contemporáneos"),
            (3, 52, "Pantalón Sastre Lana Fría Miraflores", "Pantalón formal con raya marcada al planchado y forro interno parcial.", 440.00, "pantalones", "Hombre", "OTOÑO", "Sastrería Ejecutiva"),
            (3, 52, "Culotte Urbano Cochabamba", "Pantalón cropped holgado de tiro medio en gabardina de algodón.", 320.00, "pantalones", "Mujer", "VERANO", "Urbano Vanguardia"),

            (3, 53, "Abrigo Largo Pura Alpaca Andina", "Abrigo de paño de baby alpaca 100% boliviana con solapa corrida y cinturón.", 980.00, "abrigos_invierno", "Mujer", "INVIERNO", "Lujo Andino"),
            (3, 53, "Chaqueta Corta de Alpaca & Cuero", "Cazadora forrada con detalles de tejido autóctono y cuello alto abrigador.", 780.00, "abrigos_invierno", "Hombre", "INVIERNO", "Lujo Andino"),
            (3, 53, "Cardigan Grueso Tejido a Mano", "Suéter largo abierto con bolsillos profundos tejido en punto arroz de alpaca.", 520.00, "abrigos_invierno", "Unisex", "OTOÑO", "Tejidos Ancestrales"),
            (3, 53, "Parka Urbana Impermeable Illimani", "Parka con capucha desmontable forrada en micropolar para lluvia y frío andino.", 640.00, "abrigos_invierno", "Unisex", "INVIERNO", "Urbano Nieve"),

            (3, 54, "Polera Básica Algodón Pima Paceña", "Polera de algodón pima peruano-boliviano de fibra larga, ultra suave.", 160.00, "verano", "Unisex", "PERMANENTE", "Esenciales"),
            (3, 54, "Hoodie Oversize El Prado", "Buzo con capucha en friza de algodón pesado y bolsillo canguro reforzado.", 310.00, "verano", "Unisex", "OTOÑO", "Urbano Vanguardia"),
            (3, 54, "Jeans Rectos Selvedge Denim", "Pantalón vaquero de mezclilla rígida de 13.5 oz con costuras contrastantes.", 390.00, "pantalones", "Unisex", "PERMANENTE", "Denim Auténtico"),
            (3, 54, "Short de Lino Playero Coroico", "Bermuda liviana de lino lavado con cordón ajustable en cintura.", 220.00, "verano", "Hombre", "VERANO", "Lino Natural"),
            (3, 54, "Falda Midi Denim Desflecada", "Falda de jean con abertura frontal y tiro alto en lavado medio.", 290.00, "pantalones", "Mujer", "PRIMAVERA", "Denim Auténtico"),

            (3, 55, "Bolso Tote de Cuero Vacuno Tarija", "Cartera espaciosa de cuero genuino graneado con herrajes dorados.", 580.00, "accesorios", "Mujer", "PERMANENTE", "Marroquinería Fina"),
            (3, 55, "Mochila Urbana de Cuero & Lona", "Mochila resistente para portátil con compartimentos acolchados.", 460.00, "accesorios", "Unisex", "PERMANENTE", "Marroquinería Fina"),
            (3, 55, "Cinturón de Cuero Reversible Clásico", "Cinturón vacuno formal café/negro con hebilla giratoria niquelada.", 180.00, "accesorios", "Hombre", "PERMANENTE", "Marroquinería Fina"),
            (3, 55, "Billetera Compacta Protección RFID", "Billetera tarjetero de piel con bloqueo de seguridad para tarjetas.", 140.00, "accesorios", "Unisex", "PERMANENTE", "Marroquinería Fina"),
            (3, 55, "Bufanda Suave de Alpaca Fina", "Pashmina tejida con flecos laterales en tono vicuña tradicional.", 240.00, "accesorios", "Unisex", "INVIERNO", "Tejidos Ancestrales"),

            # -------------------------------------------------------------
            # TENANT 2: FASHIONWORLD BOLIVIA (Santa Cruz) - 25 productos
            # -------------------------------------------------------------
            (2, 42, "Vestido Gala Equipetrol Platinum", "Vestido de alta noche con detalles de pedrería fina y forro de seda pura.", 890.00, "vestidos_gala", "Mujer", "PRIMAVERA", "Noche de Gala"),
            (2, 42, "Vestido Tropical Urubó Glam", "Vestido maxi con estampado botánico caribeño en chifón liviano.", 560.00, "vestidos_gala", "Mujer", "VERANO", "Resort Tropical"),
            (2, 42, "Vestido Coctelero Satín Champagne", "Silueta tubo ajustada con escote palabra de honor y mangas desmontables.", 620.00, "vestidos_gala", "Mujer", "VERANO", "Noche de Gala"),
            (2, 42, "Vestido Sirena Terciopelo Esmeralda", "Corte sirena que realza la figura con cola corta de pasarela.", 790.00, "vestidos_gala", "Mujer", "INVIERNO", "Alta Costura"),

            (2, 43, "Blazer Smoking Solapa Raso", "Chaqueta formal con solapa en contraste de satén para cenas y cócteles.", 720.00, "sastreria", "Hombre", "OTOÑO", "Black Tie"),
            (2, 43, "Blazer Lino Tropical Montero", "Blazer unlined desestructurado en lino color marfil para calor cruceño.", 510.00, "sastreria", "Hombre", "VERANO", "Lino Tropical"),
            (2, 43, "Blazer Entallado Blanco Nieve", "Saco sastre femenino con botones dorados estilo marinero náutico.", 580.00, "sastreria", "Mujer", "PRIMAVERA", "Cruceña Chic"),
            (2, 43, "Traje Dos Piezas Crepe Rosa", "Conjunto de blazer y pantalón en tono rosa empolvado sofisticado.", 840.00, "sastreria", "Mujer", "PRIMAVERA", "Cruceña Chic"),

            (2, 44, "Blusa Gasa Seda Mangas Globo", "Blusa romántica vaporosa con cuello mao y abotonadura oculta.", 310.00, "camisas_blusas", "Mujer", "PRIMAVERA", "Seda & Satín"),
            (2, 44, "Guayabera de Lino Fino Camiri", "Guayabera tradicional de 4 bolsillos con alforzas verticales impecables.", 380.00, "camisas_blusas", "Hombre", "VERANO", "Lino Tropical"),
            (2, 44, "Top Halter Satén Noche", "Top elegante con cuello halter y espalda descubierta en tono ónix.", 240.00, "camisas_blusas", "Mujer", "VERANO", "Noche de Gala"),
            (2, 44, "Camisa Cuadros Vichy Primavera", "Camisa casual de algodón popelín con microcuadros vichy celestes.", 270.00, "camisas_blusas", "Hombre", "PRIMAVERA", "Casual Cruceño"),

            (2, 45, "Palazzo Satín Cintura Alta", "Pantalón de noche fluido con caída de líquido en tono borgoña.", 420.00, "pantalones", "Mujer", "OTOÑO", "Cruceña Chic"),
            (2, 45, "Pantalón Lino Regular Fit Urubó", "Pantalón fresco en lino color arena con pretina elástica interior.", 360.00, "pantalones", "Hombre", "VERANO", "Lino Tropical"),
            (2, 45, "Pantalón Cigarette Crepe Stretch", "Pantalón al tobillo con corte sastre ajustado y tiro alto favorecedor.", 340.00, "pantalones", "Mujer", "PERMANENTE", "Esenciales"),
            (2, 45, "Bermuda Chino Gabardina Verano", "Bermuda semiformal en gabardina color caqui con costuras reforzadas.", 210.00, "pantalones", "Hombre", "VERANO", "Casual Cruceño"),

            (2, 46, "Trench Coat Liviano Primavera", "Gabardina clásica impermeable ligera para días de lluvia de verano.", 680.00, "abrigos_invierno", "Mujer", "OTOÑO", "Cruceña Chic"),
            (2, 46, "Chaqueta Cuero Ecológico Biker", "Cazadora corta con cremalleras metálicas y forro satinado.", 590.00, "abrigos_invierno", "Unisex", "INVIERNO", "Urbano Noche"),
            (2, 46, "Cardigan Fino de Hilo de Seda", "Suéter abierto ultra fino para ambientes con aire acondicionado.", 290.00, "abrigos_invierno", "Mujer", "PRIMAVERA", "Esenciales"),

            (2, 47, "Polera Premium Pima Monograma FW", "Camiseta básica de alta densidad con logo bordado en tono sobre tono.", 180.00, "verano", "Unisex", "PERMANENTE", "Esenciales"),
            (2, 47, "Vestido Playero Crochet Artesanal", "Vestido calado tejido en hilo de algodón ideal para piscina o resort.", 350.00, "verano", "Mujer", "VERANO", "Resort Tropical"),
            (2, 47, "Jeans Flare Tiro Alto Vintage", "Pantalón acampanado en denim elástico con lavado azul índigo profundo.", 380.00, "pantalones", "Mujer", "PERMANENTE", "Denim Premium"),

            (2, 48, "Bolso Clutch Metálico Fiesta", "Bolso de mano rígido con cierre de broche de strass para bodas y galas.", 320.00, "accesorios", "Mujer", "PERMANENTE", "Accesorios Gala"),
            (2, 48, "Cinturón de Cuero Ancho con Hebilla Escultórica", "Accesorio statement en cuero curtido vegetal.", 210.00, "accesorios", "Mujer", "PERMANENTE", "Marroquinería Fina"),
            (2, 48, "Sandalias de Tiras Cuero Metalizado", "Calzado elegante de tacón fino para fiestas y graduaciones.", 490.00, "accesorios", "Mujer", "VERANO", "Noche de Gala"),

            # -------------------------------------------------------------
            # TENANT 1: SHOPPING BOLIVIA (Santa Cruz & Nacional) - 20 productos
            # -------------------------------------------------------------
            (1, 35, "Vestido Alta Costura Granados", "Vestido de gala confeccionado en mikado de seda con bordado a mano.", 1100.00, "vestidos_gala", "Mujer", "PRIMAVERA", "Couture Bolivia"),
            (1, 35, "Vestido Noche Strapless Rubí", "Vestido largo entallado con corsé interior de varillas flexibles.", 850.00, "vestidos_gala", "Mujer", "VERANO", "Gala Primavera"),
            (1, 35, "Vestido Cóctel Plisado Soleil", "Vestido midi en color amarillo oro con plisado soleil y cinturón a juego.", 610.00, "vestidos_gala", "Mujer", "VERANO", "Resort Lujo"),
            (1, 35, "Vestido Imperial Terciopelo Negro", "Pieza emblemática de corte columna con escote asimétrico.", 940.00, "vestidos_gala", "Mujer", "INVIERNO", "Couture Bolivia"),

            (1, 36, "Blazer Sastre Doble Abotonadura", "Saco formal de 6 botones con solapa en pico y paño liviano importado.", 750.00, "sastreria", "Hombre", "OTOÑO", "Sastrería Mayor"),
            (1, 36, "Blazer Lino Crudo Sirari", "Chaqueta desestructurada fresca para eventos de día en jardines.", 530.00, "sastreria", "Hombre", "VERANO", "Lino Natural"),
            (1, 36, "Saco Smoking Femenino Nácar", "Blazer smoking en satén blanco perla con solapa corrida brillante.", 690.00, "sastreria", "Mujer", "PRIMAVERA", "Gala Primavera"),

            (1, 37, "Camisa Popelina Puños Franceses", "Camisa de vestir de corte imperial con ojal para gemelos de lujo.", 390.00, "camisas_blusas", "Hombre", "PERMANENTE", "Esenciales Lujo"),
            (1, 37, "Blusa Seda Georgette Lavanda", "Blusa semitransparente con forro de tirantes y lazo en escote.", 330.00, "camisas_blusas", "Mujer", "PRIMAVERA", "Seda Pura"),
            (1, 37, "Camisa de Lino Azul Cobalto", "Camisa regular fit con teñido artesanal y botones de nácar natural.", 340.00, "camisas_blusas", "Hombre", "VERANO", "Lino Natural"),

            (1, 38, "Palazzo de Lino Puro Marfil", "Pantalón de bota muy ancha con caída elegante y bolsillos laterales.", 430.00, "pantalones", "Mujer", "VERANO", "Lino Natural"),
            (1, 38, "Pantalón Sastre Gris Grafito", "Pantalón de lana fresca con pretina reforzada y bota recta.", 410.00, "pantalones", "Hombre", "OTOÑO", "Sastrería Mayor"),
            (1, 38, "Pantalón Flare Terciopelo Noche", "Pantalón de tiro alto en terciopelo suave elástico.", 390.00, "pantalones", "Mujer", "INVIERNO", "Gala Primavera"),

            (1, 39, "Abrigo Paño Merino Imperial", "Abrigo largo de corte sastre en lana merino con cuello de solapa ancha.", 920.00, "abrigos_invierno", "Mujer", "INVIERNO", "Línea Exterior"),
            (1, 39, "Chaqueta Acolchada Plumón Ligero", "Campera liviana de duvet comprimible con acabado hidrófugo.", 580.00, "abrigos_invierno", "Unisex", "INVIERNO", "Línea Exterior"),
            (1, 39, "Ruana Tejida de Baby Alpaca", "Poncho abierto elegante con guarda andina estilizada.", 480.00, "abrigos_invierno", "Mujer", "OTOÑO", "Tejidos Nobles"),

            (1, 40, "Polera Cuello Tortuga Algodón", "Polera manga larga en algodón modal ceñida al cuerpo.", 210.00, "verano", "Mujer", "OTOÑO", "Esenciales Lujo"),
            (1, 40, "Jeans Slim Fit Denim Japonés", "Vaquero de 14 oz con teñido índigo natural y remaches cobrizos.", 450.00, "pantalones", "Hombre", "PERMANENTE", "Denim Premium"),

            (1, 41, "Cartera de Cuero Grabado Croco", "Bolso structured en piel vacuna con grabado cocodrilo y candado decorativo.", 640.00, "accesorios", "Mujer", "PERMANENTE", "Marroquinería Fina"),
            (1, 41, "Zapatos Oxford Piel Glaseada", "Calzado clásico de cordones con suela de cuero genuino cosida.", 690.00, "accesorios", "Hombre", "PERMANENTE", "Calzado Noble")
        ]

        total_prods_creados = 0
        total_vars_creadas = 0

        # Para asignar variantes, traer tallas y colores por empresa
        for item in nuevos_productos_config:
            id_emp = item[0]
            id_cat = item[1]
            nombre_p = item[2]
            desc_p = item[3]
            precio_base = Decimal(str(item[4]))
            tipo_img = item[5]
            genero_p = item[6]
            temp_p = item[7]
            col_p = item[8]

            # Verificar si ya existe por nombre y empresa
            p_exist = db.execute_query(f"""
                SELECT id_producto FROM {SCHEMA}.t_producto 
                WHERE id_empresa = %s AND nombre = %s LIMIT 1;
            """, (id_emp, nombre_p), fetchone=True)

            if p_exist:
                id_prod = p_exist[0]
            else:
                cod_pref = {1: "SB-EXP", 2: "FW-EXP", 3: "URB-EXP"}[id_emp]
                cod_prod = f"{cod_pref}-{random.randint(1000, 9999)}"
                url_img = random.choice(IMAGENES_MODA.get(tipo_img, IMAGENES_MODA["vestidos_gala"]))

                ins_p = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_producto (
                        id_categoria, codigo_producto, nombre, descripcion, marca,
                        genero, precio, imagen_url, estado, fecha_registro,
                        id_empresa, temporada, coleccion, activo, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, 'Aurora Atelier',
                        %s, %s, %s, TRUE, NOW(),
                        %s, %s, %s, TRUE, NOW()
                    ) RETURNING id_producto;
                """, (
                    id_cat, cod_prod, nombre_p, desc_p,
                    genero_p, precio_base, url_img,
                    id_emp, temp_p, col_p
                ), fetchone=True, commit=True)
                id_prod = ins_p[0]
                total_prods_creados += 1

                # Galería de imágenes (t_producto_imagen)
                fotos_pool = IMAGENES_MODA.get(tipo_img, IMAGENES_MODA["vestidos_gala"])
                for f_idx, f_url in enumerate(fotos_pool[:3]):
                    db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_producto_imagen (
                            id_producto, imagen_url, public_id, es_principal, orden
                        ) VALUES (
                            %s, %s, %s, %s, %s
                        );
                    """, (
                        id_prod, f_url, f"aurora/prod_{id_prod}_{f_idx}_{uuid4().hex[:6]}",
                        f_idx == 0, f_idx + 1
                    ), commit=True)

                # Si es fuera de temporada, vincular a promoción
                if temp_p == "VERANO":
                    db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_promocion_producto (id_promocion, id_producto, porcentaje_descuento)
                        SELECT 4, %s, 15.00
                        WHERE NOT EXISTS (SELECT 1 FROM {SCHEMA}.t_promocion_producto WHERE id_promocion = 4 AND id_producto = %s);
                    """, (id_prod, id_prod), commit=True)
                elif temp_p in ("OTOÑO", "INVIERNO"):
                    db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_promocion_producto (id_promocion, id_producto, porcentaje_descuento)
                        SELECT 5, %s, 20.00
                        WHERE NOT EXISTS (SELECT 1 FROM {SCHEMA}.t_promocion_producto WHERE id_promocion = 5 AND id_producto = %s);
                    """, (id_prod, id_prod), commit=True)

            # Crear variantes (4 a 5 variantes por prenda: XS, S, M, L, XL con colores)
            tallas_emp = db.execute_query(f"SELECT id_talla FROM {SCHEMA}.t_talla WHERE id_empresa = %s OR id_empresa IS NULL ORDER BY id_talla LIMIT 6;", (id_emp,), fetchall=True)
            colores_emp = db.execute_query(f"SELECT id_color FROM {SCHEMA}.t_color WHERE id_empresa = %s OR id_empresa IS NULL ORDER BY id_color LIMIT 5;", (id_emp,), fetchall=True)

            t_ids = [t[0] for t in tallas_emp] if tallas_emp else [1, 2, 3, 4]
            c_ids = [c[0] for c in colores_emp] if colores_emp else [1, 2, 3]

            # Sucursales de la empresa para inventario
            sucs_emp = [s[0] for s in sucursales if s[1] == id_emp]

            for t_id in t_ids[:4]:
                c_id = random.choice(c_ids)
                # Precio variante con ligera variación según talla
                delta = Decimal("0.00")
                if t_id in (5, 6, 11, 12):
                    delta = Decimal("25.00")
                p_var = precio_base + delta

                # Comprobar si variante existe
                v_exist = db.execute_query(f"""
                    SELECT id_variante FROM {SCHEMA}.t_producto_talla_color
                    WHERE id_producto = %s AND id_talla = %s AND id_color = %s LIMIT 1;
                """, (id_prod, t_id, c_id), fetchone=True)

                if not v_exist:
                    ins_v = db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_producto_talla_color (
                            id_producto, id_talla, id_color, precio, estado
                        ) VALUES (%s, %s, %s, %s, TRUE)
                        RETURNING id_variante;
                    """, (id_prod, t_id, c_id, p_var), fetchone=True, commit=True)
                    id_variante = ins_v[0]
                    total_vars_creadas += 1
                else:
                    id_variante = v_exist[0]
                    db.execute_query(f"UPDATE {SCHEMA}.t_producto_talla_color SET precio = %s, estado = TRUE WHERE id_variante = %s;", (p_var, id_variante), commit=True)

                # Inventario en cada sucursal de la empresa
                for id_suc in sucs_emp:
                    inv_exist = db.execute_query(f"""
                        SELECT id_inventario FROM {SCHEMA}.t_inventario
                        WHERE id_sucursal = %s AND id_variante = %s LIMIT 1;
                    """, (id_suc, id_variante), fetchone=True)

                    stock_init = random.randint(25, 65)
                    if not inv_exist:
                        db.execute_query(f"""
                            INSERT INTO {SCHEMA}.t_inventario (
                                id_sucursal, id_variante, stock_actual, stock_reservado,
                                stock_disponible, stock_minimo, estado, fecha_actualizacion
                            ) VALUES (
                                %s, %s, %s, 0, %s, 5, TRUE, NOW()
                            );
                        """, (id_suc, id_variante, stock_init, stock_init), commit=True)
                    else:
                        db.execute_query(f"""
                            UPDATE {SCHEMA}.t_inventario
                            SET stock_actual = stock_actual + %s, stock_disponible = stock_disponible + %s, estado = TRUE
                            WHERE id_inventario = %s;
                        """, (stock_init, stock_init, inv_exist[0]), commit=True)

        logger.info(f"Nuevos productos creados: {total_prods_creados}. Nuevas variantes: {total_vars_creadas}.")

        # Vincular productos existentes fuera de temporada a promociones para 100% visibilidad
        logger.info("Vinculando todos los productos existentes fuera de temporada a promociones activas...")
        db.execute_query(f"""
            INSERT INTO {SCHEMA}.t_promocion_producto (id_promocion, id_producto, porcentaje_descuento)
            SELECT 4, p.id_producto, 15.00
            FROM {SCHEMA}.t_producto p
            WHERE UPPER(TRIM(p.temporada)) = 'VERANO'
              AND NOT EXISTS (
                  SELECT 1 FROM {SCHEMA}.t_promocion_producto pp 
                  WHERE pp.id_promocion = 4 AND pp.id_producto = p.id_producto
              );
        """, commit=True)

        db.execute_query(f"""
            INSERT INTO {SCHEMA}.t_promocion_producto (id_promocion, id_producto, porcentaje_descuento)
            SELECT 5, p.id_producto, 20.00
            FROM {SCHEMA}.t_producto p
            WHERE UPPER(TRIM(p.temporada)) IN ('OTOÑO', 'INVIERNO')
              AND NOT EXISTS (
                  SELECT 1 FROM {SCHEMA}.t_promocion_producto pp 
                  WHERE pp.id_promocion = 5 AND pp.id_producto = p.id_producto
              );
        """, commit=True)

        logger.info("=== 4. Generando Nuevas Operaciones Transaccionales (Ventas, Cajas, Pedidos) ===")
        # Clientes bolivianos
        clientes = db.execute_query(f"""
            SELECT c.id_cliente, c.id_usuario, u.nombre, u.apellido, c.ci, c.ciudad
            FROM {SCHEMA}.t_cliente c
            JOIN {SCHEMA}.t_usuario u ON u.id_usuario = c.id_usuario
            ORDER BY c.id_cliente;
        """, fetchall=True)

        # Cajeros por empresa
        cajeros_por_emp = {
            1: [13, 22, 23],
            2: [11, 20],
            3: [16, 21]
        }
        for e_id in [1, 2, 3]:
            rows_u = db.execute_query(f"SELECT id_usuario FROM {SCHEMA}.t_usuario WHERE id_empresa = %s AND id_rol IN (3, 4, 5);", (e_id,), fetchall=True)
            if rows_u:
                cajeros_por_emp[e_id] = [r[0] for r in rows_u]

        # Traer sesiones de caja abiertas y cerradas
        sesiones_suc = {}
        for s in sucursales:
            s_id = s[0]
            ses = db.execute_query(f"SELECT id_sesion_caja FROM {SCHEMA}.t_caja_sesion WHERE id_sucursal = %s ORDER BY id_sesion_caja DESC LIMIT 4;", (s_id,), fetchall=True)
            if ses:
                sesiones_suc[s_id] = [r[0] for r in ses]

        metodos_pool = [
            (3, "EFECTIVO", "EF-POS"),
            (4, "QR", "QR-BCB"),
            (1, "TARJETA", "TARJ-VISA"),
            (2, "PAYPAL", "PAYPAL-CAP")
        ]
        metodos_weighted = [metodos_pool[0]] * 4 + [metodos_pool[1]] * 3 + [metodos_pool[2]] * 2 + [metodos_pool[3]] * 1

        now = datetime.now()
        nuevas_ventas_cfg = [
            (3, 50),  # 50 ventas para Urban Store
            (2, 40),  # 40 ventas para FashionWorld
            (1, 30)   # 30 ventas para Shopping Bolivia
        ]

        total_nuevas_ventas = 0
        for id_emp, cant_v in nuevas_ventas_cfg:
            suc_emp = [s[0] for s in sucursales if s[1] == id_emp]
            if not suc_emp:
                continue

            vars_emp = db.execute_query(f"""
                SELECT v.id_variante, v.precio, p.id_producto, p.nombre
                FROM {SCHEMA}.t_producto_talla_color v
                JOIN {SCHEMA}.t_producto p ON p.id_producto = v.id_producto
                WHERE p.id_empresa = %s AND v.precio > 0 AND v.estado = TRUE;
            """, (id_emp,), fetchall=True)

            if not vars_emp:
                continue

            cajeros = cajeros_por_emp.get(id_emp, [3])

            for _ in range(cant_v):
                dias_atras = random.randint(0, 60)
                horas_atras = random.randint(1, 10)
                f_vta = now - timedelta(days=dias_atras, hours=horas_atras, minutes=random.randint(5, 55))

                id_suc = random.choice(suc_emp)
                id_cajero = random.choice(cajeros)
                ses_list = sesiones_suc.get(id_suc, [1])
                id_sesion = random.choice(ses_list)

                cli = random.choice(clientes)
                id_cli = cli[0]
                nom_cli = f"{cli[2]} {cli[3]}".strip()
                ci_cli = cli[4] or f"{random.randint(3000000, 9999999)}"
                ciudad_cli = cli[5] or "La Paz"

                es_pos = random.random() < 0.70
                tipo_vta = "POS" if es_pos else "ECOMMERCE"
                ses_id_val = id_sesion if es_pos else None

                # Elegir entre 1 y 3 prendas
                num_p = random.choices([1, 2, 3], weights=[50, 35, 15])[0]
                prendas_v = random.sample(vars_emp, min(num_p, len(vars_emp)))

                subtotal = Decimal("0.00")
                items = []
                for p_var in prendas_v:
                    p_unit = p_var[1]
                    c_cant = 1 if p_unit > 400 else random.choice([1, 2])
                    st = p_unit * c_cant
                    subtotal += st
                    items.append((p_var[0], c_cant, p_unit, st))

                descuento = Decimal("0.00")
                if random.random() < 0.30:
                    descuento = round(subtotal * Decimal("0.15"), 2)
                total = subtotal - descuento

                tipo_doc = "FACTURA" if len(ci_cli) > 4 else "COMPROBANTE"
                num_vta = f"VTA-{id_emp}-{id_suc}-{random.randint(10000, 99999)}"

                ins_v = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_venta (
                        id_cliente, id_sucursal, id_usuario, numero_venta, tipo_venta,
                        fecha_venta, subtotal, descuento, total, estado, observacion,
                        id_empresa, nit_ci, razon_social, tipo_documento, id_sesion_caja,
                        correo_facturacion
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, 'PAGADO', 'Operación registrada en sistema',
                        %s, %s, %s, %s, %s,
                        %s
                    ) RETURNING id_venta;
                """, (
                    id_cli, id_suc, id_cajero, num_vta, tipo_vta,
                    f_vta, subtotal, descuento, total,
                    id_emp, ci_cli, nom_cli, tipo_doc, ses_id_val,
                    f"cliente{id_cli}@gmail.com"
                ), fetchone=True, commit=True)

                id_vta = ins_v[0]
                total_nuevas_ventas += 1

                for v_id, c_cant, p_u, st in items:
                    db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_detalle_venta (
                            id_venta, id_variante, cantidad, precio_unitario, descuento, subtotal
                        ) VALUES (%s, %s, %s, %s, 0.00, %s);
                    """, (id_vta, v_id, c_cant, p_u, st), commit=True)

                # Pago
                met = random.choice(metodos_weighted)
                cod_tx = f"{met[2]}-{random.randint(100000, 999999)}"
                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_pago (
                        id_venta, id_metodo_pago, codigo_transaccion, monto, fecha_pago, estado, referencia_externa
                    ) VALUES (%s, %s, %s, %s, %s, 'APROBADO', %s);
                """, (id_vta, met[0], cod_tx, total, f_vta, f"REF-VTA-{id_vta}"), commit=True)

                # Pedido si es ecommerce
                if not es_pos:
                    cod_ped = f"PED-{id_emp}-{random.randint(1000, 9999)}"
                    st_ped = "ENTREGADO" if dias_atras > 3 else "EN_CAMINO"
                    db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_pedido (
                            codigo_pedido, id_cliente, id_empresa, id_sucursal, fecha_pedido,
                            estado, estado_pago, modalidad_compra, nombre_contacto, telefono_contacto,
                            correo_contacto, direccion_entrega, ciudad_entrega, subtotal, costo_envio,
                            descuento, total, id_venta
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, 'PAGADO', 'ENVIO_DOMICILIO', %s, %s,
                            %s, %s, %s, %s, 25.00,
                            %s, %s, %s
                        );
                    """, (
                        cod_ped, id_cli, id_emp, id_suc, f_vta,
                        st_ped, nom_cli, "+591 71234567",
                        f"cliente{id_cli}@gmail.com", f"Av. Central #{random.randint(100, 900)}", ciudad_cli,
                        subtotal, descuento, total + Decimal("25.00"), id_vta
                    ), commit=True)

        logger.info(f"Nuevas ventas y pedidos generados: {total_nuevas_ventas} registros.")

        logger.info("=== 5. Generando Nuevas Reservas, Devoluciones y Valoraciones ===")
        # 36 Reservas de probador
        total_nuevas_reservas = 0
        for id_emp in [1, 2, 3]:
            suc_emp = [s[0] for s in sucursales if s[1] == id_emp]
            prods_emp = db.execute_query(f"SELECT v.id_variante FROM {SCHEMA}.t_producto_talla_color v JOIN {SCHEMA}.t_producto p ON p.id_producto=v.id_producto WHERE p.id_empresa = %s LIMIT 15;", (id_emp,), fetchall=True)
            if not suc_emp or not prods_emp:
                continue

            for r_idx in range(12):
                id_suc = random.choice(suc_emp)
                cli = random.choice(clientes)
                es_futura = r_idx < 4
                f_res = now - timedelta(days=random.randint(0, 20))
                f_vis = now + timedelta(days=random.randint(1, 5), hours=random.randint(1, 5)) if es_futura else f_res + timedelta(days=1)
                st_res = "CONFIRMADA" if es_futura else random.choice(["COMPLETADA", "COMPLETADA", "CANCELADA"])

                ins_r = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_reserva (
                        id_cliente, id_sucursal, codigo_reserva, fecha_reserva, fecha_hora_visita,
                        estado, observaciones, con_pago, estado_pago, monto_pagado
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, 'Cita personalizada en probador de boutique', FALSE, 'NO_REQUERIDO', 0.00
                    ) RETURNING id_reserva;
                """, (cli[0], id_suc, f"RES-{id_emp}-{random.randint(1000, 9999)}", f_res, f_vis, st_res), fetchone=True, commit=True)
                id_res = ins_r[0]
                total_nuevas_reservas += 1

                for p_var in random.sample(prods_emp, min(2, len(prods_emp))):
                    db.execute_query(f"""
                        INSERT INTO {SCHEMA}.t_detalle_reserva (id_reserva, id_variante, cantidad, estado_prenda)
                        VALUES (%s, %s, 1, %s);
                    """, (id_res, p_var[0], "PROBADA" if st_res == "COMPLETADA" else "PENDIENTE"), commit=True)

        logger.info(f"Nuevas reservas creadas: {total_nuevas_reservas}.")

        # 12 Devoluciones adicionales (Cambio de Talla y Ley 453)
        total_nuevas_devs = 0
        for id_emp in [1, 2, 3]:
            vtas_rec = db.execute_query(f"""
                SELECT v.id_venta, v.id_sucursal, v.id_usuario, dv.id_detalle_venta, dv.precio_unitario
                FROM {SCHEMA}.t_venta v
                JOIN {SCHEMA}.t_detalle_venta dv ON dv.id_venta = v.id_venta
                WHERE v.id_empresa = %s
                ORDER BY v.id_venta DESC LIMIT 10;
            """, (id_emp,), fetchall=True)

            for d_idx, v_row in enumerate(vtas_rec[:4]):
                id_vta = v_row[0]
                id_suc = v_row[1]
                id_usr = v_row[2]
                id_dtv = v_row[3]
                p_u = v_row[4]
                es_cambio = d_idx % 2 == 0
                tipo_res = "CAMBIO_PRENDA" if es_cambio else "REEMBOLSO_DINERO"
                motivo = "TALLA_INCORRECTA" if es_cambio else "DEFECTO_FABRICA"
                ley_453 = not es_cambio
                monto_r = Decimal("0.00") if es_cambio else p_u

                ins_dev = db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_devolucion (
                        id_venta, id_usuario, fecha_devolucion, motivo, monto_reembolso,
                        estado, codigo_devolucion, id_empresa, id_sucursal, tipo_devolucion,
                        descripcion_cliente, id_usuario_revisor, fecha_resolucion, observaciones_resolucion,
                        metodo_reembolso, fecha_reembolso, tipo_resolucion, dias_desde_compra, cumple_politica, excepcion_ley_453
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        'COMPLETADA', %s, %s, %s, 'PARCIAL',
                        'Gestión de post-venta y cambio', %s, %s, 'Trámite concluido conforme a normativa comercial',
                        'QR_TRANSFERENCIA', %s, %s, 3, TRUE, %s
                    ) RETURNING id_devolucion;
                """, (
                    id_vta, id_usr, now - timedelta(days=5), motivo, monto_r,
                    f"DEV-{id_emp}-{random.randint(1000, 9999)}", id_emp, id_suc,
                    id_usr, now - timedelta(days=4),
                    now - timedelta(days=4), tipo_res, ley_453
                ), fetchone=True, commit=True)
                id_dev = ins_dev[0]
                total_nuevas_devs += 1

                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_detalle_devolucion (
                        id_devolucion, id_detalle_venta, cantidad, condicion, precio_unitario,
                        monto_reembolso, estado_item, destino_inventario
                    ) VALUES (
                        %s, %s, 1, 'NUEVO_CON_ETIQUETA', %s, %s, 'ACEPTADO', 'RESTITUIDO'
                    );
                """, (id_dev, id_dtv, p_u, monto_r), commit=True)

        logger.info(f"Nuevas devoluciones creadas: {total_nuevas_devs}.")

        # 60 Nuevas Valoraciones
        total_nuevas_vals = 0
        for id_emp in [1, 2, 3]:
            prods = db.execute_query(f"SELECT id_producto FROM {SCHEMA}.t_producto WHERE id_empresa = %s;", (id_emp,), fetchall=True)
            suc_emp = [s[0] for s in sucursales if s[1] == id_emp]
            if not prods or not suc_emp:
                continue

            for _ in range(20):
                id_p = random.choice(prods)[0]
                id_suc = random.choice(suc_emp)
                cli = random.choice(clientes)
                score, comment = random.choice(COMENTARIOS_EXPANSION)
                req_rev = score <= 3
                f_crea = now - timedelta(days=random.randint(1, 40), hours=random.randint(1, 10))

                db.execute_query(f"""
                    INSERT INTO {SCHEMA}.t_valoracion (
                        id_empresa, id_sucursal, id_cliente, id_producto, puntuacion,
                        comentario, motivo_negativo, requiere_revision, atendido, fecha_creacion
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    id_emp, id_suc, cli[0], id_p, score,
                    comment, "TALLA_INCORRECTA" if req_rev else None, req_rev, not req_rev, f_crea
                ), commit=True)
                total_nuevas_vals += 1

        logger.info(f"Nuevas valoraciones creadas: {total_nuevas_vals}.")

        logger.info("=== 6. Re-entrenando Motor Mini-ML de Preferencias y Recomendaciones ===")
        try:
            from app.modules.ia.services.ml_preferencias_services import aprender_preferencias_cliente
            clientes_act = db.execute_query(f"SELECT DISTINCT id_cliente, id_empresa FROM {SCHEMA}.t_venta WHERE id_cliente IS NOT NULL;", fetchall=True)
            count_ml = 0
            for r_cli in clientes_act:
                try:
                    aprender_preferencias_cliente(r_cli[0], r_cli[1])
                    count_ml += 1
                except Exception:
                    pass
            logger.info(f"Motor vectorial de Machine Learning actualizado para {count_ml} clientes.")
        except Exception as e_ml:
            logger.warning(f"Aviso no bloqueante ML: {e_ml}")

        logger.info("¡Población y corrección de temporadas completadas con éxito!")

    finally:
        db.close_connection()


if __name__ == "__main__":
    ejecutar_expansion()
