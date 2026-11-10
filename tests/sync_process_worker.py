"""Fresh HTTP application process restricted to the disposable test cluster."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
settings = json.loads(sys.stdin.readline())
assert settings['DB_HOST'] == '127.0.0.1'
assert settings['SCHEMA'].startswith('pwa_')
from app.core.config import Config
for key, value in settings.items():
    if key not in ('operation', 'pause', 'user_id'):
        setattr(Config, key, value)

from app.core.security import _contexto_vigente
from app.modules.ecommerce.routes import sync_routes
from app.main import app
from fastapi.testclient import TestClient
import jwt

user_id = settings.get('user_id', 3)
ctx = _contexto_vigente({'id_usuario': user_id})
ctx.update(nro_usuario=user_id, id_usuario=user_id, sv=ctx.get('session_version', 1))
headers = {'Authorization': 'Bearer ' + jwt.encode(ctx, Config.TOKEN_KEY or Config.SECRET_KEY, algorithm='HS256')}
pause = settings.get('pause')
target = '_aplicar_operacion' if pause == 'before_commit' else '_procesar_operacion_individual'
original = getattr(sync_routes, target)


def run(*args, **kwargs):
    result = original(*args, **kwargs)
    if pause:
        assert result['status'] == 'synced', result
        print('SYNC_PAUSED=' + pause, flush=True)
        sys.stdin.readline()  # Parent kills the process; no graceful cleanup.
    return result


with patch.object(sync_routes, target, run):
    response = TestClient(app).post('/api/sync/lote', headers=headers,
                                    json={'operations': [settings['operation']]})
    print('SYNC_RESULT=' + json.dumps(response.json()['results'][0]), flush=True)
