# YouTube Anti-Recommender

A small public web app that accepts a YouTube video URL and returns intentional anti-recommendations: videos found by searching for semantic opposites of the input video's subject, tone, format, and activity.

## Features

- Public URL input with accessible UI
- Source metadata preview
- Gemini-generated discovery concepts
- Top five deduplicated anti-recommendations
- Friendly errors for invalid URLs, missing videos, quota limits, and provider failures

## Requirements

- Python 3.11+
- YouTube Data API v3 key
- Gemini API key

## Google setup

1. Create or select a Google Cloud project.
2. Enable **YouTube Data API v3**.
3. Create an API key for YouTube requests.
4. Create a Gemini API key from Google AI Studio / Google Gen AI.



## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` and set:

- `YOUTUBE_API_KEY`
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (for example `gemini-2.0-flash`)

Run the app:

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## API

`POST /api/anti-recommendations`

Request:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "en",
  "exclude_same_channel": false
}
```

`exclude_same_channel` is an optional API field (default: false). It is not currently exposed in the web UI.

Successful response includes:

- `source_video`
- `source_interpretation`
- `concepts`
- `recommendations`

Documented error codes:

- `400 invalid_youtube_url`
- `404 video_not_found`
- `429 youtube_quota_exceeded`
- `502 gemini_generation_failed`
- `503 integration_unavailable`



## Docker

```bash
docker build -t youtube-anti-recommender .
docker run --rm -p 8080:8080 \
  -e YOUTUBE_API_KEY=your_key \
  -e GEMINI_API_KEY=your_key \
  -e GEMINI_MODEL=gemini-2.0-flash \
  youtube-anti-recommender
```

Deploy the container to any host that supports Docker (Railway, Fly.io, Cloud Run, etc.) and inject the same environment variables at runtime.

## Testing

```bash
pytest
```

All external provider calls are mocked in tests.

## Known limitations

- English only in v1
- Inference is based on public metadata only
- Each request uses roughly 4–6 YouTube quota units (1 metadata lookup + 3–5 searches)
- No user accounts, history, or persistence



## Privacy

Submitted URLs are sent to the backend. Relevant metadata is sent to Gemini to form search concepts. API keys remain server-side only.