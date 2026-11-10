from app.modules.admin.repos import notificaciones_repos
from app.shared.websocket_manager import manager

#ALERTA A TODOS LOS TALLERES (CUANDO SE CREA LA EMERGENCIA)
async def enviar_push_nueva_emergencia(nro_emergencia: int, tipo_emergencia: str):
    roles_destino = ['ADMINISTRADOR', 'GERENTE TALLER', 'MECANICO']
    usuarios_destino = notificaciones_repos.obtener_usuarios_por_roles(roles_destino)
    
    titulo = "¡Nueva Emergencia Reportada!"
    cuerpo = f"Se requiere asistencia: {tipo_emergencia}"
    tipo_ref = "NUEVA_EMERGENCIA"

    mensaje_push = {
        "tipo_alerta": tipo_ref,
        "titulo": titulo,
        "cuerpo": cuerpo,
        "data": {"nro_emergencia": nro_emergencia}
    }
    
    for u in usuarios_destino:
        nro_usu = u['nro_usuario']
        # 1. Guardar en base de datos
        notificaciones_repos.guardar_notificacion_db(titulo, cuerpo, tipo_ref, nro_usu, nro_emergencia)
        # 2. Enviar por WebSocket
        await manager.send_personal_message(mensaje_push, nro_usu)

#ALERTA AL CLIENTE (CUANDO UN TALLER LE MANDA UNA OFERTA)
async def enviar_push_nueva_oferta(nro_emergencia: int, id_oferta: int, nro_usuario_cliente: int, precio: float):
    titulo = "¡Nueva Oferta Recibida!"
    cuerpo = f"Un taller ha ofrecido atender su emergencia por Bs. {precio}."
    tipo_ref = "NUEVA_OFERTA"

    # 1. Guardar en base de datos
    notificaciones_repos.guardar_notificacion_db(titulo, cuerpo, tipo_ref, nro_usuario_cliente, nro_emergencia)

    # 2. Enviar por WebSocket
    mensaje_push = {
        "tipo_alerta": tipo_ref,
        "titulo": titulo,
        "cuerpo": cuerpo,
        "data": {"nro_emergencia": nro_emergencia, "id_oferta": id_oferta}
    }
    await manager.send_personal_message(mensaje_push, nro_usuario_cliente)

#ALERTA A LOS TRABAJADORES DEL TALLER (CUANDO EL CLIENTE RESPONDE LA OFERTA)
async def enviar_push_respuesta_oferta(nro_emergencia: int, id_oferta: int, estado_respuesta: str, nro_taller: int):
    usuarios_taller = notificaciones_repos.obtener_usuarios_por_taller(nro_taller)
    
    if estado_respuesta == 'ACEPTADA':
        titulo = "¡Oferta Aceptada!"
        cuerpo = "El cliente aceptó tu cotización. ¡Inicia el trayecto!"
    else:
        titulo = "Oferta Rechazada"
        cuerpo = "El cliente ha declinado tu cotización."
        
    tipo_ref = "RESPUESTA_OFERTA"

    mensaje_push = {
        "tipo_alerta": tipo_ref,
        "titulo": titulo,
        "cuerpo": cuerpo,
        "data": {"nro_emergencia": nro_emergencia, "id_oferta": id_oferta}
    }
    
    for u in usuarios_taller:
        nro_usu = u['nro_usuario']
        # 1. Guardar en BD para cada miembro del taller
        notificaciones_repos.guardar_notificacion_db(titulo, cuerpo, tipo_ref, nro_usu, nro_emergencia)
        # 2. Notificar por WebSocket
        await manager.send_personal_message(mensaje_push, nro_usu)

def listar_mis_notificaciones(nro_usuario: int):
    if not nro_usuario:
        raise ValueError("No se pudo identificar al usuario de la sesión.")
    
    alertas = notificaciones_repos.obtener_notificaciones_por_usuario_db(int(nro_usuario))
    return {
        "success": True,
        "message": "Bandeja de notificaciones recuperada exitosamente.",
        "data": alertas
    }

def cambiar_estado_leido(nro_usuario: int, id_notificacion: int = None, marcar_todo: bool = False):
    if not nro_usuario:
        raise ValueError("Operación no autorizada. Sesión inválida.")
        
    # ESCENARIO A: Botón masivo para limpiar toda la bandeja
    if marcar_todo:
        total_actualizadas = notificaciones_repos.marcar_todas_las_notificaciones_leidas_db(int(nro_usuario))
        return {
            "success": True,
            "message": f"Todas las notificaciones fueron marcadas como leídas. ({total_actualizadas} alertas afectadas)"
        }
        
    # ESCENARIO B: Se leyó una notificación específica
    if id_notificacion:
        exito = notificaciones_repos.marcar_notificacion_leida_db(int(id_notificacion), int(nro_usuario))
        if not exito:
            raise ValueError("No se encontró la notificación seleccionada o no te pertenece.")
        return {
            "success": True,
            "message": "Notificación marcada como leída exitosamente."
        }
        
    raise ValueError("Parámetros insuficientes para procesar la lectura de alertas.")