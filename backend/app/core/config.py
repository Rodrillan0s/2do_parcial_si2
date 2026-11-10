from dotenv import load_dotenv
import os

# Cargar .env buscando tanto en backend/ como en backend/app/
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, '.env'), override=True)
load_dotenv(os.path.join(os.path.dirname(base_dir), '.env'), override=True)
load_dotenv(override=True)

class Config:
    
    # CREDENCIALES PARA LA DB
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME") 
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    SCHEMA = os.getenv("DB_SCHEMA", "comercio")
    
    # CREDENCIALES CONFIGURACION APP
    SECRET_KEY = os.getenv("SECRET_KEY")
    TOKEN_KEY = os.getenv("TOKEN_KEY")
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

    # CLOUDINARY MEDIA
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
    CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")

    # PAYPAL SANDBOX CREDENTIALS (W27)
    PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
    PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
    PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")
    PAYPAL_BASE_URL = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")

    # DEEPSEEK AI ASSISTANT (W13) & MULTI-PROVIDER AI CONFIG
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek").strip().lower()
    AI_MODEL = os.getenv("AI_MODEL", DEEPSEEK_MODEL).strip()
    AI_API_KEY = os.getenv("AI_API_KEY") or DEEPSEEK_API_KEY
    AI_BASE_URL = os.getenv("AI_BASE_URL") or DEEPSEEK_BASE_URL
    AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "25"))
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1500"))
    AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.3"))
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")