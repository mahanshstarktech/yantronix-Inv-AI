# Yantronix AI Web Scraper

An AI-powered product scraping pipeline for Yantronix.  
It takes a product page URL, extracts structured product data, cleans it, sends it to a local AI model for listing generation, stores the result in PostgreSQL, and prepares the output for publishing to Zoho Commerce.

## What this project currently does

1. Accepts a product URL through a FastAPI endpoint.
2. Scrapes the product page with `requests` + `BeautifulSoup`.
3. Extracts Quartz-specific product details such as:
   - title
   - price
   - SKU
   - availability
   - description
   - specifications
   - image URLs
4. Saves the raw scraped product to PostgreSQL.
5. Queues an AI generation job with Celery + Redis.
6. Sends the scraped content to Ollama (`llama3.1:8b`) to generate:
   - SEO title
   - meta description
   - HSN code
   - tags
   - SEO keywords
   - HTML descriptions
   - selling price details
7. Stores the AI-generated output in PostgreSQL.
8. Builds a Zoho Commerce payload and prints it in test mode, or posts it in real mode.

## Current architecture

```text
Frontend / API client
        |
        v
FastAPI `/extract`
        |
        v
Quartz scraper (BeautifulSoup + requests)
        |
        v
PostgreSQL `raw_products`
        |
        v
Celery task queue (Redis broker)
        |
        v
Ollama AI generation
        |
        v
PostgreSQL `ai_products`
        |
        v
Zoho payload builder / publish step
```

## Main files

- `main.py` — FastAPI app and Quartz scraping logic
- `database.py` — PostgreSQL save/load helpers
- `tasks.py` — Celery background job
- `celery_app.py` — Celery + Redis config
- `prompts.py` — AI prompt builder
- `ai_generator.py` — Ollama call and JSON parsing
- `publish.py` — Zoho payload builder and publisher
- `peek.py` — debug script to inspect stored AI output
- `requirements.txt` — Python dependencies
- `what_to_run.txt` — quick run notes

## Features already implemented

### 1. Scraper API
A FastAPI endpoint receives a product URL and starts the scraping flow.

### 2. Quartz extraction
Quartz product pages are parsed for title, price, SKU, availability, descriptions, specs, and images.

### 3. Database storage
Raw product data and AI-generated data are stored separately in PostgreSQL.

### 4. Background processing
Celery runs the AI generation job asynchronously so the API does not block.

### 5. AI content generation
A local Ollama model generates SEO-friendly e-commerce content in JSON format.

### 6. Zoho payload preparation
The generated data is mapped into a Zoho Commerce product payload.

## What is still in progress

- Vendor support is currently Quartz-only.
- The AI prompt and raw scraper data shape still need to be aligned cleanly.
- The publish step is in test mode by default.
- Better validation, logging, and error handling can still be added.
- A proper frontend upload UI can be connected later.

## Local setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Redis
```bash
redis-server
```

### 3. Start the Celery worker
```bash
celery -A tasks worker --loglevel=info
```

### 4. Start the FastAPI server
```bash
uvicorn main:app --reload
```

### 5. Start Ollama
Make sure Ollama is running locally before triggering AI generation.

### 6. Make sure PostgreSQL is running
This project connects to a local PostgreSQL database named `scraper_db`.

## Example request

```bash
curl -X POST http://127.0.0.1:8000/extract   -H "Content-Type: application/json"   -d '{"url":"https://quartzcomponents.com/..."}'
```

## Running order

Open these in separate terminals:

1. Redis
2. Celery worker
3. Uvicorn API server
4. Ollama server
5. PostgreSQL if it is not already running

## Recommended repo hygiene

### Ignore these folders/files in Git
- `.next/`
- `node_modules/`
- `__pycache__/`
- `webvenv/` or `.venv/`
- Redis dumps like `dump.rdb`
- `.env`
- build artifacts and local logs

### Suggested commit style
Use short, clear commit messages like:
- `feat: add quartz scraper`
- `fix: align ai prompt with scraped data`
- `chore: update readme`
- `refactor: clean database helpers`

### Suggested branch flow
- `main` for stable code
- `dev` for ongoing work
- feature branches for big changes

### Good daily habit
After each meaningful change:
1. test locally
2. commit with a clear message
3. push to GitHub
4. update README if behavior changed

## Known mismatch to fix next

The scraped Quartz data and the AI prompt currently use slightly different field names, so the prompt builder should be aligned with the scraper output before relying on the AI step fully.

## License
Add your preferred license here.
