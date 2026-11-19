"""Pieces shared by the sync and async clients: config, request bodies, retries."""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional, Tuple

import httpx

from ._errors import (
    MissingAPIKeyError,
    RateLimitError,
    error_from_response,
    job_failed_error,
)
from ._types import JobStatus, parse_job_status
from ._version import __version__

DEFAULT_BASE_URL = "https://api.importly.io"
DEFAULT_TIMEOUT = 30.0
DEFAULT_WAIT_TIMEOUT = 600.0
DEFAULT_POLL_INTERVAL = 3.0

# job type -> (start path, status path)
ENDPOINTS: Dict[str, Tuple[str, str]] = {
    "import": ("/import", "/import/status"),
    "transcribe": ("/transcribe", "/transcribe/status"),
    "metadata": ("/metadata", "/metadata/status"),
    "basic-metadata": ("/metadata/basic", "/metadata/basic/status"),
}

_IMPORT_FIELDS = {
    "include_video": "includeVideo",
    "include_audio": "includeAudio",
    "video_quality": "videoQuality",
    "audio_quality": "audioQuality",
    "max_cost_dollars": "maxCostDollars",
    "webhook_url": "webhookUrl",
    "include_transcript": "includeTranscript",
    "transcript_provider": "transcriptProvider",
    "transcript_api_key": "transcriptApiKey",
    "transcript_language": "transcriptLanguage",
    "transcript_options": "transcriptOptions",
    "store": "store",
    "storage_path": "storagePath",
    "storage_filename": "storageFilename",
    "storage_bucket": "storageBucket",
    "storage_class": "storageClass",
}

_TRANSCRIBE_FIELDS = {
    "language": "language",
    "provider": "provider",
    "api_key": "apiKey",
    "provider_options": "providerOptions",
    "max_cost_dollars": "maxCostDollars",
    "webhook_url": "webhookUrl",
}

_METADATA_FIELDS = {"webhook_url": "webhookUrl"}

FIELDS_BY_TYPE = {
    "import": _IMPORT_FIELDS,
    "transcribe": _TRANSCRIBE_FIELDS,
    "metadata": _METADATA_FIELDS,
    "basic-metadata": _METADATA_FIELDS,
}


def build_body(job_type: str, url: str, options: Mapping[str, Any]) -> Dict[str, Any]:
    """Turn snake_case keyword options into the API's camelCase JSON body.

    ``None`` values are left out so the API's defaults apply. Unknown options
    raise ``TypeError``, like a wrong keyword argument would.
    """
    fields = FIELDS_BY_TYPE[job_type]
    unknown = set(options) - set(fields)
    if unknown:
        raise TypeError(f"Unknown option(s) for {job_type}: {', '.join(sorted(unknown))}")
    body: Dict[str, Any] = {"url": url}
    for name, value in options.items():
        if value is not None:
            body[fields[name]] = value
    return body


class ClientConfig:
    def __init__(
        self,
        api_key: Optional[str],
        base_url: Optional[str],
        timeout: float,
        max_retries: int,
        max_retry_wait: float,
    ) -> None:
        key = api_key or os.environ.get("IMPORTLY_API_KEY")
        if not key:
            raise MissingAPIKeyError(
                "No API key. Pass api_key=... or set IMPORTLY_API_KEY. "
                "Get one at https://www.importly.io/dashboard/api-key (free to try, no card required).",
                code="UNAUTHORIZED",
            )
        self.api_key = key
        self.base_url = (base_url or os.environ.get("IMPORTLY_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.max_retry_wait = max_retry_wait

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": f"importly-python/{__version__}",
        }


def parse_response(response: httpx.Response) -> Any:
    """Return ``data`` from a success envelope, or raise the matching error."""
    try:
        body = response.json()
    except ValueError:
        body = {"error": response.text[:500] or f"HTTP {response.status_code}"}
    if response.status_code >= 400 or (isinstance(body, dict) and body.get("success") is False):
        raise error_from_response(response.status_code if response.status_code >= 400 else 500, body)
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def retry_delay(error: Exception, attempt: int, method: str, max_retry_wait: float) -> Optional[float]:
    """Seconds to wait before retrying, or ``None`` to give up.

    - 429 is retried for any method (the request was refused before a job
      existed), if the wait is no longer than ``max_retry_wait``.
    - 5xx and dropped connections are retried for GET only: a POST that
      reached the server may already have started a (billed) job.
    - Connection failures before anything was sent are safe for any method.
    """
    from ._errors import InternalServerError

    if isinstance(error, RateLimitError):
        wait = error.retry_after if error.retry_after is not None else 2.0 ** attempt
        return wait if wait <= max_retry_wait else None
    backoff = min(0.5 * 2 ** attempt, 8.0)
    if isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout)):
        return backoff
    if method == "GET" and isinstance(error, (InternalServerError, httpx.TransportError)):
        return backoff
    return None


def status_or_raise(job_type: str, job_id: str, data: Mapping[str, Any]) -> JobStatus:
    return parse_job_status(job_type, {"jobId": job_id, **data})


def result_or_raise(status: JobStatus) -> Any:
    if status.failed:
        raise job_failed_error(status.job_type, status.job_id, status.raw)
    return status.result
