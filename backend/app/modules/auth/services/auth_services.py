from datetime import datetime, timedelta
from fastapi import Request
from app.modules.auth.repos import auth_repos
from app.core import security
from app.modules.admin.services import bitacora_services
# Registra un nuevo cliente validando contraseñas, términos y registrando su dispositivo inicial.
def registrar_cliente(data: dict, request: Request = None) -> dict:
    correo = data.get('correo')
    password = data.get('password')
    confirm_password = data.get('confirm_password')
    nombre = data.get('nombre')
    apellido = data.get('apellido')
    telefono = data.get('telefono')
    aceptar_terminos = data.get('aceptar_terminos')
    fingerprint = data.get('device_fingerprint')
    nombre_dispositivo = data.get('nombre_dispositivo')
    
    if not correo or not password or not confirm_password or not nombre or not apellido:
        raise ValueError("Correo, nombre, apellido y contraseñas son obligatorios.")
        
    if not aceptar_terminos:
        raise ValueError("Debe aceptar los términos del servicio para registrarse.")
        
    if password != confirm_password:
        raise ValueError("Las contraseñas no coinciden.")
        
    if not security.validar_password(password):
        raise ValueError("La contraseña debe tener al menos 8 caracteres y contener al menos 1 carácter especial.")
        
    username = data.get('nombre_usuario') or correo.split('@')[0]
    
    if auth_repos.existe_usuario(correo, username):
        raise ValueError("El correo electrónico o nombre de usuario ya se encuentra registrado.")
        
    password_hash = security.hash_password(password)
    
    datos_usuario = {
        'correo': correo,
        'nombre_usuario': username,
        'username': username,
        'password_hash': password_hash,
        'nombre': nombre,
        'apellido': apellido,
        'telefono': telefono,
        'estado': 'ACTIVO',
        'id_empresa': None,
        'id_rol': 2
    }

    
    nro_usuario = auth_repos.crear_cliente(datos_usuario, fingerprint, nombre_dispositivo)
    
    token = security.create_access_token(
        nro_usuario=nro_usuario,
        username=username,
        id_rol=datos_usuario['id_rol'],
        id_empresa=datos_usuario['id_empresa'],
        nombre=nombre,
        apellido=apellido
    )
    
    # Audit log
    bitacora_services.registrar_accion(
        modulo="USUARIOS",
        accion="USUARIO_CREADO",
        nivel="INFO",
        resultado="EXITO",
        payload_jwt={"id_usuario": nro_usuario, "username": username, "id_empresa": datos_usuario['id_empresa']},
        entidad="Usuario",
        id_entidad=str(nro_usuario),
        descripcion=f"Registro de nuevo cliente: {username}",
        datos_nuevos={"correo": correo, "username": username, "id_rol": datos_usuario['id_rol']},
        request=request
    )
    
    return {
        "success": True,
        "message": "Registro completado exitosamente.",
        "usuario": {
            "nro_usuario": nro_usuario,
            "correo": correo,
            "nombre_usuario": username,
            "nombre": nombre,
            "apellido": apellido
        },
        "token": token
    }

# Autentica al usuario aplicando el control de 3 intentos fallidos y detección de dispositivos desconocidos.
def iniciar_sesion(data: dict, request: Request = None) -> dict:
    login_identifier = data.get('login_identifier') or data.get('correo') or data.get('username')
    password = data.get('password')
    fingerprint = data.get('device_fingerprint')
    nombre_dispositivo = data.get('nombre_dispositivo')
    
    if not login_identifier or not password:
        raise ValueError("Debe proporcionar usuario/correo y contraseña.")
        
    usuario_db = auth_repos.obtener_credenciales_cliente(login_identifier)
    if not usuario_db or usuario_db.get('estado') == 'INACTIVO':
        bitacora_services.registrar_accion(
            modulo="AUTENTICACION", accion="LOGIN_FALLIDO", nivel="WARNING", resultado="ERROR",
            descripcion=f"Intento de login fallido para identificador: {login_identifier}", request=request
        )
        raise ValueError("Credenciales inválidas o cuenta inactiva.")
        
    nro_usuario = usuario_db['nro_usuario']
    
    # 1. Comprobar bloqueo activo
    bloqueado_hasta = usuario_db.get('bloqueado_hasta')
    if bloqueado_hasta and datetime.now() < bloqueado_hasta:
        minutos_restantes = max(1, int((bloqueado_hasta - datetime.now()).total_seconds() // 60))
        raise ValueError(f"Cuenta bloqueada por 3 intentos fallidos. Intente nuevamente en {minutos_restantes} minuto(s).")
        
    # 2. Validar contraseña
    if not security.verificar_password_hash(usuario_db['password_hash'], password):
        intentos = usuario_db['intentos_fallidos'] + 1
        
        bitacora_services.registrar_accion(
            modulo="AUTENTICACION", accion="LOGIN_FALLIDO", nivel="WARNING", resultado="ERROR",
            payload_jwt={"id_usuario": nro_usuario, "username": usuario_db['nombre_usuario']},
            descripcion=f"Contraseña incorrecta (intento {intentos})", request=request
        )
        
        if intentos >= 3:
            nuevo_bloqueo = datetime.now() + timedelta(minutes=15)
            auth_repos.registrar_intento_fallido(nro_usuario, intentos, nuevo_bloqueo)
            
            bitacora_services.registrar_accion(
                modulo="AUTENTICACION", accion="CUENTA_BLOQUEADA", nivel="CRITICAL", resultado="EXITO",
                payload_jwt={"id_usuario": nro_usuario, "username": usuario_db['nombre_usuario']},
                descripcion="Cuenta bloqueada por 3 intentos fallidos", request=request
            )
            raise ValueError("Ha fallado 3 intentos consecutivos. Su cuenta ha sido bloqueada por 15 minutos.")
        else:
            auth_repos.registrar_intento_fallido(nro_usuario, intentos, None)
            intentos_restantes = 3 - intentos
            raise ValueError(f"Contraseña incorrecta. Le quedan {intentos_restantes} intento(s) antes del bloqueo.")
            
    # 3. Contraseña correcta -> reiniciar contador de intentos
    auth_repos.reiniciar_intentos(nro_usuario)
    
    # 4. Comprobar dispositivo conocido si se envía fingerprint
    if fingerprint and not auth_repos.es_dispositivo_conocido(nro_usuario, fingerprint):
        codigo = security.generar_codigo_seguridad()
        expira_at = datetime.now() + timedelta(minutes=15)
        auth_repos.guardar_codigo_dispositivo(nro_usuario, codigo, expira_at)
        return {
            "success": True,
            "requires_verification": True,
            "message": "Dispositivo no reconocido. Se ha enviado un código de verificación.",
            "nro_usuario": nro_usuario,
            "codigo_simulado": codigo
        }
        
    # 5. Obtener roles, permisos efectivos y sucursales autorizadas del usuario
    from app.modules.auth.repos import rbac_repos
    roles_usuario = rbac_repos.obtener_roles_usuario(nro_usuario)
    nombres_roles = [r['nombre'] for r in roles_usuario] if roles_usuario else ([usuario_db.get('nombre_rol')] if usuario_db.get('nombre_rol') else [])
    permisos_efectivos = rbac_repos.obtener_permisos_efectivos_usuario(nro_usuario)
    sucursales_usuario = rbac_repos.obtener_sucursales_usuario(nro_usuario)

    # Determinar nombre_rol principal
    nombre_rol_final = usuario_db.get('nombre_rol') or (nombres_roles[0] if nombres_roles else 'CLIENTE')

    # Determinar alcance RBAC de forma rigurosa
    from app.core.tenant_guard import obtener_alcance_usuario
    alcance_final = obtener_alcance_usuario({'roles': nombres_roles, 'id_empresa': usuario_db.get('id_empresa')})

    # 5.1 Enriquecer detalle de sucursales autorizadas
    sucursales_detalle = []
    if sucursales_usuario:
        from app.core.postgres import PostgreSQL
        from app.core.config import Config
        db_s = PostgreSQL()
        db_s.create_connection()
        try:
            schema_s = Config.SCHEMA or 'comercio'
            res_s = db_s.execute_query(
                f"""SELECT s.id_sucursal, s.nombre, s.direccion, c.nombre AS ciudad 
                    FROM {schema_s}.t_sucursal s 
                    LEFT JOIN {schema_s}.t_ciudad c ON s.id_ciudad = c.id_ciudad 
                    WHERE s.id_sucursal = ANY(%s) AND s.activo = TRUE;""",
                (sucursales_usuario,),
                fetchall=True
            )
            if res_s:
                sucursales_detalle = [{"id_sucursal": r[0], "id": r[0], "nombre": r[1], "direccion": r[2], "ciudad": r[3] or ''} for r in res_s]
        finally:
            db_s.close_connection()

    # 6. Generar token de sesión con la información RBAC
    token = security.create_access_token(
        nro_usuario=nro_usuario,
        username=usuario_db['nombre_usuario'],
        id_rol=usuario_db['id_rol'],
        id_empresa=usuario_db['id_empresa'],
        nombre_empresa=usuario_db.get('nombre_empresa'),
        nombre=usuario_db['nombre'],
        apellido=usuario_db['apellido'],
        roles=nombres_roles,
        permisos=permisos_efectivos,
        sucursales=sucursales_usuario,
        nombre_rol=nombre_rol_final
    )
    
    bitacora_services.registrar_accion(
        modulo="AUTENTICACION", accion="LOGIN_EXITOSO", nivel="INFO", resultado="EXITO",
        payload_jwt={"id_usuario": nro_usuario, "username": usuario_db['nombre_usuario'], "id_empresa": usuario_db['id_empresa']},
        descripcion=f"Inicio de sesión exitoso", request=request
    )
    
    return {
        "success": True,
        "message": "Inicio de sesión exitoso.",
        "usuario": {
            "nro_usuario": nro_usuario,
            "correo": usuario_db['correo'],
            "nombre_usuario": usuario_db['nombre_usuario'],
            "nombre": usuario_db['nombre'],
            "apellido": usuario_db['apellido'],
            "id_rol": usuario_db['id_rol'],
            "nombre_rol": nombre_rol_final,
            "id_empresa": usuario_db['id_empresa'],
            "nombre_empresa": usuario_db.get('nombre_empresa'),
            "roles": nombres_roles,
            "permisos": permisos_efectivos,
            "sucursales": sucursales_usuario,
            "sucursales_detalle": sucursales_detalle,
            "alcance": alcance_final
        },
        "token": token
    }

# Valida el código de verificación para autorizar y guardar un nuevo dispositivo.
def verificar_nuevo_dispositivo(data: dict) -> dict:
    id_usuario = data.get('id_usuario') or data.get('nro_usuario')
    codigo = data.get('codigo_verificacion')
    fingerprint = data.get('device_fingerprint')
    nombre_dispositivo = data.get('nombre_dispositivo')
    
    if not id_usuario or not codigo or not fingerprint:
        raise ValueError("El identificador de usuario, código y huella de dispositivo son obligatorios.")
        
    auth_repos.validar_codigo_dispositivo(id_usuario, codigo)
    auth_repos.guardar_dispositivo_verificado(id_usuario, fingerprint, nombre_dispositivo)
    
    return {
        "success": True,
        "message": "Dispositivo verificado y registrado exitosamente."
    }


# Genera, almacena y envía el código de recuperación vía Brevo (API / SMTP).
def solicitar_recuperacion_clave(data: dict) -> dict:
    login_input = (data.get('correo') or data.get('login_identifier') or '').strip()
    if not login_input:
        raise ValueError("El correo electrónico o nombre de usuario es obligatorio.")
        
    usuario_db = auth_repos.obtener_credenciales_cliente(login_input)
    if not usuario_db:
        raise ValueError("Si el correo está asociado a una cuenta, se le enviará un correo electrónico con el código de seguridad para verificar su identidad.")

    correo_destino = usuario_db.get('correo') or login_input
    nombre_destino = usuario_db.get('nombre') or 'Cliente'
    codigo = security.generar_codigo_seguridad()
    expira_at = datetime.now() + timedelta(minutes=15)
    
    enviado = auth_repos.guardar_codigo_recuperacion(correo_destino, codigo, expira_at)
    if not enviado:
        raise ValueError("No se pudo guardar el código de recuperación en el sistema.")
        
    # Enviar correo electrónico real mediante Brevo API en segundo plano
    import threading
    from app.shared import email_service
    threading.Thread(
        target=email_service.enviar_correo_recuperacion_brevo,
        args=(correo_destino, nombre_destino, codigo),
        daemon=True
    ).start()
    
    return {
        "success": True,
        "message": f"Código de recuperación enviado correctamente a tu correo ({correo_destino})"
    }


# Valida previamente si el código de recuperación ingresado es correcto antes de permitir ingresar la nueva clave.
def verificar_codigo_recuperacion(data: dict) -> dict:
    correo = (data.get('correo') or data.get('login_identifier') or '').strip()
    codigo = (data.get('codigo_recuperacion') or '').strip()
    if not correo or not codigo:
        raise ValueError("El correo o usuario y el código de recuperación son obligatorios.")
        
    auth_repos.validar_codigo_recuperacion(correo, codigo)
    return {
        "success": True,
        "message": "Código de recuperación verificado correctamente."
    }


# Restablece la contraseña tras validar el código enviado y las políticas de clave.
def restablecer_clave(data: dict) -> dict:
    correo = data.get('correo')
    codigo = data.get('codigo_recuperacion')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    
    if not correo or not codigo or not new_password or not confirm_password:
        raise ValueError("Todos los campos son obligatorios.")
        
    if new_password != confirm_password:
        raise ValueError("Las contraseñas no coinciden.")
        
    if not security.validar_password(new_password):
        raise ValueError("La contraseña debe tener al menos 8 caracteres y contener al menos 1 carácter especial.")
        
    nuevo_hash = security.hash_password(new_password)
    auth_repos.restablecer_contrasena(correo, codigo, nuevo_hash)
    
    return {
        "success": True,
        "message": "Contraseña restablecida exitosamente. Ahora puede iniciar sesión con su nueva clave."
    }