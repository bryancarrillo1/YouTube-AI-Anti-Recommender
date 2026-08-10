const form = document.getElementById("search-form");
const urlInput = document.getElementById("youtube-url");
const excludeSameChannel = document.getElementById("exclude-same-channel");
const submitButton = document.getElementById("submit-button");
const statusEl = document.getElementById("status");
const sourceSection = document.getElementById("source-section");
const sourceContent = document.getElementById("source-content");
const conceptsSection = document.getElementById("concepts-section");
const conceptsContent = document.getElementById("concepts-content");
const sourceInterpretation = document.getElementById("source-interpretation");
const resultsSection = document.getElementById("results-section");
const resultsList = document.getElementById("results-list");
const limitedMessage = document.getElementById("limited-message");

const loadingStages = [
  "Reading video metadata…",
  "Finding contrasting directions…",
  "Searching YouTube…",
];

const errorMessages = {
  invalid_youtube_url: "That URL does not look like a valid YouTube video link.",
  video_not_found: "That video could not be found or is not publicly accessible.",
  youtube_quota_exceeded: "YouTube search is temporarily unavailable due to quota limits.",
  gemini_generation_failed: "Could not generate discovery concepts for this video.",
  integration_unavailable: "A required service is temporarily unavailable. Please try again.",
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function hideResults() {
  sourceSection.classList.add("hidden");
  conceptsSection.classList.add("hidden");
  resultsSection.classList.add("hidden");
  sourceContent.innerHTML = "";
  conceptsContent.innerHTML = "";
  sourceInterpretation.textContent = "";
  resultsList.innerHTML = "";
  limitedMessage.classList.add("hidden");
  limitedMessage.textContent = "";
}

function renderSource(source) {
  const tags = source.tags?.length
    ? `<p><strong>Tags:</strong> ${escapeHtml(source.tags.join(", "))}</p>`
    : "";

  sourceContent.innerHTML = `
    <p><strong>${escapeHtml(source.title)}</strong></p>
    <p>Channel: ${escapeHtml(source.channel_title)}</p>
    ${tags}
  `;
  sourceSection.classList.remove("hidden");
}

function renderConcepts(data) {
  conceptsContent.innerHTML = data.concepts
    .map(
      (concept) => `
        <div class="chip">
          <strong>${escapeHtml(concept.contrast_dimension)}:</strong>
          ${escapeHtml(concept.query)}
          <div class="muted">${escapeHtml(concept.rationale)}</div>
        </div>
      `
    )
    .join("");
  sourceInterpretation.textContent = data.source_interpretation;
  conceptsSection.classList.remove("hidden");
}

function renderResults(data) {
  if (data.limited_results_message) {
    limitedMessage.textContent = data.limited_results_message;
    limitedMessage.classList.remove("hidden");
  }

  resultsList.innerHTML = data.recommendations
    .map((item) => {
      const thumb = item.thumbnail_url
        ? `<img src="${escapeHtml(item.thumbnail_url)}" alt="${escapeHtml(item.title)}" loading="lazy" />`
        : `<div aria-hidden="true"></div>`;

      return `
        <li class="result-card">
          ${thumb}
          <div>
            <h3><a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a></h3>
            <p>${escapeHtml(item.channel_title)}</p>
            <p class="muted">${escapeHtml(item.description)}</p>
            <p><strong>Matched query:</strong> ${escapeHtml(item.matched_query)}</p>
            <p><strong>Why this is different:</strong> ${escapeHtml(item.why_this_result)}</p>
          </div>
        </li>
      `;
    })
    .join("");

  resultsSection.classList.remove("hidden");
}

async function runLoadingStages() {
  for (const stage of loadingStages) {
    setStatus(stage);
    await new Promise((resolve) => setTimeout(resolve, 450));
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideResults();

  const youtubeUrl = urlInput.value.trim();
  if (!youtubeUrl) {
    setStatus("Please enter a YouTube URL.", true);
    return;
  }

  submitButton.disabled = true;
  const loadingPromise = runLoadingStages();

  try {
    const response = await fetch("/api/anti-recommendations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        youtube_url: youtubeUrl,
        language: "en",
        exclude_same_channel: excludeSameChannel.checked,
      }),
    });

    await loadingPromise;

    const payload = await response.json();
    if (!response.ok) {
      const message = errorMessages[payload.code] || payload.message || "Something went wrong.";
      setStatus(message, true);
      return;
    }

    setStatus(`Found ${payload.recommendations.length} anti-recommendation(s).`);
    renderSource(payload.source_video);
    renderConcepts(payload);
    renderResults(payload);
  } catch (_error) {
    await loadingPromise;
    setStatus("Network error while contacting the server.", true);
  } finally {
    submitButton.disabled = false;
  }
});
