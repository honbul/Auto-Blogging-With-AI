import os
import re
from typing import List
from urllib.parse import quote_plus

import httpx
from ..models import ImageResult

ENABLE_IMAGE_SEARCH = os.getenv("ENABLE_IMAGE_SEARCH", "false").lower() == "true"

async def get_vqd(client: httpx.AsyncClient, query: str) -> str:
    try:
        resp = await client.get(f"https://duckduckgo.com/?q={query}&t=h_&iax=images&ia=images")
        # Extract vqd='...' or vqd="..."
        match = re.search(r'vqd=[\'"]?([^&"\']+)[\'"]?', resp.text)
        return match.group(1) if match else ""
    except Exception:
        return ""

async def search_images(title: str, text: str) -> List[ImageResult]:
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

    # Simple keyword extraction for query
    words = re.findall(r"[A-Za-z]{4,}", text.lower())
    # Take top frequent words or just use title
    keywords = words[:3] if words else [title]
    query_str = f"{title} {' '.join(keywords)}"
    query = quote_plus(query_str)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://duckduckgo.com/",
        "X-Requested-With": "XMLHttpRequest",
    }

    results: List[ImageResult] = []
    
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            # Step 1: Get VQD
            vqd = await get_vqd(client, query)
            if not vqd:
                # Fallback: simple direct hit (often fails but worth a try if VQD extraction changes)
                # Or just return empty to allow frontend to show "No results"
                pass

            # Step 2: Fetch images
            params = {
                "l": "us-en",
                "o": "json",
                "q": query_str,
                "vqd": vqd,
                "f": ",,,",
                "p": "1"
            }
            url = "https://duckduckgo.com/i.js"
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            for item in data.get("results", [])[:6]:
                results.append(
                    ImageResult(
                        title=item.get("title", "image"),
                        thumbnail=item.get("thumbnail") or item.get("image") or "",
                        link=item.get("url") or item.get("image") or "",
                    )
                )
    except Exception:
        # Silent fail or logging
        pass

    if results:
        return results

    # Fallback to simple link generation if search fails
    fallbacks: List[ImageResult] = []
    for kw in keywords[:4]:
        q = quote_plus(f"{title} {kw}")
        fallbacks.append(
            ImageResult(
                title=f"Search: {kw}",
                thumbnail="",
                link=f"https://duckduckgo.com/?q={q}&iax=images&ia=images",
            )
        )
    return fallbacks
