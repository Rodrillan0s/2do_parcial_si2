from fastapi import WebSocket
from typing import Dict

class ConnectionManager:
    def __init__(self):
        # Diccionario para guardar { nro_usuario : WebSocket_Activo }
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, nro_usuario: int):
        await websocket.accept()
        self.active_connections[nro_usuario] = websocket
        print(f"🟢 Usuario {nro_usuario} conectado al WebSocket.")

    def disconnect(self, nro_usuario: int):
        if nro_usuario in self.active_connections:
            del self.active_connections[nro_usuario]
            print(f"🔴 Usuario {nro_usuario} desconectado.")

    async def send_personal_message(self, message: dict, nro_usuario: int):
        # Si el usuario tiene la app abierta, le disparamos el JSON
        if nro_usuario in self.active_connections:
            websocket = self.active_connections[nro_usuario]
            await websocket.send_json(message)

# Instancia global
manager = ConnectionManager()