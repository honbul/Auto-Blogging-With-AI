# Link-to-Article Studio

Generate publish-ready Markdown articles from one or more URLs using a local Ollama backend, with a custom FastAPI + vanilla JS UI.

## Features
- **Smart Summarization:** Fetches and cleans content from multiple source links, generating per-source summaries via LLM before synthesizing a final draft.
- **Canonical Source Detection:** Automatically detects and credits the original source URL (via `rel="canonical"`) instead of the syndication link.
- **LLM-Driven Image Placement:** Intelligently filters source images (removing icons/logos) and allows the LLM to insert relevant ones directly into the article flow.
- **Robust Image Search:** Includes a built-in DuckDuckGo image search (VQD-based) to find relevant visuals when source images are insufficient.
- **Interactive Editor:** 
    - Rendered + Raw Markdown tabs with live editing.
    - **Prompt Engineering Mode:** Edit the generated prompt and regenerate the article to fine-tune the output.
    - One-click image insertion from search results or source extraction.
- **Advanced Control:** Set max word count (200-4000 words), custom instructions, and view the full LLM payload.

## Architecture
Refactored into a modular `app/` package structure:
- `app/services/scraper.py`: Content extraction, canonical URL detection, and smart image filtering.
- `app/services/llm.py`: Prompt engineering, summarization, and Ollama integration.
- `app/services/search.py`: Robust DuckDuckGo image search logic.
- `main.py`: Lightweight FastAPI entry point.

## Run locally

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.ai/) running locally (default: `http://localhost:11434`)

### Installation
```bash
# Clone the repository
git clone https://github.com/honbul/Auto-Blogging-With-AI
cd Auto-Blogging-With-AI

# Install dependencies
pip install -r requirements.txt
```

### Running the App
```bash
uvicorn main:app --reload
# Open http://localhost:8000 in your browser
```

## Environment Variables
- `OLLAMA_URL`: URL of your Ollama instance (default: `http://localhost:11434`).
- `ENABLE_IMAGE_SEARCH`: Enable outbound DuckDuckGo image searches (default: `true`). Set to `false` to disable.

## Usage
1. **Paste Links:** Enter one or more URLs (one per line).
2. **Customize:** Add optional instructions (e.g., "Focus on technical details") or leave blank for the default smart synthesis.
3. **Select Model:** Choose an available model from your local Ollama instance.
4. **Generate:** The app fetches content, summarizes each source, and generates a draft.
5. **Refine:**
    - Use "Edit Prompt" in the Advanced Panel to tweak the instructions and regenerate.
    - Insert additional images from the "Image Previews" tab.
    - Edit the Markdown directly in the "Raw" tab.

## Notes
- **Image Search:** Uses a custom VQD-based flow to reliably fetch images from DuckDuckGo without an API key.
- **Fallbacks:** If Ollama or network calls fail, the app attempts to use heuristic summaries to ensure a result is always returned.