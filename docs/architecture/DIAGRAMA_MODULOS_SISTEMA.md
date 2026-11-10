# AuroraStore — Diagrama de Módulos de Sistema (Draw.io / UML 2.5)

## 1. Propósito y Estructura Arquitectónica

Este documento describe el **Diagrama de Módulos de Sistema (`pkg Diagrama de modulos de sistema`)** del ecosistema **AuroraStore SaaS**, modelado bajo el estándar **UML 2.5** en formato nativo **Draw.io (`.drawio` / XML)**.

El diagrama sigue el patrón arquitectónico de **3 Capas (Presentación, Negocio y Datos)** e integra de manera explícita y trazable los **10 Módulos Funcionales** del sistema:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        «Capa» PRESENTACIÓN                             │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐  │
│  │     «SubSistema» Web (PWA)    │  │    «SubSistema» Móvil (Flutter)│  │
│  │ Views, Services, Offline PWA  │  │ Views, Services, Vestidor RA  │  │
│  └──────────────┬────────────────┘  └──────────────┬────────────────┘  │
└─────────────────┼──────────────────────────────────┼───────────────────┘
                  │ «use»                            │ «use»
┌─────────────────▼──────────────────────────────────▼───────────────────┐
│                        «Capa» NEGOCIO (FastAPI)                        │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐  │
│  │     «SubSistema» Seguridad    │  │  «SubSistema» SaaS & Scopes   │  │
│  │      Middleware JWT & RBAC    │  │  Aislamiento Empresa/Sucursal │  │
│  └───────────────────────────────┘  └───────────────────────────────┘  │
│                                                                        │
│  10 Módulos de Dominio (Routes / Controllers ──«use»──> Services):     │
│  1. Autenticación y Usuarios         6. Punto de Venta (POS / Caja)    │
│  2. Gestión de Catálogo              7. Pedidos, Reportes & Motor BI   │
│  3. Sucursales, Inventario & Lotes   8. Inteligencia Artificial (W13)  │
│  4. E-Commerce & Checkout            9. Gestión SaaS & Suscripciones   │
│  5. Reservas (Citas de Vestidor)    10. Administración & Auditoría     │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ «use»
┌─────────────────────────────────▼──────────────────────────────────────┐
│                        «Capa» DATOS (PostgreSQL)                       │
│  ┌───────────────────────────────┐  ┌───────────────────────────────┐  │
│  │ «SubSistema» Persistencia     │  │ «SubSistema» Base de Datos    │  │
│  │ Repositorios, Entidades, DTOs │  │ Esquema comercio, Vistas SQL, │  │
│  │ y Storage Offline Local       │  │ Auditoría (t_bitacora)        │  │
│  └───────────────────────────────┘  └───────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Desglose por Capas y Componentes

### 2.1. Capa de Presentación
- **«SubSistema» Web (Angular 19 PWA):**
  - `Views / Componentes`: Storefront público, panel de administración SaaS, terminal POS, gestión de inventario y motor de reportes.
  - `Services / HTTP API`: Clientes HTTP tipados con debouncing, deduplicación y cancelación reactiva (`takeUntil`).
  - `Offline PWA (IndexedDB)`: Almacén local `aurora_store_pwa_db` particionado por usuario y empresa.
  - `Cola de Sincronización`: `SyncQueueService` con lock multi-pestaña y componente visual `PwaStatusBar`.
- **«SubSistema» Móvil (Flutter 3.x):**
  - `Views / Screens`: Pantallas 100% orientadas al cliente (Catálogo, Carrito, Mis Pedidos, Devoluciones, Asistente).
  - `Services / ApiClient`: Cliente HTTP con inyección automática de cabeceras de autorización y tenant.
  - `Vestidor Virtual RA`: Experiencia híbrida con Google ARCore, visor interactivo 3D de prendas (.glb) y detección de pose corporal ML Kit.
  - `Offline Móvil (SQLite)`: `DatabaseHelper` local y `SyncCoordinator` para sincronización por lotes (`POST /api/sync/lote`).

### 2.2. Capa de Negocio (Backend FastAPI)
- **Núcleo Transversal:**
  - `Seguridad`: Middleware de validación de tokens JWT, roles canónicos y permisos finos RBAC.
  - `SaaS Multi-tenant`: `Tenant Guard` y `Scopes` que resuelven autoritativamente `id_empresa` e `id_sucursal`.
- **Los 10 Módulos de Dominio (Routes / Controllers $\rightarrow$ Services):**
  1. **Autenticación y Gestión de Usuarios:** `auth_routes`, `users_routes`, `rbac_routes` $\rightarrow$ `auth_services`, `users_services`.
  2. **Gestión de Catálogo:** `productos_routes`, `categorias_routes`, `catalogo_routes` $\rightarrow$ `productos_services`, sincronización de variantes con precios por talla.
  3. **Gestión Sucursales, Inventario y Proveedores:** `inventario_routes`, `sucursales_routes`, `compras_lotes_routes` $\rightarrow$ `inventario_services`, control de lotes y traspasos.
  4. **Gestión de E-Commerce:** `carrito_routes`, `pago_routes`, `sync_routes` $\rightarrow$ pasarela PayPal server-to-server, sincronización offline idempotente.
  5. **Reservas:** `reserva_routes` $\rightarrow$ `reserva_services` con expiración automática de citas vencidas (12h) y restitución de prendas al stock.
  6. **Gestión de Punto de Venta (POS):** `pos_routes`, `caja_routes` $\rightarrow$ sesiones de caja, ventas en mostrador, tickets y contingencia offline.
  7. **Gestión de Pedidos y Reportes:** `pedidos_routes`, `devoluciones_routes` (Ley N° 453), `motor_reportes_routes` (procesamiento de lenguaje natural y 14 reportes), `kpis_routes`, `valoracion_routes`.
  8. **Inteligencia Artificial y Experiencia del Cliente:**
     - Orquestador conversacional multi-intención (Aurora Advisor W13) con 26 herramientas.
     - Adaptadores DeepSeek V3/R1, OpenAI y Gemini.
     - Motor predictivo de demanda y reposición (Holt Linear Trend con intervalos de confianza al 95%).
     - Mini-ML de afinidad y recomendaciones personalizadas (*Content-Based Cosine Model*).
  9. **Gestión SaaS:** `saas_routes`, `tenant_routes` $\rightarrow$ autoservicio de contratación con verificación Brevo, planes Básico (hasta 2 sucursales) y Profesional (hasta 10 sucursales), cálculo de reembolso y upgrades.
  10. **Administración, Seguridad y Respaldos:** `admin_routes`, `backup_routes` $\rightarrow$ supervisión de empresas, trazabilidad y bitácora inmutable.

### 2.3. Capa de Datos (PostgreSQL & Persistencia)
- **«SubSistema» Persistencia de Datos:**
  - `Repositories`: Capa de abstracción de datos pura con consultas SQL parametrizadas (`users_repos`, `catalogo_repos`, `inventario_repos`, `pos_repos`, etc.).
  - `Entities & Domain Schemas`: Esquemas Pydantic para validación de entrada/salida y entidades de dominio.
  - `Almacenamiento Local Offline`: IndexedDB en navegadores web y SQLite en dispositivos móviles.
  - `PostgreSQL Connection Pool`: Gestor de conexiones transaccionales en `app.core.postgres` con eliminación de doble RTT.
- **«SubSistema» Base de Datos (PostgreSQL 15+):**
  - `Esquema comercio`: Tablas maestras relacionales (`empresa`, `t_usuario`, `t_sucursal`, `t_producto`, `t_inventario`, `t_venta`, `t_pedido`, `t_reserva`, `t_suscripcion`, `t_valoracion`, etc.).
  - `Vistas Analíticas SQL`: 14 vistas canónicas (`vw_ventas_reporte`, `vw_inventario_reporte`, `vw_rentabilidad_reporte`, `vw_pos_reporte`, `vw_valoraciones_reporte`, etc.).
  - `Auditoría y Control`: `t_bitacora` (registro inmutable de eventos sensibles) y `t_sync_operacion` (deduplicación e idempotencia con UUID).

---

## 3. Ubicación de los Archivos Entregados

1. **Diagrama editable en Draw.io (Raíz):**
   [`diagrama_modulos_sistema.drawio`](file:///d:/Locked%20Files%20--EY/Projectos/Examen_parcial1_S12/diagrama_modulos_sistema.drawio)
2. **Diagrama editable en Draw.io (Directorio de arquitectura):**
   [`docs/architecture/diagrama_modulos_sistema.drawio`](file:///d:/Locked%20Files%20--EY/Projectos/Examen_parcial1_S12/docs/architecture/diagrama_modulos_sistema.drawio)
3. **Versión XML equivalente:**
   [`docs/architecture/diagrama_modulos_sistema.xml`](file:///d:/Locked%20Files%20--EY/Projectos/Examen_parcial1_S12/docs/architecture/diagrama_modulos_sistema.xml)
4. **Script generador reproducible:**
   [`docs/architecture/generate_diagrama_modulos_drawio.py`](file:///d:/Locked%20Files%20--EY/Projectos/Examen_parcial1_S12/docs/architecture/generate_diagrama_modulos_drawio.py)

---

## 4. Instrucciones para Abrir y Visualizar en Draw.io

1. Abrir la aplicación de escritorio **Draw.io** o acceder al editor web [app.diagrams.net](https://app.diagrams.net).
2. Seleccionar `Archivo` $\rightarrow$ `Abrir desde` $\rightarrow$ `Dispositivo...`
3. Elegir el archivo [`diagrama_modulos_sistema.drawio`](file:///d:/Locked%20Files%20--EY/Projectos/Examen_parcial1_S12/diagrama_modulos_sistema.drawio).
4. El diagrama se cargará con su estructura de 3 capas, los 10 módulos organizados con su estilo de componentes (`shape=component`), conectores ortogonales discontinuos y dependencias `«use»`.
