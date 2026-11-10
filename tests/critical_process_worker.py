"""A fresh process configured exclusively from its disposable test connection."""
import json
import os
from pathlib import Path
import sys

request = json.loads(sys.stdin.read())
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.core.config import Config
for key,value in request['config'].items():
    setattr(Config,key,value)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.security import verificar_token, _contexto_vigente
from app.modules.pedidos.routes.devoluciones_routes import router

app=FastAPI()
app.include_router(router)
actor=_contexto_vigente({'id_usuario':5})
app.dependency_overrides[verificar_token]=lambda:actor
response=TestClient(app).post('/api/devoluciones/solicitudes',json=request['payload'])
if request.get('drop_response') and response.status_code==201:
    os._exit(0)
print(json.dumps({'http_status':response.status_code,'body':response.json()}),flush=True)
