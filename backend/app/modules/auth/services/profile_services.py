import re
from werkzeug.security import generate_password_hash
from app.modules.auth.repos import profile_repos
from app.modules.admin.services import bitacora_services
from app.core.security import validar_password

def obtener_perfil_usuario(id_usuario: int):
    if not id_usuario:
        raise ValueError('Debe iniciar sesión para consultar su perfil.')
    
    usuario_db = profile_repos.get_profile(id_usuario)
    if not usuario_db:
        raise ValueError('El usuario no se encuentra registrado en el sistema.')
    
    return {
        'success': True,
        'message': 'Perfil recuperado exitosamente.',
        'data': usuario_db
    }

def actualizar_perfil_usuario(id_usuario: int, datos: dict, token_data: dict = None):
    if not id_usuario:
        raise ValueError('Operación no autorizada. Sesión inválida.')
    
    # Validar correo si se proporciona
    correo = datos.get('correo')
    if correo:
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(pattern, correo):
            raise ValueError('El formato del correo electrónico no es válido.')

    # Procesar cambio de contraseña si se especifica en la actualización general
    password_plano = datos.get('password')
    if password_plano and str(password_plano).strip():
        if not validar_password(password_plano):
            raise ValueError('La contraseña debe tener al menos 8 caracteres y al menos un carácter especial (!@#$%^&*()_+-=[]{}|;:,.<>?).')
        datos['password_hash'] = generate_password_hash(password_plano)
    else:
        datos['password_hash'] = None

    # Obtener datos anteriores para la bitácora
    perfil_anterior = profile_repos.get_profile(id_usuario)

    # Actualizar en BD
    resultado = profile_repos.update_profile(id_usuario, datos)

    # Registrar en bitácora de auditoría
    try:
        bitacora_services.registrar_accion(
            modulo='PERFIL',
            accion='ACTUALIZAR_DATOS',
            nivel='INFO',
            resultado='EXITO',
            payload_jwt=token_data or {'id_usuario': id_usuario},
            entidad='t_usuario',
            id_entidad=str(id_usuario),
            descripcion=f"Actualización de datos personales para usuario {perfil_anterior.get('username') if perfil_anterior else id_usuario}",
            datos_anteriores=perfil_anterior,
            datos_nuevos=datos
        )
    except Exception as e:
        print(f"Advertencia: No se pudo registrar en bitácora: {e}")

    # Retornar perfil actualizado
    perfil_actualizado = profile_repos.get_profile(id_usuario)
    return {
        'success': True,
        'message': 'Perfil actualizado correctamente.',
        'data': perfil_actualizado
    }

def cambiar_password_usuario(id_usuario: int, datos: dict, token_data: dict = None):
    if not id_usuario:
        raise ValueError('Operación no autorizada. Sesión inválida.')

    nueva_password = datos.get('password') or datos.get('nueva_password')
    if not nueva_password or not str(nueva_password).strip():
        raise ValueError('La nueva contraseña no puede estar vacía.')

    # Validaciones idénticas a recuperación de contraseña
    if not validar_password(nueva_password):
        raise ValueError('La contraseña debe tener al menos 8 caracteres y al menos un carácter especial (!@#$%^&*()_+-=[]{}|;:,.<>?).')

    password_hash = generate_password_hash(nueva_password)
    profile_repos.update_password(id_usuario, password_hash)

    # Registrar auditoría en bitácora
    try:
        bitacora_services.registrar_accion(
            modulo='PERFIL',
            accion='CAMBIAR_PASSWORD',
            nivel='INFO',
            resultado='EXITO',
            payload_jwt=token_data or {'id_usuario': id_usuario},
            entidad='t_usuario',
            id_entidad=str(id_usuario),
            descripcion=f"Cambio de contraseña exitoso desde gestión de perfil para usuario {id_usuario}"
        )
    except Exception as e:
        print(f"Advertencia: No se pudo registrar en bitácora: {e}")

    return {
        'success': True,
        'message': 'Tu contraseña ha sido actualizada exitosamente.'
    }