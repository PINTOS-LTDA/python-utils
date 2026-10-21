"""Public exceptions raised by the email module."""


class EmailError(Exception):
    """Base class for errors exposed by ``pintos_utils.email``."""


class EmailValidationError(EmailError):
    """Raised when an email model contains invalid or unsafe values."""


class EmailConfigurationError(EmailError):
    """Raised when provider configuration is missing or unusable."""


class EmailAuthenticationError(EmailError):
    """Raised when provider credentials are rejected or cannot be refreshed."""


class EmailProviderError(EmailError):
    """Raised when a provider request fails or has an indeterminate outcome."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable
