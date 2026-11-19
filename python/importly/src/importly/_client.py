"""Sync (``Importly``) and async (``AsyncImportly``) clients for the Importly API.

Every job is asynchronous on the server. Each job type has three calls:

- ``start_<job>(url, ...)`` queues it and returns a ``QueuedJob`` (use this with
  ``webhook_url``);
- ``get_<job>(job_id)`` returns one ``JobStatus`` poll;
- ``wait_for_<job>(job_id)`` polls until it finishes and returns the typed
  result, raising ``JobFailedError`` or ``JobTimeoutError``.

The one-call helpers ``import_media``, ``transcribe``, ``metadata`` and
``basic_metadata`` start a job and wait for it.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

import httpx

from ._base import (
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_WAIT_TIMEOUT,
    ENDPOINTS,
    ClientConfig,
    build_body,
    parse_response,
    result_or_raise,
    retry_delay,
    status_or_raise,
)
from ._errors import APIConnectionError, JobTimeoutError
from ._types import (
    Balance,
    BasicMetadata,
    ImportResult,
    JobStatus,
    Metadata,
    QueuedJob,
    Transcript,
)


class Importly:
    """Synchronous client.

    >>> client = Importly()  # reads IMPORTLY_API_KEY
    >>> transcript = client.transcribe("https://www.youtube.com/watch?v=jNQXAC9IVRw")
    >>> transcript.text
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 2,
        max_retry_wait: float = 60.0,
        http_client: Optional[httpx.Client] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = ClientConfig(api_key, base_url, timeout, max_retries, max_retry_wait)
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)
        self._sleep = sleep

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> "Importly":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- transport -----------------------------------------------------

    def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json: Any = None) -> Any:
        attempt = 0
        while True:
            try:
                response = self._http.request(
                    method,
                    self._config.base_url + path,
                    params=params,
                    json=json,
                    headers=self._config.headers,
                    timeout=self._config.timeout,
                )
                return parse_response(response)
            except Exception as error:  # noqa: BLE001 - re-raised below
                delay = retry_delay(error, attempt, method, self._config.max_retry_wait) if attempt < self._config.max_retries else None
                if delay is None:
                    if isinstance(error, httpx.TransportError):
                        raise APIConnectionError(f"Could not reach the Importly API: {error}") from error
                    raise
                attempt += 1
                self._sleep(delay)

    def _start(self, job_type: str, url: str, options: Dict[str, Any]) -> QueuedJob:
        data = self._request("POST", ENDPOINTS[job_type][0], json=build_body(job_type, url, options))
        return QueuedJob.from_dict(data)

    def get_job(self, job_type: str, job_id: str) -> JobStatus:
        """Poll any job by type (``import``, ``transcribe``, ``metadata``, ``basic-metadata``)."""
        data = self._request("GET", ENDPOINTS[job_type][1], params={"id": job_id})
        return status_or_raise(job_type, job_id, data)

    def wait_for_job(
        self,
        job_type: str,
        job_id: str,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> Any:
        """Poll until the job is final. Returns the typed result or raises ``JobFailedError``."""
        deadline = time.monotonic() + timeout
        while True:
            status = self.get_job(job_type, job_id)
            if status.is_done:
                return result_or_raise(status)
            if time.monotonic() + poll_interval > deadline:
                raise JobTimeoutError(
                    f"{job_type} job {job_id} still {status.status} after {timeout:.0f}s. "
                    "It may still finish: poll get_job() later or use a webhook.",
                    job_id=job_id,
                    job_type=job_type,
                )
            self._sleep(poll_interval)

    # -- import ----------------------------------------------------------

    def start_import(self, url: str, **options: Any) -> QueuedJob:
        """Queue a download. Options: ``include_video``, ``include_audio``, ``video_quality``,
        ``audio_quality``, ``max_cost_dollars``, ``webhook_url``, ``include_transcript``,
        ``transcript_provider``, ``transcript_api_key``, ``transcript_language``,
        ``transcript_options``, ``store``, ``storage_path``, ``storage_filename``,
        ``storage_bucket``, ``storage_class``."""
        return self._start("import", url, options)

    def get_import(self, job_id: str) -> JobStatus:
        return self.get_job("import", job_id)

    def wait_for_import(self, job_id: str, **wait: Any) -> ImportResult:
        return self.wait_for_job("import", job_id, **wait)

    def import_media(
        self, url: str, *, timeout: float = DEFAULT_WAIT_TIMEOUT, poll_interval: float = DEFAULT_POLL_INTERVAL, **options: Any
    ) -> ImportResult:
        """Download the media and wait. ``result.media_url`` is a signed link valid for 7 days."""
        job = self.start_import(url, **options)
        return self.wait_for_import(job.job_id, timeout=timeout, poll_interval=poll_interval)

    # -- transcribe ------------------------------------------------------

    def start_transcription(self, url: str, **options: Any) -> QueuedJob:
        """Queue a transcription. Options: ``language``, ``provider`` (``importly``,
        ``assemblyai``, ``deepgram``, ``openai``), ``api_key``, ``provider_options``,
        ``max_cost_dollars``, ``webhook_url``. Without ``provider`` it uses the media's captions."""
        return self._start("transcribe", url, options)

    def get_transcription(self, job_id: str) -> JobStatus:
        return self.get_job("transcribe", job_id)

    def wait_for_transcription(self, job_id: str, **wait: Any) -> Transcript:
        return self.wait_for_job("transcribe", job_id, **wait)

    def transcribe(
        self, url: str, *, timeout: float = DEFAULT_WAIT_TIMEOUT, poll_interval: float = DEFAULT_POLL_INTERVAL, **options: Any
    ) -> Transcript:
        """Transcribe and wait. Raises ``TranscriptionProviderRequiredError`` (with a ``quote``)
        when the media has no captions and no ``provider`` was set."""
        job = self.start_transcription(url, **options)
        return self.wait_for_transcription(job.job_id, timeout=timeout, poll_interval=poll_interval)

    # -- metadata --------------------------------------------------------

    def start_metadata(self, url: str, *, webhook_url: Optional[str] = None) -> QueuedJob:
        return self._start("metadata", url, {"webhook_url": webhook_url})

    def get_metadata(self, job_id: str) -> JobStatus:
        return self.get_job("metadata", job_id)

    def wait_for_metadata(self, job_id: str, **wait: Any) -> Metadata:
        return self.wait_for_job("metadata", job_id, **wait)

    def metadata(self, url: str, *, timeout: float = DEFAULT_WAIT_TIMEOUT, poll_interval: float = 2.0) -> Metadata:
        """Full metadata (title, description, uploader, stats, formats, ...) without downloading."""
        job = self.start_metadata(url)
        return self.wait_for_metadata(job.job_id, timeout=timeout, poll_interval=poll_interval)

    def start_basic_metadata(self, url: str, *, webhook_url: Optional[str] = None) -> QueuedJob:
        return self._start("basic-metadata", url, {"webhook_url": webhook_url})

    def get_basic_metadata(self, job_id: str) -> JobStatus:
        return self.get_job("basic-metadata", job_id)

    def wait_for_basic_metadata(self, job_id: str, **wait: Any) -> BasicMetadata:
        return self.wait_for_job("basic-metadata", job_id, **wait)

    def basic_metadata(self, url: str, *, timeout: float = DEFAULT_WAIT_TIMEOUT, poll_interval: float = 1.0) -> BasicMetadata:
        """Title, duration and thumbnail only: faster, for link previews and import forms."""
        job = self.start_basic_metadata(url)
        return self.wait_for_basic_metadata(job.job_id, timeout=timeout, poll_interval=poll_interval)

    # -- account ---------------------------------------------------------

    def balance(self) -> Balance:
        return Balance.from_dict(self._request("GET", "/balance"))


class AsyncImportly:
    """Asynchronous client with the same methods as ``Importly``, as coroutines.

    >>> async with AsyncImportly() as client:
    ...     transcripts = await asyncio.gather(*(client.transcribe(u) for u in urls))
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 2,
        max_retry_wait: float = 60.0,
        http_client: Optional[httpx.AsyncClient] = None,
        sleep: Optional[Callable[[float], Any]] = None,
    ) -> None:
        self._config = ClientConfig(api_key, base_url, timeout, max_retries, max_retry_wait)
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)
        self._sleep = sleep or asyncio.sleep

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> "AsyncImportly":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None, json: Any = None) -> Any:
        attempt = 0
        while True:
            try:
                response = await self._http.request(
                    method,
                    self._config.base_url + path,
                    params=params,
                    json=json,
                    headers=self._config.headers,
                    timeout=self._config.timeout,
                )
                return parse_response(response)
            except Exception as error:  # noqa: BLE001 - re-raised below
                delay = retry_delay(error, attempt, method, self._config.max_retry_wait) if attempt < self._config.max_retries else None
                if delay is None:
                    if isinstance(error, httpx.TransportError):
                        raise APIConnectionError(f"Could not reach the Importly API: {error}") from error
                    raise
                attempt += 1
                await self._sleep(delay)

    async def _start(self, job_type: str, url: str, options: Dict[str, Any]) -> QueuedJob:
        data = await self._request("POST", ENDPOINTS[job_type][0], json=build_body(job_type, url, options))
        return QueuedJob.from_dict(data)

    async def get_job(self, job_type: str, job_id: str) -> JobStatus:
        data = await self._request("GET", ENDPOINTS[job_type][1], params={"id": job_id})
        return status_or_raise(job_type, job_id, data)

    async def wait_for_job(
        self,
        job_type: str,
        job_id: str,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> Any:
        deadline = time.monotonic() + timeout
        while True:
            status = await self.get_job(job_type, job_id)
            if status.is_done:
                return result_or_raise(status)
            if time.monotonic() + poll_interval > deadline:
                raise JobTimeoutError(
                    f"{job_type} job {job_id} still {status.status} after {timeout:.0f}s. "
                    "It may still finish: poll get_job() later or use a webhook.",
                    job_id=job_id,
                    job_type=job_type,
                )
            await self._sleep(poll_interval)

    async def start_import(self, url: str, **options: Any) -> QueuedJob:
        return await self._start("import", url, options)

    async def get_import(self, job_id: str) -> JobStatus:
        return await self.get_job("import", job_id)

    async def wait_for_import(self, job_id: str, **wait: Any) -> ImportResult:
        return await self.wait_for_job("import", job_id, **wait)

    async def import_media(
        self, url: str, *, timeout: float = DEFAULT_WAIT_TIMEOUT, poll_interval: float = DEFAULT_POLL_INTERVAL, **options: Any
    ) -> ImportResult:
        job = await self.start_import(url, **options)
        return await self.wait_for_import(job.job_id, timeout=timeout, poll_interval=poll_interval)

    async def start_transcription(self, url: str, **options: Any) -> QueuedJob:
        return await self._start("transcribe", url, options)

    async def get_transcription(self, job_id: str) -> JobStatus:
        return await self.get_job("transcribe", job_id)

    async def wait_for_transcription(self, job_id: str, **wait: Any) -> Transcript:
        return await self.wait_for_job("transcribe", job_id, **wait)

    async def transcribe(
        self, url: str, *, timeout: float = DEFAULT_WAIT_TIMEOUT, poll_interval: float = DEFAULT_POLL_INTERVAL, **options: Any
    ) -> Transcript:
        job = await self.start_transcription(url, **options)
        return await self.wait_for_transcription(job.job_id, timeout=timeout, poll_interval=poll_interval)

    async def start_metadata(self, url: str, *, webhook_url: Optional[str] = None) -> QueuedJob:
        return await self._start("metadata", url, {"webhook_url": webhook_url})

    async def get_metadata(self, job_id: str) -> JobStatus:
        return await self.get_job("metadata", job_id)

    async def wait_for_metadata(self, job_id: str, **wait: Any) -> Metadata:
        return await self.wait_for_job("metadata", job_id, **wait)

    async def metadata(self, url: str, *, timeout: float = DEFAULT_WAIT_TIMEOUT, poll_interval: float = 2.0) -> Metadata:
        job = await self.start_metadata(url)
        return await self.wait_for_metadata(job.job_id, timeout=timeout, poll_interval=poll_interval)

    async def start_basic_metadata(self, url: str, *, webhook_url: Optional[str] = None) -> QueuedJob:
        return await self._start("basic-metadata", url, {"webhook_url": webhook_url})

    async def get_basic_metadata(self, job_id: str) -> JobStatus:
        return await self.get_job("basic-metadata", job_id)

    async def wait_for_basic_metadata(self, job_id: str, **wait: Any) -> BasicMetadata:
        return await self.wait_for_job("basic-metadata", job_id, **wait)

    async def basic_metadata(self, url: str, *, timeout: float = DEFAULT_WAIT_TIMEOUT, poll_interval: float = 1.0) -> BasicMetadata:
        job = await self.start_basic_metadata(url)
        return await self.wait_for_basic_metadata(job.job_id, timeout=timeout, poll_interval=poll_interval)

    async def balance(self) -> Balance:
        return Balance.from_dict(await self._request("GET", "/balance"))


__all__: List[str] = ["Importly", "AsyncImportly"]
