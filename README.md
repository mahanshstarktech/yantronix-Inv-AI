# Yantronix AI Product Listing Generator

Yantronix AI Product Listing Generator is a human-reviewed product-ingestion pipeline for electronics e-commerce. A user pastes a supplier product URL, reviews the extracted plain text, queues a bounded Gemini generation job, and publishes or dry-runs a Zoho Commerce payload.

## Architecture

```text
Next.js UI
  └─ POST /extract       FastAPI scrape service
      └─ Supplier HTML → sanitized text preview
  └─ POST /generate      MongoDB raw product + Celery job
      └─ Gemini 2.5 Flash with token/output limits
      └─ Validated AIProduct saved to MongoDB
  └─ GET /status/{id}    queued | processing | complete | failed
  └─ POST /publish/{id}  Zoho payload dry-run or live publish
```

## Clean-code structure

```text
backend/
├── app/
│   ├── api/routes.py                    # Thin FastAPI route handlers
│   ├── core/config.py                   # Typed settings loaded from env
│   ├── core/rate_limiter.py             # Dependency-free request limiters
│   ├── main.py                          # FastAPI app factory
│   ├── models/product.py                # Pydantic API/DB/AI contracts
│   ├── repositories/product_repository.py # MongoDB persistence boundary
│   ├── services/
│   │   ├── ai_service.py                # Gemini client + JSON validation
│   │   ├── prompt_builder.py            # Bounded prompt builder
│   │   ├── publisher.py                 # Zoho payload/publisher service
│   │   └── scraper.py                   # Vendor detection + HTML cleanup
│   └── workers/tasks.py                 # Celery background tasks
├── main.py                              # Compatibility entrypoint
├── tasks.py                             # Compatibility Celery entrypoint
└── zoho/                                # Zoho OAuth implementation
```

The backend follows a layered pattern:

- **API layer:** validates requests, applies rate limits, and delegates work.
- **Service layer:** contains business logic for scraping, AI generation, and publishing.
- **Repository layer:** owns MongoDB reads/writes and status updates.
- **Model layer:** defines explicit Pydantic contracts for API, AI output, and persisted records.
- **Worker layer:** runs long AI work outside request/response cycles.

## Safeguards and limits

The app includes guardrails to reduce API spam and AI token spend:

| Setting | Default | Purpose |
|---|---:|---|
| `MAX_RAW_TEXT_CHARS` | `12000` | Caps scraped/edited text sent into Gemini prompts |
| `GEMINI_MAX_OUTPUT_TOKENS` | `12000` | Caps generated response size |
| `RATE_LIMIT_EXTRACT_PER_MINUTE` | `10` | Limits scrape requests per caller |
| `RATE_LIMIT_GENERATE_PER_MINUTE` | `5` | Limits generation queue requests per caller |
| `RATE_LIMIT_AI_CALLS_PER_HOUR` | `20` | Hourly AI job limiter per caller |
| `RATE_LIMIT_PUBLISH_PER_MINUTE` | `3` | Limits publish attempts per caller |

> The current limiter is in-memory and works for a single FastAPI process. For multi-instance production deployments, replace it with a Redis-backed limiter using the same policy names.

## Generated product contract

Gemini output is validated into an `AIProduct` model before saving:

- `product_title`
- `seo_title`
- `meta_description`
- `seo_description`
- `hsn_code`
- `sku`
- `weight_kg`
- `dimensions_cm`
- `selling_price`
- `tags`
- `seo_keywords`
- `short_description_html`
- `long_description_html`

Legacy grouped keyword objects are normalized into a flat `seo_keywords: string[]` list.

## Prerequisites

- Node.js 22+
- Python 3.10+
- MongoDB
- Redis
- Google Gemini API key
- Zoho OAuth credentials if live publishing is enabled

## Installation

```bash
npm install
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

## Environment variables

See `.env.example` for the full list. Minimum local dry-run setup:

```env
GEMINI_API_KEY=your_gemini_api_key_here
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=scraper_db
REDIS_URL=redis://localhost:6379/0
TEST_MODE=true
NEXT_PUBLIC_API_URL=http://localhost:8000
ALLOWED_ORIGINS=http://localhost:3000
```

## Running locally

Open separate terminals:

```bash
# Redis
redis-server

# FastAPI
cd backend
uvicorn main:app --reload

# Celery worker
cd backend
celery -A tasks worker --loglevel=info --pool=solo

# Next.js
npm run dev
```

Visit <http://localhost:3000>.

## API workflow

### Extract supplier text

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://quartzcomponents.com/products/ra-02-lora-module-ai-thinker"}'
```

### Queue AI generation

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"raw_text":"...reviewed text...","vendor":"quartz","source_url":"https://example.com/product"}'
```

### Poll status

```bash
curl http://127.0.0.1:8000/status/<product_id>
```

### Publish or dry-run Zoho payload

```bash
curl -X POST http://127.0.0.1:8000/publish/<product_id>
```

## Supported vendors

| Vendor | Domain | Status |
|---|---|---|
| Quartz Components | `quartzcomponents.com` | Supported |
| Robu | `robu.in` | Supported |

## Development checks

```bash
npm run lint
PYTHONPATH=backend python3 -m compileall backend
```
