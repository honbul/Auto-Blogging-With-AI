import asyncio
import os
import re
from collections import Counter
from typing import List, Optional, Tuple

import httpx
from fastapi import HTTPException

# Default configuration
SUPPORTED_MODELS = {"llama": "Llama 3", "gemma": "Gemma 2"}
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_ORDER = "Blend insights from every source, balance strengths and gaps, keep it concise and publish-ready."


async def get_supported_models() -> List[str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            found = [m.get("name") for m in data.get("models", []) if m.get("name")]
            return found or list(SUPPORTED_MODELS.keys())
    except Exception:
        return list(SUPPORTED_MODELS.keys())


def extract_keywords(text: str, limit: int = 5) -> List[str]:
    stopwords = {
        "this", "that", "with", "from", "about", "would", "could", "there", "their",
        "where", "which", "while", "these", "those", "have", "because", "between",
        "other", "under", "after", "before", "whose", "over", "into", "given",
        "might", "should", "during", "against", "your", "they"
    }
    words = re.findall(r"[A-Za-z]{4,}", text.lower())
    counts = Counter(w for w in words if w not in stopwords)
    return [word for word, _ in counts.most_common(limit)]


def summarize_text(text: str, target_words: int = 120) -> str:
    words = text.split()
    if len(words) <= target_words:
        return " ".join(words)
    return " ".join(words[:target_words]) + "…"


def derive_points(text: str, keywords: List[str]) -> List[str]:
    snippets = []
    for kw in keywords[:4]:
        match = re.search(rf"([^\.?!]{{0,120}}{kw}[^\.?!]{{0,120}})", text, re.IGNORECASE)
        if match:
            snippets.append(match.group(1).strip())
    if not snippets:
        snippets.append("The source provides context but needs deeper synthesis for meaningful takeaways.")
    return snippets


def build_paragraph(text: str, keywords: List[str], tone: str) -> str:
    base = summarize_text(text, target_words=180)
    keyword_line = ", ".join(keywords) if keywords else "the core themes"
    return f"{base} This read centers on {keyword_line}, framed in a {tone} voice to stay approachable."


def synthesize_article_fallback(model: str, title: str, source_text: str) -> str:
    keywords = extract_keywords(source_text, limit=7)
    summary = summarize_text(source_text, target_words=140)
    tone = "strategic and concise" if "gemma" in model else "conversational and bold"
    perspective = "product strategist" if "gemma" in model else "tech editor"
    model_label = model

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


async def summarize_sources_with_ollama(
    model: str,
    titles: List[str],
    urls: List[str],
    texts: List[str],
    max_words: int,
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
    
    # Fallback for missing summaries
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
    source_images: List[List[str]],
) -> str:
    user_order = instructions.strip() if instructions else DEFAULT_ORDER
    summaries_block = "\n".join(
        f"- {source_titles[i] or 'Untitled'} ({source_urls[i]}) :: {src_sum}"
        for i, src_sum in enumerate(source_summaries)
    )
    
    # Flatten images with indices for the LLM
    image_block_lines = []
    img_idx = 1
    for i, images in enumerate(source_images):
        src_title = source_titles[i] or f"Source {i+1}"
        for img_url in images:
            image_block_lines.append(f"[{img_idx}] {img_url} (from {src_title})")
            img_idx += 1
    
    image_instruction = ""
    if image_block_lines:
        image_instruction = (
            "\nAvailable Images (you MUST use at least 2 relevant images if they fit the context):\n"
            + "\n".join(image_block_lines)
            + "\n\nInstruction for images: Insert images using Markdown syntax `![Alt Text](URL)`. "
            "Only use URLs from the list above. Choose images that match the section context."
        )

    return f"""
You are an expert blog editor. Write a Markdown article that is clean and ready to paste into a CMS.
Follow the user's order exactly.

User order: {user_order}
Per-source summaries:
{summaries_block}
{image_instruction}

Requirements:
- Include sections: # Title, ## TL;DR, ## Highlights (bullets), ## Analysis, ## What to watch.
- Keep tone confident and concise.
- Keep length under {max_words} words unless the order says otherwise.
- Do not hallucinate facts beyond the source summary.
- Use every per-source summary above—do not focus only on the first link. If sources conflict, call it out.
- Embed relevant images from the "Available Images" list directly into the markdown flow.
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
    source_images: List[List[str]],
) -> Tuple[str, str]:
    prompt = build_prompt(
        title, source_text, instructions, source_titles, source_urls, max_words, source_summaries, source_images
    )
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
        return synthesize_article_fallback(model, title, source_text), prompt
