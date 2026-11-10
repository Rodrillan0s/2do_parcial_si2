import sys
from app.core import postgres
from app.shared import websocket_manager

sys.modules['app.classes.postgres'] = postgres
sys.modules['app.classes.websocket_manager'] = websocket_manager
