from pintos_utils.email.exceptions import (
    EmailAuthenticationError,
    EmailConfigurationError,
    EmailError,
    EmailProviderError,
    EmailValidationError,
)


def test_public_exceptions_share_email_error_base() -> None:
    assert issubclass(EmailValidationError, EmailError)
    assert issubclass(EmailConfigurationError, EmailError)
    assert issubclass(EmailAuthenticationError, EmailError)
    assert issubclass(EmailProviderError, EmailError)


def test_provider_error_exposes_provider_and_retryability() -> None:
    error = EmailProviderError(
        "Gmail temporarily rejected the request",
        provider="gmail",
        retryable=True,
    )

    assert error.provider == "gmail"
    assert error.retryable is True
    assert str(error) == "Gmail temporarily rejected the request"


def test_provider_error_allows_unknown_retryability() -> None:
    error = EmailProviderError("Provider outcome is unknown", provider="gmail")

    assert error.retryable is None
