# Link-to-Article Studio

Generate publish-ready Markdown articles from one or more URLs using a local Ollama backend, with a custom FastAPI + vanilla JS UI.

## Features
- Multiple source links per draft; per-link LLM summaries plus a final LLM pass for the article.
- User order/instructions with a sensible default if left blank.
- Rendered + raw Markdown tabs with live editing, copy, and revert.
- Insert images directly into Markdown from search results or original sources.
- Advanced panel shows the exact prompt, source list, and lets you set max words.
- Image previews via DuckDuckGo (optional; toggle by env var).
- References section appended with all source links.

## How it works
1. Fetch & clean each URL (strip scripts/styles, normalize text).
2. Per-source summaries: one Ollama call per link to condense content (falls back to heuristic if needed).
3. Build prompt: user/default order + per-source summaries + constraints.
4. Final article: single Ollama call to generate Markdown; references appended.
5. Image search (optional): DuckDuckGo thumbnails; placeholder when disabled.

## Run locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload
# open http://localhost:8000
```

## Environment
- `OLLAMA_URL` (default `http://localhost:11434`)
- `ENABLE_IMAGE_SEARCH` (`true` to allow outbound DuckDuckGo image fetches; default `false`)

## Usage
1. Paste one or more links (one per line).
2. Add an order (optional; default keeps it concise and multi-source aware).
3. Pick a model (loaded from Ollama `/api/tags`).
4. Generate; copy rendered or raw Markdown, or the prompt from the advanced panel.

## Notes
- Image previews require outbound HTTPS to `duckduckgo.com` when `ENABLE_IMAGE_SEARCH=true`; no API key needed.
- If Ollama or outbound calls fail, the app falls back to heuristic summaries/generation to keep the UI responsive.
