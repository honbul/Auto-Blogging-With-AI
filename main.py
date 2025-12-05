import asyncio
import os
import re
from collections import Counter
from typing import List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl, field_validator

# Models listed in the dropdown UI. Add your own identifiers here to route to a real LLM.
SUPPORTED_MODELS = {"llama": "Llama 3", "gemma": "Gemma 2"}
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_ORDER = "Blend insights from every source, balance strengths and gaps, keep it concise and publish-ready."
ENABLE_IMAGE_SEARCH = os.getenv("ENABLE_IMAGE_SEARCH", "false").lower() == "true"


class GenerateRequest(BaseModel):
    urls: List[HttpUrl]
    model: str
    instructions: Optional[str] = None
    max_words: int = 500
    source_labels: Optional[List[str]] = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Model is required.")
        return value.strip()

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, urls: List[HttpUrl]) -> List[HttpUrl]:
        if not urls:
            raise ValueError("At least one URL is required.")
        return urls

    @field_validator("max_words")
    @classmethod
    def validate_max_words(cls, value: int) -> int:
        return max(120, min(1500, value))


class ImageResult(BaseModel):
    title: str
    thumbnail: str
    link: str


class GenerateResponse(BaseModel):
    markdown: str
    images: List[ImageResult]
    source_titles: List[str]
    source_urls: List[str]
    model: str
    prompt_preview: str
    source_summaries: List[str]


app = FastAPI(title="Link-to-Article LLM", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse("static/index.html")


@app.post("/generate", response_model=GenerateResponse)
async def generate_article(payload: GenerateRequest) -> GenerateResponse:
    texts, titles = await fetch_all_texts([str(u) for u in payload.urls])
    combined_text = "\n\n".join(texts)
    if not combined_text or len(combined_text.split()) < 25:
        raise HTTPException(status_code=400, detail="Source page did not contain enough readable text.")

    source_titles = [
        (payload.source_labels[i] if payload.source_labels and i < len(payload.source_labels) else None)
        or titles[i]
        or build_fallback_title(str(payload.urls[i]))
        for i in range(len(payload.urls))
    ]

    main_title = source_titles[0]
    source_urls = [str(u) for u in payload.urls]
    source_summaries = await summarize_sources_with_ollama(
        payload.model, source_titles, source_urls, texts, payload.max_words
    )
    article_markdown, prompt_preview = await synthesize_with_ollama(
        payload.model,
        main_title,
        combined_text,
        payload.instructions,
        source_titles,
        source_urls,
        payload.max_words,
        source_summaries,
    )
    article_markdown = append_references(article_markdown, source_titles, source_urls)
    images = await build_image_results(main_title, combined_text)

    return GenerateResponse(
        markdown=article_markdown,
        images=images,
        source_titles=source_titles,
        source_urls=source_urls,
        model=payload.model,
        prompt_preview=prompt_preview,
        source_summaries=source_summaries,
    )


@app.get("/models")
async def list_models() -> List[str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            found = [m.get("name") for m in data.get("models", []) if m.get("name")]
            return found or list(SUPPORTED_MODELS.keys())
    except Exception:
        return list(SUPPORTED_MODELS.keys())


async def fetch_page_text(url: str) -> Tuple[str, Optional[str]]:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - defensive network handling
        raise HTTPException(status_code=400, detail=f"Unable to fetch URL: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    source_title = soup.title.string.strip() if soup.title and soup.title.string else None
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text, source_title


async def fetch_all_texts(urls: List[str]) -> Tuple[List[str], List[str]]:
    fetched = await asyncio.gather(*[fetch_page_text(url) for url in urls], return_exceptions=True)
    texts: List[str] = []
    titles: List[str] = []
    for item in fetched:
        if isinstance(item, Exception):
            continue
        text, title = item
        if text:
            texts.append(text)
        titles.append(title or "")
    return texts, titles


def build_fallback_title(url: str) -> str:
    cleaned = re.sub(r"https?://(www\\.)?", "", url)
    cleaned = cleaned.split("/")[0]
    return f"Highlights from {cleaned}"


def synthesize_article(model: str, title: str, source_text: str) -> str:
    keywords = extract_keywords(source_text, limit=7)
    summary = summarize_text(source_text, target_words=140)
    tone = "strategic and concise" if model == "gemma" else "conversational and bold"
    perspective = "product strategist" if model == "gemma" else "tech editor"
    model_label = SUPPORTED_MODELS.get(model, model)

    highlights = "\n".join(f"- {point}" for point in derive_points(source_text, keywords))
    reading_time = max(2, int(len(source_text.split()) / 180))

    return f"""# {title}

*Model: {model_label} · Tone: {tone} · Est. read time: {reading_time} min*

## TL;DR
{summary}

## Highlights
{highlights}

## Analysis
With the lens of a {perspective}, here's the gist of the source:

{build_paragraph(source_text, keywords[:3], tone)}

## What to watch
- Emerging themes: {", ".join(keywords[:3]) if keywords else "n/a"}
- Open questions: Where does this narrative go next? Who is most impacted?
- Suggested follow-up: Validate the claims from the source with an additional independent reference.

## Footer
Draft generated from the linked source. Replace `synthesize_article` with your real LLM call to upgrade depth and style.
"""


def summarize_text(text: str, target_words: int = 120) -> str:
    words = text.split()
    if len(words) <= target_words:
        return " ".join(words)
    return " ".join(words[:target_words]) + "…"


def extract_keywords(text: str, limit: int = 5) -> List[str]:
    stopwords = {
        "this",
        "that",
        "with",
        "from",
        "about",
        "would",
        "could",
        "there",
        "their",
        "where",
        "which",
        "while",
        "these",
        "those",
        "have",
        "because",
        "between",
        "other",
        "under",
        "after",
        "before",
        "whose",
        "over",
        "into",
        "given",
        "might",
        "should",
        "during",
        "against",
    }
    words = re.findall(r"[A-Za-z]{4,}", text.lower())
    counts = Counter(w for w in words if w not in stopwords)
    return [word for word, _ in counts.most_common(limit)]


def derive_points(text: str, keywords: List[str]) -> List[str]:
    snippets = []
    for kw in keywords[:4]:
        match = re.search(rf"([^\\.?!]{{0,120}}{kw}[^\\.?!]{{0,120}})", text, re.IGNORECASE)
        if match:
            snippets.append(match.group(1).strip())
    if not snippets:
        snippets.append("The source provides context but needs deeper synthesis for meaningful takeaways.")
    return snippets


def build_paragraph(text: str, keywords: List[str], tone: str) -> str:
    base = summarize_text(text, target_words=180)
    keyword_line = ", ".join(keywords) if keywords else "the core themes"
    return f"{base} This read centers on {keyword_line}, framed in a {tone} voice to stay approachable."


async def summarize_sources_with_ollama(
    model: str, titles: List[str], urls: List[str], texts: List[str], max_words: int
) -> List[str]:
    summaries: List[str] = []

    async def summarize_single(title: str, url: str, text: str) -> str:
        snippet = " ".join(text.split()[:800])
        prompt = f"""Summarize the following source in 80-120 words. Keep it factual and concise.
Title: {title}
URL: {url}
Text:
{snippet}
"""
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                resp.raise_for_status()
                data = resp.json()
                if "response" in data:
                    return data["response"]
        except Exception:
            return summarize_text(text, target_words=120)
        return summarize_text(text, target_words=120)

    tasks = []
    for title, url, text in zip(titles, urls, texts):
        tasks.append(summarize_single(title or "Untitled", url, text))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            summaries.append("")
        else:
            summaries.append(res)
    # If any summary missing, fall back to heuristic.
    for idx, summary in enumerate(summaries):
        if not summary:
            summaries[idx] = summarize_text(texts[idx], target_words=120) if idx < len(texts) else ""
    return summaries


def build_prompt(
    title: str,
    source_text: str,
    instructions: Optional[str],
    source_titles: List[str],
    source_urls: List[str],
    max_words: int,
    source_summaries: List[str],
) -> str:
    user_order = instructions.strip() if instructions else DEFAULT_ORDER
    summaries_block = "\n".join(
        f"- {source_titles[i] or 'Untitled'} ({source_urls[i]}) :: {src_sum}"
        for i, src_sum in enumerate(source_summaries)
    )
    return f"""
You are an expert blog editor. Write a Markdown article that is clean and ready to paste into a CMS.
Follow the user's order exactly.

User order: {user_order}
Per-source summaries:
{summaries_block}

Requirements:
- Include sections: # Title, ## TL;DR, ## Highlights (bullets), ## Analysis, ## What to watch.
- Keep tone confident and concise.
- Keep length under {max_words} words unless the order says otherwise.
- Do not hallucinate facts beyond the source summary.
- Use every per-source summary above—do not focus only on the first link. If sources conflict, call it out.
"""


async def synthesize_with_ollama(
    model: str,
    title: str,
    source_text: str,
    instructions: Optional[str],
    source_titles: List[str],
    source_urls: List[str],
    max_words: int,
    source_summaries: List[str],
) -> Tuple[str, str]:
    prompt = build_prompt(title, source_text, instructions, source_titles, source_urls, max_words, source_summaries)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            if "response" not in data:
                raise HTTPException(status_code=502, detail="Ollama did not return text.")
            return data["response"], prompt
    except Exception:
        return synthesize_article(model, title, source_text), prompt


async def build_image_results(title: str, text: str) -> List[ImageResult]:
    if not ENABLE_IMAGE_SEARCH:
        placeholder_svg = (
            "data:image/svg+xml;utf8,"
            "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='200' viewBox='0 0 320 200'>"
            "<rect width='320' height='200' fill='%23111a2f'/>"
            "<text x='50%' y='50%' fill='%23bcd9ff' font-size='14' font-family='sans-serif' text-anchor='middle'>"
            "Image search disabled (no outbound)</text></svg>"
        )
        return [
            ImageResult(
                title="Image search disabled (set ENABLE_IMAGE_SEARCH=true to enable)",
                thumbnail=placeholder_svg,
                link="",
            )
        ]

    from urllib.parse import quote_plus

    keywords = extract_keywords(text, limit=3) or [title]
    query = quote_plus(f"{title} {keywords[0] if keywords else ''}")
    url = f"https://duckduckgo.com/i.js?l=us-en&o=json&q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            results: List[ImageResult] = []
            for item in data.get("results", [])[:6]:
                results.append(
                    ImageResult(
                        title=item.get("title", "image"),
                        thumbnail=item.get("thumbnail") or item.get("image") or "",
                        link=item.get("url") or item.get("image") or "",
                    )
                )
            if results:
                return results
    except Exception:
        pass

    fallbacks: List[ImageResult] = []
    for kw in keywords[:4]:
        query = quote_plus(f"{title} {kw}")
        fallbacks.append(
            ImageResult(
                title=f"Search: {kw}",
                thumbnail="",
                link=f"https://duckduckgo.com/?q={query}&iax=images&ia=images",
            )
        )
    return fallbacks


def append_references(markdown: str, titles: List[str], urls: List[str]) -> str:
    lines = ["\n## References"]
    for t, u in zip(titles, urls):
        label = t or u
        lines.append(f"- [{label}]({u})")
    return markdown.rstrip() + "\n\n" + "\n".join(lines) + "\n"
