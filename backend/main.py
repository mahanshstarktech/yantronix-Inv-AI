#Grouping imports according to PEP8 standard
#Standard Library
import json
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
    allow_origins=["http://localhost:3000"],
    allow_credentials=True, #Allows cookies / auth headers #Needed if later I add login/session support
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Request schema
# -----------------------------
class ExtractRequest(BaseModel): #I expect JSON like { "url": "https://..." }
    url: HttpUrl                  #Auto validation, Auto Docs, Type Safety # Ensures valid URL format

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

def detect_vendors(url: HttpUrl) -> str:
    if url.host == "quartzcomponents.com":
        return "quartz"
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported vendor"
        )

# -----------------------------
# Pricing Engine
# -----------------------------    
def calculate_prices(base_price: float, vendor: str) -> dict:
    vendor_lower = vendor.lower()

    if vendor_lower == "quartz":
        selling_price = base_price * 1.18 * 1.05
    
    elif vendor_lower == "robu":
        selling_price = base_price * 1.05

    else:
        selling_price = base_price

    selling_price = round(selling_price, 2)

    #Fake retail price for discount effect:
    retail_price = round(selling_price * 1.25, 2)

    return{
        "base_price" : base_price,
        "selling_price" : selling_price,
        "retail_price" : retail_price
    }
# -----------------------------
# Quartz extractor
# -----------------------------
def extract_quartz_product(soup: BeautifulSoup) -> dict:
    #Title
    title_tag = soup.select_one("h1.productView-title span")
    title = title_tag.text.strip() if title_tag else ""
    title = title.replace("– QuartzComponents", "").strip()

    #price
    price_tag = soup.select_one("span.price-item--regular")
    price = clean_price(price_tag.text) if price_tag else 0
    pricing = calculate_prices(price, "quartz") if price else{
        "base_price": None,
        "selling_price": None,
        "retail_price": None
    }

    #SKU & Availability
    sku = ""
    availability_text = ""

    for block in soup.select("div.productView-info-item"):
        label = block.select_one(".productView-info-name")
        value = block.select_one(".productView-info-value")

        if not label or not value:
            continue

        label_text = label.text.strip().lower()
        value_text = value.text.strip()

        if "sku" in label_text:
            sku = value_text
        elif "availability" in label_text:
            availability_text = value_text

    #Availability
    def parse_availability(text: str) -> dict:
        match = re.search(r"(\d+)", text)
        quantity = int(match.group(1)) if match else None

        status = "In Stock" if "stock" in text.lower() else "Out of Stock"

        return{
            "status": status,
            "quantity": quantity
        }
    availability = parse_availability(availability_text)

    #Description
    desc_tag = soup.select_one("#tab-description-mobile .tab-popup-content")
    description_raw = (
        desc_tag.get_text(" ", strip=True)
        if desc_tag else ""
    )

    def clean_description(text: str) -> str:
        lines = text.split(". ")
        filtered = [
            line for line in lines
            if "http" not in line.lower()
            and "note" not in line.lower()
            and "for other color" not in line.lower()
        ]
        return ". ".join(filtered).strip()
    
    description_clean = clean_description(description_raw)
    
    # -------- SPECS --------  
    def extract_specs_from_description(soup: BeautifulSoup) -> dict:
        specs = {}
        for li in soup.select("#tab-description-mobile li"):
            text = li.get_text(strip=True)
            if ":" in text:
                key, value = text.split(":", 1)
                specs[key.strip()] = value.strip()
        return specs
    specifications = extract_specs_from_description(soup)

    #Images
    def extract_images_from_json_ld(soup: BeautifulSoup) -> list[str]:
        images = []

        for script in soup.find_all("script", type="application/ld+json"):

            if not script.string:
                continue
            
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "Product":
                    imgs = data.get("image", [])
                    if isinstance(imgs, list):
                        images.extend(imgs)
                    elif isinstance(imgs, str):
                        images.append(imgs)
            except Exception:
                pass
        return list(dict.fromkeys(images))
    
    images = extract_images_from_json_ld(soup)

     # -------- RETURN --------
    return {
        "vendor": "quartz",
        "title": title,
        "vendor_sku": sku,
        "availability": availability,
        "pricing": {
            "base_price": pricing["base_price"],
            "selling_price": pricing["selling_price"],
            "retail_price": pricing["retail_price"],
            "currency": "INR",
            "includes_gst": False
        },
        "description_raw": description_clean,
        "specifications": specifications,
        "images": images
    }

# -----------------------------
# Main API endpoint
# -----------------------------
@app.post("/extract")
def extract_website(data: ExtractRequest): #ExtractRequest -> FastAPI automatically: reads JSON, validates, converts to object
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
            timeout=10
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch page — site returned {response.status_code}"
            )
        
        soup = BeautifulSoup(response.text, "html.parser")

        vendor = detect_vendors(data.url)

        if vendor == "quartz":
            product_data = extract_quartz_product(soup)
            product_id = save_raw_product(product_data, str(data.url))
        else:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported Vendor"
            )

        #queing AI Job
        generate_ai_task.delay(product_id)

        return{
            "success": True,
            "message": "Product scraped and queued for AI generation",
            "product_id": product_id,
        }
    
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=408,
            detail="Request timed out or failed"
        )

    except HTTPException:
        raise  # Re-raise 400/404/etc. as-is — don't let them become 500s
    
    except Exception as e:
        raise HTTPException(
            status_code = 500, 
            detail=str(e)
        )
    
    # except Exception as e:
    #     print("Error: ", e)
    #     raise
        
