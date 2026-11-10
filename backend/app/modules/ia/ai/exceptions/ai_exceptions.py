"""
Excepciones tipadas para la capa de abstracción de proveedores de IA y el orquestador conversacional.
Permiten distinguir fallos del proveedor externo (que activan fallback local) de violaciones de
seguridad, errores de autorización o errores de base de datos (que NUNCA deben ocultarse con fallback).
"""

from typing import Optional


class AIException(Exception):
    """Excepción base del módulo de IA."""
    def __init__(self, message: str, code: str = "AI_ERROR", provider: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.provider = provider


class AIProviderUnavailableError(AIException):
    """El proveedor externo no está disponible (sin API Key, error 5xx o caída de red)."""
    def __init__(self, message: str, provider: Optional[str] = None, code: str = "PROVIDER_UNAVAILABLE"):
        super().__init__(message, code=code, provider=provider)


class AITimeoutError(AIProviderUnavailableError):
    """El proveedor externo excedió el tiempo máximo de respuesta."""
    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider=provider, code="PROVIDER_TIMEOUT")


class AIAuthenticationError(AIProviderUnavailableError):
    """Credenciales o API Key inválidas en el proveedor externo."""
    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider=provider, code="PROVIDER_AUTH_ERROR")


class AIInvalidResponseError(AIProviderUnavailableError):
    """El proveedor devolvió un payload malformado o JSON inválido."""
    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider=provider, code="PROVIDER_INVALID_RESPONSE")


class AISecurityViolationError(AIException):
    """
    Violación de seguridad: intento de acceso inter-tenant, escalamiento de rol,
    ejecución de herramienta sin permisos RBAC o reutilización indebida de memoria.
    NUNCA activa fallback.
    """
    def __init__(self, message: str, status_code: int = 403, code: str = "SECURITY_VIOLATION"):
        super().__init__(message, code=code)
        self.status_code = status_code


class AIPromptInjectionError(AISecurityViolationError):
    """Intento detectado de manipulación del system prompt, rol o reglas de negocio."""
    def __init__(self, message: str = "Solicitud bloqueada por políticas de seguridad conversacional."):
        super().__init__(message, status_code=400, code="PROMPT_INJECTION_DETECTED")


class AIRateLimitExceededError(AIException):
    """Límite de solicitudes o presupuesto de tokens excedido para el usuario o empresa."""
    def __init__(self, message: str = "Se ha alcanzado el límite de consultas por minuto. Intenta nuevamente en unos instantes."):
        super().__init__(message, code="RATE_LIMIT_EXCEEDED")


class AIToolExecutionError(AIException):
    """Error controlado en la validación o ejecución de una herramienta de negocio."""
    def __init__(self, message: str, tool_name: Optional[str] = None, code: str = "TOOL_EXECUTION_ERROR"):
        super().__init__(message, code=code)
        self.tool_name = tool_name


class AIDatabaseError(AIException):
    """Error de conectividad o ejecución en PostgreSQL."""
    def __init__(self, message: str = "Error al consultar la base de datos de la tienda."):
        super().__init__(message, code="DATABASE_ERROR")
