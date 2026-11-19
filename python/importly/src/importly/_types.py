"""Typed results returned by the Importly client.

Each result keeps the API's JSON in ``raw`` so fields the API adds later are
still reachable without a new release of this package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Mapping, Optional

JobType = Literal["import", "transcribe", "metadata", "basic-metadata"]
JobStatusValue = Literal["queued", "running", "completed", "failed"]

FINAL_STATUSES = ("completed", "failed")


def _float(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _int(value: Any) -> Optional[int]:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def format_timestamp(seconds: float) -> str:
    """``75.4`` -> ``"00:01:15"``."""
    total = int(seconds)
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


@dataclass(frozen=True)
class QueuedJob:
    """What a ``start_*`` call returns: the job id to poll or match a webhook against."""

    job_id: str
    status: str
    message: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "QueuedJob":
        return cls(job_id=str(data["jobId"]), status=str(data.get("status", "queued")), message=data.get("message"), raw=dict(data))


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TranscriptSegment":
        return cls(start=float(data.get("start") or 0), end=float(data.get("end") or 0), text=str(data.get("text") or ""))


@dataclass(frozen=True)
class TranscriptChunk:
    """Consecutive segments grouped into one window of roughly ``chunk_seconds``."""

    index: int
    start: float
    end: float
    text: str

    @property
    def start_timestamp(self) -> str:
        return format_timestamp(self.start)

    @property
    def end_timestamp(self) -> str:
        return format_timestamp(self.end)


@dataclass(frozen=True)
class Transcript:
    """A finished transcription: full text plus timestamped segments."""

    text: str
    source: Optional[str] = None
    language: Optional[str] = None
    duration: Optional[float] = None
    segments: List[TranscriptSegment] = field(default_factory=list)
    cost_in_dollars: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Transcript":
        inner = data.get("data") if isinstance(data.get("data"), Mapping) else {}
        segments = inner.get("segments") if isinstance(inner, Mapping) else None
        return cls(
            text=str(data.get("text") or ""),
            source=data.get("source"),
            language=data.get("language"),
            duration=_float(data.get("duration")),
            segments=[TranscriptSegment.from_dict(s) for s in (segments or []) if isinstance(s, Mapping)],
            cost_in_dollars=_float(data.get("costInDollars")),
            raw=dict(data),
        )

    def chunks(self, chunk_seconds: float = 120) -> List[TranscriptChunk]:
        """Group segments into windows of about ``chunk_seconds``.

        A chunk closes at the first segment boundary at or past the window, so
        no segment is split. With no segments, the whole text is one chunk.
        """
        if chunk_seconds <= 0:
            raise ValueError("chunk_seconds must be positive")
        if not self.segments:
            if not self.text:
                return []
            return [TranscriptChunk(index=0, start=0.0, end=self.duration or 0.0, text=self.text)]
        chunks: List[TranscriptChunk] = []
        current: List[TranscriptSegment] = []
        for segment in self.segments:
            if current and segment.start - current[0].start >= chunk_seconds:
                chunks.append(self._chunk(len(chunks), current))
                current = []
            current.append(segment)
        if current:
            chunks.append(self._chunk(len(chunks), current))
        return chunks

    @staticmethod
    def _chunk(index: int, segments: List[TranscriptSegment]) -> TranscriptChunk:
        text = " ".join(s.text.strip() for s in segments if s.text.strip())
        return TranscriptChunk(index=index, start=segments[0].start, end=segments[-1].end, text=text)


@dataclass(frozen=True)
class S3Location:
    url: Optional[str] = None
    bucket: Optional[str] = None
    key: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "S3Location":
        return cls(url=data.get("url"), bucket=data.get("bucket"), key=data.get("key"))


@dataclass(frozen=True)
class ImportResult:
    """A finished import: a signed download link (valid 7 days) and file details."""

    media_url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None
    filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    downloaded_bytes: Optional[int] = None
    cost_in_dollars: Optional[float] = None
    transcript: Optional[Transcript] = None
    transcript_skipped_reason: Optional[str] = None
    s3_storage: Optional[S3Location] = None
    s3_storage_error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ImportResult":
        transcript_data = data.get("transcript")
        transcript: Optional[Transcript] = None
        skipped: Optional[str] = None
        if isinstance(transcript_data, Mapping):
            if transcript_data.get("status") == "skipped":
                skipped = str(transcript_data.get("reason") or "skipped")
            elif "text" in transcript_data:
                transcript = Transcript.from_dict(transcript_data)
        s3 = data.get("s3Storage")
        return cls(
            media_url=data.get("mediaUrl"),
            title=data.get("title"),
            duration=_float(data.get("duration")),
            thumbnail_url=data.get("thumbnailUrl"),
            filename=data.get("filename"),
            file_size_bytes=_int(data.get("fileSizeBytes")),
            downloaded_bytes=_int(data.get("downloadedBytes")),
            cost_in_dollars=_float(data.get("costInDollars")),
            transcript=transcript,
            transcript_skipped_reason=skipped,
            s3_storage=S3Location.from_dict(s3) if isinstance(s3, Mapping) else None,
            s3_storage_error=data.get("s3StorageError"),
            raw=dict(data),
        )


@dataclass(frozen=True)
class Metadata:
    """Full metadata. Fields vary by platform; everything is in ``raw`` (snake_case)."""

    id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[float] = None
    uploader: Optional[str] = None
    upload_date: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    thumbnail: Optional[str] = None
    webpage_url: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    formats: List[Dict[str, Any]] = field(default_factory=list, repr=False)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Metadata":
        return cls(
            id=data.get("id"),
            title=data.get("title"),
            description=data.get("description"),
            duration=_float(data.get("duration")),
            uploader=data.get("uploader"),
            upload_date=data.get("upload_date"),
            view_count=_int(data.get("view_count")),
            like_count=_int(data.get("like_count")),
            thumbnail=data.get("thumbnail"),
            webpage_url=data.get("webpage_url"),
            tags=[str(t) for t in (data.get("tags") or [])],
            formats=[dict(f) for f in (data.get("formats") or []) if isinstance(f, Mapping)],
            raw=dict(data),
        )


@dataclass(frozen=True)
class BasicMetadata:
    """Title, duration and thumbnail: the fast, cheap preview."""

    title: Optional[str] = None
    duration: Optional[float] = None
    thumbnail: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BasicMetadata":
        return cls(title=data.get("title"), duration=_float(data.get("duration")), thumbnail=data.get("thumbnail"), raw=dict(data))


@dataclass(frozen=True)
class Balance:
    balance: float
    currency: str = "USD"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Balance":
        return cls(balance=float(data.get("balance") or 0), currency=str(data.get("currency") or "USD"))


@dataclass(frozen=True)
class JobStatus:
    """One poll of a job's ``/status`` endpoint.

    ``result`` is the typed result once ``status == "completed"`` (an
    ``ImportResult``, ``Transcript``, ``Metadata`` or ``BasicMetadata``).
    ``code``, ``message`` and ``documentation_url`` are set when it failed.
    """

    job_id: str
    job_type: str
    status: str
    result: Any = None
    code: Optional[str] = None
    message: Optional[str] = None
    documentation_url: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_done(self) -> bool:
        return self.status in FINAL_STATUSES

    @property
    def succeeded(self) -> bool:
        return self.status == "completed"

    @property
    def failed(self) -> bool:
        return self.status == "failed"


RESULT_PARSERS = {
    "import": ImportResult.from_dict,
    "transcribe": Transcript.from_dict,
    "metadata": Metadata.from_dict,
    "basic-metadata": BasicMetadata.from_dict,
}


def parse_job_status(job_type: str, data: Mapping[str, Any]) -> JobStatus:
    status = str(data.get("status") or "queued")
    result_data = data.get("result")
    result = None
    if status == "completed" and isinstance(result_data, Mapping):
        result = RESULT_PARSERS[job_type](result_data)
    return JobStatus(
        job_id=str(data.get("jobId") or ""),
        job_type=job_type,
        status=status,
        result=result,
        code=data.get("code"),
        message=data.get("message"),
        documentation_url=data.get("documentationUrl"),
        raw=dict(data),
    )
