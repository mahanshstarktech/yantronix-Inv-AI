# Yantronix AI Product Scraper - Quick Start Guide

This guide will help you get the application up and running locally in just a few steps.

## Prerequisites
- **Node.js** (v22+ recommended; v18+ may work for older Next.js versions)
- **Python** (3.10+)
- **MongoDB** and **Redis** (installed on your PATH, running separately, or downloaded into `local-dbs` by the helper scripts).
- **Bash** (Git Bash on Windows, or the standard terminal on Linux/macOS).

---

## 1. Environment Setup

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Fill in the `.env` file:**
   - **`GEMINI_API_KEY`**: Get this from Google AI Studio.
   - **`ZOHO_CLIENT_ID` & `ZOHO_CLIENT_SECRET`**: Get this from your Zoho API Console (create a "Self Client").
   - **`ZOHO_ORGANIZATION_ID`**: Found in your Zoho Commerce Admin settings.
   - **`ZOHO_REFRESH_TOKEN`**: Generate a temporary grant token in the Zoho API Console, and run the backend's token generation script to get the refresh token.

*(See `.env.example` for details on datacenter endpoints).*

---

## 2. Install Dependencies

**Frontend (Next.js):**
```bash
# In the root directory
npm install
```

**Local databases:**
```bash
# In the root directory
./setup_dbs.sh
```

The database setup script uses Docker Compose when it is available on Linux/macOS, downloads local Windows binaries when running in Git Bash, or reuses Redis/MongoDB if they are already installed on PATH.

**Backend (Python FastAPI & Celery):**
```bash
# In the root directory
python3 -m venv .venv

# Activate it (Linux/macOS)
source .venv/bin/activate

# Or activate it on Windows Git Bash if you set VENV_PATH=backend/venv_win
# source backend/venv_win/Scripts/activate

# Install requirements
pip install -r backend/requirements.txt
```

---

## 3. Start the Application

The project includes a unified script to start the databases, backend server, celery worker, and frontend all at once.

1. Open a Bash terminal (Git Bash on Windows, or your standard terminal on Linux/macOS).
2. Run the start script from the root directory:
   ```bash
   ./run_app.sh
   ```

This script will automatically:
- Load variables from `.env` when the file exists; shell-level environment variables are also supported.
- Create `.venv` and install backend requirements when needed.
- Run `npm install` when `node_modules` is missing.
- Start **Redis** and **MongoDB** from Docker Compose, PATH binaries, or `local-dbs`; otherwise it will tell you to run `./setup_dbs.sh` or start them separately.
- Start the **Celery** worker.
- Start the **FastAPI** backend on `http://localhost:8000`.
- Start the **Next.js** frontend on `http://localhost:3000`.

---

## 4. Usage

1. Open your browser and go to **`http://localhost:3000`**.
2. Paste a product URL from supported sites (e.g., quartzcomponents.com or robu.in).
3. Click **"Extract →"** to pull the raw text.
4. Review the text and click **"Approve & Send to AI →"**.
   - *Note: If this URL has been generated before, it will instantly load from the database cache.*
5. Review the AI-generated SEO listing, tags, and pricing.
6. Click **"Approve & Publish →"** to instantly push the listing live to your Zoho Commerce store!

---

## Graceful Shutdown
To stop all services properly:
1. Press `Ctrl + C` in the terminal where `./run_app.sh` is running.
2. The script will automatically kill the frontend, backend, and background workers.
3. It will then gracefully stop Redis and MongoDB before exiting.
