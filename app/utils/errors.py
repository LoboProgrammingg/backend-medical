"""Custom exception classes."""

from typing import Any, Dict, Optional


class AppError(Exception):
    """Base class para erros da aplicação."""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Inicializa o erro.

        Args:
            message: Mensagem de erro amigável para o usuário.
            code: Código único do erro.
            status_code: Status HTTP code.
            details: Detalhes adicionais do erro.
        """
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Converte o erro para dicionário."""
        return {
            "success": False,
            "error": self.message,
            "code": self.code,
            "details": self.details,
        }


class AuthenticationError(AppError):
    """Erro de autenticação."""

    def __init__(self, message: str = "Falha na autenticação", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details,
        )


class AuthorizationError(AppError):
    """Erro de autorização."""

    def __init__(self, message: str = "Sem permissão para acessar este recurso", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
            details=details,
        )


class NotFoundError(AppError):
    """Recurso não encontrado."""

    def __init__(self, resource: str, details: Optional[Dict] = None):
        super().__init__(
            message=f"{resource} não encontrado",
            code="NOT_FOUND",
            status_code=404,
            details=details,
        )


class ValidationError(AppError):
    """Erro de validação."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class DatabaseError(AppError):
    """Erro de banco de dados."""

    def __init__(self, message: str = "Erro ao acessar o banco de dados", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=500,
            details=details,
        )


class ExternalServiceError(AppError):
    """Erro em serviço externo."""

    def __init__(self, service: str, details: Optional[Dict] = None):
        super().__init__(
            message=f"Erro ao comunicar com {service}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=503,
            details=details,
        )

