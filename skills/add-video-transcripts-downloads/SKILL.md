---
name: add-video-transcripts-downloads
description: Build video and audio link support into the user's app with the Importly API. Use when the app should take a YouTube, TikTok, X, Instagram, podcast or other media link and get the file (import from URL), a timestamped transcript, or metadata such as title, duration and thumbnail for link previews. Covers the backend route, the webhook and polling fallback, keeping the API key server-side, and one real test call.
license: MIT
compatibility: Works in any coding agent that can edit files. Importly's MCP server (https://mcp.importly.io/mcp) is optional; without it the skill reads Importly's docs over HTTPS.
metadata:
  homepage: https://www.importly.io/docs/integrations/build-with-your-agent
---

# Add video downloads, transcripts or metadata to this app

Importly is one API that turns a video or audio link into a file, a transcript or metadata. The app calls it from its backend with an API key, and it keeps working on production servers where downloads usually get blocked. These steps build that into the user's app the way the Importly docs describe.

## Rules

- Never ask the user to paste their Importly API key into the chat, and never print, log or commit it. Refer to it as `IMPORTLY_API_KEY`. The user puts the value in place.
- The key is read in server code only: an env file listed in `.gitignore`, or the host's secret store. Never in client code or a browser-exposed variable (`NEXT_PUBLIC_*`, `VITE_*`, `EXPO_PUBLIC_*`).
- Call the REST API at `https://api.importly.io` over HTTP, as in the docs. There is no official SDK package to install, so don't guess one.
- Use only facts from Importly's docs or `get_integration_guide`. If something isn't covered, say so instead of inventing parameters.

## 1. Look at the project

Find the framework and where server code lives (`package.json`, `requirements.txt` or `pyproject.toml`, `app/api` or `pages/api`, an Express or FastAPI server, `supabase/functions`). Tell the user what you found in one or two lines. If the folder has no app yet, follow https://www.importly.io/setup.md instead, which covers connecting and running a first test.

## 2. Ask what the feature should do

Unless the user already said, ask which one, and wait:

- **Import from URL**: download the video or audio file (`POST /import`). Links in the result expire after 7 days, so the app copies the file to its own storage, or uses `store: true` to deliver it to the user's S3-compatible bucket.
- **Transcripts**: text with timestamped segments (`POST /transcribe`). Uses the video's own captions when it has them. For media without captions, `provider: "importly"` runs speech-to-text.
- **Metadata**: `POST /metadata/basic` for a fast title, duration and thumbnail (link previews), or `POST /metadata` for formats, uploader and stats.

## 3. Get the code for this stack

- If Importly's MCP tools are available, call `get_integration_guide` with `language` (`node`, `nextjs`, `python` or `curl`) and `useCase` (`import`, `transcribe` or `metadata`). It's free and returns code for the key, the route, the webhook and polling.
- Otherwise fetch https://www.importly.io/docs/integrations/build-with-your-agent.md and the endpoint page for the use case: https://www.importly.io/docs/endpoints/import.md, https://www.importly.io/docs/endpoints/transcribe.md or https://www.importly.io/docs/endpoints/basic-metadata.md. https://www.importly.io/llms-full.txt has everything in one file.

[references/api.md](references/api.md) has the request and result shapes in short form.

## 4. Build it in

Follow the project's own patterns (router, ORM, job table, error handling):

1. A server route or backend function starts the job and stores `data.jobId` with the record. The browser calls this route, never Importly directly.
2. Results arrive by webhook at a server route (`webhookUrl` must be a public `https://` URL). The result fields sit directly on `data` in the webhook (`data.mediaUrl`, `data.text`) and under `data.result` when polling. Only act on a `data.jobId` the app stored, and make the handler idempotent.
3. Keep a polling fallback: `GET /<type>/status?id=<jobId>` every few seconds until `completed` or `failed`. Each webhook is sent once with no retries, so a missed delivery is caught here. During local development, when the app has no public URL, poll only.
4. Handle `402` (balance too low: tell the user to top up) and `429` (wait, then retry). For links that end users submit, set `maxCostDollars` on imports and speech-to-text so one request can't run up the bill.
5. If the project has `.env.example`, add `IMPORTLY_API_KEY=` to it with no value.

## 5. Key in place, then one real test

If the key goes in an env file, make sure that file is in `.gitignore` first. Then ask the user to:

1. Sign up at https://www.importly.io/login?mode=signup&utm_source=skills&utm_medium=skill&utm_campaign=guerrilla-2026-11&utm_content=add-video-transcripts-downloads (free to try, no card required) or sign in.
2. Copy the key from https://www.importly.io/dashboard/api-key.
3. Add `IMPORTLY_API_KEY=their_key` to the server env (`.env.local` for Next.js) or the host's secrets, and tell you when it's done.

Then try the feature once on a real link, through the app's own route, or with the matching MCP tool (`import_media`, `transcribe_media`, `get_metadata` or `get_basic_metadata`), which runs the same job as the endpoint. A transcript from captions or a metadata lookup costs $0.003 of the free credit.

## 6. Report

Finish with: the files you changed, where the key lives (the variable or secret name, never the value), how results arrive (webhook, polling or both), the test result, and the one next step for the user, such as setting the webhook URL once the app is deployed.
