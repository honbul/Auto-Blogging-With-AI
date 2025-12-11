# Project Summary: Link-to-Article Studio

**Repository:** https://github.com/honbul/Auto-Blogging-With-AI

## Overview
Link-to-Article Studio is a local web application that automates creating blog posts from URLs. It fetches content, summarizes it using a local LLM (Ollama), and synthesizes a full Markdown article with images and references.

## Tech Stack
- **Backend:** Python (FastAPI, Uvicorn, HTTPX, BeautifulSoup4)
- **Frontend:** HTML/CSS/Vanilla JS (No build step required)
- **AI/LLM:** Local Ollama instance (Llama 3, Gemma 2, etc.)
- **Search:** DuckDuckGo (Direct HTTP requests mimicking browser VQD flow)

## Architecture
The project is structured as a modular `app/` package with a lightweight entry point:

- **`main.py`**: Entry point. Sets up FastAPI, mounts static files, and defines API endpoints (`/generate`, `/models`).
- **`app/services/scraper.py`**:
  - Fetches page content.
  - Extracts canonical URLs (prioritizes `rel="canonical"` over provided URL).
  - Filters images (removes icons/logos based on size and keywords).
- **`app/services/llm.py`**:
  - Manages prompt engineering ("LLM Payload").
  - Handles per-source summarization and final article synthesis.
  - Passes available images to the LLM for context-aware insertion.
- **`app/services/search.py`**:
  - Implements a 2-step DuckDuckGo image search (Fetch VQD -> Fetch Images).
  - Robust error handling and fallback.
  - Controlled by `ENABLE_IMAGE_SEARCH` (default: `true`).
- **`app/models.py`**: Pydantic models for API requests/responses.
- **`static/`**: Frontend assets (index.html, app.js, style.css).

## Key Features
1.  **Smart Image Handling:** The LLM is aware of filtered source images and search results, inserting them directly into the Markdown (`![Alt](URL)`).
2.  **Canonical Linking:** References always point to the original source if detected.
3.  **Interactive UI:**
    - "Edit Prompt" mode allows refining the instructions before regeneration.
    - Live Markdown preview and raw editing.
    - Image insertion from search/source tabs.

## Recent Changes (Refactor)
- Split monolithic `main.py` into `app/` services.
- Fixed image search by implementing VQD token extraction.
- Enabled image search by default.
- Added prompt editing and regeneration in the UI.

## Setup & Run
```bash
pip install -r requirements.txt
uvicorn main:app --reload
# Access at http://localhost:8000
```
