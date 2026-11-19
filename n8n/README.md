# n8n-nodes-importly

Turn any video or audio link into files, transcripts and metadata in [n8n](https://n8n.io/). Save YouTube, TikTok and Instagram videos to Google Drive or S3, put transcripts in Sheets or Notion, and pull titles, captions, views and tags into any workflow.

Downloads usually get blocked when they run from n8n Cloud or a VPS, and transcript nodes break when YouTube changes something. [Importly](https://www.importly.io/?utm_source=n8n&utm_medium=readme&utm_campaign=guerrilla-2026-11) is one API that keeps working from servers. This node gives you the actual file, not just the transcript. Free to try, no card required.

- [Installation](#installation)
- [Credentials](#credentials)
- [Operations](#operations)
- [Waiting for results](#waiting-for-results)
- [Templates](#templates)
- [Pricing](#pricing)
- [Compatibility](#compatibility)
- [Resources](#resources)

## Installation

Follow the [community nodes installation guide](https://docs.n8n.io/integrations/community-nodes/installation/): in n8n, open **Settings > Community Nodes > Install** and enter `n8n-nodes-importly`.

## Credentials

1. Sign up at [importly.io](https://www.importly.io/?utm_source=n8n&utm_medium=readme&utm_campaign=guerrilla-2026-11) (free to try, no card required) and copy your key from the [API key page](https://www.importly.io/dashboard/api-key?utm_source=n8n&utm_medium=readme&utm_campaign=guerrilla-2026-11).
2. In n8n, create an **Importly API** credential and paste the key. n8n checks it by reading your balance.

## Operations

| Resource | Operation | What you get |
| --- | --- | --- |
| Media | Import | The video or audio file as binary data (ready for Google Drive, S3, Dropbox or any node that takes a file), plus a download link valid for 7 days. Options: video or audio only, video and audio quality, a cost cap, a transcript from the same job, and a copy straight to your own S3-compatible bucket. |
| Transcript | Get | Plain text plus timestamped segments. Uses the video's captions by default; switch **Source** to Importly speech-to-text for videos without captions. |
| Metadata | Get | Title, description, uploader, upload date, duration, views, likes, comments, thumbnail, tags. Turn off **Simplify** for the full response, including every available format. |
| Metadata | Get Basic | Just the title, duration and thumbnail. Faster. |
| Job | Get Status | The state and result of a job you started earlier, by job ID. |
| Account | Get Balance | Your remaining credit in US dollars. |

Links from YouTube, TikTok, Instagram, X, Facebook, Reddit, SoundCloud, podcasts and [1,000+ other sites](https://www.importly.io/docs/features/supported-sites?utm_source=n8n&utm_medium=readme&utm_campaign=guerrilla-2026-11) work.

The node can also be used as a tool by n8n's AI Agent.

## Waiting for results

Every Importly job runs in the background. The node gives you two ways to get the result:

- **Wait for Completion: on** (default). The node checks the job every few seconds and outputs the result when it's done. Set **Poll Interval** and **Timeout** under Options. Several input items run at the same time, five at once.
- **Wait for Completion: off**. The node outputs the job ID right away. Set **Webhook URL** and Importly sends the result there once, when the job completes or fails. To continue the same workflow, set the Webhook URL to `{{ $execution.resumeUrl }}` and add a **Wait** node after this one with **Resume: On Webhook Call** and **HTTP Method: POST**. Give the Wait node a time limit, and use **Job > Get Status** as a fallback.

Failed jobs stop the workflow with Importly's message (for example "Source video is unavailable"), or output it as an item when **On Error** is set to continue.

## Templates

Import these from `templates/` (in n8n: **Workflows > Import from File**):

- `save-youtube-videos-to-google-drive.json`: every new video on a YouTube channel lands in a Google Drive folder.
- `youtube-transcripts-to-google-sheets.json`: add video links to a sheet and get the title, language and transcript filled in every day.
- `tiktok-instagram-form-to-s3.json`: a form takes a TikTok or Instagram link and saves the video plus a metadata JSON file to S3.

## Pricing

Pay per use from credits: transcripts from captions and metadata lookups are $0.003 each, speech-to-text is $0.01 per minute, and downloads are $0.002 per MB. Most failed jobs are free. Set **Max Cost (USD)** to cap a single request. Details: [importly.io/pricing](https://www.importly.io/pricing?utm_source=n8n&utm_medium=readme&utm_campaign=guerrilla-2026-11).

## Compatibility

Built with n8n's community node starter (`@n8n/node-cli`) and its n8n Cloud lint rules. Tested against `n8n-workflow` 2.x. Needs Node.js 20.15 or later.

## Development

```bash
npm ci
npm run lint
npm test      # builds, then runs the unit tests in test/
npm run dev   # runs n8n locally with this node loaded (needs Docker or Podman)
```

## Resources

- [Importly docs](https://www.importly.io/docs?utm_source=n8n&utm_medium=readme&utm_campaign=guerrilla-2026-11)
- [API reference](https://www.importly.io/docs/api-reference?utm_source=n8n&utm_medium=readme&utm_campaign=guerrilla-2026-11)
- [n8n community nodes docs](https://docs.n8n.io/integrations/#community-nodes)

## License

[MIT](LICENSE)
