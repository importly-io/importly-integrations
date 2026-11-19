# Importly skills for coding agents

Skills that build video and audio link support into your app: a user pastes a YouTube, TikTok, X, Instagram or podcast link, and your app gets the file, a timestamped transcript or metadata. Your agent writes the backend route, the webhook and the polling fallback, keeps the API key on the server, and runs one real test call.

[Importly](https://www.importly.io/?utm_source=skills&utm_medium=readme&utm_campaign=guerrilla-2026-11) is one API for this, and it keeps working on production servers where downloads usually get blocked. Free to try, no card required.

## Skills

| Skill | What your agent builds |
| --- | --- |
| `add-video-transcripts-downloads` | Import from URL (the file), transcripts or link-preview metadata in your app, with the key server-side, webhook plus polling fallback, error handling and a test call |
| `video-transcript-to-markdown` | A step that turns a media link into timestamped Markdown sections for RAG, search or an LLM prompt |

## Install

Any agent that supports skills (Claude Code, Cursor, Codex, Windsurf and others):

```bash
npx skills add importly-io/importly-integrations
```

Claude Code, as a plugin (adds both skills and Importly's hosted MCP server):

```bash
/plugin marketplace add importly-io/importly-integrations
/plugin install importly@importly
```

Then ask your agent something like: "Add an import-from-URL option to our upload form" or "Store a transcript with timestamps for every video link users add".

## What it runs and connects to

- The skills are instructions only. They contain no scripts and install no packages.
- Your agent reads Importly's public docs at https://www.importly.io/docs and https://www.importly.io/setup.md.
- The Claude Code plugin adds Importly's hosted MCP server at `https://mcp.importly.io/mcp`. You sign in to Importly the first time it connects (`/mcp`, then Authenticate). Its `get_integration_guide` tool is free; the other tools run real jobs on your account at the same prices as the API.
- Your app calls `https://api.importly.io` with your `IMPORTLY_API_KEY`. The skills never ask you to paste the key into the chat.

## Pricing

Pay per use from credits: a transcript from captions or a metadata lookup is $0.003, AI speech-to-text $0.01 per minute, downloads $0.002 per MB. See https://www.importly.io/pricing?utm_source=skills&utm_medium=readme&utm_campaign=guerrilla-2026-11.

## Support

Docs: https://www.importly.io/docs · Email: support@importly.io

MIT licensed.

## What's in this repo

- `skills/` and `.claude-plugin/`: the skills and Claude Code plugin above (repo root, so `npx skills add` and `/plugin marketplace add` find them)
- `python/`: the Python SDK and LangChain / LlamaIndex loaders (coming soon)
- `n8n/`: the n8n community node and workflow templates (coming soon)
