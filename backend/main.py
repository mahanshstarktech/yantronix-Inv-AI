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

#FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException #server, clear error messages
from pydantic import BaseModel, HttpUrl #define what data we expect, so that user can't send garbage

#Local
from tasks import generate_ai_task
from database import save_raw_product

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
    vendor: str = "quartz"      #default vendor, can be overridden later

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
# Utility helpers
# -----------------------------
def clean_price(text: str) -> float:
    return float(
        text.replace("Rs.", "")
            .replace("₹", "")
            .replace(",", "")
            .strip()
    )

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
    Strip characters PostgreSQL cannot store in a text/JSON column:
      - Null bytes (\x00) — hard crash in psycopg2
      - Unicode surrogates — unpaired surrogates from bad page encodings
    Encode/decode with 'ignore' drops anything that isn't valid UTF-8.
    """
    text = text.replace('\x00', '')                          # kill null bytes first
    text = text.encode('utf-8', errors='ignore').decode('utf-8')  # drop bad surrogates
    return text

# -----------------------------
# Main API endpoint
# -----------------------------
@app.post("/extract")
def extract_website(data: ExtractRequest): #ExtractRequest -> FastAPI automatically: reads JSON, validates, converts to object
    """
    Accepts a product page URL.
    Fetches the page, converts HTML to plain text, and queues an AI generation job.
    Gemini reads the raw text and both extracts the product data AND
    generates the full e-commerce listing in one call.
    """
    try:
        #Step1: Fetch webpage
        response = requests.get(
            str(data.url),
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
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
        
        #Step 2: Convert HTML to plain text
        raw_text = sanitize_text(html_to_text(response.text))

        if len(raw_text) < 100:
            raise HTTPException(
                status_code=422,
                detail="Page returned too little text - it may be behind a login or JS-rendered."
            )
        
        # Step 3: Detect vendor
        vendor = detect_vendors(data.url)

        # Step 4: Build a product dict with the raw text
        # Gemini will extract all real fields (title, price, SKU etc.)
        # from raw_text inside the prompt — no selector logic needed here
        product_data = {
            "vendor":        vendor,
            "source":        "url_scrape",
            "source_url":    str(data.url),
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

        # Step 5: Save raw product and queue AI job
        product_id = save_raw_product(product_data, str(data.url))
        generate_ai_task.delay(product_id)

        return{
            "success": True,
            "message": "Product scraped and queued for AI generation",
            "product_id": product_id,
            "vendor": vendor,
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