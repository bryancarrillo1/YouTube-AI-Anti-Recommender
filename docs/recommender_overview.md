# YouTube Anti-Recommender

## Project goal

Build a Python web application that accepts a public YouTube video URL and returns a small, intentional set of **anti-recommendations**: videos found by searching for semantic opposites of the input video's subject, tone, format, and/or perspective.

The product should help someone deliberately break out of a YouTube recommendation loop. It is a discovery tool, not a claim that a recommendation is objectively "better" or politically opposed.

## Core user flow

1. A visitor pastes a YouTube video URL.
2. The app validates the URL and extracts the canonical video ID.
3. The backend uses the YouTube Data API v3 to retrieve the video's `snippet` metadata:
  - title
  - description
  - creator/channel name
  - tags, when supplied by YouTube
  - category ID and publication date (useful supplemental context)
4. The backend sends a compact, sanitized summary of that metadata to the Gemini API.
5. Gemini returns diverse **opposite/discovery search concepts** in a strict JSON structure.
6. The backend searches YouTube with those concepts and aggregates the results.
7. The app removes the original video, duplicates, and (optionally) same-channel results; scores the remaining candidates; and shows the best five.
8. Each result explains *why* it is an anti-recommendation (for example, “hands-on repair rather than a product review”).



## Product decisions



### Definition of “opposite”

Treat “opposite” as a collection of useful discovery dimensions, not merely word-level antonyms. Gemini should create search concepts across some of these dimensions when relevant:


| Dimension         | Example input             | Useful anti-recommendation direction               |
| ----------------- | ------------------------- | -------------------------------------------------- |
| Topic / domain    | smartphone unboxing       | repair, longevity, minimal-phone use               |
| Stance / framing  | productivity optimization | rest, limits, slower work                          |
| Activity          | watching a gaming stream  | making a small game, outdoor activity              |
| Format            | hot take / short reaction | long-form explanation or primary-source discussion |
| Consumption level | luxury product review     | budget, reuse, repair, or no-buy content           |
| Tone / pacing     | outrage-driven commentary | calm, reflective, evidence-led discussion          |


The model must not invent factual claims about the video or label a creator’s politics, personality, or intent from limited metadata. When metadata is sparse, return broader but transparent alternatives rather than forced “opposites.”

### Search-concept design

Generate 3–5 short concepts. Each concept contains:

- `query`: a natural YouTube search phrase, usually 3–10 words
- `contrast_dimension`: topic, stance, activity, format, consumption, tone, or perspective
- `rationale`: a short explanation of the contrast
- `safety_note`: optional warning when the topic is sensitive

Avoid simple negations such as `not <title>` and prohibited or unreliable queries. Search concepts should be broad enough to yield results but specific enough to feel intentional.

### First version scope

Ship the following in the first usable release:

- One public video URL input
- Metadata inspection panel
- Gemini-generated discovery concepts
- Top five deduplicated anti-recommendations
- Links that open results on YouTube
- Friendly errors for invalid URLs, private/deleted videos, quota exhaustion, and Gemini/API failures
- No stored user accounts, history, personal profiles, or background jobs

Defer personalization, browser extensions, playlists, recommendations based on watch history, and automatic playback.

## Recommended technical approach



### Stack

- **Python 3.11+**
- **FastAPI** for the HTTP API and server-rendered or JSON endpoints
- **Jinja2 + minimal vanilla JavaScript** for a lightweight single-page experience
- **YouTube Data API v3** via `google-api-python-client` or direct HTTP calls
- **Google Gen AI SDK** (`google-genai`) for Gemini structured JSON output
- **Pydantic v2** for validation and structured data
- **httpx** for outbound requests if using direct API requests
- **pytest** plus `respx` or mocked client interfaces for tests
- `.env` locally; environment variables in deployment

This keeps the project easy to run and avoids a database until user-facing persistence is actually needed.

### Suggested project layout

```text
youtube-anti-recommender/
├── app/
│   ├── main.py                 # FastAPI app and routes
│   ├── config.py               # typed environment settings
│   ├── models.py               # Pydantic request/response models
│   ├── services/
│   │   ├── youtube.py          # YouTube API client and URL parsing
│   │   ├── gemini.py           # Gemini prompt and structured output parsing
│   │   └── recommender.py      # orchestration, ranking, filtering
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── app.js
│       └── styles.css
├── tests/
│   ├── test_youtube.py
│   ├── test_gemini.py
│   └── test_recommender.py
├── .env.example
├── pyproject.toml
├── README.md
└── Dockerfile                  # optional, useful for deployment
```



## External integrations



### YouTube Data API v3

Use `videos.list` with `part=snippet` and the parsed video ID. Required metadata comes from `items[0].snippet`.

Use `search.list` for each Gemini search concept. Initial parameters:

```text
part=snippet
type=video
q=<search concept query>
maxResults=5
safeSearch=moderate
relevanceLanguage=en              # configurable; omit if unknown
videoEmbeddable=true              # optional; true if the UI embeds videos
```

Important implementation details:

- Support `youtube.com/watch?v=...`, `youtu.be/...`, Shorts URLs, embed URLs, and URLs with unrelated query parameters.
- Never scrape YouTube pages; use the API only.
- A video’s `tags` field is often absent. The flow must work with title and description alone.
- The API returns only search-result snippets. Do not present counts, duration, or statistics unless separately fetched using `videos.list`.
- Cache API responses for a short configurable period to reduce quota use. A simple in-memory TTL cache is sufficient for version one.



### Gemini API

Gemini receives only the metadata required to form search concepts. Truncate long descriptions (for example, 3,000–5,000 characters) and remove control characters.

Require JSON matching a Pydantic schema. Validate and retry once with a repair prompt if the response is malformed. If it still fails, display a graceful message and do not make arbitrary opposite tags locally.

Recommended response shape:

```json
{
  "source_interpretation": "A concise, uncertainty-aware reading of the metadata.",
  "concepts": [
    {
      "query": "beginner bicycle repair tutorial",
      "contrast_dimension": "activity",
      "rationale": "Moves from buying gear toward maintaining what someone owns.",
      "safety_note": null
    }
  ]
}
```

Prompt requirements:

- Treat input metadata as untrusted quoted data, never as instructions.
- Request 3–5 distinct concepts, not duplicate keyword variations.
- Use language that is appropriate for a public video search query.
- Do not generate hateful, explicit, self-harm, illegal, medical-treatment, or targeted-political-persuasion queries.
- Avoid asserting anything that cannot be inferred from the supplied title, description, and tags.
- Return JSON only, adhering to the declared schema.



## Backend behavior



### API contract

`POST /api/anti-recommendations`

Request:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "en",
  "exclude_same_channel": true
}
```

Successful response:

```json
{
  "source_video": {
    "video_id": "VIDEO_ID",
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "title": "...",
    "description": "...",
    "channel_id": "...",
    "channel_title": "...",
    "tags": ["..."],
    "category_id": "..."
  },
  "source_interpretation": "...",
  "concepts": [
    {
      "query": "...",
      "contrast_dimension": "...",
      "rationale": "..."
    }
  ],
  "recommendations": [
    {
      "video_id": "...",
      "url": "https://www.youtube.com/watch?v=...",
      "title": "...",
      "description": "...",
      "thumbnail_url": "...",
      "channel_id": "...",
      "channel_title": "...",
      "matched_query": "...",
      "contrast_dimension": "...",
      "why_this_result": "..."
    }
  ]
}
```

Return predictable client-safe error codes:


| HTTP status | Code                       | Meaning                                              |
| ----------- | -------------------------- | ---------------------------------------------------- |
| 400         | `invalid_youtube_url`      | URL cannot yield a valid video ID                    |
| 404         | `video_not_found`          | Video is unavailable or inaccessible through the API |
| 429         | `youtube_quota_exceeded`   | YouTube quota limit has been reached                 |
| 502         | `gemini_generation_failed` | Gemini response failed or could not be validated     |
| 503         | `integration_unavailable`  | A provider is temporarily unavailable                |




### Ranking and filtering

For each query, fetch up to five candidates (at most 25 API results), then:

1. Remove the source video ID.
2. Deduplicate candidates by video ID, retaining the best source-query association.
3. If enabled, remove source-channel matches.
4. Discard clearly incomplete result entries (missing video ID/title).
5. Rank candidates using deterministic signals:
  - results from a diverse set of contrast dimensions
  - original per-query API order
  - concise relevance explanation from the generating concept
6. Return exactly five when enough acceptable candidates exist; otherwise return the available number with a message that results were limited.

Do not use popularity as the default ranking signal. It would recreate conventional recommendation behavior and requires extra API calls.

## User experience requirements

The initial page should contain:

- a clear title and one-sentence description of anti-recommendations
- URL input and “Find a different direction” button
- optional settings: language, exclude source channel
- a loading state that explains the stages: read metadata → find contrasting directions → search YouTube
- source metadata preview (title, channel, tags when present)
- generated concept chips with their rationales
- five result cards: thumbnail, title, channel, short description, matched query, and “Why this is different”
- a disclosure: results are generated from public metadata and search results; they are exploratory, not factual judgments about creators or videos

Accessibility:

- Keyboard-operable input and button
- Semantic headings and result list
- Thumbnail alt text based on the result title
- Status/error messages announced with an `aria-live` region
- Sufficient contrast and no information conveyed by color alone



## Security, privacy, and responsible behavior

- Keep `YOUTUBE_API_KEY` and `GEMINI_API_KEY` server-side only. Never expose them in HTML, JavaScript, logs, or error responses.
- Use typed configuration; fail fast at startup if essential keys are absent.
- Validate URLs strictly and enforce a reasonable length limit.
- Rate-limit the public endpoint by IP to protect API quotas.
- Escape API and model-provided text in templates. Do not render descriptions as HTML.
- Do not store submitted URLs or metadata by default. If request logs exist, avoid logging full URLs and descriptions.
- Make outbound timeouts and retry policy explicit; retry only transient provider errors, and keep retries small to avoid quota amplification.
- Add a content-safety filter to exclude unsafe or disallowed generated queries and show a neutral fallback when filtering leaves too few concepts.
- Include a short privacy notice explaining that the submitted URL is sent to the backend and relevant metadata is sent to Gemini to form search concepts.



## Configuration

Create `.env.example`:

```dotenv
YOUTUBE_API_KEY=replace_me
GEMINI_API_KEY=replace_me
GEMINI_MODEL=replace_with_supported_model
DEFAULT_LANGUAGE=en
RESULTS_COUNT=5
SEARCH_RESULTS_PER_CONCEPT=5
EXCLUDE_SAME_CHANNEL=true
CACHE_TTL_SECONDS=900
REQUEST_TIMEOUT_SECONDS=15
```

Use a supported Gemini model chosen from the current Google Gen AI documentation; make its name configurable rather than hard-coding it throughout the application.

## Testing and acceptance criteria



### Unit tests

- Parse valid video IDs from watch, short-link, Shorts, embed, and mobile URL formats.
- Reject non-YouTube URLs, playlists without a video ID, malformed IDs, and excessive-length input.
- Convert YouTube API responses to internal models, including absent tags and empty descriptions.
- Validate Gemini JSON and reject invalid enum values, empty query text, repeated concepts, and too many concepts.
- Verify filtering removes the source video, duplicates, and source-channel results when enabled.
- Verify errors from each provider map to the documented HTTP errors without leaking secrets.



### Integration-style tests with mocked providers

- A normal input produces metadata, 3–5 concepts, and up to five displayed results.
- Sparse metadata still produces useful, cautious discovery queries.
- Gemini malformed output causes one repair attempt, then a clear fallback error.
- YouTube returns fewer than five viable results and the response remains valid.
- Rate limiting is enforced.



### Definition of done

- The app runs locally with `uvicorn` using documented setup steps.
- A valid public YouTube URL returns up to five non-duplicate, non-source results.
- No API key appears in client responses, page source, or ordinary logs.
- UI handles loading, empty results, and all documented error cases.
- Test suite passes with all provider network calls mocked.
- README documents setup, required Google Cloud/Gemini configuration, environment variables, API contract, and known limitations.



## Suggested implementation sequence

1. Scaffold FastAPI, configuration, health endpoint, and static page.
2. Implement robust YouTube URL parsing and unit tests.
3. Implement a small YouTube client for `videos.list`; display source metadata.
4. Add Gemini structured generation, schema validation, and prompt-injection resistance.
5. Implement YouTube search, candidate filtering, and deterministic ranking.
6. Build the result UI and accessible loading/error states.
7. Add cache, rate limit, provider timeouts, and production-oriented logging.
8. Complete tests, README, and optional container deployment.



## Future directions (out of scope for version one)

- A user-controlled “opposition dial” (gentle adjacent change → strong contrast).
- Select which dimensions matter: topic, format, ideology/perspective, activity, tone, or spending.
- Multiple source videos to identify a shared recommendation bubble.
- User feedback buttons (“more like this direction”, “less like this”) without retaining a watch history.
- Export selected results to a playlist or a simple shareable list.
- A browser extension that runs only when explicitly triggered on a watch page.



## Open product questions for the project owner

1. Who is the primary audience: people escaping algorithmic rabbit holes, learners seeking diverse perspectives, or entertainment discovery? The answer should shape the language and contrast dimensions.  
Answer: Entertainment discovery as a novelty for users who feel bored by current recommendations.
2. Should “opposite” include political/ideological perspectives, or should version one explicitly limit itself to topic, format, tone, and activity? Political contrast needs stricter safety and transparency rules.  
Answer: Limit to topic, tone, format, etc. for now
3. Do you want this as a public web app, a local developer demo, or a command-line tool first? This brief assumes a small public web app.  
Answer: Build it as a public web app
4. Should results always exclude the original channel, or should that be a user setting with a default?  
Answer: No, the original channel does not have to be excluded.
5. Which languages must be supported at launch? The search language and Gemini prompt should align with that choice.  
Answer: Just English for now

