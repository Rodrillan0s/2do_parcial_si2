# Índice Maestro de Documentación — AuroraStore

**Propósito:** Este documento clasifica, describe y centraliza todos los archivos de documentación (`.md`) existentes en el repositorio de AuroraStore, estableciendo el nuevo estándar de documentación segmentada por dominios arquitectónicos.

---

## 1. Reglas y Estándar de Documentación

A partir de noviembre de 2026, la documentación sigue una política de **segmentación por módulo y propósito**, reemplazando el registro monolítico en un único archivo:

1. **Arquitectura y Diseño:** Residen en `docs/architecture/` y describen los componentes, modelos de datos, máquinas de estados y flujos funcionales de cada subsistema.
2. **Historial de Cambios (Changelogs):** Residen en `docs/changes/`, divididos por dominio operativo (PWA, Reservas, Devoluciones, SaaS). **Queda prohibido continuar acumulando entradas en `docs/AGENT_CHANGES.md`**, el cual se preserva únicamente como archivo histórico inmutable de las primeras 92 entradas.
3. **Casos de Uso y Secuencias:** Residen en la raíz (`README_Sequence_*.md` y `VALIDACION_SEQUENCE_*.md`) para la trazabilidad de los Casos de Uso de la plataforma.

---

## 2. Mapa de Documentación por Categorías

### A. Gobernanza y Reglas de Desarrollo
| Archivo | Ubicación | Descripción |
| :--- | :--- | :--- |
| **`AGENTS.md`** | Raíz (`/`) | Reglas operativas no negociables para agentes IA: aislamiento multitenant estricto, trabajo en rama actual, división de responsabilidades (Codex vs Antigravity), prohibición de tocar `mobile/` y respaldos `CU41W`. |

---

### B. Arquitectura de Módulos (`docs/architecture/` y `docs/`)
| Archivo | Ubicación | Descripción |
| :--- | :--- | :--- |
| **`PWA_ARQUITECTURA.md`** | `docs/architecture/` | Arquitectura completa de la Progressive Web App: Service Worker v2.0.0, IndexedDB v4, matriz offline vs online, bloqueos transaccionales y cola de sincronización. |
| **`POS_CONTINGENCIA_OFFLINE.md`** | `docs/architecture/` | Estrategia de contingencia offline POS (Migración 008): cuotas de inventario aisladas por sesión de caja, sincronización prioritaria P0, prevención de sobreventa y comprobantes provisionales. |
| **`VENTAS_STOREFRONT_ARQUITECTURA.md`** | `docs/architecture/` | Arquitectura de ventas y pedidos online: reserva atómica de inventario, máquina de estados ortogonales, cancelación de órdenes, expiración 48h y desacoplamiento de reservas. |
| **`RESERVAS_ARQUITECTURA.md`** | `docs/architecture/` | Especificación de citas de probador en boutique, caja registradora única compartida con POS, y algoritmo atómico de expiración automática. |
| **`ITER1_CONTEXT.md`** | `docs/` | Modelos de datos base de la Iteración 1, entidades de usuario, sucursales y principios de aislamiento multi-tenant. |
| **`ITER1_API.md`** | `docs/` | Catálogo de contratos REST de la Iteración 1, parámetros de consulta y códigos de respuesta. |
| **`ITER1_MIGRATIONS.md`** | `docs/` | Bitácora y especificación de las migraciones 001 (SaaS) y 002 (Índices de Rendimiento). |

---

### C. Historial de Cambios Modular (`docs/changes/`)
| Archivo | Ubicación | Dominio Cubierto |
| :--- | :--- | :--- |
| **`CHANGELOG_PWA.md`** | `docs/changes/` | Service Worker, IndexedDB v4, suite `test_pwa_iter2.py` (8/8 superadas), detección de red y sincronización en reconexión. |
| **`CHANGELOG_POS.md`** | `docs/changes/` | Contingencia offline POS (Migración 008), cuotas de sesión, sincronización P0, suite `test_pos_contingencia.py` (5/5 superadas) y comprobantes provisionales. |
| **`CHANGELOG_RESERVAS.md`** | `docs/changes/` | Saneamiento de reservas, 46 prendas liberadas a stock disponible, expiración automática JIT y validación de horarios comerciales. |
| **`CHANGELOG_VENTAS_RESERVAS.md`** | `docs/changes/` | Alineación funcional pedidos vs reservas, reserva atómica de stock en órdenes online, cancelación voluntaria, consumo de stock pre-reservado y suite de pruebas `test_ventas_reservas_flujo.py`. |
| **`CHANGELOG_PAGOS_INVENTARIO.md`** | `docs/changes/` | Conciliación de inventario (Migración 009 reversible, 5.690 registros sincronizados), pre-vuelo de pasarelas de pago y resolución de error 409 en captura PayPal. |
| **`CHANGELOG_DEVOLUCIONES.md`** | `docs/changes/` | Flujos de mostrador: cambio de prenda, saldo a favor y reembolso de dinero; buscador multicriterio y cumplimiento Ley 453. |
| **`CHANGELOG_SAAS.md`** | `docs/changes/` | Contratación autónoma, resolución storefront multitenant, pasarela PayPal Sandbox, modal de suscripciones y políticas de cancelación. |
| **`AGENT_CHANGES.md`** | `docs/` | *(Histórico / Solo Lectura)* Bitácora original acumulada con las 92 entradas iniciales del proyecto. |

---

### D. Protocolo de Sincronización Offline e Idempotencia
| Archivo | Ubicación | Descripción |
| :--- | :--- | :--- |
| **`PWA_CONTRATO_SYNC.md`** | `docs/` | Contrato canónico de sincronización por lotes (`POST /api/sync/lote`), huella digital SHA-256 y compatibilidad Angular PWA / Flutter. |
| **`PWA_COLA_RETENCION_RESULTADOS.md`** | `docs/` | Protocolo de retención de recibos locales en `sync_receipts` y reglas contra purgas destructivas en IndexedDB. |
| **`SYNC_IDEMPOTENCIA_TRANSACCIONAL.md`** | `docs/` | Análisis formal de la eliminación de commits parciales y uso de advisory locks en PostgreSQL. |
| **`SYNC_MIGRACION_APLICADA_2026-10-31.md`** | `docs/` | Acta de verificación y aplicación de las migraciones 003 y 004 en la base de datos de destino. |
| **`ANTIGRAVITY_SYNC_RETENCION.md`** | `docs/` | Verificación de retención de operaciones críticas entre recargas y cambios de sesión. |

---

### E. Devoluciones, Auditoría y Rendimiento
| Archivo | Ubicación | Descripción |
| :--- | :--- | :--- |
| **`DEVOLUCIONES_AUDITORIA.md`** | `docs/` | Auditoría de flujo de devoluciones en tienda de ropa: distinción entre condición revendible y defectuosa. |
| **`DEVOLUCIONES_IMPLEMENTACION.md`** | `docs/` | Detalles técnicos de implementación de las devoluciones en POS y storefront. |
| **`diagnostico.md`** | `docs/performance/` | Auditoría de latencia de endpoints, detección de problemas N+1 y consumo de memoria. |
| **`cambios.md`** | `docs/performance/` | Optimizaciones de consultas SQL y creación de índices especializados. |
| **`resultados.md`** | `docs/performance/` | Métricas antes y después de la optimización de rendimiento en FastAPI. |
| **`PWA_RENDIMIENTO_ANTES_DESPUES.md`**| `docs/` | Métricas de tamaño del bundle frontend, tiempos de carga del App Shell y latencia offline. |

---

### F. Diagramas de Secuencia y Validación de Casos de Uso
| Archivo | Ubicación | Casos de Uso Cubiertos |
| :--- | :--- | :--- |
| **`README_Sequence_CU01W_CU05W.md`** | Raíz (`/`) | CU01W (Login), CU02W (Usuarios), CU03W (Sucursales), CU04W (Catálogo), CU05W (Búsqueda). |
| **`VALIDACION_SEQUENCE_CU01W_CU05W.md`** | Raíz (`/`) | Validación formal contra endpoints y pruebas unitarias de CU01W a CU05W. |
| **`README_Sequence_CU06W_CU10W.md`** | Raíz (`/`) | CU06W (Detalle), CU07W (Stock Sucursal), CU08W (Bolsa), CU09W (Pedido), CU10W (Reservas). |
| **`VALIDACION_SEQUENCE_CU06W_CU10W.md`** | Raíz (`/`) | Validación formal contra endpoints y pruebas unitarias de CU06W a CU10W. |
| **`README_Sequence_CU11W_CU15W.md`** | Raíz (`/`) | CU11W (Inventario), CU12W (Movimientos), CU13W (Proveedores), CU14W (Lotes), CU15W (Pedidos Proveedor). |
| **`VALIDACION_SEQUENCE_CU11W_CU15W.md`** | Raíz (`/`) | Validación formal contra endpoints y pruebas unitarias de CU11W a CU15W. |
| **`README_Sequence_CU16W_CU17W_CU24W_CU25W.md`** | Raíz (`/`) | CU16W (Apertura Caja), CU17W (Cierre Caja), CU24W (Ventas POS), CU25W (Devoluciones). |
| **`VALIDACION_SEQUENCE_CU16W_CU17W_CU24W_CU25W.md`** | Raíz (`/`) | Validación formal contra endpoints y pruebas unitarias de CU16W, CU17W, CU24W y CU25W. |
| **`pruebas_casos_de_uso.md`** | `docs/` | Matriz integral de casos de uso y batería de pruebas de aceptación. |

---

### G. Propuestas y Normalización
| Archivo | Ubicación | Descripción |
| :--- | :--- | :--- |
| **`CORRECCIONES_CRITICAS_2026-11-01.md`** | `docs/` | Informe de correcciones de integridad en movimientos de inventario y sesiones de caja. |
| **`CORRECCIONES_CRITICAS_SQL_PROPUESTO.md`** | `docs/` | Scripts SQL propuestos para saneamiento de inconsistencias de datos. |
| **`NORMALIZACION_PROPUESTA_2026-11-01.md`** | `docs/` | Propuesta de normalización de tipos de datos, códigos de error y respuestas JSON. |
| **`PROPUESTA_REDISENO_RBAC_Y_ACCESOS.md`**| `docs/` | Propuesta de jerarquía y delegación de roles y permisos multitenant. |
| **`REVISION_CAJA_POS_Y_ERRORES_API.md`** | `docs/` | Auditoría de respuestas HTTP y manejo de sesiones de caja activas. |
| **`diagramas_robustez/README.md`** | `docs/diagramas_robustez/` | Directorio de diagramas de robustez de los principales flujos comerciales. |

---

### H. Readmes de Proyectos
| Archivo | Ubicación | Descripción |
| :--- | :--- | :--- |
| **`frontend/README.md`** | `frontend/` | Guía de comandos de Angular 21 (`ng serve`, `ng build`, `ng test`). |
| **`mobile/README.md`** | `mobile/` | Documentación base de la app móvil Flutter (preservada sin modificaciones). |
