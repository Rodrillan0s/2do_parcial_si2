import sys
from app.core import config

sys.modules['app.config'] = config
Config = config.Config

__all__ = ["Config", "config"]