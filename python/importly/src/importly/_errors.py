"""Errors raised by the Importly client.

Every error is an ``ImportlyError``. Request errors (the API said no) are
``APIError`` subclasses chosen by HTTP status and ``code``. A job that was
accepted but failed later raises ``JobFailedError`` from the ``wait_*`` and
one-call helpers.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


class ImportlyError(Exception):
    """Base class for every error this package raises."""

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        documentation_url: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.documentation_url = documentation_url

    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.append(f"[{self.code}]")
        if self.documentation_url:
            parts.append(f"See {self.documentation_url}")
        return " ".join(parts)


class MissingAPIKeyError(ImportlyError):
    """No API key was passed and ``IMPORTLY_API_KEY`` is not set."""


class APIConnectionError(ImportlyError):
    """The request never got an HTTP response (DNS, TLS, timeout, reset)."""


class APIError(ImportlyError):
    """The API answered with an error status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: Optional[str] = None,
        documentation_url: Optional[str] = None,
        body: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message, code=code, documentation_url=documentation_url)
        self.status_code = status_code
        self.body: Dict[str, Any] = dict(body or {})


class InvalidRequestError(APIError):
    """400: a parameter is missing or invalid. Fix the request; don't retry it."""


class InvalidURLError(InvalidRequestError):
    """400 with ``INVALID_URL`` (or ``PLAYLIST_NOT_SUPPORTED``): the media URL was rejected."""


class AuthenticationError(APIError):
    """401: the API key is missing or invalid."""


class InsufficientBalanceError(APIError):
    """402: the balance is below what the job needs to start. Add credits, then retry."""

    @property
    def balance_required(self) -> Optional[float]:
        value = self.body.get("balanceRequired")
        return float(value) if value is not None else None

    @property
    def endpoint(self) -> Optional[str]:
        return self.body.get("endpoint")


class NotFoundError(APIError):
    """404: no job with that id belongs to this account."""


class RateLimitError(APIError):
    """429: over the hourly limit for this endpoint. Wait ``retry_after`` seconds."""

    @property
    def retry_after(self) -> Optional[float]:
        value = self.body.get("retryAfter")
        return float(value) if value is not None else None

    @property
    def limit(self) -> Optional[int]:
        return self.body.get("limit")

    @property
    def remaining(self) -> Optional[int]:
        return self.body.get("remaining")

    @property
    def reset(self) -> Optional[int]:
        """When the window resets, as Unix time in milliseconds."""
        return self.body.get("reset")


class InternalServerError(APIError):
    """5xx: something broke on Importly's side. Safe to retry with backoff."""


class JobFailedError(ImportlyError):
    """A job was accepted but failed, e.g. ``VIDEO_PRIVATE`` or ``MAX_COST_EXCEEDED``."""

    def __init__(
        self,
        message: str,
        *,
        job_id: str,
        job_type: str,
        code: Optional[str] = None,
        documentation_url: Optional[str] = None,
        raw: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message, code=code, documentation_url=documentation_url)
        self.job_id = job_id
        self.job_type = job_type
        self.raw: Dict[str, Any] = dict(raw or {})


class TranscriptionProviderRequiredError(JobFailedError):
    """The media has no captions and no speech-to-text provider was set.

    ``quote`` holds what built-in speech-to-text (``provider="importly"``) would
    cost, when the duration is known.
    """

    @property
    def quote(self) -> Optional[Dict[str, Any]]:
        return self.raw.get("quote")


class JobTimeoutError(ImportlyError):
    """The job was still running when the wait timed out. It may still finish."""

    def __init__(self, message: str, *, job_id: str, job_type: str) -> None:
        super().__init__(message)
        self.job_id = job_id
        self.job_type = job_type


def error_from_response(status_code: int, body: Any) -> APIError:
    """Map an error response to the matching ``APIError`` subclass."""
    data: Dict[str, Any] = body if isinstance(body, dict) else {}
    message = str(data.get("error") or data.get("message") or f"HTTP {status_code}")
    code = data.get("code")
    kwargs: Dict[str, Any] = {
        "status_code": status_code,
        "code": code,
        "documentation_url": data.get("documentationUrl"),
        "body": data,
    }
    if status_code == 401:
        return AuthenticationError(message, **kwargs)
    if status_code == 402:
        return InsufficientBalanceError(message, **kwargs)
    if status_code == 404:
        return NotFoundError(message, **kwargs)
    if status_code == 429:
        return RateLimitError(message, **kwargs)
    if status_code == 400:
        if code in ("INVALID_URL", "PLAYLIST_NOT_SUPPORTED"):
            return InvalidURLError(message, **kwargs)
        return InvalidRequestError(message, **kwargs)
    if status_code >= 500:
        return InternalServerError(message, **kwargs)
    return APIError(message, **kwargs)


def job_failed_error(job_type: str, job_id: str, data: Mapping[str, Any]) -> JobFailedError:
    """Build the error for a job whose status is ``failed``."""
    message = str(data.get("message") or f"{job_type} job {job_id} failed")
    code = data.get("code")
    cls = TranscriptionProviderRequiredError if code == "TRANSCRIPTION_PROVIDER_REQUIRED" else JobFailedError
    return cls(
        message,
        job_id=job_id,
        job_type=job_type,
        code=code,
        documentation_url=data.get("documentationUrl"),
        raw=data,
    )
