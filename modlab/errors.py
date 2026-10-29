"""Errores con mensajes pensados para mostrarse al usuario tal cual."""


class CatalogError(ValueError):
    """Error explicable de un catálogo o de una operación del pack."""


class AuthError(CatalogError):
    pass


class RateLimitError(CatalogError):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class NetworkError(CatalogError):
    pass


class NotFoundError(CatalogError):
    pass


class Cancelled(Exception):
    """La persona canceló la operación; no es un error."""
