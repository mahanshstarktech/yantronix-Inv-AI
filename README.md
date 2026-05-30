# Yantronix AI Product Scraper

An automated e-commerce product pipeline for Yantronix. Paste a supplier product page URL — the system fetches it, converts the HTML to clean text, sends it to Gemini AI, and generates a fully structured, SEO-optimized product listing ready for Zoho Commerce.

---

## How It Works

```
Product URL (POST /extract)
        │
        ▼
FastAPI fetches page (requests)
        │
        ▼
HTML → clean plain text (BeautifulSoup)
        │
        ▼
PostgreSQL  ←──  raw_products saved
        │
        ▼
Celery task queued (Redis broker)
        │
        ▼
Gemini 2.5 Flash extracts + generates listing
        │
        ▼
PostgreSQL  ←──  ai_products saved
        │
        ▼
Zoho Commerce payload built + published
```

---

## Generated Output (per product)

Every product URL produces the following structured data:

| Field | Description |
|---|---|
| `product_title` | Full descriptive title with chip name, interface, and use case |
| `seo_title` | 60–70 character keyword-rich SEO title |
| `meta_description` | 150–160 character meta with specs and CTA |
| `seo_description` | 2–3 sentence paragraph for the product page |
| `hsn_code` | 6-digit GST HSN code |
| `sku` | Extracted or inferred SKU |
| `weight_kg` | Weight in kilograms |
| `dimensions_cm` | L × W × H in centimetres |
| `selling_price` | Breakdown: base → after GST (×1.18) → after margin (×1.05) |
| `tags` | 20+ tags covering chip, interface, use case, platform, audience |
| `seo_keywords` | 25+ flat keyword list: short-tail, long-tail, buy/shop phrases |
| `short_description_html` | HTML `<ul>` spec list with intro paragraph |
| `long_description_html` | Full HTML: Overview, Specs table, How It Works, Pin Description, Compatible Platforms, Applications, Assembly Tips, Sample Code, Package Contents, Safety Warning |

---

## Project Structure

```
yantronix-scraper/
├── main.py          # FastAPI app — URL ingestion, HTML→text, vendor detection
├── tasks.py         # Celery background task — orchestrates the full pipeline
├── ai_generator.py  # Gemini 2.5 Flash API call and JSON parsing
├── prompts.py       # Prompt builder — feeds raw text + pricing to Gemini
├── database.py      # PostgreSQL helpers — save/load raw and AI products
├── publish.py       # Zoho Commerce payload builder and publisher
├── celery_app.py    # Celery + Redis configuration
├── peek.py          # CLI tool to inspect generated output in the database
├── requirements.txt # Python dependencies
└── .env             # API keys and config (never commit this)
```

---

## Local Setup

### Prerequisites

- Python 3.10+
- PostgreSQL (local or remote)
- Redis
- A Gemini API key ([get one here](https://aistudio.google.com/app/apikey))

### 1. Clone and install

```bash
git clone https://github.com/your-username/yantronix-scraper.git
cd yantronix-scraper
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
DB_NAME=scraper_db
DB_USER=your_postgres_username
DB_HOST=localhost
DB_PORT=5432
TEST_MODE=true
ZOHO_TOKEN=             # leave blank until you are ready to publish
```

### 3. Set up the PostgreSQL database

```sql
CREATE DATABASE scraper_db;

CREATE TABLE raw_products (
    id         SERIAL PRIMARY KEY,
    source_url TEXT,
    vendor     TEXT,
    data       JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ai_products (
    id              SERIAL PRIMARY KEY,
    raw_product_id  INTEGER REFERENCES raw_products(id),
    ai_data         JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### 4. Start all services

Open four terminal windows and run one command in each:

```bash
# Terminal 1 — Redis
redis-server

# Terminal 2 — Celery worker
celery -A tasks worker --loglevel=info

# Terminal 3 — FastAPI server
uvicorn main:app --reload

# Terminal 4 — (optional) watch Celery logs or run peek.py
python peek.py
```

---

## Usage

### Submit a product URL

```bash
curl -X POST http://127.0.0.1:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://quartzcomponents.com/products/ra-02-lora-module-ai-thinker"}'
```

**Response:**

```json
{
  "success": true,
  "message": "Product scraped and queued for AI generation",
  "product_id": 27,
  "vendor": "quartz",
  "text_length": 4821
}
```

The product is saved to the database immediately. Gemini runs in the background — check the Celery terminal for progress.

### Inspect generated output

```bash
python peek.py
```

This prints the last 5 generated products with all fields: titles, pricing, tags, keywords, and both HTML descriptions.

### Interactive API docs

Visit [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the auto-generated Swagger UI.

---

## Supported Vendors

| Vendor | Domain | Status |
|---|---|---|
| Quartz Components | quartzcomponents.com | ✅ Supported |
| Robu | robu.in | ✅ Detected (same pipeline) |

Adding a new vendor requires only one entry in `detect_vendors()` in `main.py` — no scraping selectors to write.

---

## Pricing Formula

All prices are calculated automatically:

```
Quartz Base Price  →  × 1.18  →  After GST  →  × 1.05  →  Final Selling Price
```

If the base price cannot be found in the page text, Gemini estimates it from any price signal visible on the page.

---

## Zoho Commerce Integration

By default `TEST_MODE=true` in `.env`. In test mode, the Zoho payload is printed to the Celery terminal instead of being sent.

To publish to Zoho Commerce:

1. Obtain an OAuth token from Zoho
2. Set `ZOHO_TOKEN=your_token` in `.env`
3. Set `TEST_MODE=false`

The payload maps to these Zoho fields: `name`, `description`, `price`, `sku`, `tags`, `seo_title`, `seo_desc`.

---

## Architecture Notes

**Why HTML → plain text instead of CSS selectors?**
Earlier versions used BeautifulSoup selectors to extract specific fields (title, price, SKU). These broke whenever the supplier updated their page layout. The current approach strips all HTML noise and passes the raw visible text directly to Gemini, which extracts every field itself. This is vendor-agnostic and requires zero maintenance when page layouts change.

**Why Celery + Redis?**
Gemini generation takes 30–60 seconds per product. Running it synchronously would block the API and time out the HTTP request. Celery runs it as a background job so `/extract` returns immediately and the AI result appears in the database when ready.

**JSON robustness**
Gemini occasionally emits literal newline characters inside JSON string values (common in multi-line HTML blocks), which breaks `json.loads`. `ai_generator.py` includes a character-level cleaner that converts any control characters inside JSON strings to their proper escape sequences before parsing.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ | — | Google Gemini API key |
| `DB_NAME` | ✅ | `scraper_db` | PostgreSQL database name |
| `DB_USER` | ✅ | — | PostgreSQL username |
| `DB_HOST` | — | `localhost` | PostgreSQL host |
| `DB_PORT` | — | `5432` | PostgreSQL port |
| `TEST_MODE` | — | `true` | Print Zoho payload instead of posting |
| `ZOHO_TOKEN` | — | — | Zoho Commerce OAuth token |

---

## Dependencies

```
fastapi
uvicorn
requests 
beautifulsoup4
psycopg2-binary
google-genai
python-dotenv
celery
redis
```

---

## Git Hygiene

`.gitignore` should include:

```
.env
__pycache__/
*.pyc
.venv/
webvenv/
dump.rdb
*.egg-info/
```

Suggested commit style:

```
feat: add robu vendor detection
fix: sanitize null bytes before postgres insert
chore: update requirements
refactor: move prompt builder to separate file
```

---

## Roadmap

- [ ] Bulk URL ingestion (CSV upload)
- [ ] Frontend dashboard to submit URLs and preview generated listings
- [ ] Image scraping and upload to Zoho media library
- [ ] Automatic retry on Gemini parse failure
- [ ] Support for additional vendors (Robu full integration, mouser.in, evelta.com)
- [ ] Webhook or polling endpoint to check job status by `product_id`
- [ ] Admin panel to review and edit AI output before publishing
<!-- 
---

## License

Add your preferred license here. -->