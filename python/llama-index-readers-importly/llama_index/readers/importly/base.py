"""LlamaIndex reader for video and audio links, backed by the Importly API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Literal, Optional, Tuple

from llama_index.core.bridge.pydantic import Field, PrivateAttr
from llama_index.core.readers.base import BasePydanticReader
from llama_index.core.schema import Document

from importly import (
    AsyncImportly,
    BasicMetadata,
    Importly,
    ImportlyError,
    QueuedJob,
    Transcript,
    format_timestamp,
)

logger = logging.getLogger(__name__)

TranscriptFormat = Literal["text", "chunks", "segments"]

# Kept out of the text the LLM and the embedding model see; still on the node.
_HIDDEN_KEYS = ["job_id", "thumbnail", "transcript_source", "chunk_index", "start_seconds", "end_seconds"]


class ImportlyReader(BasePydanticReader):
    """Read transcripts of video and audio links into LlamaIndex ``Document`` objects.

    Works with YouTube, TikTok, X, Instagram, podcasts and 1,000+ other sites,
    and from servers and agent sandboxes where downloads usually get blocked.
    Needs an Importly API key (``IMPORTLY_API_KEY``); free to try, no card required:
    https://www.importly.io/?utm_source=llamaindex&utm_medium=package&utm_campaign=guerrilla-2026-11

    Example:
        .. code-block:: python

            from llama_index.readers.importly import ImportlyReader

            reader = ImportlyReader(transcript_format="chunks", chunk_size_seconds=60)
            documents = reader.load_data(["https://www.youtube.com/watch?v=jNQXAC9IVRw"])

    Args:
        api_key: Importly API key. Defaults to ``IMPORTLY_API_KEY``.
        transcript_format: ``"text"`` (one Document per link), ``"chunks"``
            (one per ~``chunk_size_seconds`` window) or ``"segments"``.
        chunk_size_seconds: Window length for ``"chunks"``.
        language: Two-letter language code, e.g. ``"es"``.
        provider: ``"importly"`` turns on speech-to-text for media without
            captions (billed per minute). Default: captions only.
        max_cost_dollars: Cap per link for speech-to-text.
        include_metadata: Also fetch title, duration and thumbnail.
        continue_on_failure: Log and skip links that fail instead of raising.
        timeout: Seconds to wait for each link.
        max_concurrency: Links processed at once by ``aload_data``.
    """

    is_remote: bool = True
    api_key: Optional[str] = Field(default=None, exclude=True, repr=False)
    base_url: Optional[str] = None
    transcript_format: TranscriptFormat = "text"
    chunk_size_seconds: float = Field(default=120, gt=0)
    language: Optional[str] = None
    provider: Optional[str] = None
    max_cost_dollars: Optional[float] = None
    include_metadata: bool = True
    continue_on_failure: bool = False
    timeout: float = 600
    poll_interval: float = 3
    max_concurrency: int = Field(default=4, ge=1)

    _client: Optional[Importly] = PrivateAttr(default=None)
    _async_client: Optional[AsyncImportly] = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        client: Optional[Importly] = None,
        async_client: Optional[AsyncImportly] = None,
        **data: Any,
    ) -> None:
        super().__init__(**data)
        self._client = client
        self._async_client = async_client

    @classmethod
    def class_name(cls) -> str:
        return "ImportlyReader"

    # -- shared -------------------------------------------------------------

    def _transcribe_options(self) -> Dict[str, Any]:
        return {"language": self.language, "provider": self.provider, "max_cost_dollars": self.max_cost_dollars}

    def _documents(self, url: str, job_id: str, transcript: Transcript, basic: Optional[BasicMetadata]) -> List[Document]:
        base: Dict[str, Any] = {
            "url": url,
            "job_id": job_id,
            "language": transcript.language,
            "transcript_source": transcript.source,
            "duration": transcript.duration,
        }
        if basic is not None:
            base["title"] = basic.title
            base["thumbnail"] = basic.thumbnail
            if base["duration"] is None:
                base["duration"] = basic.duration
        base = {k: v for k, v in base.items() if v is not None}

        if self.transcript_format == "text":
            return [self._document(f"{url}#transcript", transcript.text, base)]
        if self.transcript_format == "segments":
            pieces: List[Tuple[int, float, float, str]] = [(i, s.start, s.end, s.text) for i, s in enumerate(transcript.segments)]
        else:
            pieces = [(c.index, c.start, c.end, c.text) for c in transcript.chunks(self.chunk_size_seconds)]
        return [
            self._document(
                f"{url}#t={start:.3f}",
                text,
                {
                    **base,
                    "chunk_index": index,
                    "start_seconds": start,
                    "end_seconds": end,
                    "start_timestamp": format_timestamp(start),
                    "end_timestamp": format_timestamp(end),
                },
            )
            for index, start, end, text in pieces
            if text.strip()
        ]

    @staticmethod
    def _document(doc_id: str, text: str, metadata: Dict[str, Any]) -> Document:
        hidden = [k for k in _HIDDEN_KEYS if k in metadata]
        return Document(
            id_=doc_id,
            text=text,
            metadata=metadata,
            excluded_llm_metadata_keys=hidden,
            excluded_embed_metadata_keys=hidden,
        )

    def _handle_failure(self, url: str, error: Exception) -> None:
        if not self.continue_on_failure:
            raise error
        logger.warning("Skipping %s: %s", url, error)

    # -- sync -------------------------------------------------------------

    def load_data(self, urls: List[str], **load_kwargs: Any) -> List[Document]:
        """Load transcripts for ``urls``. Every link's jobs start before any wait."""
        if isinstance(urls, str):
            urls = [urls]
        client = self._client or Importly(self.api_key, base_url=self.base_url)
        try:
            started: List[Tuple[str, QueuedJob, Optional[QueuedJob]]] = []
            for url in urls:
                try:
                    job = client.start_transcription(url, **self._transcribe_options())
                except ImportlyError as error:
                    self._handle_failure(url, error)
                    continue
                started.append((url, job, self._start_basic(client, url)))

            documents: List[Document] = []
            for url, job, meta_job in started:
                try:
                    transcript = client.wait_for_transcription(job.job_id, timeout=self.timeout, poll_interval=self.poll_interval)
                except ImportlyError as error:
                    self._handle_failure(url, error)
                    continue
                documents.extend(self._documents(url, job.job_id, transcript, self._wait_basic(client, url, meta_job)))
            return documents
        finally:
            if self._client is None:
                client.close()

    def _start_basic(self, client: Importly, url: str) -> Optional[QueuedJob]:
        if not self.include_metadata:
            return None
        try:
            return client.start_basic_metadata(url)
        except ImportlyError as error:
            logger.warning("No title/thumbnail for %s: %s", url, error)
            return None

    def _wait_basic(self, client: Importly, url: str, job: Optional[QueuedJob]) -> Optional[BasicMetadata]:
        if job is None:
            return None
        try:
            return client.wait_for_basic_metadata(job.job_id, timeout=self.timeout, poll_interval=1.0)
        except ImportlyError as error:
            logger.warning("No title/thumbnail for %s: %s", url, error)
            return None

    # -- async -------------------------------------------------------------

    async def aload_data(self, urls: List[str], **load_kwargs: Any) -> List[Document]:
        """Like ``load_data``, processing up to ``max_concurrency`` links at once."""
        if isinstance(urls, str):
            urls = [urls]
        client = self._async_client or AsyncImportly(self.api_key, base_url=self.base_url)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        try:
            results = await asyncio.gather(*(self._aload_one(client, semaphore, url) for url in urls))
            return [doc for docs in results for doc in docs]
        finally:
            if self._async_client is None:
                await client.aclose()

    async def _aload_one(self, client: AsyncImportly, semaphore: asyncio.Semaphore, url: str) -> List[Document]:
        async with semaphore:
            basic_task: Optional["asyncio.Future[Optional[BasicMetadata]]"] = None
            try:
                job = await client.start_transcription(url, **self._transcribe_options())
                if self.include_metadata:
                    basic_task = asyncio.ensure_future(self._abasic(client, url))
                transcript = await client.wait_for_transcription(job.job_id, timeout=self.timeout, poll_interval=self.poll_interval)
            except ImportlyError as error:
                if basic_task is not None:
                    basic_task.cancel()
                self._handle_failure(url, error)
                return []
            basic = await basic_task if basic_task is not None else None
            return self._documents(url, job.job_id, transcript, basic)

    async def _abasic(self, client: AsyncImportly, url: str) -> Optional[BasicMetadata]:
        try:
            return await client.basic_metadata(url, timeout=self.timeout)
        except ImportlyError as error:
            logger.warning("No title/thumbnail for %s: %s", url, error)
            return None
