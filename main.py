from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import GenerateRequest, GenerateResponse
from app.services.scraper import fetch_all_data, build_fallback_title
from app.services.llm import summarize_sources_with_ollama, synthesize_with_ollama, get_supported_models, SUPPORTED_MODELS
from app.services.search import search_images


app = FastAPI(title="Link-to-Article LLM", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse("static/index.html")


@app.post("/generate", response_model=GenerateResponse)
async def generate_article(payload: GenerateRequest) -> GenerateResponse:
    texts, titles, source_images, final_urls = await fetch_all_data([str(u) for u in payload.urls])
    combined_text = "\n\n".join(texts)
    if not combined_text or len(combined_text.split()) < 25:
        raise HTTPException(status_code=400, detail="Source page did not contain enough readable text.")

    source_titles = [
        (payload.source_labels[i] if payload.source_labels and i < len(payload.source_labels) else None)
        or titles[i]
        or build_fallback_title(final_urls[i])
        for i in range(len(payload.urls))
    ]

    main_title = source_titles[0]
    source_urls = final_urls
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
        source_images,
    )
    
    # Append references locally or move this to llm service? 
    # Logic is simple enough to keep here or move. keeping it here for now but function was removed.
    # Re-implementing append_references briefly or importing it? 
    # I should have moved it to llm.py or utils. Let's add it here or move it.
    # Inline is fine for now as it's simple string manipulation.
    
    lines = ["\n## References"]
    for t, u in zip(source_titles, source_urls):
        label = t or u
        lines.append(f"- [{label}]({u})")
    article_markdown = article_markdown.rstrip() + "\n\n" + "\n".join(lines) + "\n"

    images = await search_images(main_title, combined_text)

    return GenerateResponse(
        markdown=article_markdown,
        images=images,
        source_titles=source_titles,
        source_urls=source_urls,
        model=payload.model,
        prompt_preview=prompt_preview,
        source_summaries=source_summaries,
        source_images=source_images,
    )


@app.get("/models")
async def list_models() -> List[str]:
    return await get_supported_models()