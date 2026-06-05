#Grouping imports according to PEP8 standard
#Standard Library
import re
import os

#Load .env file
from dotenv import load_dotenv
load_dotenv()

#Third-party
import requests #This is how python open websites
from bs4 import BeautifulSoup #This turns ugly HTML into a tree you can clean.
import unicodedata

#FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException #server, clear error messages
from pydantic import BaseModel, HttpUrl #define what data we expect, so that user can't send garbage

#Local
from tasks import generate_ai_task
from database import save_raw_product, get_raw_product, get_ai_product
from publish import publish_to_zoho


# -----------------------------
# App initialization
# -----------------------------
app = FastAPI(title="Yantronix Scraper API") #server object

app.add_middleware( #Middleware = code that runs before every request
    CORSMiddleware, #This one handles browser security rules
    allow_origins       =["http://localhost:3000"],
    allow_credentials   =True, #Allows cookies / auth headers #Needed if later I add login/session support
    allow_methods       =["*"],
    allow_headers       =["*"],
)

# -----------------------------
# Request schema
# -----------------------------
class ExtractRequest(BaseModel):#I expect JSON like { "url": "https://..." }
    url: HttpUrl                #Auto validation, Auto Docs, Type Safety # Ensures valid URL format

class GenerateRequest(BaseModel):
    raw_text:   str
    vendor:     str
    source_url: str

# -----------------------------
# Vendor Detection
# -----------------------------
def detect_vendors(url: HttpUrl) -> str:
    host = str(url.host)
    if "quartzcomponents.com" in host:
        return "quartz"
    if "robu.in" in host:
        return "robu"
    raise HTTPException(status_code=400, detail=f"Unsupported vendor: {host}")

# -----------------------------
# HTML -> clean plain text
# -----------------------------
def html_to_text(html: str) -> str:
    """
    Convert a full HTML page to clean plain text — the same thing the
    'Web Page Text Extractor' Chrome extension does manually.
 
    Steps:
      1. Remove script/style/nav/footer/header tags entirely (noise)
      2. Extract visible text with BeautifulSoup
      3. Collapse blank lines
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove noisy tags that add no product information
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe", "svg", "form"]):
        tag.decompose()
    
    # Get all visible text, separated by newlines
    text = soup.get_text(separator="\n", strip=True)

    # Collapse 3+ consecutive blank lines into one
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

def sanitize_text(text: str) -> str:
    """
    Strip everything PostgreSQL can't store AND everything that produces
    garbled/binary display in the UI:
      - Null bytes          → hard crash in psycopg2
      - U+FFFD              → Unicode replacement char (the garbled boxes)
      - Surrogate code points → broken encodings from bad pages
      - Non-printable control chars (keep \\n and \\t for readability)
      - Lone high/low surrogates that survive re-encode
    """
    # 1. Kill null bytes
    text = text.replace('\x00', '')
 
    # 2. Kill replacement character — this is the main source of the
    #    garbled '6666' / box characters you're seeing in the UI
    text = text.replace('\ufffd', '')
 
    # 3. Drop unpaired surrogates from pages with broken encodings
    text = text.encode('utf-8', errors='ignore').decode('utf-8')
 
    # 4. Remove ALL non-printable control characters except \\n and \\t
    #    unicodedata category 'C' = control, format, surrogate, private-use, unassigned
    text = ''.join(
        ch for ch in text
        if unicodedata.category(ch)[0] != 'C' or ch in '\n\t'
    )
 
    # 5. Collapse runs of 3+ blank lines (already done in html_to_text,
    #    but binary pages can reintroduce them after stripping)
    text = re.sub(r'\n{3,}', '\n\n', text)
 
    return text.strip()

# -----------------------------
# Main API endpoint
# -----------------------------
# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — POST /scrape
# Fetch the URL and convert HTML to plain text.
# Returns the raw text for the user to review in the UI.
# Does NOT save to DB or queue anything yet.
# ═════════════════════════════════════════════════════════════════════════════
@app.post("/extract")
def extract_website(data: ExtractRequest): #ExtractRequest -> FastAPI automatically: reads JSON, validates, converts to object
    """
    Accepts a product page URL.
    Fetches the page, converts HTML to plain text, and queues an AI generation job.
    Gemini reads the raw text and both extracts the product data AND
    generates the full e-commerce listing in one call.
    """
    try:
        #Fetch webpage
        response = requests.get(
            str(data.url),
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            timeout=15
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch page — site returned {response.status_code}"
            )
        
        #Convert HTML to plain text
        raw_text = sanitize_text(html_to_text(response.text))

        if len(raw_text) < 100:
            raise HTTPException(
                status_code=422,
                detail="Page returned too little text - it may be behind a login or JS-rendered."
            )
        
        # Detect vendor
        vendor = detect_vendors(data.url)

        return {
            "raw_text":    raw_text,
            "vendor":      vendor,
            "source_url":  str(data.url),
            "text_length": len(raw_text),
        }
    
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=408,
            detail=f"Request timed out or failed: {e}"
        )

    except HTTPException:
        raise  # Re-raise 400/404/etc. as-is — don't let them become 500s
    
    except Exception as ex:
        raise HTTPException(
            status_code = 500, 
            detail=str(ex)
        )

# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — POST /generate
# User approved the extracted text. Save to DB and queue the AI job.
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/generate")
def generate_listing(data: GenerateRequest):
    raw_text = sanitize_text(data.raw_text)
 
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text is empty.")
    
    # Build a product dict with the raw text
    # Gemini will extract all real fields (title, price, SKU etc.)
    # from raw_text inside the prompt — no selector logic needed here
    product_data = {
        "vendor":        data.vendor,
        "source":        "url_scrape",
        "source_url":    data.source_url,
        "raw_page_text": raw_text,
        # Placeholder fields — Gemini fills real values in ai_data
        "title":           "",
        "vendor_sku":      "",
        "description_raw": "",
        "specifications":  {},
        "pricing": {
            "base_price":    None,
            "selling_price": None,
            "retail_price":  None,
            "currency":      "INR",
            "includes_gst":  False,
        },
        "images": [],
    }

    try:
        product_id = save_raw_product(product_data, data.source_url)
        generate_ai_task.delay(product_id)

        return{
            "success": True,
            "message": "Product scraped and queued for AI generation",
            "product_id": product_id,
            "vendor": data.vendor,
            "text_length": len(raw_text),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — GET /status/{product_id}
# Polled by the frontend every 3 seconds.
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/status/{product_id}")
def get_status(product_id: str):
    ai_data = get_ai_product(product_id)
    if ai_data:
        return {"status": "complete", "data": ai_data}
 
    raw = get_raw_product(product_id)
    if raw:
        return {"status": "processing"}
 
    raise HTTPException(status_code=404, detail="Product not found")
 
 
# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — POST /publish/{product_id}
# User clicked Approve & Publish. Sends to Zoho (or prints in test mode).
# ═════════════════════════════════════════════════════════════════════════════
@app.post("/publish/{product_id}")
def publish_product(product_id: str):
    ai_data = get_ai_product(product_id)
    if not ai_data:
        raise HTTPException(status_code=404, detail="AI product not ready or not found")
 
    result = publish_to_zoho(ai_data)
    return {"success": True, "result": result}
    
