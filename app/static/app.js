"use strict";

// Text from indexers and qBittorrent is untrusted: it is only ever set through
// textContent (or append with a string), never as HTML.

const RESULTS_PAGE_SIZE = 50;
const DOWNLOADS_REFRESH_MS = 5000;
const KINOARR_TAG = "kinoarr";
const SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"];
const BYTES_PER_UNIT = 1024;
const SAFE_LINK_PROTOCOLS = ["http:", "https:"];
const MISSING_VALUE = "–";

const STATE_LABELS = {
  downloading: "Downloading",
  forcedDL: "Downloading",
  metaDL: "Downloading",
  forcedMetaDL: "Downloading",
  allocating: "Downloading",
  stalledDL: "Stalled",
  queuedDL: "Queued",
  pausedDL: "Paused",
  stoppedDL: "Paused",
  checkingDL: "Checking",
  checkingUP: "Checking",
  checkingResumeData: "Checking",
  moving: "Moving",
  uploading: "Finished",
  forcedUP: "Finished",
  stalledUP: "Finished",
  queuedUP: "Finished",
  pausedUP: "Finished",
  stoppedUP: "Finished",
  error: "Error",
  missingFiles: "Error",
};

const elements = {
  searchForm: document.getElementById("search-form"),
  searchQuery: document.getElementById("search-query"),
  searchStatus: document.getElementById("search-status"),
  resultsTable: document.getElementById("results-table"),
  resultsBody: document.getElementById("results-body"),
  showMoreButton: document.getElementById("show-more"),
  downloadsStatus: document.getElementById("downloads-status"),
  downloadsList: document.getElementById("downloads-list"),
};

let latestSearchId = 0;
let resultsNotShown = [];
let downloadsRefreshInFlight = false;
let downloadsRefreshPending = false;
// Kept by torrent hash, so the periodic re-render of the list does not lose them.
const subtitleMessages = new Map();
const subtitleRequestsInFlight = new Set();

// ---------- API ----------

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("Cannot reach Kinoarr");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(errorMessageFrom(body, response.status));
  }
  return body;
}

function errorMessageFrom(body, status) {
  // Kinoarr's own errors have a string detail; FastAPI's validation errors have a list.
  if (body && typeof body.detail === "string") {
    return body.detail;
  }
  return `Request failed (HTTP ${status})`;
}

function postJson(path, data) {
  return apiRequest(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// ---------- Formatting ----------

function formatSize(bytes) {
  let value = bytes;
  let unitIndex = 0;
  while (value >= BYTES_PER_UNIT && unitIndex < SIZE_UNITS.length - 1) {
    value /= BYTES_PER_UNIT;
    unitIndex += 1;
  }
  const decimals = unitIndex === 0 ? 0 : 1;
  return `${value.toFixed(decimals)} ${SIZE_UNITS[unitIndex]}`;
}

function formatDate(isoDate) {
  const date = new Date(isoDate);
  return Number.isNaN(date.getTime()) ? isoDate : date.toLocaleDateString();
}

function formatCount(count) {
  return count === null ? MISSING_VALUE : String(count);
}

function describeState(state) {
  return STATE_LABELS[state] ?? state;
}

function safeLink(url) {
  if (!url) {
    return null;
  }
  try {
    return SAFE_LINK_PROTOCOLS.includes(new URL(url).protocol) ? url : null;
  } catch {
    return null;
  }
}

function progressPercent(progress) {
  // Rounded down, so an unfinished download never shows 100%.
  return Math.floor(progress * 100);
}

// ---------- DOM helpers ----------

function createElement(tagName, { className, text } = {}) {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (text !== undefined) {
    element.textContent = text;
  }
  return element;
}

function createButton(text, className) {
  const button = createElement("button", { className, text });
  button.type = "button";
  return button;
}

function setStatus(element, text, isError = false) {
  element.textContent = text;
  element.classList.toggle("error", isError);
}

// ---------- Search ----------

async function searchReleases(query) {
  latestSearchId += 1;
  const searchId = latestSearchId;
  clearResults();
  setStatus(elements.searchStatus, "Searching…");
  try {
    const results = await apiRequest(`api/search?${new URLSearchParams({ query })}`);
    if (searchId === latestSearchId) {
      renderResults(results);
    }
  } catch (error) {
    if (searchId === latestSearchId) {
      setStatus(elements.searchStatus, error.message, true);
    }
  }
}

function clearResults() {
  elements.resultsBody.replaceChildren();
  elements.resultsTable.hidden = true;
  elements.showMoreButton.hidden = true;
  resultsNotShown = [];
}

function renderResults(results) {
  if (results.length === 0) {
    setStatus(elements.searchStatus, "No results");
    return;
  }
  setStatus(elements.searchStatus, results.length === 1 ? "1 result" : `${results.length} results`);
  elements.resultsTable.hidden = false;
  appendResults(results.slice(0, RESULTS_PAGE_SIZE));
  resultsNotShown = results.slice(RESULTS_PAGE_SIZE);
  elements.showMoreButton.textContent = `Show ${resultsNotShown.length} more`;
  elements.showMoreButton.hidden = resultsNotShown.length === 0;
}

function showMoreResults() {
  appendResults(resultsNotShown);
  resultsNotShown = [];
  elements.showMoreButton.hidden = true;
}

function appendResults(results) {
  elements.resultsBody.append(...results.map(createResultRow));
}

function createResultRow(result) {
  const row = document.createElement("tr");
  row.append(
    createCell("Title", createReleaseTitle(result), "title-cell"),
    createCell("Indexer", result.indexer),
    createCell("Size", formatSize(result.size), "numeric"),
    createCell("Seeders", formatCount(result.seeders), "numeric"),
    createCell("Leechers", formatCount(result.leechers), "numeric"),
    createCell("Published", formatDate(result.publish_date)),
    createCell("", createDownloadControls(result.id)),
  );
  return row;
}

function createCell(label, content, className) {
  const cell = createElement("td", { className });
  // Shown as a caption when narrow screens turn each row into a card.
  cell.dataset.label = label;
  cell.append(content);
  return cell;
}

function createReleaseTitle(result) {
  const link = safeLink(result.info_url);
  if (!link) {
    return result.title;
  }
  const anchor = createElement("a", { text: result.title });
  anchor.href = link;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  return anchor;
}

function createDownloadControls(releaseId) {
  const controls = createElement("div", { className: "action" });
  const button = createButton("Download");
  const message = createElement("span", { className: "status" });
  button.addEventListener("click", () => startDownload(releaseId, button, message));
  controls.append(button, message);
  return controls;
}

async function startDownload(releaseId, button, message) {
  button.disabled = true;
  setStatus(message, "Adding…");
  try {
    await postJson("api/downloads", { release_id: releaseId });
    setStatus(message, "Added");
    refreshDownloads();
  } catch (error) {
    button.disabled = false;
    setStatus(message, error.message, true);
  }
}

// ---------- Downloads ----------

async function refreshDownloads() {
  if (downloadsRefreshInFlight) {
    // Run once more afterwards, so a download added meanwhile shows up.
    downloadsRefreshPending = true;
    return;
  }
  downloadsRefreshInFlight = true;
  try {
    const torrents = await apiRequest(`api/downloads?${new URLSearchParams({ tag: KINOARR_TAG })}`);
    renderDownloads(torrents);
  } catch (error) {
    elements.downloadsList.replaceChildren();
    setStatus(elements.downloadsStatus, error.message, true);
  } finally {
    downloadsRefreshInFlight = false;
  }
  if (downloadsRefreshPending) {
    downloadsRefreshPending = false;
    refreshDownloads();
  }
}

function renderDownloads(torrents) {
  setStatus(elements.downloadsStatus, torrents.length === 0 ? "No downloads yet" : "");
  elements.downloadsList.replaceChildren(...torrents.map(createDownloadItem));
}

function createDownloadItem(torrent) {
  const item = createElement("li", { className: "download" });
  item.dataset.hash = torrent.hash;

  const header = createElement("div", { className: "download-header" });
  header.append(
    createElement("span", { className: "download-name", text: torrent.name }),
    createElement("span", { className: "download-state", text: describeState(torrent.state) }),
  );
  const details = createElement("span", {
    className: "download-details",
    text: `${progressPercent(torrent.progress)}% of ${formatSize(torrent.size)}`,
  });

  item.append(header, createProgressBar(torrent.progress), details);
  if (torrent.progress >= 1) {
    item.append(createSubtitleControls(torrent.hash));
  }
  return item;
}

function createProgressBar(progress) {
  const percent = progressPercent(progress);
  const bar = createElement("div", { className: "progress" });
  bar.setAttribute("role", "progressbar");
  bar.setAttribute("aria-valuemin", "0");
  bar.setAttribute("aria-valuemax", "100");
  bar.setAttribute("aria-valuenow", String(percent));
  const fill = createElement("div", { className: "progress-fill" });
  fill.style.width = `${percent}%`;
  bar.append(fill);
  return bar;
}

// ---------- Subtitles ----------

function createSubtitleControls(torrentHash) {
  const controls = createElement("div", { className: "action" });
  const button = createButton("Get subtitles", "secondary");
  button.disabled = subtitleRequestsInFlight.has(torrentHash);
  button.addEventListener("click", () => fetchSubtitles(torrentHash));

  const message = createElement("span", { className: "status" });
  const savedMessage = subtitleMessages.get(torrentHash);
  if (savedMessage) {
    setStatus(message, savedMessage.text, savedMessage.isError);
  }

  controls.append(button, message);
  return controls;
}

async function fetchSubtitles(torrentHash) {
  subtitleRequestsInFlight.add(torrentHash);
  showSubtitleMessage(torrentHash, "Looking for subtitles…");
  try {
    const result = await apiRequest(`api/downloads/${encodeURIComponent(torrentHash)}/subtitles`, {
      method: "POST",
    });
    subtitleRequestsInFlight.delete(torrentHash);
    showSubtitleMessage(torrentHash, describeSubtitleResult(result));
  } catch (error) {
    subtitleRequestsInFlight.delete(torrentHash);
    showSubtitleMessage(torrentHash, error.message, true);
  }
}

function describeSubtitleResult(result) {
  if (result.status === "already_present") {
    return "Already has English subtitles";
  }
  return `Subtitle saved: ${result.subtitle_file}`;
}

function showSubtitleMessage(torrentHash, text, isError = false) {
  subtitleMessages.set(torrentHash, { text, isError });
  // The list may have been re-rendered since the click, so look the item up again.
  const item = [...elements.downloadsList.children].find((child) => child.dataset.hash === torrentHash);
  item?.querySelector(".action")?.replaceWith(createSubtitleControls(torrentHash));
}

// ---------- Start ----------

function startDownloadsRefresh() {
  refreshDownloads();
  setInterval(() => {
    if (!document.hidden) {
      refreshDownloads();
    }
  }, DOWNLOADS_REFRESH_MS);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      refreshDownloads();
    }
  });
}

elements.searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = elements.searchQuery.value.trim();
  if (query) {
    searchReleases(query);
  }
});
elements.showMoreButton.addEventListener("click", showMoreResults);
startDownloadsRefresh();
