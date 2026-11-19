"""Parse the webhooks Importly sends to your ``webhook_url``.

Importly POSTs once per job: ``success: true`` with the result fields flattened
into ``data`` when the job completes, or ``success: false`` with ``code`` and
``message`` when it fails for good. Deliveries are not retried, so keep a
polling fallback (``client.get_job(event.job_type, event.job_id)``).

Webhooks are not signed. Put a hard-to-guess token in your webhook URL
(``https://your-app.com/webhooks/importly?token=...``) and check it with
``token_matches``, and match ``event.job_id`` against the ids you started. For
anything that moves money or data, confirm with ``client.get_job(...)``.

Flask example::

    from importly.webhooks import parse_webhook, token_matches

    @app.post("/webhooks/importly")
    def importly_webhook():
        if not token_matches(request.args.get("token"), os.environ["IMPORTLY_WEBHOOK_TOKEN"]):
            abort(401)
        event = parse_webhook(request.get_data())
        if event.succeeded and event.job_type == "transcribe":
            save_transcript(event.job_id, event.result.text)
        elif event.failed:
            mark_failed(event.job_id, event.code, event.message)
        return "", 204
"""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Union

from ._errors import ImportlyError, JobFailedError, job_failed_error
from ._types import RESULT_PARSERS

_ENVELOPE_KEYS = ("jobId", "type", "status")


class InvalidWebhookError(ImportlyError):
    """The body isn't an Importly webhook payload."""


@dataclass(frozen=True)
class WebhookEvent:
    """One webhook delivery.

    ``result`` is typed by ``job_type``: ``ImportResult`` (import),
    ``Transcript`` (transcribe), ``Metadata`` (metadata) or ``BasicMetadata``
    (basic-metadata). It is ``None`` when the job failed.
    """

    job_id: str
    job_type: str
    status: str
    result: Any = None
    code: Optional[str] = None
    message: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def succeeded(self) -> bool:
        return self.status == "completed"

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    def to_error(self) -> JobFailedError:
        """The failure as an exception, e.g. to raise it in a worker."""
        return job_failed_error(self.job_type, self.job_id, self.raw.get("data") or {})


def parse_webhook(payload: Union[bytes, str, Mapping[str, Any]]) -> WebhookEvent:
    """Parse a webhook body (raw bytes, a JSON string, or an already-decoded dict)."""
    body: Any = payload
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        try:
            body = json.loads(payload)
        except ValueError as error:
            raise InvalidWebhookError("Webhook body is not valid JSON") from error
    if not isinstance(body, Mapping) or not isinstance(body.get("data"), Mapping):
        raise InvalidWebhookError("Webhook body has no 'data' object")
    data = body["data"]
    missing = [key for key in _ENVELOPE_KEYS if key not in data]
    if missing:
        raise InvalidWebhookError(f"Webhook data is missing {', '.join(missing)}")
    job_type = str(data["type"])
    if job_type not in RESULT_PARSERS:
        raise InvalidWebhookError(f"Unknown webhook job type: {job_type}")
    status = str(data["status"])
    failed = body.get("success") is False or status == "failed"
    result = None
    if not failed:
        fields = {k: v for k, v in data.items() if k not in _ENVELOPE_KEYS}
        result = RESULT_PARSERS[job_type](fields)
    return WebhookEvent(
        job_id=str(data["jobId"]),
        job_type=job_type,
        status="failed" if failed else status,
        result=result,
        code=data.get("code"),
        message=data.get("message"),
        raw=dict(body),
    )


def token_matches(received: Optional[str], expected: str) -> bool:
    """Constant-time check of the token you put in your webhook URL."""
    if not received or not expected:
        return False
    return hmac.compare_digest(received.encode(), expected.encode())
