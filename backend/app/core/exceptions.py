from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class IncuBrixException(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str = "An unexpected error occurred",
        error_code: str = "INTERNAL_ERROR",
        extra: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.extra = extra or {}


class AuthenticationError(IncuBrixException):
    def __init__(self, detail: str = "Invalid credentials or token expired"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="AUTHENTICATION_FAILED"
        )


class PermissionDeniedError(IncuBrixException):
    def __init__(self, detail: str = "You do not have permission to access this resource"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="PERMISSION_DENIED"
        )


class NotFoundError(IncuBrixException):
    def __init__(self, resource: str = "Resource", identifier: str = ""):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} {identifier} was not found" if identifier else f"{resource} not found",
            error_code="NOT_FOUND"
        )


class ProviderUnavailableError(IncuBrixException):
    def __init__(self, provider: str, reason: str):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Integration provider '{provider}' is currently unavailable: {reason}",
            error_code="PROVIDER_UNAVAILABLE",
            extra={"provider": provider, "reason": reason}
        )


class ContentValidationError(IncuBrixException):
    def __init__(self, violations: list):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Content failed brand or platform validation rules",
            error_code="VALIDATION_FAILED",
            extra={"violations": violations}
        )
