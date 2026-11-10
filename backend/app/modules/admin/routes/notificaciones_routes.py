from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.shared.websocket_manager import manager
from app.core.security import decode_access_token
from fastapi import Depends, HTTPException, Body
from app.core.security import verificar_token
from app.modules.admin.services import notificaciones_services
router = APIRouter(tags=["WebSockets Notificaciones"])


@router.websocket("/notificaciones")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    await websocket.accept()
    
    print("INTENTANDO CONECTAR WEBSOCKET")
    print(f"TOKEN RECIBIDO POR URL: {token[:30]}...")

    #VALIDAR EL TOKEN
    validation = decode_access_token(token)
    
    #COMPROBACION DE TOKEN
    if not validation or (isinstance(validation, dict) and validation.get('success') is False):
        print("❌ CONEXIÓN RECHAZADA: El token es inválido o expiró.")
        await websocket.close(code=1008)
        return

    #EXTRAER CONTENIDO DEL TOKEN
    payload = validation.get('payload') if isinstance(validation, dict) else None
    if not payload:
        payload = validation.get('data', validation) if isinstance(validation, dict) else validation

    try:
        nro_usuario = payload.get('nro_usuario')
    except Exception:
        nro_usuario = None

    if not nro_usuario:
        print("CONEXIÓN RECHAZADA: NO SE ENCONTRO UN NRO_USUARIO DENTRO DEL TOKEN.")
        await websocket.close(code=1008)
        return

    print(f"TOKEN VALIDO. VINCULANDO CANAL AL USUARIO: {nro_usuario}")

    #GUARDAR CONEXION ACTIVA
    manager.active_connections[int(nro_usuario)] = websocket
    print(f"CANAL EN TIEMPO REAL ABIERTO EXITOSAMENTE PARA EL USUARIO {nro_usuario}.")
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if int(nro_usuario) in manager.active_connections:
            del manager.active_connections[int(nro_usuario)]
        print(f"USUARIO {nro_usuario} DESCONECTADO DEL WEBSOCKET.")
# ============================================================
# 📡 ENDPOINTS HTTP TRADICIONALES (Bandeja de Entrada e Historial)
# ============================================================

@router.get('/historial')
def get_mis_notificaciones(token_data: dict = Depends(verificar_token)):
    """
    Endpoint HTTP para poblar la lista/bandeja de entrada del usuario.
    """
    nro_usuario = token_data.get('nro_usuario')
    try:
        return notificaciones_services.listar_mis_notificaciones(nro_usuario)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put('/leer')
def update_marcar_como_leido(data: dict = Body(...), token_data: dict = Depends(verificar_token)):
    """
    Endpoint flexible para marcar una o todas las notificaciones como leídas.
    """
    nro_usuario = token_data.get('nro_usuario')
    id_notificacion = data.get('id_notificacion')
    marcar_todo = data.get('marcar_todo', False)
    
    try:
        return notificaciones_services.cambiar_estado_leido(
            nro_usuario=nro_usuario, 
            id_notificacion=id_notificacion, 
            marcar_todo=marcar_todo
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))