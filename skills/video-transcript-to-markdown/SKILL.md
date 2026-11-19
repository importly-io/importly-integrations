---
name: video-transcript-to-markdown
description: Add a step to the user's app that turns a video or audio link into clean, timestamped Markdown for RAG, search or an LLM prompt, using Importly transcripts. Use when the app ingests YouTube, TikTok, X, podcast or other media links into a knowledge base, vector store or chat-with-video feature, or the user asks for transcripts as Markdown or chunks with timestamps.
license: MIT
compatibility: Works in any coding agent that can edit files. Builds on the add-video-transcripts-downloads skill for the API call itself.
metadata:
  homepage: https://www.importly.io/docs/features/transcripts
---

# Video transcript to Markdown for RAG

This adds one step to an app's ingestion pipeline: a media link goes in, Markdown with a title, source link and timestamped sections comes out, ready to chunk and embed. Importly supplies the transcript from the app's backend, so it works on production servers, not only on a laptop.

## 1. Get transcripts flowing first

If the app doesn't call Importly yet, follow the `add-video-transcripts-downloads` skill (or https://www.importly.io/setup.md) to add the `POST /transcribe` route, the webhook and the polling fallback, with `IMPORTLY_API_KEY` kept server-side. Never ask for the key in chat. Then come back here.

The completed transcript has `text`, `language`, `duration` and timestamped segments (`{ start, end, text }`, in seconds). In a webhook they sit on `data` (`data.text`, `data.data.segments`); when polling, under `data.result` (`data.result.text`, `data.result.data.segments`). For the title, either start a `POST /metadata/basic` job for the same link (it returns `title`, `duration`, `thumbnail`) or use a title the app already has.

## 2. Write the converter

Add one pure function in the app's language, next to the ingestion code, with a unit test. Input: the segments, the source URL, the title and the language. Output: a Markdown string like this one (made with a 10-second window):

```markdown
# Me at the zoo

Source: https://www.youtube.com/watch?v=jNQXAC9IVRw
Language: en · Duration: 0:19

## 0:01

All right, so here we are, in front of the elephants the cool thing about these guys is that they have really... really really long trunks

## 0:12

and that's cool (baaaaaaaaaaahhh!!) and that's pretty much all there is to say
```

Rules for the function:

- Group segments into sections by time window (default 60 seconds; make it a parameter). Start a new section only on a segment boundary, so no sentence is cut.
- Heading per section is the start time of its first segment as `m:ss` or `h:mm:ss`. For YouTube links, the app can also link the heading to `?t=<seconds>`.
- Join segment text with spaces and collapse whitespace. Keep the words as they are: no rewriting or summarising in this step.
- If there are no segments, fall back to `text` under a single section.
- Escape nothing that isn't Markdown syntax; leave caption markers such as `[Music]` as they are.

## 3. Chunk and store

If the app already chunks documents, feed it the Markdown and split on the `## ` headings, keeping the title and source line on each chunk. If it doesn't, store one record per section with `sourceUrl`, `startSeconds`, `endSeconds` and the section text, so answers can cite the moment in the video.

## 4. Test it

Unit-test the converter with a fixed segment list (including an empty list and a segment longer than the window). Then run the whole flow once on a real link once the user's key is in place. A transcript from captions costs $0.003; media without captions needs `provider: "importly"` ($0.01 per minute), so ask the user before using it.

Finish by telling the user which files changed and where the Markdown is stored. New to Importly? It's free to try, no card required: https://www.importly.io/?utm_source=skills&utm_medium=skill&utm_campaign=guerrilla-2026-11&utm_content=video-transcript-to-markdown
