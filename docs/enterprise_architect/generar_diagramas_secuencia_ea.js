/*
 * =================================================================================================
 * SCRIPT MAESTRO DE AUTOMATIZACIÓN DE DIAGRAMAS DE SECUENCIA UML 2.5 (BCE) PARA ENTERPRISE ARCHITECT
 * =================================================================================================
 * Proyecto: AuroraStore SaaS
 * Casos de Uso soportados:
 *   - CU01W: Gestionar usuarios y roles
 *   - CU02W: Gestionar cadena de tiendas / Empresas SaaS
 *   - CU03W: Gestionar sucursales
 *   - CU04W: Gestionar productos y catálogo
 *   - CU05W: Gestionar planes de suscripción
 *   - CU12W / CU03M: Consultar detalles de producto (Online / Modo Offline)
 *   - CU13W / CU04M: Consultar disponibilidad por sucursal (Online / Modo Offline)
 *   - CU14W / CU05M: Gestionar reservas de stock (Online / Modo Offline)
 *
 * Arquitectura BCE estricta:
 *   ACTOR -> BOUNDARY («boundary») -> CONTROLLER («control») -> ENTITY («entity»)
 *
 * Instrucciones de ejecución en Enterprise Architect:
 * 1. Abrir Sparx Enterprise Architect.
 * 2. Ir a la pestaña: Develop > Scripting (o pulsar Ctrl + F9 / Tools > Scripting).
 * 3. En la ventana "Scripting", ubicarse en un Script Group (ej. "New group" o crear uno tipo JScript).
 * 4. Crear un nuevo script (JScript) o abrir el existente.
 * 5. Reemplazar TODO el código por este contenido completo y guardar (Ctrl + S).
 * 6. En el Project Browser (árbol del proyecto), seleccionar el paquete donde desea crear los diagramas.
 * 7. Hacer clic en "Run" (botón de reproducción verde).
 * =================================================================================================
 */

// Helpers de Posicionamiento y Creación de Elementos en EA
function crearLifeline(pkg, diag, nombre, tipo, estereotipo, posX, ancho, alto) {
    var eaType = "Object";
    if (tipo == "Actor") {
        eaType = "Actor";
    } else if (tipo == "Boundary" || estereotipo == "boundary") {
        eaType = "Boundary";
    } else if (tipo == "Class") {
        eaType = "Class";
    }

    var el = pkg.Elements.AddNew(nombre, eaType);
    if (estereotipo && estereotipo != "") {
        el.Stereotype = estereotipo;
    }
    el.Update();

    var left = posX;
    var right = posX + ancho;
    var top = 70;
    var bottom = top + alto;

    var diagObj = diag.DiagramObjects.AddNew("l=" + left + ";r=" + right + ";t=" + top + ";b=" + bottom + ";", "");
    diagObj.ElementID = el.ElementID;
    diagObj.Update();

    return el;
}

function crearMensaje(sourceEl, targetEl, nombre, seqNum, esRetorno, esError) {
    if (!sourceEl || !targetEl) return null;
    
    var conn = sourceEl.Connectors.AddNew(nombre, "Sequence");
    conn.SupplierID = targetEl.ElementID;
    
    if (esError) {
        conn.Stereotype = "error";
        conn.Notes = "EXCEPTION_FLOW";
    }
    
    conn.Update();
    sourceEl.Connectors.Refresh();

    // En Enterprise Architect Automation, los atributos de retorno y SeqNo 
    // se sincronizan a través de t_connector de forma segura y portable
    try {
        if (esRetorno) {
            Repository.Execute("UPDATE t_connector SET PDATA4 = '1' WHERE Connector_ID = " + conn.ConnectorID);
        }
        if (seqNum > 0) {
            Repository.Execute("UPDATE t_connector SET SeqNo = " + seqNum + " WHERE Connector_ID = " + conn.ConnectorID);
        }
    } catch (ex) {
        // Fallback transparente: el orden secuencial se mantiene por el flujo cronológico
    }
    return conn;
}

function crearFragmentoCombinado(pkg, diag, nombre, tipoFragmento, guarda, left, right, top, bottom) {
    var frag = pkg.Elements.AddNew(nombre, "InteractionFragment");
    frag.Stereotype = tipoFragmento; // "alt", "opt", "loop"
    frag.Notes = guarda;
    frag.Update();

    var fragObj = diag.DiagramObjects.AddNew("l=" + left + ";r=" + right + ";t=" + top + ";b=" + bottom + ";", "");
    fragObj.ElementID = frag.ElementID;
    fragObj.Update();
    return frag;
}

// =================================================================================================
// CU01W: Gestionar usuarios y roles
// =================================================================================================
function generarCU01W(pkg) {
    Session.Output(" -> Generando: sd CU01W - Gestionar usuarios");
    var diag = pkg.Diagrams.AddNew("sd CU01W - Gestionar usuarios", "Sequence");
    diag.Update();

    var h = 950;
    var act  = crearLifeline(pkg, diag, "Administrador / Admin Tienda", "Actor", "", 50, 90, h);
    var bUrl = crearLifeline(pkg, diag, "URL: Gestión Usuarios", "Boundary", "boundary", 200, 95, h);
    var bLst = crearLifeline(pkg, diag, "ListaUsuarios", "Boundary", "boundary", 340, 85, h);
    var bFrm = crearLifeline(pkg, diag, "Modal: Formulario Registro", "Boundary", "boundary", 470, 95, h);
    var bDel = crearLifeline(pkg, diag, "Pantalla Eliminar Usuario", "Boundary", "boundary", 610, 95, h);
    var bErr = crearLifeline(pkg, diag, "Ventana: Error", "Boundary", "boundary", 750, 85, h);
    var ctl  = crearLifeline(pkg, diag, "UsuarioControl", "Control", "control", 880, 95, h);
    var tUsr = crearLifeline(pkg, diag, "t_usuario", "Entity", "entity", 1020, 85, h);
    var tRol = crearLifeline(pkg, diag, "t_rol", "Entity", "entity", 1150, 80, h);
    var tUR  = crearLifeline(pkg, diag, "t_usuario_rol", "Entity", "entity", 1270, 90, h);
    var tPer = crearLifeline(pkg, diag, "t_permiso", "Entity", "entity", 1400, 85, h);
    var tUP  = crearLifeline(pkg, diag, "t_usuario_permiso", "Entity", "entity", 1530, 95, h);
    var tUS  = crearLifeline(pkg, diag, "t_usuario_sucursal", "Entity", "entity", 1670, 95, h);
    var tBit = crearLifeline(pkg, diag, "t_bitacora", "Entity", "entity", 1810, 85, h);

    var seq = 1;

    // Escenario 1: Listar
    crearMensaje(act, bUrl, seq++ + ": acceder_gestion_usuarios()", seq, false, false);
    crearMensaje(bUrl, ctl, seq++ + ": listar_usuarios(id_empresa)", seq, false, false);
    crearMensaje(ctl, tUsr, seq++ + ": SELECT id_usuario, username, estado FROM t_usuario WHERE id_empresa = :id", seq, false, false);
    crearMensaje(tUsr, ctl, seq++ + ": return lista_usuarios", seq, true, false);
    crearMensaje(ctl, tRol, seq++ + ": SELECT id_rol, nombre_rol FROM t_rol", seq, false, false);
    crearMensaje(tRol, ctl, seq++ + ": return lista_roles", seq, true, false);
    crearMensaje(ctl, bLst, seq++ + ": renderizar_usuarios(lista_usuarios, lista_roles)", seq, false, false);

    // Escenario 2: Registrar / Modificar
    crearMensaje(act, bFrm, seq++ + ": enviar_formulario_usuario(datos_usuario)", seq, false, false);
    crearMensaje(bFrm, ctl, seq++ + ": procesar_registro(datos_usuario)", seq, false, false);
    crearMensaje(ctl, tUsr, seq++ + ": SELECT 1 FROM t_usuario WHERE username = :username", seq, false, false);
    crearMensaje(tUsr, ctl, seq++ + ": return usuario_existente", seq, true, false);

    // Fragmento alt: Validación de duplicidad
    crearFragmentoCombinado(pkg, diag, "alt_registro_usuario", "alt", "[campos vacios || username duplicado] vs [else: datos validos]", 450, 1890, 370, 680);
    
    // Rama Error (Nodo Rojo)
    crearMensaje(ctl, bErr, seq++ + ": notificar_error(\"Nombre de usuario ya existente\")", seq, false, true);
    crearMensaje(bErr, act, seq++ + ": mostrar_error_en_formulario()", seq, true, true);

    // Rama Normal (else)
    crearMensaje(ctl, ctl, seq++ + ": hashear_password(password)", seq, false, false);
    crearMensaje(ctl, tUsr, seq++ + ": INSERT INTO t_usuario(username, correo, password_hash, id_empresa, estado)", seq, false, false);
    crearMensaje(tUsr, ctl, seq++ + ": return id_usuario", seq, true, false);
    crearMensaje(ctl, tUR, seq++ + ": INSERT INTO t_usuario_rol(id_usuario, id_rol)", seq, false, false);

    // loop permisos
    crearFragmentoCombinado(pkg, diag, "loop_permisos", "loop", "[para cada id_permiso asignado]", 860, 1640, 520, 580);
    crearMensaje(ctl, tUP, seq++ + ": INSERT INTO t_usuario_permiso(id_usuario, id_permiso, activo)", seq, false, false);

    // opt sucursales
    crearFragmentoCombinado(pkg, diag, "opt_sucursales", "opt", "[ids_sucursales asignadas != null]", 860, 1780, 590, 650);
    crearMensaje(ctl, tUS, seq++ + ": INSERT INTO t_usuario_sucursal(id_usuario, id_sucursal)", seq, false, false);

    crearMensaje(ctl, tBit, seq++ + ": INSERT INTO t_bitacora(id_usuario, modulo='USUARIOS', accion='USUARIO_REGISTRADO', ...)", seq, false, false);
    crearMensaje(ctl, bFrm, seq++ + ": confirmar_registro_exitoso(id_usuario)", seq, true, false);
    crearMensaje(bFrm, act, seq++ + ": mostrar_confirmacion_y_actualizar()", seq, true, false);

    // Escenario 3: Eliminar / Desactivar
    crearMensaje(act, bDel, seq++ + ": solicitar_desactivacion(id_usuario)", seq, false, false);
    crearMensaje(bDel, ctl, seq++ + ": desactivar_usuario(id_usuario)", seq, false, false);

    crearFragmentoCombinado(pkg, diag, "alt_eliminar", "alt", "[usuario con dependencias activas || SuperAdmin] vs [else: permitido]", 590, 1890, 750, 920);
    crearMensaje(ctl, bErr, seq++ + ": notificar_error(\"No se puede desactivar usuario con dependencias activas\")", seq, false, true);
    crearMensaje(bErr, act, seq++ + ": mostrar_error_bloqueo()", seq, true, true);

    crearMensaje(ctl, tUsr, seq++ + ": UPDATE t_usuario SET estado = 'INACTIVO' WHERE id_usuario = :id_usuario", seq, false, false);
    crearMensaje(ctl, tBit, seq++ + ": INSERT INTO t_bitacora(id_usuario, modulo='USUARIOS', accion='DESACTIVAR_USUARIO', ...)", seq, false, false);
    crearMensaje(ctl, bDel, seq++ + ": confirmar_desactivacion()", seq, true, false);
    crearMensaje(bDel, act, seq++ + ": mostrar_usuario_desactivado()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// CU02W: Gestionar cadena de tiendas (Empresas SaaS)
// =================================================================================================
function generarCU02W(pkg) {
    Session.Output(" -> Generando: sd CU02W - Gestionar cadena de tiendas");
    var diag = pkg.Diagrams.AddNew("sd CU02W - Gestionar cadena de tiendas", "Sequence");
    diag.Update();

    var h = 820;
    var act  = crearLifeline(pkg, diag, "Administrador (SuperAdmin)", "Actor", "", 50, 90, h);
    var bUrl = crearLifeline(pkg, diag, "URL: Empresas", "Boundary", "boundary", 200, 90, h);
    var bLst = crearLifeline(pkg, diag, "Lista empresas", "Boundary", "boundary", 340, 85, h);
    var bSus = crearLifeline(pkg, diag, "Suscripciones", "Boundary", "boundary", 470, 85, h);
    var bFrm = crearLifeline(pkg, diag, "Formulario Crear/modificar", "Boundary", "boundary", 600, 95, h);
    var bErr = crearLifeline(pkg, diag, "Formulario: Error", "Boundary", "boundary", 740, 85, h);
    var ctl  = crearLifeline(pkg, diag, "EmpresaControl", "Control", "control", 870, 95, h);
    var emp  = crearLifeline(pkg, diag, "empresa", "Entity", "entity", 1020, 85, h);
    var tPln = crearLifeline(pkg, diag, "t_plan", "Entity", "entity", 1150, 80, h);
    var tSus = crearLifeline(pkg, diag, "t_suscripcion", "Entity", "entity", 1270, 90, h);
    var tBit = crearLifeline(pkg, diag, "t_bitacora", "Entity", "entity", 1400, 85, h);

    var seq = 1;

    // Escenario 1: Listar
    crearMensaje(act, bUrl, seq++ + ": solicitar_listado_empresas()", seq, false, false);
    crearMensaje(bUrl, ctl, seq++ + ": listar_empresas()", seq, false, false);
    crearMensaje(ctl, emp,  seq++ + ": SELECT id_empresa, nombre_empresa, nit, correo, estado FROM empresa", seq, false, false);
    crearMensaje(emp, ctl,  seq++ + ": return lista_empresas", seq, true, false);
    crearMensaje(ctl, bLst, seq++ + ": mostrar_empresas(lista_empresas)", seq, false, false);

    // Navegar suscripciones (opt)
    crearFragmentoCombinado(pkg, diag, "opt_navegar_suscripciones", "opt", "[clic en ver suscripciones]", 180, 520, 260, 320);
    crearMensaje(act, bUrl, seq++ + ": click_ver_suscripciones()", seq, false, false);
    crearMensaje(bUrl, bSus, seq++ + ": navegar_a_suscripciones()", seq, false, false);

    // Escenario 2: Crear / Modificar
    crearMensaje(act, bFrm, seq++ + ": enviar_datos_empresa(datos_empresa)", seq, false, false);
    crearMensaje(bFrm, ctl, seq++ + ": registrar_empresa(datos_empresa)", seq, false, false);
    crearMensaje(ctl, emp,  seq++ + ": SELECT 1 FROM empresa WHERE LOWER(nit) = LOWER(:nit) AND id != :id", seq, false, false);
    crearMensaje(emp, ctl,  seq++ + ": return nit_duplicado", seq, true, false);

    crearFragmentoCombinado(pkg, diag, "alt_validar_nit", "alt", "[campos invalidos || NIT duplicado] vs [else: NIT unico]", 580, 1490, 440, 750);
    
    // Rama Error
    crearMensaje(ctl, bErr, seq++ + ": notificar_error(\"NIT fiscal ya registrado\")", seq, false, true);
    crearMensaje(bErr, act, seq++ + ": mostrar_error_en_formulario()", seq, true, true);

    // Rama Normal
    crearMensaje(ctl, emp,  seq++ + ": INSERT INTO empresa(nombre_empresa, razon_social, nit, correo, estado='ACTIVO')", seq, false, false);
    crearMensaje(emp, ctl,  seq++ + ": return id_empresa", seq, true, false);

    crearFragmentoCombinado(pkg, diag, "opt_plan_inicial", "opt", "[empresa nueva == true]", 850, 1370, 570, 660);
    crearMensaje(ctl, tPln, seq++ + ": SELECT codigo, max_sucursales FROM t_plan WHERE codigo = 'BASICO'", seq, false, false);
    crearMensaje(tPln, ctl, seq++ + ": return datos_plan_base", seq, true, false);
    crearMensaje(ctl, tSus, seq++ + ": INSERT INTO t_suscripcion(id_empresa, codigo_plan, estado='ACTIVA', inicio, fin)", seq, false, false);

    crearMensaje(ctl, tBit, seq++ + ": INSERT INTO t_bitacora(id_usuario, id_empresa, modulo='EMPRESAS', accion='CREAR_EMPRESA', ...)", seq, false, false);
    crearMensaje(ctl, bUrl, seq++ + ": confirmar_empresa_creada(id_empresa)", seq, true, false);
    crearMensaje(bUrl, act, seq++ + ": actualizar_listado_empresas()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// CU03W: Gestionar sucursales
// =================================================================================================
function generarCU03W(pkg) {
    Session.Output(" -> Generando: sd CU03W - Gestionar sucursales");
    var diag = pkg.Diagrams.AddNew("sd CU03W - Gestionar sucursales", "Sequence");
    diag.Update();

    var h = 850;
    var act  = crearLifeline(pkg, diag, "Administrador Tienda", "Actor", "", 50, 90, h);
    var bUrl = crearLifeline(pkg, diag, "URL: Gestion sucursales", "Boundary", "boundary", 200, 95, h);
    var bLst = crearLifeline(pkg, diag, "Lista sucursales", "Boundary", "boundary", 340, 85, h);
    var bFrm = crearLifeline(pkg, diag, "Formulario Crear/modificar", "Boundary", "boundary", 470, 95, h);
    var bErr = crearLifeline(pkg, diag, "Formulario: Error", "Boundary", "boundary", 610, 85, h);
    var ctl  = crearLifeline(pkg, diag, "SucursalControl", "Control", "control", 740, 95, h);
    var emp  = crearLifeline(pkg, diag, "empresa", "Entity", "entity", 880, 80, h);
    var tSus = crearLifeline(pkg, diag, "t_suscripcion", "Entity", "entity", 1000, 90, h);
    var tPln = crearLifeline(pkg, diag, "t_plan", "Entity", "entity", 1130, 80, h);
    var tSuc = crearLifeline(pkg, diag, "t_sucursal", "Entity", "entity", 1250, 85, h);
    var tCiu = crearLifeline(pkg, diag, "t_ciudad", "Entity", "entity", 1380, 80, h);
    var tBit = crearLifeline(pkg, diag, "t_bitacora", "Entity", "entity", 1500, 85, h);

    var seq = 1;

    // Escenario 1: Listar
    crearMensaje(act, bUrl, seq++ + ": solicitar_sucursales()", seq, false, false);
    crearMensaje(bUrl, ctl, seq++ + ": listar_sucursales(id_empresa)", seq, false, false);
    crearMensaje(ctl, tSuc, seq++ + ": SELECT s.*, c.nombre FROM t_sucursal s JOIN t_ciudad c ON c.id_ciudad = s.id_ciudad WHERE s.id_empresa = :id", seq, false, false);
    crearMensaje(tSuc, ctl, seq++ + ": return lista_sucursales", seq, true, false);
    crearMensaje(ctl, bLst, seq++ + ": mostrar_sucursales(lista_sucursales)", seq, false, false);

    // Escenario 2: Crear / Modificar
    crearMensaje(act, bFrm, seq++ + ": enviar_datos_sucursal(datos_sucursal)", seq, false, false);
    crearMensaje(bFrm, ctl, seq++ + ": registrar_sucursal(datos_sucursal)", seq, false, false);

    crearMensaje(ctl, tSus, seq++ + ": SELECT codigo_plan FROM t_suscripcion WHERE id_empresa = :id AND estado='ACTIVA'", seq, false, false);
    crearMensaje(tSus, ctl, seq++ + ": return codigo_plan", seq, true, false);
    crearMensaje(ctl, tPln, seq++ + ": SELECT max_sucursales FROM t_plan WHERE codigo = :codigo_plan", seq, false, false);
    crearMensaje(tPln, ctl, seq++ + ": return max_sucursales", seq, true, false);
    crearMensaje(ctl, tSuc, seq++ + ": SELECT COUNT(*) FROM t_sucursal WHERE id_empresa = :id AND activo = true", seq, false, false);
    crearMensaje(tSuc, ctl, seq++ + ": return conteo_sucursales_activas", seq, true, false);

    crearFragmentoCombinado(pkg, diag, "alt_limite_sucursales", "alt", "[conteo >= max_sucursales] vs [else: conteo < max_sucursales]", 450, 1590, 440, 780);

    // Rama Error
    crearMensaje(ctl, bErr, seq++ + ": notificar_error(\"Limite de sucursales alcanzado para el plan contratado\")", seq, false, true);
    crearMensaje(bErr, act, seq++ + ": mostrar_error(\"Actualice su plan para habilitar mas sucursales\")", seq, true, true);

    // Rama Normal
    crearFragmentoCombinado(pkg, diag, "opt_nueva_ciudad", "opt", "[ciudad no registrada previamente]", 720, 1460, 560, 620);
    crearMensaje(ctl, tCiu, seq++ + ": INSERT INTO t_ciudad(nombre, codigo_pais) RETURNING id_ciudad", seq, false, false);
    crearMensaje(tCiu, ctl, seq++ + ": return id_ciudad_nuevo", seq, true, false);

    crearMensaje(ctl, tSuc, seq++ + ": INSERT INTO t_sucursal(nombre, direccion, telefono, id_ciudad, id_empresa, activo=true)", seq, false, false);
    crearMensaje(tSuc, ctl, seq++ + ": return id_sucursal", seq, true, false);
    crearMensaje(ctl, tBit, seq++ + ": INSERT INTO t_bitacora(id_usuario, id_empresa, modulo='SUCURSALES', accion='CREAR_SUCURSAL', ...)", seq, false, false);
    crearMensaje(ctl, bUrl, seq++ + ": redirigir_a_gestion_sucursales()", seq, false, false);
    crearMensaje(bUrl, act, seq++ + ": actualizar_listado()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// CU04W: Gestionar productos y catálogo
// =================================================================================================
function generarCU04W(pkg) {
    Session.Output(" -> Generando: sd CU04W - Gestionar productos");
    var diag = pkg.Diagrams.AddNew("sd CU04W - Gestionar productos", "Sequence");
    diag.Update();

    var h = 950;
    var act  = crearLifeline(pkg, diag, "Administrador Tienda", "Actor", "", 50, 90, h);
    var bUrl = crearLifeline(pkg, diag, "URL: Gestion productos", "Boundary", "boundary", 200, 95, h);
    var bLst = crearLifeline(pkg, diag, "Lista productos", "Boundary", "boundary", 340, 85, h);
    var bFrm = crearLifeline(pkg, diag, "Formulario Registrar/modificar", "Boundary", "boundary", 470, 95, h);
    var bDel = crearLifeline(pkg, diag, "Ventana confirmacion", "Boundary", "boundary", 610, 90, h);
    var bErr = crearLifeline(pkg, diag, "Formulario: Error", "Boundary", "boundary", 740, 85, h);
    var ctl  = crearLifeline(pkg, diag, "ProductoControl", "Control", "control", 870, 95, h);
    var tCat = crearLifeline(pkg, diag, "t_categoria", "Entity", "entity", 1010, 85, h);
    var tPrd = crearLifeline(pkg, diag, "t_producto", "Entity", "entity", 1140, 85, h);
    var tTal = crearLifeline(pkg, diag, "t_talla", "Entity", "entity", 1270, 80, h);
    var tCol = crearLifeline(pkg, diag, "t_color", "Entity", "entity", 1390, 80, h);
    var tVar = crearLifeline(pkg, diag, "t_producto_talla_color", "Entity", "entity", 1510, 95, h);
    var tImg = crearLifeline(pkg, diag, "t_imagen_producto", "Entity", "entity", 1650, 90, h);
    var tBit = crearLifeline(pkg, diag, "t_bitacora", "Entity", "entity", 1780, 85, h);

    var seq = 1;

    // Escenario 1: Listar
    crearMensaje(act, bUrl, seq++ + ": solicitar_catalogo()", seq, false, false);
    crearMensaje(bUrl, ctl, seq++ + ": listar_productos(id_empresa)", seq, false, false);
    crearMensaje(ctl, tPrd, seq++ + ": SELECT p.*, c.nombre FROM t_producto p JOIN t_categoria c ON c.id_categoria = p.id_categoria", seq, false, false);
    crearMensaje(tPrd, ctl, seq++ + ": return lista_productos", seq, true, false);
    crearMensaje(ctl, bLst, seq++ + ": mostrar_productos(lista_productos)", seq, false, false);

    // Escenario 2: Crear / Modificar
    crearMensaje(act, bFrm, seq++ + ": enviar_datos_producto(datos, variantes, imagenes)", seq, false, false);
    crearMensaje(bFrm, ctl, seq++ + ": crear_o_modificar_producto(datos, variantes)", seq, false, false);
    crearMensaje(ctl, tCat, seq++ + ": SELECT activo FROM t_categoria WHERE id_categoria = :id", seq, false, false);
    crearMensaje(tCat, ctl, seq++ + ": return categoria_activa", seq, true, false);
    crearMensaje(ctl, tPrd, seq++ + ": SELECT 1 FROM t_producto WHERE nombre = :nombre AND id_empresa = :id", seq, false, false);
    crearMensaje(tPrd, ctl, seq++ + ": return nombre_duplicado", seq, true, false);

    crearFragmentoCombinado(pkg, diag, "alt_validar_producto", "alt", "[campos incorrectos || categoria inactiva || duplicado] vs [else: valido]", 450, 1870, 390, 710);
    
    // Rama Error
    crearMensaje(ctl, bErr, seq++ + ": notificar_error(\"Producto duplicado o categoria inactiva\")", seq, false, true);
    crearMensaje(bErr, act, seq++ + ": mostrar_error_en_formulario()", seq, true, true);

    // Rama Normal
    crearMensaje(ctl, tPrd, seq++ + ": INSERT INTO t_producto(nombre, precio, descripcion, id_categoria, id_empresa, activo=true)", seq, false, false);
    crearMensaje(tPrd, ctl, seq++ + ": return id_producto", seq, true, false);

    crearFragmentoCombinado(pkg, diag, "loop_variantes", "loop", "[para cada variante (talla, color, sku)]", 850, 1610, 520, 580);
    crearMensaje(ctl, tVar, seq++ + ": INSERT INTO t_producto_talla_color(id_producto, id_talla, id_color, sku, precio)", seq, false, false);

    crearFragmentoCombinado(pkg, diag, "opt_imagenes", "opt", "[imagenes adjuntas != null]", 850, 1740, 590, 650);
    crearMensaje(ctl, tImg, seq++ + ": INSERT INTO t_imagen_producto(id_producto, url_imagen, orden)", seq, false, false);

    crearMensaje(ctl, tBit, seq++ + ": INSERT INTO t_bitacora(id_usuario, id_empresa, modulo='CATALOGO', accion='PRODUCTO_CREADO', ...)", seq, false, false);
    crearMensaje(ctl, bUrl, seq++ + ": redirigir_a_gestion_productos()", seq, false, false);
    crearMensaje(bUrl, act, seq++ + ": actualizar_catalogo()", seq, true, false);

    // Escenario 3: Desactivar Producto
    crearMensaje(act, bDel, seq++ + ": confirmar_desactivacion(id_producto)", seq, false, false);
    crearMensaje(bDel, ctl, seq++ + ": desactivar_producto(id_producto)", seq, false, false);

    crearFragmentoCombinado(pkg, diag, "alt_desactivar_producto", "alt", "[producto con dependencias activas] vs [else: permitido]", 590, 1870, 780, 930);
    crearMensaje(ctl, bErr, seq++ + ": notificar_error(\"Producto no deshabilitable por dependencias activas\")", seq, false, true);
    crearMensaje(bErr, act, seq++ + ": mostrar_error_bloqueo()", seq, true, true);

    crearMensaje(ctl, tPrd, seq++ + ": UPDATE t_producto SET activo = false WHERE id_producto = :id_producto", seq, false, false);
    crearMensaje(ctl, tBit, seq++ + ": INSERT INTO t_bitacora(id_usuario, modulo='CATALOGO', accion='DESACTIVAR_PRODUCTO', ...)", seq, false, false);
    crearMensaje(ctl, bDel, seq++ + ": mostrar_desactivacion()", seq, true, false);
    crearMensaje(bDel, act, seq++ + ": confirmar_desactivacion_exitosa()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// CU05W: Gestionar planes de suscripción
// =================================================================================================
function generarCU05W(pkg) {
    Session.Output(" -> Generando: sd CU05W - Gestionar planes de suscripción");
    var diag = pkg.Diagrams.AddNew("sd CU05W - Gestionar planes de suscripción", "Sequence");
    diag.Update();

    var h = 760;
    var act  = crearLifeline(pkg, diag, "Administrador (SuperAdmin)", "Actor", "", 50, 90, h);
    var bUrl = crearLifeline(pkg, diag, "URL: Planes de suscripcion", "Boundary", "boundary", 200, 95, h);
    var bLst = crearLifeline(pkg, diag, "Lista Planes", "Boundary", "boundary", 340, 85, h);
    var bFrm = crearLifeline(pkg, diag, "Formulario : Edición de plan", "Boundary", "boundary", 470, 95, h);
    var bErr = crearLifeline(pkg, diag, "Ventana: Error", "Boundary", "boundary", 610, 85, h);
    var ctl  = crearLifeline(pkg, diag, "PlanControl", "Control", "control", 740, 95, h);
    var tPln = crearLifeline(pkg, diag, "t_plan", "Entity", "entity", 880, 85, h);
    var tSus = crearLifeline(pkg, diag, "t_suscripcion", "Entity", "entity", 1010, 90, h);
    var tBit = crearLifeline(pkg, diag, "t_bitacora", "Entity", "entity", 1140, 85, h);

    var seq = 1;

    // Escenario 1: Listar
    crearMensaje(act, bUrl, seq++ + ": solicitar_listado_planes()", seq, false, false);
    crearMensaje(bUrl, ctl, seq++ + ": listar_planes()", seq, false, false);
    crearMensaje(ctl, tPln, seq++ + ": SELECT codigo, nombre, max_sucursales, precio_mensual, activo FROM t_plan", seq, false, false);
    crearMensaje(tPln, ctl, seq++ + ": return lista_planes", seq, true, false);
    crearMensaje(ctl, bLst, seq++ + ": mostrar_planes(lista_planes)", seq, false, false);

    // Escenario 2: Modificar Plan
    crearMensaje(act, bFrm, seq++ + ": enviar_datos_modificacion(codigo_plan, nuevos_datos)", seq, false, false);
    crearMensaje(bFrm, ctl, seq++ + ": actualizar_detalles_del_plan(codigo_plan, nuevos_datos)", seq, false, false);
    crearMensaje(ctl, tPln, seq++ + ": SELECT codigo, activo FROM t_plan WHERE codigo = :codigo_plan", seq, false, false);
    crearMensaje(tPln, ctl, seq++ + ": return plan_existente", seq, true, false);
    crearMensaje(ctl, tSus, seq++ + ": SELECT COUNT(*) FROM t_suscripcion WHERE codigo_plan = :codigo AND estado='ACTIVA'", seq, false, false);
    crearMensaje(tSus, ctl, seq++ + ": return conteo_empresas_activas", seq, true, false);

    crearFragmentoCombinado(pkg, diag, "alt_validar_plan", "alt", "[plan inexistente || (desactivar && conteo > 0)] vs [else: permitido]", 450, 1230, 420, 680);

    // Rama Error
    crearMensaje(ctl, bErr, seq++ + ": notificar_error(\"No se puede desactivar un plan con suscripciones activas\")", seq, false, true);
    crearMensaje(bErr, act, seq++ + ": mostrar_error_operacion_bloqueada()", seq, true, true);

    // Rama Normal
    crearMensaje(ctl, tPln, seq++ + ": UPDATE t_plan SET nombre=:nom, max_sucursales=:max, activo=:act WHERE codigo=:cod", seq, false, false);
    crearMensaje(ctl, tBit, seq++ + ": INSERT INTO t_bitacora(id_usuario, modulo='SAAS', accion='ACTUALIZAR_PLAN', entidad='t_plan', ...)", seq, false, false);
    crearMensaje(ctl, bUrl, seq++ + ": redirigir_a_planes()", seq, false, false);
    crearMensaje(bUrl, act, seq++ + ": mostrar_planes_actualizados()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// CU12W / CU03M: Consultar detalles de producto (con soporte Offline)
// =================================================================================================
function generarCU12W(pkg) {
    Session.Output(" -> Generando: sd CU12W - Consultar detalles de producto");
    var diag = pkg.Diagrams.AddNew("sd CU12W - Consultar detalles de producto", "Sequence");
    diag.Update();

    var h = 820;
    var act  = crearLifeline(pkg, diag, "Usuario (Cliente / Vendedor)", "Actor", "", 50, 95, h);
    var bUrl = crearLifeline(pkg, diag, "URL: Catálogo", "Boundary", "boundary", 200, 90, h);
    var bDet = crearLifeline(pkg, diag, "vDetalleProducto", "Boundary", "boundary", 340, 95, h);
    var bOff = crearLifeline(pkg, diag, "Ventana: Modo Offline", "Boundary", "boundary", 480, 95, h);
    var ctl  = crearLifeline(pkg, diag, "CatalogoControl", "Control", "control", 620, 95, h);
    var tPrd = crearLifeline(pkg, diag, "t_producto", "Entity", "entity", 760, 85, h);
    var tCat = crearLifeline(pkg, diag, "t_categoria", "Entity", "entity", 890, 85, h);
    var tVar = crearLifeline(pkg, diag, "t_producto_talla_color", "Entity", "entity", 1020, 95, h);
    var tCol = crearLifeline(pkg, diag, "t_color", "Entity", "entity", 1160, 80, h);
    var tTal = crearLifeline(pkg, diag, "t_talla", "Entity", "entity", 1280, 80, h);
    var cLoc = crearLifeline(pkg, diag, "cache_local", "Entity", "entity", 1400, 85, h);

    var seq = 1;

    // Escenario 1: Listar Catálogo
    crearMensaje(act, bUrl, seq++ + ": filtrar_productos(categoria, texto)", seq, false, false);
    crearMensaje(bUrl, ctl, seq++ + ": listar_catalogo(filtros)", seq, false, false);
    crearMensaje(ctl, tPrd, seq++ + ": SELECT p.*, c.nombre FROM t_producto p JOIN t_categoria c ON c.id_categoria = p.id_categoria WHERE p.activo = true", seq, false, false);
    crearMensaje(tPrd, ctl, seq++ + ": return catalogo_filtrado", seq, true, false);
    crearMensaje(ctl, bUrl, seq++ + ": renderizar_catalogo(catalogo_filtrado)", seq, false, false);

    // Escenario 2: Seleccionar producto y ver detalles con condición Offline
    crearMensaje(act, bUrl, seq++ + ": seleccionar_producto(id_producto)", seq, false, false);
    crearMensaje(bUrl, ctl, seq++ + ": obtener_detalle_producto(id_producto)", seq, false, false);

    crearFragmentoCombinado(pkg, diag, "alt_conexion_catalogo", "alt", "[sin conexion de red] vs [else: conexion activa]", 320, 1490, 390, 720);

    // Rama Offline (Nodo Rojo)
    crearMensaje(ctl, bOff, seq++ + ": habilitar_modo_sin_conexion()", seq, false, true);
    crearMensaje(ctl, cLoc, seq++ + ": consultar_producto_en_cache(id_producto)", seq, false, true);
    crearMensaje(cLoc, ctl, seq++ + ": return datos_producto_cache", seq, true, true);
    crearMensaje(ctl, bDet, seq++ + ": mostrar_detalles_offline(datos_producto_cache)", seq, false, true);

    // Rama Online
    crearMensaje(ctl, tVar, seq++ + ": SELECT ptc.*, col.nombre_color, tal.talla FROM t_producto_talla_color ptc JOIN t_color col ON col.id_color = ptc.id_color JOIN t_talla tal ON tal.id_talla = ptc.id_talla WHERE ptc.id_producto = :id", seq, false, false);
    crearMensaje(tVar, ctl, seq++ + ": return variantes_completas", seq, true, false);
    crearMensaje(ctl, cLoc, seq++ + ": actualizar_cache_local(id_producto, variantes)", seq, false, false);
    crearMensaje(ctl, bDet, seq++ + ": mostrar_detalles(variantes_completas)", seq, true, false);
    crearMensaje(bDet, act, seq++ + ": desplegar_vista_producto()", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// CU13W / CU04M: Consultar disponibilidad por sucursal (con soporte Offline)
// =================================================================================================
function generarCU13W(pkg) {
    Session.Output(" -> Generando: sd CU13W - Consultar disponibilidad por sucursal");
    var diag = pkg.Diagrams.AddNew("sd CU13W - Consultar disponibilidad por sucursal", "Sequence");
    diag.Update();

    var h = 820;
    var act  = crearLifeline(pkg, diag, "Usuario (Cliente / Vendedor)", "Actor", "", 50, 95, h);
    var bDet = crearLifeline(pkg, diag, "vDetalleProducto", "Boundary", "boundary", 200, 95, h);
    var bOff = crearLifeline(pkg, diag, "Ventana: Modo Offline", "Boundary", "boundary", 340, 95, h);
    var ctl  = crearLifeline(pkg, diag, "DisponibilidadControl", "Control", "control", 480, 95, h);
    var tSuc = crearLifeline(pkg, diag, "t_sucursal", "Entity", "entity", 620, 85, h);
    var tPrd = crearLifeline(pkg, diag, "t_producto", "Entity", "entity", 750, 85, h);
    var tVar = crearLifeline(pkg, diag, "t_producto_talla_color", "Entity", "entity", 880, 95, h);
    var tInv = crearLifeline(pkg, diag, "t_inventario", "Entity", "entity", 1020, 85, h);
    var cLoc = crearLifeline(pkg, diag, "cache_local", "Entity", "entity", 1150, 85, h);

    var seq = 1;

    // Escenario 1: Cargar sucursales disponibles
    crearMensaje(act, bDet, seq++ + ": abrir_selector_sucursales(id_producto)", seq, false, false);
    crearMensaje(bDet, ctl, seq++ + ": listar_sucursales_con_stock(id_producto)", seq, false, false);
    crearMensaje(ctl, tSuc, seq++ + ": SELECT id_sucursal, nombre, direccion FROM t_sucursal WHERE activo = true", seq, false, false);
    crearMensaje(tSuc, ctl, seq++ + ": return lista_sucursales", seq, true, false);
    crearMensaje(ctl, bDet, seq++ + ": poblar_combo_sucursales(lista_sucursales)", seq, false, false);

    // Escenario 2: Consultar disponibilidad específica
    crearMensaje(act, bDet, seq++ + ": seleccionar_sucursal_y_variante(id_sucursal, id_variante)", seq, false, false);
    crearMensaje(bDet, ctl, seq++ + ": consultar_disponibilidad(id_sucursal, id_variante)", seq, false, false);

    crearFragmentoCombinado(pkg, diag, "alt_conexion_stock", "alt", "[sin conexion de red] vs [else: conexion activa]", 180, 1240, 390, 710);

    // Rama Offline (Nodo Rojo)
    crearMensaje(ctl, bOff, seq++ + ": habilitar_modo_sin_conexion()", seq, false, true);
    crearMensaje(ctl, cLoc, seq++ + ": obtener_stock_estimado_cache(id_sucursal, id_variante)", seq, false, true);
    crearMensaje(cLoc, ctl, seq++ + ": return stock_cache", seq, true, true);
    crearMensaje(ctl, bDet, seq++ + ": mostrar_disponibilidad_offline(stock_cache, \"(Datos no sincronizados)\")", seq, false, true);

    // Rama Online
    crearMensaje(ctl, tInv, seq++ + ": SELECT stock_actual, stock_reservado, (stock_actual - stock_reservado) AS disponible FROM t_inventario WHERE id_sucursal = :suc AND id_producto_talla_color = :var", seq, false, false);
    crearMensaje(tInv, ctl, seq++ + ": return stock_disponible", seq, true, false);
    crearMensaje(ctl, cLoc, seq++ + ": cachear_disponibilidad(id_sucursal, id_variante, stock_disponible)", seq, false, false);
    crearMensaje(ctl, bDet, seq++ + ": mostrar_disponibilidad(stock_disponible)", seq, true, false);
    crearMensaje(bDet, act, seq++ + ": actualizar_indicador_stock(stock_disponible)", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// CU14W / CU05M: Gestionar reservas de stock (con soporte Offline)
// =================================================================================================
function generarCU14W(pkg) {
    Session.Output(" -> Generando: sd CU14W - Gestionar reservas");
    var diag = pkg.Diagrams.AddNew("sd CU14W - Gestionar reservas", "Sequence");
    diag.Update();

    var h = 950;
    var act  = crearLifeline(pkg, diag, "Cliente", "Actor", "", 50, 85, h);
    var bPrd = crearLifeline(pkg, diag, "vDetalleProducto", "Boundary", "boundary", 190, 95, h);
    var bRes = crearLifeline(pkg, diag, "vDetalleReserva", "Boundary", "boundary", 330, 95, h);
    var bOff = crearLifeline(pkg, diag, "Ventana: Modo Offline", "Boundary", "boundary", 470, 95, h);
    var ctl  = crearLifeline(pkg, diag, "ReservaControl", "Control", "control", 610, 95, h);
    var tVar = crearLifeline(pkg, diag, "t_producto_talla_color", "Entity", "entity", 750, 95, h);
    var tInv = crearLifeline(pkg, diag, "t_inventario", "Entity", "entity", 890, 85, h);
    var tSuc = crearLifeline(pkg, diag, "t_sucursal", "Entity", "entity", 1020, 80, h);
    var tCli = crearLifeline(pkg, diag, "t_cliente", "Entity", "entity", 1140, 80, h);
    var tRes = crearLifeline(pkg, diag, "t_reserva", "Entity", "entity", 1260, 85, h);
    var tDet = crearLifeline(pkg, diag, "t_detalle_reserva", "Entity", "entity", 1390, 95, h);
    var tBit = crearLifeline(pkg, diag, "t_bitacora", "Entity", "entity", 1530, 85, h);
    var cLoc = crearLifeline(pkg, diag, "cache_local", "Entity", "entity", 1660, 85, h);

    var seq = 1;

    // Escenario 1: Agendar y verificar disponibilidad
    crearMensaje(act, bPrd, seq++ + ": agendar_reserva(id_variante, cantidad)", seq, false, false);
    crearMensaje(bPrd, ctl, seq++ + ": iniciar_solicitud_reserva(id_variante, cantidad)", seq, false, false);

    crearFragmentoCombinado(pkg, diag, "alt_conexion_reserva", "alt", "[sin conexion de red] vs [else: conexion activa]", 180, 1750, 240, 480);

    // Rama Offline (Nodo Rojo)
    crearMensaje(ctl, bOff, seq++ + ": habilitar_modo_sin_conexion()", seq, false, true);
    crearMensaje(ctl, cLoc, seq++ + ": encolar_reserva_pendiente_offline(solicitud)", seq, false, true);
    crearMensaje(cLoc, ctl, seq++ + ": return ticket_local_pendiente", seq, true, true);
    crearMensaje(ctl, bRes, seq++ + ": notificar_reserva_pendiente_sync(ticket_local)", seq, false, true);

    // Rama Online
    crearMensaje(ctl, tInv, seq++ + ": SELECT stock_actual, stock_reservado FROM t_inventario WHERE id_sucursal=:suc AND id_producto_talla_color=:var FOR UPDATE", seq, false, false);
    crearMensaje(tInv, ctl, seq++ + ": return datos_stock", seq, true, false);
    crearMensaje(ctl, bRes, seq++ + ": seleccionar_metodo_de_reserva(tiempo_limite, metodos_pago)", seq, false, false);

    // Escenario 2: Confirmar reserva
    crearMensaje(act, bRes, seq++ + ": confirmar_reserva(datos_cliente, metodo_retiro)", seq, false, false);
    crearMensaje(bRes, ctl, seq++ + ": procesar_confirmacion_reserva(datos_reserva)", seq, false, false);

    crearMensaje(ctl, tCli, seq++ + ": SELECT id_cliente FROM t_cliente WHERE ci_nit = :ci", seq, false, false);
    crearMensaje(tCli, ctl, seq++ + ": return id_cliente", seq, true, false);

    crearFragmentoCombinado(pkg, diag, "opt_nuevo_cliente", "opt", "[cliente no registrado]", 590, 1220, 600, 660);
    crearMensaje(ctl, tCli, seq++ + ": INSERT INTO t_cliente(nombre, ci_nit, telefono) RETURNING id_cliente", seq, false, false);
    crearMensaje(tCli, ctl, seq++ + ": return id_cliente_nuevo", seq, true, false);

    crearMensaje(ctl, tRes, seq++ + ": INSERT INTO t_reserva(id_cliente, id_sucursal, estado='PENDIENTE', expira=NOW()+24h) RETURNING id_reserva", seq, false, false);
    crearMensaje(tRes, ctl, seq++ + ": return id_reserva", seq, true, false);
    crearMensaje(ctl, tDet, seq++ + ": INSERT INTO t_detalle_reserva(id_reserva, id_producto_talla_color, cantidad, precio_unitario)", seq, false, false);
    crearMensaje(ctl, tInv, seq++ + ": UPDATE t_inventario SET stock_reservado = stock_reservado + :cant WHERE id_sucursal=:suc AND id_producto_talla_color=:var", seq, false, false);
    crearMensaje(ctl, tBit, seq++ + ": INSERT INTO t_bitacora(modulo='RESERVAS', accion='RESERVA_CONFIRMADA', id_entidad=:id_reserva, ...)", seq, false, false);

    crearMensaje(ctl, bRes, seq++ + ": reserva_registrada(id_reserva, codigo_retiro, fecha_expiracion)", seq, true, false);
    crearMensaje(bRes, act, seq++ + ": mostrar_comprobante_reserva(codigo_retiro)", seq, true, false);

    diag.Update();
    Repository.ReloadDiagram(diag.DiagramID);
}

// =================================================================================================
// FUNCIÓN PRINCIPAL DE EJECUCIÓN
// =================================================================================================
function Main() {
    Repository.EnsureOutputVisible("Script");
    Session.Output("================================================================================");
    Session.Output("Iniciando generación de Diagramas de Secuencia BCE en Enterprise Architect...");
    Session.Output("================================================================================");

    var pkg = Repository.GetTreeSelectedPackage();
    if (pkg == null) {
        Session.Prompt("ERROR: Por favor seleccione un paquete en el Project Browser antes de ejecutar.", 0);
        return;
    }

    // Crear o reutilizar subpaquete para organizar los diagramas de secuencia
    var subPkg = null;
    for (var i = 0; i < pkg.Packages.Count; i++) {
        var p = pkg.Packages.GetAt(i);
        if (p.Name == "Diagramas de Secuencia (BCE)") {
            subPkg = p;
            break;
        }
    }
    if (subPkg == null) {
        subPkg = pkg.Packages.AddNew("Diagramas de Secuencia (BCE)", "");
        subPkg.Update();
        pkg.Packages.Refresh();
    }

    Session.Output("Paquete destino: " + subPkg.Name);

    generarCU01W(subPkg);
    generarCU02W(subPkg);
    generarCU03W(subPkg);
    generarCU04W(subPkg);
    generarCU05W(subPkg);
    generarCU12W(subPkg);
    generarCU13W(subPkg);
    generarCU14W(subPkg);

    Repository.RefreshModelView(subPkg.PackageID);
    Session.Output("================================================================================");
    Session.Output(" ¡EXITO TOTAL! Se han generado los 8 diagramas de secuencia en Enterprise Architect.");
    Session.Output(" Paquete: " + subPkg.Name);
    Session.Output("================================================================================");
}

Main();
