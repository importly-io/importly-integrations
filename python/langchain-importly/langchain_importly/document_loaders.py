"""LangChain document loader for video and audio links, backed by the Importly API."""

from __future__ import annotations

import asyncio
import logging
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

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


class ImportlyLoader(BaseLoader):
    """Load transcripts of video and audio links as LangChain ``Document`` objects.

    Works with YouTube, TikTok, X, Instagram, podcasts and 1,000+ other sites,
    and from servers and agent sandboxes where downloads usually get blocked.
    Needs an Importly API key (``IMPORTLY_API_KEY``); free to try, no card
    required: https://www.importly.io/?utm_source=langchain&utm_medium=package&utm_campaign=guerrilla-2026-11

    Setup:
        .. code-block:: bash

            pip install -U langchain-importly
            export IMPORTLY_API_KEY="..."

    Instantiate:
        .. code-block:: python

            from langchain_importly import ImportlyLoader

            loader = ImportlyLoader(
                ["https://www.youtube.com/watch?v=jNQXAC9IVRw"],
                transcript_format="chunks",
                chunk_size_seconds=60,
            )

    Load:
        .. code-block:: python

            docs = loader.load()
            docs[0].metadata
            # {'source': 'https://www.youtube.com/watch?v=jNQXAC9IVRw', 'title': 'Me at the zoo',
            #  'duration': 19.0, 'language': 'en', 'start_seconds': 1.2, 'start_timestamp': '00:00:01', ...}

    Async load:
        .. code-block:: python

            docs = await loader.aload()

    Args:
        urls: One link or a list of links.
        api_key: Importly API key. Defaults to ``IMPORTLY_API_KEY``.
        transcript_format: ``"text"`` (one Document per link), ``"chunks"``
            (one per ~``chunk_size_seconds`` window) or ``"segments"`` (one per
            caption segment).
        chunk_size_seconds: Window length for ``"chunks"``.
        language: Two-letter language code, e.g. ``"es"``. Picks the caption
            track, or is sent to speech-to-text.
        provider: Set to ``"importly"`` to use built-in speech-to-text for media
            without captions (billed per minute). Default: captions only.
        max_cost_dollars: Cap per link for speech-to-text.
        include_metadata: Also fetch title, duration and thumbnail (one basic
            metadata call per link).
        continue_on_failure: Log and skip links that fail instead of raising.
        timeout: Seconds to wait for each link.
        max_concurrency: Links processed at once by ``alazy_load``.
    """

    def __init__(
        self,
        urls: Union[str, Sequence[str]],
        *,
        api_key: Optional[str] = None,
        transcript_format: TranscriptFormat = "text",
        chunk_size_seconds: float = 120,
        language: Optional[str] = None,
        provider: Optional[str] = None,
        max_cost_dollars: Optional[float] = None,
        include_metadata: bool = True,
        continue_on_failure: bool = False,
        timeout: float = 600,
        poll_interval: float = 3,
        max_concurrency: int = 4,
        base_url: Optional[str] = None,
        client: Optional[Importly] = None,
        async_client: Optional[AsyncImportly] = None,
    ) -> None:
        if transcript_format not in ("text", "chunks", "segments"):
            raise ValueError("transcript_format must be 'text', 'chunks' or 'segments'")
        if chunk_size_seconds <= 0:
            raise ValueError("chunk_size_seconds must be positive")
        self.urls: List[str] = [urls] if isinstance(urls, str) else list(urls)
        self.api_key = api_key
        self.base_url = base_url
        self.transcript_format = transcript_format
        self.chunk_size_seconds = chunk_size_seconds
        self.language = language
        self.provider = provider
        self.max_cost_dollars = max_cost_dollars
        self.include_metadata = include_metadata
        self.continue_on_failure = continue_on_failure
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_concurrency = max(1, max_concurrency)
        self._client = client
        self._async_client = async_client

    # -- shared -------------------------------------------------------------

    def _transcribe_options(self) -> Dict[str, Any]:
        return {"language": self.language, "provider": self.provider, "max_cost_dollars": self.max_cost_dollars}

    def _documents(self, url: str, job_id: str, transcript: Transcript, basic: Optional[BasicMetadata]) -> List[Document]:
        base: Dict[str, Any] = {
            "source": url,
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
            return [Document(page_content=transcript.text, metadata=base)]
        if self.transcript_format == "segments":
            pieces: List[Tuple[int, float, float, str]] = [
                (i, s.start, s.end, s.text) for i, s in enumerate(transcript.segments)
            ]
        else:
            pieces = [(c.index, c.start, c.end, c.text) for c in transcript.chunks(self.chunk_size_seconds)]
        return [
            Document(
                page_content=text,
                metadata={
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

    def _handle_failure(self, url: str, error: Exception) -> None:
        if not self.continue_on_failure:
            raise error
        logger.warning("Skipping %s: %s", url, error)

    # -- sync -------------------------------------------------------------

    def lazy_load(self) -> Iterator[Document]:
        """Start every link's jobs first, then yield each link's Documents in order."""
        client = self._client or Importly(self.api_key, base_url=self.base_url)
        try:
            started: List[Tuple[str, QueuedJob, Optional[QueuedJob]]] = []
            for url in self.urls:
                try:
                    job = client.start_transcription(url, **self._transcribe_options())
                except ImportlyError as error:
                    self._handle_failure(url, error)
                    continue
                meta_job = self._start_basic(client, url)
                started.append((url, job, meta_job))

            for url, job, meta_job in started:
                try:
                    transcript = client.wait_for_transcription(job.job_id, timeout=self.timeout, poll_interval=self.poll_interval)
                except ImportlyError as error:
                    self._handle_failure(url, error)
                    continue
                basic = self._wait_basic(client, url, meta_job)
                yield from self._documents(url, job.job_id, transcript, basic)
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

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Process up to ``max_concurrency`` links at once; yield Documents in input order."""
        client = self._async_client or AsyncImportly(self.api_key, base_url=self.base_url)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        try:
            tasks = [asyncio.ensure_future(self._aload_one(client, semaphore, url)) for url in self.urls]
            try:
                for task in tasks:
                    for doc in await task:
                        yield doc
            finally:
                for task in tasks:
                    task.cancel()
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

