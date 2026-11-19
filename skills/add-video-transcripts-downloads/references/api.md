# Importly API in short

Base URL `https://api.importly.io`. Every request sends `Authorization: Bearer $IMPORTLY_API_KEY` from server code. The full reference is https://www.importly.io/docs/api-reference.md; when this file and the docs differ, the docs win.

## Start a job

Each call returns at once with `{ "success": true, "data": { "jobId": "…", "status": "queued" } }`. Store `data.jobId`.

| Use case | Request | Main body fields |
| --- | --- | --- |
| Download the file | `POST /import` | `url`, `webhookUrl`, `includeVideo` / `includeAudio`, `videoQuality`, `audioQuality`, `includeTranscript`, `store` (copy to the user's S3-compatible bucket), `maxCostDollars` |
| Transcript | `POST /transcribe` | `url`, `webhookUrl`, `language`, `provider` (`importly` for speech-to-text when there are no captions), `maxCostDollars` |
| Full metadata | `POST /metadata` | `url`, `webhookUrl` |
| Title, duration, thumbnail | `POST /metadata/basic` | `url`, `webhookUrl` |

## Get the result

- Webhook: one `POST` to `webhookUrl` when the job finishes. Envelope `{ success, data: { jobId, type, status, …result fields } }`. `data.type` is `import`, `transcribe`, `metadata` or `basic-metadata`. Result fields sit directly on `data`.
- Polling: `GET /import/status?id=<jobId>` (likewise `/transcribe/status`, `/metadata/status`, `/metadata/basic/status`) until `data.status` is `completed` or `failed`. Result fields sit under `data.result`. Failed jobs carry `data.message` and usually `data.code`.

## Result fields

- Import: `mediaUrl` (signed link, valid 7 days), `title`, `duration`, `thumbnailUrl`, `filename`, `fileSizeBytes`, `costInDollars`; `s3Storage: { url, bucket, key }` with `store: true`; `transcript` with `includeTranscript`.
- Transcribe: `text`, `language`, `duration`, `source`, and timestamped segments at `data.segments` inside the result (`{ start, end, text }`, seconds).
- Basic metadata: `title`, `duration`, `thumbnail`.
- Metadata: the platform's own fields in snake_case (`title`, `uploader`, `upload_date`, `view_count`, `formats`, …). They vary by site.

## Errors

`400` bad input, `401` bad key, `402` balance too low, `429` rate limited (wait and retry). A transcript job on media with no captions and no `provider` fails with `TRANSCRIPTION_PROVIDER_REQUIRED` and a price quote; retry with `provider: "importly"` if the user agrees to the cost.

Pages: https://www.importly.io/docs/webhooks.md, https://www.importly.io/docs/error-handling.md, https://www.importly.io/docs/billing.md.
