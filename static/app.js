const urlsInput = document.getElementById("urls");
const orderInput = document.getElementById("order");
const modelSelect = document.getElementById("model");
const statusEl = document.getElementById("status");
const progressEl = document.getElementById("progress");
const generateBtn = document.getElementById("generate");
const previewEl = document.getElementById("preview");
const titleEl = document.getElementById("article-title");
const imagesEl = document.getElementById("images");
const modelPill = document.getElementById("model-pill");
const tabs = document.querySelectorAll(".tab");
const previewView = document.getElementById("preview");
const rawView = document.getElementById("raw-markdown");
const copyBtn = document.getElementById("copy-raw");
const promptPreview = document.getElementById("prompt-preview");
const copyPromptBtn = document.getElementById("copy-prompt");
const sourcesList = document.getElementById("sources-list");
const maxWordsInput = document.getElementById("max-words");
let lastMarkdown = "";
let lastPrompt = "";
const defaultOrder =
  "Blend insights from every source, balance strengths and gaps, keep it concise and publish-ready.";

marked.setOptions({
  headerIds: false,
  mangle: false,
});

const setStatus = (msg, isError = false) => {
  statusEl.textContent = msg;
  statusEl.classList.toggle("error", isError);
};

const renderImages = (images = []) => {
  imagesEl.innerHTML = "";
  if (!images.length) {
    imagesEl.innerHTML = '<p class="status">No prompts yet. Generate an article first.</p>';
    return;
  }
  images.forEach((img, idx) => {
    const card = document.createElement("div");
    card.className = "image-card";
    const thumb = img.thumbnail
      ? `<img src="${img.thumbnail}" alt="${img.title}" loading="lazy" />`
      : `<div class="img-fallback">Image search link</div>`;
    card.innerHTML = `<span>#${idx + 1}</span>${thumb}<p><a href="${img.link}" target="_blank" rel="noreferrer">${img.title}</a></p>`;
    imagesEl.appendChild(card);
  });
};

const renderPreview = (markdown) => {
  lastMarkdown = markdown || "Paste links to start.";
  previewEl.innerHTML = marked.parse(lastMarkdown);
  rawView.value = lastMarkdown;
};

const renderProgress = (steps = []) => {
  if (!steps.length) {
    progressEl.innerHTML = "";
    return;
  }
  progressEl.innerHTML = steps
    .map(
      (s) =>
        `<div class="progress-row ${s.done ? "done" : ""} ${s.blink ? "blink" : ""}">${s.done ? "✓" : "…"} ${
          s.label
        }</div>`
    )
    .join("");
};

const renderSources = (titles = [], urls = []) => {
  if (!titles.length) {
    sourcesList.innerHTML = '<p class="status">No sources loaded yet.</p>';
    return;
  }
  sourcesList.innerHTML = titles
    .map((t, i) => {
      const url = urls[i] || "";
      return `<div class="source-row"><strong>${t || "Untitled"}</strong><span>${url}</span></div>`;
    })
    .join("");
};

const toggleBusy = (busy) => {
  generateBtn.disabled = busy;
  generateBtn.textContent = busy ? "Working…" : "Generate article";
};

const parseUrls = (value) =>
  value
    .split(/\s+/)
    .map((s) => s.trim())
    .filter(Boolean);

const generate = async () => {
  const urls = parseUrls(urlsInput.value);
  const model = modelSelect.value;
  const instructions = orderInput.value.trim() || defaultOrder;
  const sourceLabels = [];
  const max_words = Number(maxWordsInput.value) || 500;
  if (!urls.length) {
    setStatus("Please paste at least one valid URL.", true);
    return;
  }
  if (!model) {
    setStatus("Choose a model.", true);
    return;
  }

  toggleBusy(true);
  setStatus("Working on your draft…");
  renderProgress([
    { label: "Fetching sources", done: false, blink: true },
    { label: "Summarizing each source", done: false },
    { label: "Generating final article", done: false },
  ]);

  try {
    const response = await fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls, model, instructions, source_labels: sourceLabels, max_words }),
    });

    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || "Request failed");
    }

    const data = await response.json();
    setStatus("Draft ready. You can tweak the Markdown or regenerate.");
    renderProgress([
      { label: "Fetching sources", done: true },
      { label: "Summarizing each source", done: true },
      { label: "Generating final article", done: true },
    ]);
    titleEl.textContent = data.source_titles?.[0] || "Untitled draft";
    modelPill.textContent = `model: ${data.model}`;
    renderPreview(data.markdown);
    renderImages(data.images);
    renderSources(data.source_titles, data.source_urls);
    promptPreview.value = data.prompt_preview || "";
    lastPrompt = data.prompt_preview || "";
  } catch (err) {
    console.error(err);
    setStatus(err.message || "Something went wrong.", true);
    renderProgress();
  } finally {
    toggleBusy(false);
  }
};

const loadModels = async () => {
  try {
    const resp = await fetch("/models");
    const models = await resp.json();
    modelSelect.innerHTML = "";
    (models || []).forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      modelSelect.appendChild(opt);
    });
  } catch (err) {
    console.error("Model load failed", err);
    modelSelect.innerHTML = '<option value="llama">llama</option><option value="gemma">gemma</option>';
  }
};

const switchTab = (target) => {
  tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === target));
  previewView.classList.toggle("active", target === "rendered");
  rawView.classList.toggle("active", target === "raw");
};

tabs.forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab.dataset.tab));
});

copyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(lastMarkdown);
    setStatus("Markdown copied to clipboard.");
  } catch (err) {
    setStatus("Copy failed. Select and copy manually.", true);
  }
});

copyPromptBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(lastPrompt);
    setStatus("Prompt copied to clipboard.");
  } catch (err) {
    setStatus("Copy failed. Select and copy manually.", true);
  }
});

generateBtn.addEventListener("click", generate);
urlsInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
    generate();
  }
});

renderPreview("Paste links and hit Generate to see a live preview.");
renderImages();
renderProgress();
loadModels();
