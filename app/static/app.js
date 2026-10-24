"use strict";

// Text from indexers and qBittorrent is untrusted: it is only ever set through
// textContent (or append with a string), never as HTML.

const RESULTS_PAGE_SIZE = 15;
const DOWNLOADS_REFRESH_MS = 5000;
const KINOARR_TAG = "kinoarr";
const SIZE_UNITS = ["B", "KB", "MB", "GB", "TB"];
const BYTES_PER_UNIT = 1024;
const SAFE_LINK_PROTOCOLS = ["http:", "https:"];
const MISSING_VALUE = "–";
const UNKNOWN_LABEL = "Unknown";

// One row of filter buttons per entry. `order` lists the values in display order
// (null = not named in the title); without it, values with the most results come first.
const FILTERS = [
  { key: "indexer", label: "Indexer" },
  { key: "resolution", label: "Resolution", order: ["2160p", "1080p", "720p", "SD", null] },
  { key: "video_codec", label: "Codec", order: ["H.265", "H.264", "AV1", "XviD/DivX", null] },
];

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
  resultsSection: document.getElementById("results-section"),
  resultFilters: document.getElementById("result-filters"),
  resultsStatus: document.getElementById("results-status"),
  resultsTable: document.getElementById("results-table"),
  resultsBody: document.getElementById("results-body"),
  showMoreButton: document.getElementById("show-more"),
  downloadsStatus: document.getElementById("downloads-status"),
  downloadsList: document.getElementById("downloads-list"),
  appVersion: document.getElementById("app-version"),
};

let latestSearchId = 0;
let allResults = []; // the last search, most seeders first
let shownResultsCount = 0;
// Filter key -> chosen value; a missing key means "All". Kept across searches during the visit.
const selectedValues = new Map();
let downloadsRefreshInFlight = false;
let downloadsRefreshPending = false;
// Downloads already on screen once, so only new ones fade in.
const knownDownloadHashes = new Set();
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

function formatQuality(result) {
  const parts = [result.resolution, result.video_codec].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : MISSING_VALUE;
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

function plural(count, word) {
  return count === 1 ? word : `${word}s`;
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

// kind: "info", "busy" (shows a spinner), "success" or "error".
function setStatus(element, text, kind = "info") {
  element.textContent = text;
  element.dataset.kind = kind;
}

// ---------- Search ----------

async function searchReleases(query) {
  latestSearchId += 1;
  const searchId = latestSearchId;
  clearResults();
  elements.resultsSection.hidden = false;
  setStatus(elements.resultsStatus, "Searching…", "busy");
  try {
    const results = await apiRequest(`api/search?${new URLSearchParams({ query })}`);
    if (searchId === latestSearchId) {
      renderResults(results);
    }
  } catch (error) {
    if (searchId === latestSearchId) {
      setStatus(elements.resultsStatus, error.message, "error");
    }
  }
}

function clearResults() {
  allResults = [];
  elements.resultFilters.hidden = true;
  elements.resultsBody.replaceChildren();
  elements.resultsTable.hidden = true;
  elements.showMoreButton.hidden = true;
}

function renderResults(results) {
  allResults = results;
  forgetSelectionsMissingFrom(results);
  renderFilters();
  showFirstPage();
}

// ---------- Filters ----------

function forgetSelectionsMissingFrom(results) {
  for (const [key, value] of selectedValues) {
    if (!results.some((result) => result[key] === value)) {
      selectedValues.delete(key);
    }
  }
}

function countValues(results, filter) {
  const counts = new Map();
  for (const result of results) {
    const value = result[filter.key];
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  const entries = [...counts.entries()];
  if (filter.order) {
    return entries.sort(([valueA], [valueB]) => filter.order.indexOf(valueA) - filter.order.indexOf(valueB));
  }
  return entries.sort(([valueA, countA], [valueB, countB]) => countB - countA || valueA.localeCompare(valueB));
}

function filteredResults() {
  return allResults.filter((result) =>
    [...selectedValues].every(([key, value]) => result[key] === value),
  );
}

function renderFilters() {
  const rows = FILTERS.map(createFilterRow).filter((row) => row !== null);
  elements.resultFilters.replaceChildren(...rows);
  elements.resultFilters.hidden = rows.length === 0;
}

function createFilterRow(filter) {
  const valueCounts = countValues(allResults, filter);
  if (valueCounts.length < 2) {
    return null;
  }
  const row = createElement("div", { className: "filter-row" });
  row.setAttribute("role", "group");
  row.setAttribute("aria-label", `Filter by ${filter.label.toLowerCase()}`);

  const isAllSelected = !selectedValues.has(filter.key);
  row.append(
    createElement("span", { className: "filter-label", text: filter.label }),
    createFilterButton("All", allResults.length, isAllSelected, () => clearFilter(filter.key)),
    ...valueCounts.map(([value, count]) =>
      createFilterButton(
        value ?? UNKNOWN_LABEL,
        count,
        !isAllSelected && selectedValues.get(filter.key) === value,
        () => selectFilterValue(filter.key, value),
      ),
    ),
  );
  return row;
}

function createFilterButton(label, count, isSelected, onClick) {
  const button = createButton(undefined, "pill");
  button.setAttribute("aria-pressed", String(isSelected));
  button.append(label, createElement("span", { className: "pill-count", text: String(count) }));
  button.addEventListener("click", onClick);
  return button;
}

// value may be null ("Unknown"), which is a real choice, unlike "All".
function selectFilterValue(key, value) {
  selectedValues.set(key, value);
  applyFilters();
}

function clearFilter(key) {
  selectedValues.delete(key);
  applyFilters();
}

function applyFilters() {
  renderFilters();
  showFirstPage();
}

// ---------- Results table ----------

function showFirstPage() {
  elements.resultsBody.replaceChildren();
  shownResultsCount = 0;
  showNextPage();
}

function showNextPage() {
  const matching = filteredResults();
  const nextResults = matching.slice(shownResultsCount, shownResultsCount + RESULTS_PAGE_SIZE);
  elements.resultsBody.append(...nextResults.map(createResultRow));
  shownResultsCount += nextResults.length;

  const remaining = matching.length - shownResultsCount;
  elements.resultsTable.hidden = matching.length === 0;
  elements.showMoreButton.hidden = remaining === 0;
  elements.showMoreButton.textContent = `Show ${Math.min(remaining, RESULTS_PAGE_SIZE)} more`;
  setStatus(elements.resultsStatus, describeShownResults(matching.length));
}

function describeShownResults(matchingCount) {
  if (allResults.length === 0) {
    return "No results";
  }
  if (matchingCount === 0) {
    return "No results match these filters";
  }
  return `Showing ${shownResultsCount} of ${matchingCount} ${plural(matchingCount, "result")}`;
}

function createResultRow(result) {
  const row = document.createElement("tr");
  row.append(
    createCell("Title", createReleaseTitle(result), "title-cell"),
    createCell("Indexer", result.indexer, "detail-cell"),
    createCell("Quality", formatQuality(result), "detail-cell"),
    createCell("Size", formatSize(result.size), "detail-cell numeric"),
    createCell("Seeders", formatCount(result.seeders), "detail-cell numeric"),
    createCell("Leechers", formatCount(result.leechers), "detail-cell numeric"),
    createCell("Published", formatDate(result.publish_date), "detail-cell"),
    createCell("", createDownloadControls(result.id), "action-cell"),
  );
  return row;
}

function createCell(label, content, className) {
  const cell = createElement("td", { className });
  // Shown as a caption on detail cells when narrow screens turn each row into a card.
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
  setStatus(message, "Adding…", "busy");
  try {
    await postJson("api/downloads", { release_id: releaseId });
    setStatus(message, "Added", "success");
    refreshDownloads();
  } catch (error) {
    button.disabled = false;
    setStatus(message, error.message, "error");
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
    setStatus(elements.downloadsStatus, error.message, "error");
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
  const isFinished = torrent.progress >= 1;
  const item = createElement("li", { className: "download" });
  item.dataset.hash = torrent.hash;
  item.classList.toggle("is-finished", isFinished);
  if (!knownDownloadHashes.has(torrent.hash)) {
    item.classList.add("is-new");
    knownDownloadHashes.add(torrent.hash);
  }

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
  if (isFinished) {
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
    setStatus(message, savedMessage.text, savedMessage.kind);
  }

  controls.append(button, message);
  return controls;
}

async function fetchSubtitles(torrentHash) {
  subtitleRequestsInFlight.add(torrentHash);
  showSubtitleMessage(torrentHash, "Looking for subtitles…", "busy");
  try {
    const result = await apiRequest(`api/downloads/${encodeURIComponent(torrentHash)}/subtitles`, {
      method: "POST",
    });
    subtitleRequestsInFlight.delete(torrentHash);
    showSubtitleMessage(torrentHash, describeSubtitleResult(result), "success");
  } catch (error) {
    subtitleRequestsInFlight.delete(torrentHash);
    showSubtitleMessage(torrentHash, error.message, "error");
  }
}

function describeSubtitleResult(result) {
  if (result.status === "already_present") {
    return "Already has English subtitles";
  }
  if (result.status === "copied_from_torrent") {
    return `Subtitle copied from the torrent: ${result.subtitle_file}`;
  }
  if (result.synced_to_audio) {
    return `Subtitle saved and synced to the audio: ${result.subtitle_file}`;
  }
  return `Subtitle saved: ${result.subtitle_file}`;
}

function showSubtitleMessage(torrentHash, text, kind) {
  subtitleMessages.set(torrentHash, { text, kind });
  // The list may have been re-rendered since the click, so look the item up again.
  const item = [...elements.downloadsList.children].find((child) => child.dataset.hash === torrentHash);
  item?.querySelector(".action")?.replaceWith(createSubtitleControls(torrentHash));
}

// ---------- Start ----------

async function showVersion() {
  try {
    const health = await apiRequest("health");
    elements.appVersion.textContent = `Kinoarr v${health.version}`;
  } catch {
    // Keep the plain "Kinoarr": the downloads list already reports connection problems.
  }
}

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
elements.showMoreButton.addEventListener("click", showNextPage);
startDownloadsRefresh();
showVersion();
