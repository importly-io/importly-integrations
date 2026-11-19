"""Importly: turn any video or audio link into files, transcripts and metadata.

    from importly import Importly

    client = Importly()  # reads IMPORTLY_API_KEY
    transcript = client.transcribe("https://www.youtube.com/watch?v=jNQXAC9IVRw")
    print(transcript.text)

Docs: https://www.importly.io/docs
"""

from ._client import AsyncImportly, Importly
from ._errors import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    ImportlyError,
    InsufficientBalanceError,
    InternalServerError,
    InvalidRequestError,
    InvalidURLError,
    JobFailedError,
    JobTimeoutError,
    MissingAPIKeyError,
    NotFoundError,
    RateLimitError,
    TranscriptionProviderRequiredError,
)
from ._types import (
    Balance,
    BasicMetadata,
    ImportResult,
    JobStatus,
    Metadata,
    QueuedJob,
    S3Location,
    Transcript,
    TranscriptChunk,
    TranscriptSegment,
    format_timestamp,
)
from ._version import __version__
from .webhooks import InvalidWebhookError, WebhookEvent, parse_webhook, token_matches

__all__ = [
    "Importly",
    "AsyncImportly",
    "ImportlyError",
    "MissingAPIKeyError",
    "APIConnectionError",
    "APIError",
    "InvalidRequestError",
    "InvalidURLError",
    "AuthenticationError",
    "InsufficientBalanceError",
    "NotFoundError",
    "RateLimitError",
    "InternalServerError",
    "JobFailedError",
    "TranscriptionProviderRequiredError",
    "JobTimeoutError",
    "Balance",
    "BasicMetadata",
    "ImportResult",
    "JobStatus",
    "Metadata",
    "QueuedJob",
    "S3Location",
    "Transcript",
    "TranscriptChunk",
    "TranscriptSegment",
    "format_timestamp",
    "WebhookEvent",
    "InvalidWebhookError",
    "parse_webhook",
    "token_matches",
    "__version__",
]
