import asyncio
import re
from typing import List, Optional, Tuple, Set
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag
from fastapi import HTTPException


def extract_image_urls(soup: BeautifulSoup, base_url: str) -> List[str]:
    urls: List[str] = []
    # prioritization: look for article images first
    candidates = soup.find_all("img")
    
    ignore_terms = {"icon", "logo", "avatar", "button", "share", "social", "tracker", "pixel"}
    
    for tag in candidates:
        if not isinstance(tag, Tag):
            continue
            
        # Basic attribute filtering
        src = tag.get("src") or ""
        alt = (tag.get("alt") or "").lower()
        cls = " ".join(tag.get("class") or []).lower()
        
        if not src or src.startswith("data:"):
            continue
            
        # Filter by size if attributes exist (heuristic)
        width = tag.get("width")
        height = tag.get("height")
        if width and width.isdigit() and int(width) < 150:
            continue
        if height and height.isdigit() and int(height) < 150:
            continue
            
        # Filter by keywords
        combined_attrs = (src + " " + alt + " " + cls).lower()
        if any(term in combined_attrs for term in ignore_terms):
            continue

        full = urljoin(base_url, src)
        if full.startswith(("http://", "https://")):
            urls.append(full)
        if len(urls) >= 12:
            break
    return urls


async def fetch_page_text(url: str) -> Tuple[str, Optional[str], List[str], str]:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
        response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to fetch URL: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    source_title = soup.title.string.strip() if soup.title and soup.title.string else None
    
    # Check for canonical URL
    canonical_tag = soup.find("link", rel="canonical")
    canonical_url = canonical_tag.get("href") if canonical_tag else url
    if not canonical_url or not isinstance(canonical_url, str) or not canonical_url.startswith(("http://", "https://")):
        canonical_url = url
        
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    image_urls = extract_image_urls(soup, url)
    return text, source_title, image_urls, canonical_url


async def fetch_all_data(urls: List[str]) -> Tuple[List[str], List[str], List[List[str]], List[str]]:
    fetched = await asyncio.gather(*[fetch_page_text(url) for url in urls], return_exceptions=True)
    texts: List[str] = []
    titles: List[str] = []
    images: List[List[str]] = []
    final_urls: List[str] = []
    
    for i, result in enumerate(fetched):
        if isinstance(result, Exception):
            texts.append("")
            titles.append("")
            images.append([])
            final_urls.append(urls[i])
            continue
        text, title, img_urls, canon_url = result
        texts.append(text or "")
        titles.append(title or "")
        images.append(img_urls or [])
        final_urls.append(canon_url or urls[i])
    return texts, titles, images, final_urls


def build_fallback_title(url: str) -> str:
    cleaned = re.sub(r"https?://(www\\.)?", "", url)
    cleaned = cleaned.split("/")[0]
    return f"Highlights from {cleaned}"
