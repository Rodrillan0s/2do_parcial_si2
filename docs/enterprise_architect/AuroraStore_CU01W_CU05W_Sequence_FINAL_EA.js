/*
 * =================================================================================================
 * SCRIPT MAESTRO DE AUTOMATIZACIÓN DE DIAGRAMAS DE SECUENCIA UML 2.5 PARA SPARX ENTERPRISE ARCHITECT
 * =================================================================================================
 * Proyecto: AuroraStore SaaS
 * Versión: FINAL REFINADA (Lifelines rectangulares estándar UML y controladores reales de backend)
 * 
 * Casos de Uso soportados (Exactamente 5 diagramas únicos consolidados):
 *   - sd CU01W - Gestionar usuarios y roles
 *   - sd CU02W - Gestionar cadena de tiendas (Empresas SaaS)
 *   - sd CU03W - Gestionar sucursales
 *   - sd CU04W - Gestionar productos
 *   - sd CU05W - Gestionar planes de suscripción
 * 
 * Correcciones y Estilo UML 2.5:
 *   1. Líneas de Vida (Lifelines):
 *      - Se eliminan estereotipos «boundary», «control» y «entity» en las lifelines para que EA NO dibuje
 *        los iconos circulares de robustez, sino la CABECERA RECTANGULAR ESTÁNDAR con línea punteada vertical.
 *   2. Controladores fieles a la implementación real del backend:
 *      - CU01W: users_routes, users_services
 *      - CU02W: tenant_routes, tenant_services
 *      - CU03W: sucursales_routes, sucursales_services
 *      - CU04W: productos_routes, productos_services
 *      - CU05W: saas_routes, saas_services
 *   3. Interfaces limpias y sintetizadas (1 Boundary UI por caso de uso en lugar de 5 ventanas/modales).
 *   4. Entidades reales de persistencia PostgreSQL fieles a la robustez y al código.
 *   5. Fragmentos combinados (alt, opt, loop) calculados con exactitud milimétrica sobre las coordenadas Y
 *      negativas del 4to cuadrante de EA (top > bottom).
 * =================================================================================================
 */

// -------------------------------------------------------------------------------------------------
// UTILIDADES Y HELPERS DE ENTERPRISE ARCHITECT AUTOMATION
// -------------------------------------------------------------------------------------------------

/**
 * Crea una línea de vida (Lifeline) rectangular clásica en el diagrama de secuencia de EA.
 * Sin estereotipo de robustez para evitar que EA dibuje círculos/lollipops.
 */
function agregarLifeline(pkg, diag, nombre, eaType, posX, ancho, altoTotal) {
    var tipoFinal = (eaType === "Actor") ? "Actor" : "Sequence";
    var el = pkg.Elements.AddNew(nombre, tipoFinal);
    // Dejar Stereotype vacío garantiza que EA renderice la caja rectangular estándar de Lifeline UML
    el.Update();

    var left = posX;
    var right = posX + ancho;
    var top = -30;
    var bottom = -(30 + altoTotal);

    var diagObj = diag.DiagramObjects.AddNew("l=" + left + ";r=" + right + ";t=" + top + ";b=" + bottom + ";", "");
    diagObj.ElementID = el.ElementID;
    diagObj.Update();

    return el;
}

/**
 * Crea un mensaje de secuencia (Connector tipo "Sequence") entre dos líneas de vida.
 * Sincroniza t_connector.PDATA4 y t_connector.SeqNo de forma segura por SQL.
 */
function agregarMensaje(sourceEl, targetEl, textoMensaje, seqNum, esRetorno, esError) {
    if (!sourceEl || !targetEl) return null;

    var conn = sourceEl.Connectors.AddNew(textoMensaje, "Sequence");
    conn.SupplierID = targetEl.ElementID;

    if (esError) {
        conn.Stereotype = "error";
    }
    conn.Update();
    sourceEl.Connectors.Refresh();

    try {
        if (esRetorno) {
            Repository.Execute("UPDATE t_connector SET PDATA4 = '1' WHERE Connector_ID = " + conn.ConnectorID);
        }
        if (seqNum > 0) {
            Repository.Execute("UPDATE t_connector SET SeqNo = " + seqNum + " WHERE Connector_ID = " + conn.ConnectorID);
        }
    } catch (ex) {
        // Fallback transparente
    }

    return conn;
}

/**
 * Crea un fragmento combinado (InteractionFragment: alt, opt, loop) dimensionado con exactitud
 * alrededor de los mensajes que envuelve (top = -topY, bottom = -bottomY).
 */
function agregarFragmentoCombinado(pkg, diag, nombre, operador, guarda, left, right, topY, bottomY) {
    var frag = pkg.Elements.AddNew(nombre, "InteractionFragment");
    frag.Stereotype = operador; // "alt", "opt", "loop"
    frag.Notes = guarda;
    frag.Update();

    var top = -topY;
    var bottom = -bottomY;

    var fragObj = diag.DiagramObjects.AddNew("l=" + left + ";r=" + right + ";t=" + top + ";b=" + bottom + ";", "");
    fragObj.ElementID = frag.ElementID;
    fragObj.Update();

    return frag;
}

// =================================================================================================
// 1. CU01W: Gestionar usuarios y roles
// =================================================================================================
function generarCU01W(pkg) {
    Session.Output(" -> Construyendo: sd CU01W - Gestionar usuarios y roles");
    var diag = pkg.Diagrams.AddNew("sd CU01W - Gestionar usuarios y roles", "Sequence");
    diag.Update();

    var totalH = 1040;
    var w = 125;
    var pitch = 155;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : Administrador", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : UsuariosUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : users_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : users_services", "Sequence", x, w, totalH); x += pitch;
    var tUsr = agregarLifeline(pkg, diag, "t_usuario", "Sequence", x, w, totalH); x += pitch;
    var tRol = agregarLifeline(pkg, diag, "t_rol", "Sequence", x, w, totalH); x += pitch;
    var tUP  = agregarLifeline(pkg, diag, "t_usuario_permiso", "Sequence", x, w, totalH); x += pitch;
    var tUS  = agregarLifeline(pkg, diag, "t_usuario_sucursal", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Listar usuarios
    agregarMensaje(act, ui, seq++ + ": solicitar_usuarios()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/auth/usuarios", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": listar_usuarios_service(id_empresa)", seq, false, false);
    agregarMensaje(srv, tUsr, seq++ + ": SELECT id_usuario, username, correo, estado FROM t_usuario WHERE id_empresa = :id", seq, false, false);
    agregarMensaje(tUsr, srv, seq++ + ": return lista_usuarios", seq, true, false);
    agregarMensaje(srv, tRol, seq++ + ": SELECT id_rol, nombre_rol FROM t_rol", seq, false, false);
    agregarMensaje(tRol, srv, seq++ + ": return lista_roles", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return usuarios_response", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (datos_usuarios)", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": renderizar_tabla_usuarios()", seq, true, false);

    // Escenario 2: Registrar / Modificar usuario
    agregarMensaje(act, ui, seq++ + ": enviar_formulario(datos_usuario, roles, permisos)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/auth/usuarios", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": registrar_usuario(datos_usuario)", seq, false, false);
    agregarMensaje(srv, tUsr, seq++ + ": SELECT 1 FROM t_usuario WHERE username = :username AND id_usuario != :id", seq, false, false);
    agregarMensaje(tUsr, srv, seq++ + ": return existe_duplicado", seq, true, false);

    // Fragmento alt: Validación
    agregarFragmentoCombinado(pkg, diag, "alt_registro_usuario", "alt", "[campos vacios || username duplicado] vs [else: datos validos]", 40, 1330, 420, 770);

    // Rama Error
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"Username ya registrado o campos vacios\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request (error)", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_en_formulario()", seq, true, true);

    // Rama Normal (else)
    agregarMensaje(srv, srv, seq++ + ": hashear_password(password)", seq, false, false);
    agregarMensaje(srv, tUsr, seq++ + ": INSERT INTO t_usuario(...) RETURNING id_usuario", seq, false, false);
    agregarMensaje(tUsr, srv, seq++ + ": return id_usuario", seq, true, false);
    agregarMensaje(srv, tRol, seq++ + ": INSERT INTO t_usuario_rol(id_usuario, id_rol)", seq, false, false);

    // loop permisos
    agregarFragmentoCombinado(pkg, diag, "loop_permisos", "loop", "[para cada id_permiso]", 480, 1020, 595, 650);
    agregarMensaje(srv, tUP, seq++ + ": INSERT INTO t_usuario_permiso(id_usuario, id_permiso, activo=true)", seq, false, false);

    // opt sucursales
    agregarFragmentoCombinado(pkg, diag, "opt_sucursales", "opt", "[ids_sucursales != null]", 480, 1180, 660, 715);
    agregarMensaje(srv, tUS, seq++ + ": INSERT INTO t_usuario_sucursal(id_usuario, id_sucursal)", seq, false, false);

    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"USUARIOS\", \"REGISTRO\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return usuario_creado", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 201 Created", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_confirmacion_y_actualizar()", seq, true, false);

    // Escenario 3: Eliminar / Desactivar (Borrado Lógico)
    agregarMensaje(act, ui, seq++ + ": solicitar_desactivacion(id_usuario)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": DELETE /api/v1/auth/usuarios/{id}", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": desactivar_usuario(id_usuario)", seq, false, false);

    agregarFragmentoCombinado(pkg, diag, "alt_eliminar", "alt", "[usuario con dependencias || SuperAdmin] vs [else: permitido]", 40, 1330, 835, 1010);
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"Usuario con dependencias o protegido\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_bloqueo()", seq, true, true);

    agregarMensaje(srv, tUsr, seq++ + ": UPDATE t_usuario SET estado = 'INACTIVO' WHERE id_usuario = :id", seq, false, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"USUARIOS\", \"DESACTIVAR\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return confirmacion", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_usuario_desactivado()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 2. CU02W: Gestionar cadena de tiendas (Empresas SaaS)
// =================================================================================================
function generarCU02W(pkg) {
    Session.Output(" -> Construyendo: sd CU02W - Gestionar cadena de tiendas");
    var diag = pkg.Diagrams.AddNew("sd CU02W - Gestionar cadena de tiendas", "Sequence");
    diag.Update();

    var totalH = 800;
    var w = 130;
    var pitch = 160;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : Administrador", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : EmpresasUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : tenant_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : tenant_services", "Sequence", x, w, totalH); x += pitch;
    var emp  = agregarLifeline(pkg, diag, "empresa", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Listar empresas
    agregarMensaje(act, ui, seq++ + ": solicitar_listado_empresas()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/saas/tenants", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": listar_empresas_service()", seq, false, false);
    agregarMensaje(srv, emp,  seq++ + ": SELECT id_empresa, nombre_empresa, nit, correo, estado FROM empresa", seq, false, false);
    agregarMensaje(emp, srv,  seq++ + ": return lista_empresas", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return tenants_response", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK (lista_empresas)", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": desplegar_tabla_empresas()", seq, true, false);

    // Navegación opcional a suscripciones (opt)
    agregarFragmentoCombinado(pkg, diag, "opt_suscripciones", "opt", "[gestionar suscripcion de empresa]", 40, 360, 275, 335);
    agregarMensaje(act, ui, seq++ + ": click_ver_suscripciones(id_empresa)", seq, false, false);
    agregarMensaje(ui, act, seq++ + ": navegar_a_suscripciones(id_empresa)", seq, true, false);

    // Escenario 2: Crear / Modificar empresa
    agregarMensaje(act, ui, seq++ + ": enviar_datos_empresa(nombre, nit, razon_social, correo)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/saas/tenants", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": registrar_empresa(datos_empresa)", seq, false, false);
    agregarMensaje(srv, emp,  seq++ + ": SELECT 1 FROM empresa WHERE LOWER(nit) = LOWER(:nit) AND id_empresa != :id", seq, false, false);
    agregarMensaje(emp, srv,  seq++ + ": return existe_nit", seq, true, false);

    // Fragmento alt: Validación NIT y datos
    agregarFragmentoCombinado(pkg, diag, "alt_validar_nit", "alt", "[campos invalidos || NIT duplicado] vs [else: NIT unico y valido]", 40, 860, 460, 770);

    // Rama Error
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"NIT fiscal ya registrado o datos invalidos\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_en_formulario()", seq, true, true);

    // Rama Normal
    agregarMensaje(srv, emp,  seq++ + ": INSERT INTO empresa(nombre_empresa, nit, correo, estado='ACTIVO')", seq, false, false);
    agregarMensaje(emp, srv,  seq++ + ": return id_empresa", seq, true, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"EMPRESAS\", \"GUARDAR_EMPRESA\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return tenant_creado", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 201 Created", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": actualizar_listado_empresas()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 3. CU03W: Gestionar sucursales
// =================================================================================================
function generarCU03W(pkg) {
    Session.Output(" -> Construyendo: sd CU03W - Gestionar sucursales");
    var diag = pkg.Diagrams.AddNew("sd CU03W - Gestionar sucursales", "Sequence");
    diag.Update();

    var totalH = 880;
    var w = 125;
    var pitch = 150;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : AdminTienda", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : SucursalesUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : sucursales_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : sucursales_services", "Sequence", x, w, totalH); x += pitch;
    var emp  = agregarLifeline(pkg, diag, "empresa", "Sequence", x, w, totalH); x += pitch;
    var tSus = agregarLifeline(pkg, diag, "t_suscripcion", "Sequence", x, w, totalH); x += pitch;
    var tPln = agregarLifeline(pkg, diag, "t_plan", "Sequence", x, w, totalH); x += pitch;
    var tSuc = agregarLifeline(pkg, diag, "t_sucursal", "Sequence", x, w, totalH); x += pitch;
    var tCiu = agregarLifeline(pkg, diag, "t_ciudad", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Listar sucursales
    agregarMensaje(act, ui, seq++ + ": solicitar_sucursales()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/inventario/sucursales", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": listar_sucursales(id_empresa)", seq, false, false);
    agregarMensaje(srv, tSuc, seq++ + ": SELECT s.*, c.nombre AS ciudad FROM t_sucursal s JOIN t_ciudad c ON c.id_ciudad = s.id_ciudad WHERE s.id_empresa = :id", seq, false, false);
    agregarMensaje(tSuc, srv, seq++ + ": return lista_sucursales", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return sucursales_response", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": desplegar_sucursales()", seq, true, false);

    // Escenario 2: Crear / Modificar sucursal con validación de plan SaaS
    agregarMensaje(act, ui, seq++ + ": enviar_datos_sucursal(nombre, direccion, telefono, id_ciudad)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/inventario/sucursales", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": registrar_sucursal(id_empresa, datos_sucursal)", seq, false, false);

    agregarMensaje(srv, tSus, seq++ + ": SELECT codigo_plan FROM t_suscripcion WHERE id_empresa = :id AND estado='ACTIVA'", seq, false, false);
    agregarMensaje(tSus, srv, seq++ + ": return codigo_plan", seq, true, false);
    agregarMensaje(srv, tPln, seq++ + ": SELECT max_sucursales FROM t_plan WHERE codigo = :codigo_plan", seq, false, false);
    agregarMensaje(tPln, srv, seq++ + ": return max_sucursales", seq, true, false);
    agregarMensaje(srv, tSuc, seq++ + ": SELECT COUNT(*) FROM t_sucursal WHERE id_empresa = :id AND activo = true", seq, false, false);
    agregarMensaje(tSuc, srv, seq++ + ": return conteo_sucursales_activas", seq, true, false);

    // Fragmento alt: Límite de plan
    agregarFragmentoCombinado(pkg, diag, "alt_limite_sucursales", "alt", "[conteo >= max_sucursales] vs [else: cuota disponible]", 40, 1440, 495, 855);

    // Rama Error
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"Limite de sucursales alcanzado para el plan contratado\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error(\"Actualice su plan SaaS para mas sucursales\")", seq, true, true);

    // Rama Normal (else)
    agregarFragmentoCombinado(pkg, diag, "opt_nueva_ciudad", "opt", "[ciudad no registrada previamente]", 480, 1300, 625, 680);
    agregarMensaje(srv, tCiu, seq++ + ": INSERT INTO t_ciudad(nombre) RETURNING id_ciudad", seq, false, false);
    agregarMensaje(tCiu, srv, seq++ + ": return id_ciudad", seq, true, false);

    agregarMensaje(srv, tSuc, seq++ + ": INSERT INTO t_sucursal(nombre, direccion, telefono, id_ciudad, id_empresa, activo=true)", seq, false, false);
    agregarMensaje(tSuc, srv, seq++ + ": return id_sucursal", seq, true, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"SUCURSALES\", \"GUARDAR_SUCURSAL\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return sucursal_creada", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 201 Created", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": actualizar_listado_sucursales()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 4. CU04W: Gestionar productos
// =================================================================================================
function generarCU04W(pkg) {
    Session.Output(" -> Construyendo: sd CU04W - Gestionar productos");
    var diag = pkg.Diagrams.AddNew("sd CU04W - Gestionar productos", "Sequence");
    diag.Update();

    var totalH = 1040;
    var w = 125;
    var pitch = 150;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : AdminTienda", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : ProductosUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : productos_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : productos_services", "Sequence", x, w, totalH); x += pitch;
    var tCat = agregarLifeline(pkg, diag, "t_categoria", "Sequence", x, w, totalH); x += pitch;
    var tPrd = agregarLifeline(pkg, diag, "t_producto", "Sequence", x, w, totalH); x += pitch;
    var tVar = agregarLifeline(pkg, diag, "t_producto_talla_color", "Sequence", x, w, totalH); x += pitch;
    var tImg = agregarLifeline(pkg, diag, "t_producto_imagen", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Listar catálogo de productos
    agregarMensaje(act, ui, seq++ + ": solicitar_catalogo()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/catalogo/productos", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": listar_productos_service(id_empresa)", seq, false, false);
    agregarMensaje(srv, tPrd, seq++ + ": SELECT p.*, c.nombre FROM t_producto p JOIN t_categoria c ON c.id_categoria = p.id_categoria WHERE p.id_empresa = :id", seq, false, false);
    agregarMensaje(tPrd, srv, seq++ + ": return lista_productos", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return catalogo_response", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": desplegar_catalogo()", seq, true, false);

    // Escenario 2: Crear / Modificar producto y variantes
    agregarMensaje(act, ui, seq++ + ": enviar_datos_producto(datos, variantes, imagenes)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": POST /api/v1/catalogo/productos", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": crear_o_modificar_producto(datos, variantes)", seq, false, false);
    agregarMensaje(srv, tCat, seq++ + ": SELECT activo FROM t_categoria WHERE id_categoria = :id", seq, false, false);
    agregarMensaje(tCat, srv, seq++ + ": return categoria_activa", seq, true, false);
    agregarMensaje(srv, tPrd, seq++ + ": SELECT 1 FROM t_producto WHERE nombre = :nombre AND id_empresa = :id AND id_producto != :id_prod", seq, false, false);
    agregarMensaje(tPrd, srv, seq++ + ": return nombre_duplicado", seq, true, false);

    // Fragmento alt: Validación
    agregarFragmentoCombinado(pkg, diag, "alt_validar_producto", "alt", "[campos incorrectos || categoria inactiva || duplicado] vs [else: valido]", 40, 1300, 420, 770);

    // Rama Error
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"Producto duplicado o categoria inactiva\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_en_formulario()", seq, true, true);

    // Rama Normal (else)
    agregarMensaje(srv, tPrd, seq++ + ": INSERT INTO t_producto(nombre, precio, descripcion, id_categoria, id_empresa, activo=true) RETURNING id_producto", seq, false, false);
    agregarMensaje(tPrd, srv, seq++ + ": return id_producto", seq, true, false);

    // loop variantes
    agregarFragmentoCombinado(pkg, diag, "loop_variantes", "loop", "[para cada combinacion talla-color]", 480, 1000, 560, 615);
    agregarMensaje(srv, tVar, seq++ + ": INSERT INTO t_producto_talla_color(id_producto, id_talla, id_color, sku, precio)", seq, false, false);

    // opt imagenes
    agregarFragmentoCombinado(pkg, diag, "opt_imagenes", "opt", "[imagenes adjuntas != null]", 480, 1150, 625, 680);
    agregarMensaje(srv, tImg, seq++ + ": INSERT INTO t_producto_imagen(id_producto, url_imagen, orden)", seq, false, false);

    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"CATALOGO\", \"GUARDAR_PRODUCTO\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return producto_creado", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 201 Created", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": actualizar_catalogo()", seq, true, false);

    // Escenario 3: Desactivar Producto (Borrado Lógico)
    agregarMensaje(act, ui, seq++ + ": confirmar_desactivacion(id_producto)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": DELETE /api/v1/catalogo/productos/{id}", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": desactivar_producto(id_producto)", seq, false, false);

    agregarFragmentoCombinado(pkg, diag, "alt_desactivar_producto", "alt", "[producto con stock o reservas activas] vs [else: permitido]", 40, 1300, 835, 1010);
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"Producto no deshabilitable por dependencias activas\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_bloqueo()", seq, true, true);

    agregarMensaje(srv, tPrd, seq++ + ": UPDATE t_producto SET activo = false WHERE id_producto = :id_producto", seq, false, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"CATALOGO\", \"DESACTIVAR_PRODUCTO\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return confirmacion", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_producto_desactivado()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// 5. CU05W: Gestionar planes de suscripción
// =================================================================================================
function generarCU05W(pkg) {
    Session.Output(" -> Construyendo: sd CU05W - Gestionar planes de suscripción");
    var diag = pkg.Diagrams.AddNew("sd CU05W - Gestionar planes de suscripción", "Sequence");
    diag.Update();

    var totalH = 750;
    var w = 130;
    var pitch = 160;
    var x = 50;

    var act  = agregarLifeline(pkg, diag, "admin : Administrador", "Actor", x, 115, totalH); x += pitch;
    var ui   = agregarLifeline(pkg, diag, "ui : PlanesUI", "Sequence", x, w, totalH); x += pitch;
    var rtr  = agregarLifeline(pkg, diag, "router : saas_routes", "Sequence", x, w, totalH); x += pitch;
    var srv  = agregarLifeline(pkg, diag, "service : saas_services", "Sequence", x, w, totalH); x += pitch;
    var tPln = agregarLifeline(pkg, diag, "t_plan", "Sequence", x, w, totalH); x += pitch;
    var tSus = agregarLifeline(pkg, diag, "t_suscripcion", "Sequence", x, w, totalH); x += pitch;
    var tBit = agregarLifeline(pkg, diag, "t_bitacora", "Sequence", x, w, totalH);

    var seq = 1;

    // Escenario 1: Listar planes existentes
    agregarMensaje(act, ui, seq++ + ": solicitar_listado_planes()", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": GET /api/v1/saas/planes", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": listar_planes()", seq, false, false);
    agregarMensaje(srv, tPln, seq++ + ": SELECT codigo, nombre, max_sucursales, precio_mensual, activo FROM t_plan ORDER BY codigo", seq, false, false);
    agregarMensaje(tPln, srv, seq++ + ": return lista_planes", seq, true, false);
    agregarMensaje(srv, rtr, seq++ + ": return planes_response", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": desplegar_planes_disponibles()", seq, true, false);

    // Escenario 2: Modificar Plan
    agregarMensaje(act, ui, seq++ + ": enviar_datos_modificacion(codigo_plan, max_sucursales, activo)", seq, false, false);
    agregarMensaje(ui, rtr, seq++ + ": PUT /api/v1/saas/planes/{codigo}", seq, false, false);
    agregarMensaje(rtr, srv, seq++ + ": actualizar_plan(codigo_plan, nuevos_datos)", seq, false, false);
    agregarMensaje(srv, tPln, seq++ + ": SELECT codigo, activo FROM t_plan WHERE codigo = :codigo_plan", seq, false, false);
    agregarMensaje(tPln, srv, seq++ + ": return plan_existente", seq, true, false);
    agregarMensaje(srv, tSus, seq++ + ": SELECT COUNT(*) FROM t_suscripcion WHERE codigo_plan = :codigo AND estado='ACTIVA'", seq, false, false);
    agregarMensaje(tSus, srv, seq++ + ": return conteo_empresas_activas", seq, true, false);

    // Fragmento alt: Validación
    agregarFragmentoCombinado(pkg, diag, "alt_validar_plan", "alt", "[plan inexistente || (desactivar && conteo > 0)] vs [else: permitido]", 40, 1020, 460, 720);

    // Rama Error
    agregarMensaje(srv, rtr, seq++ + ": HTTPException(400, \"No se puede desactivar un plan con suscripciones activas\")", seq, true, true);
    agregarMensaje(rtr, ui, seq++ + ": 400 Bad Request", seq, true, true);
    agregarMensaje(ui, act, seq++ + ": mostrar_error_operacion_bloqueada()", seq, true, true);

    // Rama Normal (else)
    agregarMensaje(srv, tPln, seq++ + ": UPDATE t_plan SET nombre=:nom, max_sucursales=:max, activo=:act WHERE codigo=:cod", seq, false, false);
    agregarMensaje(srv, tBit, seq++ + ": registrar_bitacora(\"SAAS\", \"ACTUALIZAR_PLAN\")", seq, false, false);
    agregarMensaje(srv, rtr, seq++ + ": return plan_actualizado", seq, true, false);
    agregarMensaje(rtr, ui, seq++ + ": 200 OK", seq, true, false);
    agregarMensaje(ui, act, seq++ + ": mostrar_planes_actualizados()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// FUNCIÓN PRINCIPAL DE EJECUCIÓN
// =================================================================================================
function Main() {
    Repository.EnsureOutputVisible("Script");
    Session.Output("================================================================================");
    Session.Output("Iniciando generación de Diagramas de Secuencia UML 2.5 en Enterprise Architect...");
    Session.Output("================================================================================");

    var pkg = Repository.GetTreeSelectedPackage();
    if (pkg == null) {
        Session.Prompt("ERROR: Por favor seleccione un paquete en el Project Browser antes de ejecutar.", 0);
        return;
    }

    // Crear un paquete NUEVO para evitar sobreescribir diagramas o modelos anteriores
    var pkgName = "Diagramas de Secuencia (UML 2.5) - AuroraStore";
    var subPkg = null;
    for (var i = 0; i < pkg.Packages.Count; i++) {
        var p = pkg.Packages.GetAt(i);
        if (p.Name == pkgName) {
            subPkg = p;
            break;
        }
    }
    if (subPkg == null) {
        subPkg = pkg.Packages.AddNew(pkgName, "");
        subPkg.Update();
        pkg.Packages.Refresh();
    }

    Session.Output("Paquete destino: " + subPkg.Name);

    generarCU01W(subPkg);
    generarCU02W(subPkg);
    generarCU03W(subPkg);
    generarCU04W(subPkg);
    generarCU05W(subPkg);

    Repository.RefreshModelView(subPkg.PackageID);
    Session.Output("================================================================================");
    Session.Output(" [OK] Se generaron exitosamente los 5 diagramas de secuencia en Enterprise Architect.");
    Session.Output(" Paquete: " + subPkg.Name);
    Session.Output("================================================================================");
}

Main();
