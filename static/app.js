const urlsInput = document.getElementById("urls");
const orderInput = document.getElementById("order");
const modelSelect = document.getElementById("model");
const statusEl = document.getElementById("status");
const progressEl = document.getElementById("progress");
const generateBtn = document.getElementById("generate");
const previewEl = document.getElementById("preview");
const imagesEl = document.getElementById("images");
const sourceImagesEl = document.getElementById("source-images");
const viewTabs = document.querySelectorAll(".tabs .tab[data-tab]");
const previewView = document.getElementById("preview");
const rawView = document.getElementById("raw-markdown");
const copyBtn = document.getElementById("copy-raw");
const revertBtn = document.getElementById("revert-raw");
const anchorText = document.getElementById("anchor-text");
const clearAnchorBtn = document.getElementById("clear-anchor");
const promptPreview = document.getElementById("prompt-preview");
const copyPromptBtn = document.getElementById("copy-prompt");
const sourcesList = document.getElementById("sources-list");
const maxWordsInput = document.getElementById("max-words");
const imageTabs = document.querySelectorAll(".image-tabs .tab");
const customImageInput = document.getElementById("custom-image-url");
const insertCustomImageBtn = document.getElementById("insert-custom-image");
const imageWidthSelect = document.getElementById("image-width");
let lastMarkdown = "";
let lastPrompt = "";
let generatedMarkdown = "";
let lastSourceImages = [];
let lastSourceTitles = [];
let anchorSnippet = "";
let anchorRangeHint = null;
const escapeRegExp = (str) => str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const markdownToPlainWithMap = (md) => {
  const plain = [];
  const map = [];
  for (let i = 0; i < md.length; i++) {
    const ch = md[i];
    if ("#*_`>".includes(ch)) continue;
    plain.push(ch);
    map.push(i);
  }
  return { plain: plain.join(""), map };
};
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

const renderSearchImages = (images = []) => {
  imagesEl.innerHTML = "";
  if (!images.length) {
    imagesEl.innerHTML = '<p class="status">No images yet. Generate an article first.</p>';
    return;
  }
  images.forEach((img, idx) => {
    const card = document.createElement("div");
    card.className = "image-card";
    const thumb = img.thumbnail
      ? `<img src="${img.thumbnail}" alt="${img.title}" loading="lazy" />`
      : `<div class="img-fallback">Image search link</div>`;
    const insertBtn = img.link
      ? `<button class="mini insert-image" data-url="${img.link}" data-title="${img.title}">Insert in Markdown</button>`
      : "";
    card.innerHTML = `<span>#${idx + 1}</span>${thumb}<p><a href="${img.link}" target="_blank" rel="noreferrer">${img.title}</a></p>${insertBtn}`;
    imagesEl.appendChild(card);
  });
};

const renderSourceImages = (sources = [], titles = []) => {
  sourceImagesEl.innerHTML = "";
  const flattened = sources.flat().length;
  if (!flattened) {
    sourceImagesEl.innerHTML = '<p class="status">No images found in the provided links.</p>';
    return;
  }
  sources.forEach((imgs, idx) => {
    imgs.forEach((url, innerIdx) => {
      const card = document.createElement("div");
      card.className = "image-card";
      const title = titles[idx] || `Source ${idx + 1}`;
      card.innerHTML = `<span>${title}</span><img src="${url}" alt="${title} image ${innerIdx + 1}" loading="lazy" /><button class="mini insert-image" data-url="${url}" data-title="${title}">Insert in Markdown</button>`;
      sourceImagesEl.appendChild(card);
    });
  });
};

const renderPreview = (markdown) => {
  lastMarkdown = markdown || "Paste links to start.";
  previewEl.innerHTML = marked.parse(lastMarkdown);
  rawView.value = lastMarkdown;
  applyAnchorHighlight();
};

const renderPreviewFromRaw = () => {
  lastMarkdown = rawView.value;
  previewEl.innerHTML = marked.parse(lastMarkdown || "");
  applyAnchorHighlight();
};

const updateAnchorInfo = () => {
  anchorText.textContent = anchorSnippet ? `"${anchorSnippet}"` : "None. Click rendered text to set.";
};

const applyAnchorHighlight = () => {
  previewEl.querySelectorAll(".anchor-mark").forEach((el) => {
    const parent = el.parentNode;
    while (el.firstChild) parent.insertBefore(el.firstChild, el);
    parent.removeChild(el);
  });
  previewEl.querySelectorAll(".anchor-icon").forEach((el) => el.remove());
  if (!anchorSnippet) return;
  const walker = document.createTreeWalker(previewEl, NodeFilter.SHOW_TEXT, null);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const idx = node.nodeValue.indexOf(anchorSnippet);
    if (idx !== -1) {
      const range = document.createRange();
      range.setStart(node, idx);
      range.setEnd(node, idx + anchorSnippet.length);
      const mark = document.createElement("span");
      mark.className = "anchor-mark";
      range.surroundContents(mark);
      const icon = document.createElement("span");
      icon.textContent = "📍";
      icon.className = "anchor-icon";
      mark.parentNode.insertBefore(icon, mark.nextSibling);
      break;
    }
  }
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

const locateAnchorInRaw = (snippet, raw) => {
  if (!snippet) return null;
  const { plain, map } = markdownToPlainWithMap(raw);
  const pattern = escapeRegExp(snippet.trim()).replace(/\s+/g, "\\s+");
  const regex = new RegExp(pattern, "i");
  const match = plain.match(regex);
  if (!match) return null;
  const endPlainIdx = match.index + match[0].length - 1;
  const mapped = map[Math.min(endPlainIdx, map.length - 1)];
  return typeof mapped === "number" ? mapped + 1 : null;
};

const insertImageMarkdown = (title, url) => {
  const width = imageWidthSelect.value || "480";
  const insertion = `\n\n<div class="inserted-image"><img src="${url}" alt="${title || "image"}" width="${width}" style="display:block;margin:16px auto;max-width:100%;height:auto;" /></div>\n\n`;
  const value = rawView.value;
  let insertPos = rawView.selectionStart || value.length;

  const anchorPos = locateAnchorInRaw(anchorSnippet, value);
  if (anchorPos !== null) {
    insertPos = anchorPos;
    const post = value.slice(insertPos);
    const newlineIdx = post.indexOf("\n");
    const punctIdx = post.search(/[\\.?!]/);
    const stop = [newlineIdx, punctIdx].filter((v) => v !== -1);
    if (stop.length) {
      insertPos += Math.min(...stop) + 1;
    }
  }

  const end = anchorPos !== null ? insertPos : rawView.selectionEnd || insertPos;
  rawView.value = value.slice(0, insertPos) + insertion + value.slice(end);
  rawView.focus();
  rawView.selectionStart = rawView.selectionEnd = insertPos + insertion.length;
  renderPreviewFromRaw();
  applyAnchorHighlight();
};

const generate = async () => {
  const urls = parseUrls(urlsInput.value);
  const model = modelSelect.value;
  const instructions = orderInput.value.trim() || defaultOrder;
  const sourceLabels = [];
  const max_words = Number(maxWordsInput.value) || 2000;
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
    // model pill removed from UI; keep status instead
    setStatus(`Draft ready using model: ${data.model}`);
    renderPreview(data.markdown);
    generatedMarkdown = data.markdown || "";
    applyAnchorHighlight();
    renderSearchImages(data.images);
    lastSourceImages = data.source_images || [];
    lastSourceTitles = data.source_titles || [];
    renderSourceImages(lastSourceImages, lastSourceTitles);
    renderSources(data.source_titles, data.source_urls);
  promptPreview.value = data.prompt_preview || "";
  lastPrompt = data.prompt_preview || "";
  anchorSnippet = "";
  updateAnchorInfo();
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
  viewTabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === target));
  previewView.classList.toggle("active", target === "rendered");
  rawView.classList.toggle("active", target === "raw");
};

viewTabs.forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab.dataset.tab));
});

const switchImageTab = (target) => {
  imageTabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.imgTab === target));
  imagesEl.classList.toggle("active", target === "search");
  sourceImagesEl.classList.toggle("active", target === "source");
};

imageTabs.forEach((tab) => {
  tab.addEventListener("click", () => switchImageTab(tab.dataset.imgTab));
});

copyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(rawView.value || lastMarkdown);
    setStatus("Markdown copied to clipboard.");
  } catch (err) {
    setStatus("Copy failed. Select and copy manually.", true);
  }
});

revertBtn.addEventListener("click", () => {
  if (!generatedMarkdown) {
    setStatus("Generate a draft first to use revert.", true);
    return;
  }
  rawView.value = generatedMarkdown;
  renderPreviewFromRaw();
  setStatus("Reverted to last generated draft.");
  switchTab("raw");
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

rawView.addEventListener("input", renderPreviewFromRaw);

const bindImageInsert = (el) => {
  el.addEventListener("click", (e) => {
    const btn = e.target.closest(".insert-image");
    if (!btn) return;
    const url = btn.dataset.url;
    const title = btn.dataset.title;
    if (url) {
      insertImageMarkdown(title, url);
      switchTab("rendered");
      window.scrollTo({ top: 0, behavior: "smooth" });
      setStatus("Image inserted. Review in the rendered view; adjust alt/width if needed.");
    }
  });
};

[imagesEl, sourceImagesEl].forEach(bindImageInsert);

insertCustomImageBtn.addEventListener("click", () => {
  const url = customImageInput.value.trim();
  if (!url) {
    setStatus("Paste an image URL to insert.", true);
    return;
  }
  insertImageMarkdown("custom-image", url);
  switchTab("rendered");
  window.scrollTo({ top: 0, behavior: "smooth" });
  setStatus("Custom image inserted. Review in the rendered view.");
});

previewEl.addEventListener("click", (event) => {
  const selection = window.getSelection();
  if (!selection) return;

  if (!selection.isCollapsed && selection.toString().trim()) {
    anchorSnippet = selection.toString().trim().slice(0, 120);
    setStatus("Anchor set from selected text. Insert will follow it.");
    updateAnchorInfo();
    applyAnchorHighlight();
    return;
  }

  const anchorNode = selection.anchorNode;
  const offset = selection.anchorOffset;
  if (anchorNode && anchorNode.nodeType === Node.TEXT_NODE) {
    const text = anchorNode.textContent || "";
    const start = Math.max(0, offset - 20);
    const end = Math.min(text.length, offset + 20);
    anchorSnippet = text.slice(start, end).trim() || text.trim().slice(0, 120);
    setStatus("Anchor set at cursor position. Insert will follow the paragraph end.");
    updateAnchorInfo();
    applyAnchorHighlight();
  }
});

clearAnchorBtn.addEventListener("click", () => {
  anchorSnippet = "";
  updateAnchorInfo();
  renderPreviewFromRaw();
  setStatus("Anchor cleared. Cursor position will be used for inserts.");
});

renderPreview("Paste links and hit Generate to see a live preview.");
renderSearchImages();
renderSourceImages();
renderProgress();
loadModels();
