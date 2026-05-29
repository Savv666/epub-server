var LIBRARY_URL = "library.json";
var ALTERNATE_SOURCES_URL = "alternate-sources.json";
var SITE_SETTINGS_URL = "site-settings.json";
var DELETE_NOVEL_TEMPLATE = "delete-novel.yml";
var UPDATE_COVER_TEMPLATE = "update-cover-image.yml";

var allNovels = [];
var alternateSources = [];
var activeAlternateNovel = null;

var siteSettings = {
  default_engine: "Auto",
  default_new_novel_chapters: 10,
  default_new_novel_batches: 1,
  default_continue_chapters: 100,
  default_continue_batches: 1,
  latest_epubs_count: 3
};

var COVER_OVERRIDES_KEY = "coverOverrides";

function getNovelCoverKey(novel) {
  var title = safeText(novel && novel.title, "").trim().toLowerCase();
  var sourceUrl = safeText(novel && novel.source_url, "").trim().toLowerCase();
  return sourceUrl || title;
}

function getCoverOverrides() {
  try {
    var raw = window.localStorage.getItem(COVER_OVERRIDES_KEY);

    if (!raw) {
      return {};
    }

    var parsed = JSON.parse(raw);

    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }

    return parsed;
  } catch (error) {
    return {};
  }
}

function saveCoverOverride(novel, coverUrl) {
  var key = getNovelCoverKey(novel);

  if (!key) {
    return;
  }

  var overrides = getCoverOverrides();
  overrides[key] = safeText(coverUrl, "").trim();

  try {
    window.localStorage.setItem(COVER_OVERRIDES_KEY, JSON.stringify(overrides));
  } catch (error) {
    console.warn("Could not save cover override", error);
  }
}

function getEffectiveCover(novel) {
  return safeText(novel && novel.cover, "covers/default.svg").trim() || "covers/default.svg";
}

function getCoverVersion(novel) {
  return encodeURIComponent(
    safeText(
      novel && (novel.last_updated || novel.created_at || novel.cover),
      Date.now()
    )
  );
}

function getCoverSrc(novel) {
  var cover = getEffectiveCover(novel);
  var version = getCoverVersion(novel);

  if (cover.indexOf("?") === -1) {
    return cover + "?v=" + version;
  }

  return cover + "&v=" + version;
}

function getGitHubRepoUrl() {
  var host = window.location.hostname;
  var pathParts = window.location.pathname.split("/").filter(Boolean);

  if (host.endsWith(".github.io") && pathParts.length > 0) {
    var owner = host.replace(".github.io", "");
    var repo = pathParts[0];
    return "https://github.com/" + owner + "/" + repo;
  }

  return "https://github.com/Sav666/epub-server";
}

function safeText(value, fallback) {
  if (fallback === undefined) {
    fallback = "";
  }

  if (value === null || value === undefined) {
    return fallback;
  }

  return String(value);
}

function getSetting(name, fallback) {
  if (siteSettings && Object.prototype.hasOwnProperty.call(siteSettings, name)) {
    return siteSettings[name];
  }

  return fallback;
}

function absoluteSiteUrl(relativeUrl) {
  var value = safeText(relativeUrl, "").trim();

  if (!value) {
    return "";
  }

  try {
    return new URL(value, window.location.href).href;
  } catch (error) {
    return value;
  }
}

function copyToClipboard(text, button) {
  var value = safeText(text, "").trim();

  if (!value) {
    alert("No link found to copy.");
    return;
  }

  function markCopied() {
    if (!button) {
      return;
    }

    var oldText = button.textContent;
    button.classList.add("copied");
    button.textContent = "Copied";

    window.setTimeout(function () {
      button.classList.remove("copied");
      button.textContent = oldText;
    }, 1400);
  }

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(value).then(markCopied).catch(function () {
      fallbackCopy(value);
      markCopied();
    });
  } else {
    fallbackCopy(value);
    markCopied();
  }
}

function fallbackCopy(text) {
  var textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "-9999px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  try {
    document.execCommand("copy");
  } finally {
    document.body.removeChild(textarea);
  }
}

function escapeHtml(value) {
  return safeText(value)
    .split("&").join("&amp;")
    .split("<").join("&lt;")
    .split(">").join("&gt;")
    .split('"').join("&quot;")
    .split("'").join("&#039;");
}

function formatDate(value) {
  if (!value) {
    return "Not recorded";
  }

  try {
    var date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric"
    });
  } catch (error) {
    return value;
  }
}

function getDownloads(novel) {
  if (!novel || !Array.isArray(novel.downloads)) {
    return [];
  }

  return novel.downloads.slice().sort(function (a, b) {
    var startA = Number(a.start || 0);
    var startB = Number(b.start || 0);
    return startA - startB;
  });
}

function getLastChapterNumber(novel) {
  if (novel && novel.last_chapter_number) {
    return Number(novel.last_chapter_number);
  }

  var downloads = getDownloads(novel);

  if (downloads.length === 0) {
    return Number((novel && novel.chapters) || 0);
  }

  var last = 0;

  downloads.forEach(function (download) {
    var end = Number(download.end || 0);

    if (end > last) {
      last = end;
    }
  });

  return last;
}

function getNextChapterNumber(novel) {
  var lastChapter = getLastChapterNumber(novel);

  if (!lastChapter || Number.isNaN(lastChapter)) {
    return 1;
  }

  return lastChapter + 1;
}

function getNovelStatus(novel) {
  var status = safeText(novel && novel.status, "").trim();

  if (status) {
    return status;
  }

  if (getDownloads(novel).length > 0) {
    return "Built";
  }

  return "Unknown";
}

function getStatusClass(status) {
  var lower = safeText(status).toLowerCase();

  if (lower.indexOf("complete") !== -1) {
    return "status-complete";
  }

  if (lower.indexOf("partial") !== -1 || lower.indexOf("locked") !== -1) {
    return "status-partial";
  }

  if (lower.indexOf("fail") !== -1) {
    return "status-failed";
  }

  if (lower.indexOf("test") !== -1) {
    return "status-test";
  }

  return "status-built";
}

function buildIssueUrl(title, body, template) {
  var repoUrl = getGitHubRepoUrl();

  var params = new URLSearchParams({
    title: title,
    body: body || "",
    labels: "epub-manager"
  });

  if (template) {
    params.set("template", template);
  }

  return repoUrl + "/issues/new?" + params.toString();
}

function buildDeleteNovelIssueUrl(novel) {
  var novelTitle = safeText(novel && novel.title, "").trim() || "Unknown title";
  var issueTitle = "[EPUB MANAGER] Delete " + novelTitle;
  var issueBody = buildDeleteIssueBody(novel);

  var repoUrl = getGitHubRepoUrl();

  var params = new URLSearchParams({
    template: DELETE_NOVEL_TEMPLATE,
    title: issueTitle,
    labels: "epub-manager,delete-novel",
    body: issueBody
  });

  return repoUrl + "/issues/new?" + params.toString();
}

function buildUpdateCoverIssueUrl(novel, coverUrl) {
  var novelTitle = safeText(novel && novel.title, "Untitled Novel");
  var repoUrl = getGitHubRepoUrl();

  var issueTitle = "[EPUB MANAGER] Update Cover " + novelTitle;

  var issueBody = [
    "### Request mode",
    "",
    "Update Cover Image",
    "",
    "### Update Cover Novel Name",
    "",
    novelTitle,
    "",
    "### Update Cover Image URL",
    "",
    coverUrl
  ].join("\n");

  var params = new URLSearchParams({
    template: UPDATE_COVER_TEMPLATE,
    title: issueTitle,
    labels: "epub-manager",
    update_cover_novel_name: novelTitle,
    update_cover_image_url: coverUrl,
    body: issueBody
  });

  return repoUrl + "/issues/new?" + params.toString();
}

function openIssueComposer(issueUrl) {
  var popup = window.open(issueUrl, "_blank");

  if (popup) {
    return;
  }

  window.location.href = issueUrl;
}

function openUpdateCoverPrompt(novel, currentSrc) {
  if (!novel) {
    alert("Could not find this novel in the current page data.");
    return;
  }

  var message = [
    "Paste a new cover image URL.",
    "",
    "After clicking OK, a pre-filled GitHub issue will open.",
    "Submit the issue to permanently update the website cover.",
    "",
    "Current cover:",
    currentSrc || getEffectiveCover(novel)
  ].join("\n");

  var enteredSrc = window.prompt(message, "");

  if (enteredSrc === null) {
    return;
  }

  enteredSrc = safeText(enteredSrc, "").trim();

  if (!enteredSrc) {
    return;
  }

  openIssueComposer(buildUpdateCoverIssueUrl(novel, enteredSrc));
}

function buildNewNovelIssueBody(novelLink, novelName, startingChapter, chaptersToDownload, batchSize, engine) {
  return [
    "### Request mode",
    "",
    "New Novel",
    "",
    "### Engine",
    "",
    engine || "Auto",
    "",
    "### Chapters to download",
    "",
    String(chaptersToDownload || 10),
    "",
    "### Batch size",
    "",
    String(batchSize || 1),
    "",
    "### Novel 1 Link",
    "",
    novelLink,
    "",
    "### Novel 1 Name",
    "",
    novelName,
    "",
    "### Novel 1 Starting Chapter",
    "",
    String(startingChapter || 1)
  ].join("\n");
}

function buildScheduleUpdateIssueUrl(startAtIso, repeatDays) {
  var issueTitle = "[EPUB MANAGER] Schedule Update All";
  var issueBody = [
    "### Request mode", "", "Schedule Update All", "",
    "### Start at (UTC)", "", startAtIso, "",
    "### Repeat days", "", String(repeatDays || 1), "",
    "### Engine", "", getSetting("default_engine", "Auto")
  ].join("\n");
  return buildIssueUrl(issueTitle, issueBody, "epub-manager.yml");
}

function buildUpdateAllIssueUrl() {
  var issueTitle = "[EPUB MANAGER] Update All Existing Novels";

  var issueBody = [
    "### Request mode",
    "",
    "Update All Existing Novels",
    "",
    "### Engine",
    "",
    getSetting("default_engine", "Auto"),
    "",
    "### Chapters to download",
    "",
    String(getSetting("default_continue_chapters", 100)),
    "",
    "### Batch size",
    "",
    String(getSetting("default_continue_batches", 1))
  ].join("\n");

  return buildIssueUrl(issueTitle, issueBody);
}

function buildRebuildEpubIssueUrl(novel, download) {
  var novelTitle = safeText(novel && novel.title, "Untitled Novel");
  var start = Number(download && download.start) || 1;
  var end = Number(download && download.end) || start;
  var chapters = Math.max(1, end - start + 1);
  var sourceUrl = getPreferredSourceUrl(novel, start);

  var issueTitle = "[EPUB MANAGER] Rebuild " + novelTitle + " chapters " + start + "-" + end;

  var issueBody = [
    "### Request mode",
    "",
    "Rebuild EPUB",
    "",
    "### Engine",
    "",
    getSetting("default_engine", "Auto"),
    "",
    "### Chapters to download",
    "",
    String(chapters),
    "",
    "### Batch size",
    "",
    "1",
    "",
    "### Rebuild Novel Name",
    "",
    novelTitle,
    "",
    "### Rebuild Source URL",
    "",
    sourceUrl || safeText(novel && novel.source_url, ""),
    "",
    "### Rebuild Starting Chapter",
    "",
    String(start),
    "",
    "### Rebuild Ending Chapter",
    "",
    String(end),
    "",
    "### Existing EPUB URL",
    "",
    safeText(download && download.url, "")
  ].join("\n");

  return buildIssueUrl(issueTitle, issueBody);
}

function buildDeleteEpubIssueUrl(novel, download) {
  var novelTitle = safeText(novel && novel.title, "Untitled Novel");
  var start = Number(download && download.start) || 0;
  var end = Number(download && download.end) || start;
  var issueTitle = "[EPUB MANAGER] Delete EPUB " + novelTitle + " chapters " + start + "-" + end;

  var issueBody = [
    "### Request mode",
    "",
    "Delete EPUB",
    "",
    "### Delete EPUB Novel Name",
    "",
    novelTitle,
    "",
    "### Delete EPUB Start Chapter",
    "",
    String(start),
    "",
    "### Delete EPUB End Chapter",
    "",
    String(end),
    "",
    "### Delete EPUB URL",
    "",
    safeText(download && download.url, "")
  ].join("\n");

  return buildIssueUrl(issueTitle, issueBody);
}

function buildCombineChunksIssueUrl(novel) {
  var novelTitle = safeText(novel && novel.title, "Untitled Novel");
  var slug = safeText(novel && novel.slug, "");
  var downloads = getDownloads(novel);
  var start = downloads.length ? Number(downloads[0].start || 1) : 1;
  var end = downloads.length ? downloads.reduce(function (max, download) {
    return Math.max(max, Number(download.end || download.start || 0));
  }, start) : getLastChapterNumber(novel);
  var files = downloads.map(function (download) {
    return safeText(download.url, "").replace(/^epubs\//, "");
  }).filter(Boolean).join("\n");

  var issueTitle = "[EPUB MANAGER] Combine EPUB Chunks " + novelTitle;
  var issueBody = [
    "### Request mode",
    "",
    "Combine EPUB Chunks",
    "",
    "### Novel name",
    "",
    novelTitle,
    "",
    "### Novel slug",
    "",
    slug,
    "",
    "### Selected EPUB files",
    "",
    files || "PASTE_EPUB_FILENAMES_HERE",
    "",
    "### Start chapter",
    "",
    String(start || 1),
    "",
    "### End chapter",
    "",
    String(end || start || 1),
    "",
    "### Overwrite combined file",
    "",
    "No",
    "",
    "### Notes",
    "",
    "Combine all separately downloaded EPUB files for this novel into one EPUB."
  ].join("\n");

  var repoUrl = getGitHubRepoUrl();
  var params = new URLSearchParams({
    template: "combine-epub-chunks.yml",
    title: issueTitle,
    labels: "epub-manager",
    novel_name: novelTitle,
    novel_slug: slug,
    selected_files: files,
    start_chapter: String(start || 1),
    end_chapter: String(end || start || 1),
    overwrite: "No",
    body: issueBody
  });

  return repoUrl + "/issues/new?" + params.toString();
}

function normaliseEngineChoice(choice) {
  var value = safeText(choice, "1").trim().toLowerCase();

  if (value === "1" || value === "auto") {
    return "Auto";
  }

  if (value === "2" || value === "generic" || value === "generic scraper") {
    return "Generic Scraper";
  }

  if (value === "3" || value === "fanficfare" || value === "fan fic fare") {
    return "FanFicFare";
  }

  if (value === "4" || value === "freewebnovel" || value === "free web novel") {
    return "FreeWebNovel";
  }

  if (value === "5" || value === "pattern" || value === "pattern scraper") {
    return "Pattern Scraper";
  }

  return "Auto";
}

function askEngineForContinue() {
  var choice = window.prompt(
    "Choose engine for this update:\n\n1 = Auto\n2 = Generic Scraper\n3 = FanFicFare\n4 = FreeWebNovel\n5 = Pattern Scraper\n\nDefault is 1.",
    "1"
  );

  if (choice === null) {
    return null;
  }

  return normaliseEngineChoice(choice);
}

function askSourceForContinue(novel) {
  var storedNextUrl = safeText(getPreferredSourceUrl(novel), "").trim();
  var nextChapter = getNextChapterNumber(novel);

  var message = [
    "Optional: paste a different source/chapter URL for this update.",
    "",
    "Use this if the current source failed and you want to continue from another website.",
    "",
    "Next chapter expected: " + nextChapter,
    "",
    "Leave blank to use the saved URL:",
    storedNextUrl || "No saved URL found"
  ].join("\n");

  var enteredUrl = window.prompt(message, "");

  if (enteredUrl === null) {
    return null;
  }

  enteredUrl = safeText(enteredUrl, "").trim();

  if (enteredUrl) {
    return enteredUrl;
  }

  return storedNextUrl || "PASTE_NEXT_CHAPTER_URL_HERE";
}

function getLastSuccessfulSourceUrl(novel) {
  if (!novel) {
    return "";
  }

  return safeText(
    novel.last_successful_source_url ||
    novel.last_chapter_url ||
    novel.preferred_source_url ||
    novel.next_url ||
    novel.source_url,
    ""
  ).trim();
}

function getPreferredSourceUrl(novel, startChapter) {
  if (!novel) {
    return "";
  }

  var history = Array.isArray(novel.source_history) ? novel.source_history.slice() : [];

  if (history.length) {
    history.sort(function (a, b) {
      var timeA = new Date(safeText(a.updated_at, "1970-01-01")).getTime() || 0;
      var timeB = new Date(safeText(b.updated_at, "1970-01-01")).getTime() || 0;
      return timeB - timeA;
    });

    for (var i = 0; i < history.length; i += 1) {
      var item = history[i];
      var url = safeText(item.url, "").trim();

      if (url) {
        return url;
      }
    }
  }

  return safeText(
    novel.preferred_source_url ||
    novel.last_successful_source_url ||
    novel.last_chapter_url ||
    novel.next_url ||
    novel.source_url,
    ""
  ).trim();
}

function buildDeleteIssueBody(novel) {
  var title = safeText(novel && novel.title, "").trim();
  var sourceUrl = safeText(novel && (novel.preferred_source_url || novel.source_url), "").trim();
  var status = getNovelStatus(novel);
  var lastChapter = getLastChapterNumber(novel);
  var downloads = getDownloads(novel);

  return [
    "### Request mode",
    "",
    "Delete Novel",
    "",
    "### Engine",
    "",
    "Generic Scraper",
    "",
    "### Chapters to download",
    "",
    "10",
    "",
    "### Batch size",
    "",
    "1",
    "",
    "### Delete Novel Name",
    "",
    title || "Unknown title",
    "",
    "### Delete Novel Source URL",
    "",
    sourceUrl || "Not recorded",
    "",
    "### Delete Novel Last Chapter",
    "",
    String(lastChapter || "Not recorded"),
    "",
    "### Delete Novel Status",
    "",
    status,
    "",
    "### Delete Novel EPUB Count",
    "",
    String(downloads.length),
    "",
    "### Delete EPUB files",
    "",
    "Yes"
  ].join("\n");
}

function buildContinueIssueUrl(novel, engine, sourceUrl) {
  var novelTitle = safeText(novel && novel.title, "Untitled Novel");
  var nextChapter = getNextChapterNumber(novel);
  var selectedEngine = engine || getSetting("default_engine", "Auto");
  var chaptersToDownload = getSetting("default_continue_chapters", 100);
  var batchSize = getSetting("default_continue_batches", 1);

  var issueTitle = "[EPUB MANAGER] Continue " + novelTitle;

  var issueBody = [
    "### Request mode",
    "",
    "Continue Novel",
    "",
    "### Engine",
    "",
    selectedEngine,
    "",
    "### Chapters to download",
    "",
    String(chaptersToDownload),
    "",
    "### Batch size",
    "",
    String(batchSize),
    "",
    "### Novel 1 Link",
    "",
    sourceUrl || "PASTE_NEXT_CHAPTER_URL_HERE",
    "",
    "### Novel 1 Name",
    "",
    novelTitle,
    "",
    "### Novel 1 Starting Chapter",
    "",
    String(nextChapter)
  ].join("\n");

  return buildIssueUrl(issueTitle, issueBody);
}

function buildLockedNotice(novel) {
  if (!novel) {
    return "";
  }

  var lockedChapter = safeText(novel.locked_chapter_number, "").trim();
  var progressState = safeText(novel.progress_state, "").trim();
  var progressReason = safeText(novel.progress_reason, "").trim();
  var lockedReason = safeText(novel.locked_reason, "").trim();
  var status = safeText(novel.status, "").trim();
  var lowerStatus = status.toLowerCase();
  var lowerProgressState = progressState.toLowerCase();
  var hasLockedState =
    Boolean(lockedChapter) ||
    Boolean(lockedReason) ||
    lowerProgressState === "locked" ||
    lowerStatus.indexOf("locked") !== -1;

  if (!hasLockedState && !progressReason) {
    return "";
  }

  var noticeTitle = hasLockedState ? "Locked chapter notice" : "Progress notice";
  var parts = [];

  if (lockedChapter) {
    parts.push("Locked at chapter " + lockedChapter + ".");
  }

  var reason = lockedReason || progressReason;

  if (reason) {
    parts.push(reason);
  }

  if (!parts.length && progressState) {
    parts.push("Progress state: " + progressState + ".");
  }

  var sourceUrl = getPreferredSourceUrl(novel);
  var html = ''
    + '<div class="locked-notice">'
    + '<strong>' + escapeHtml(noticeTitle) + '</strong>'
    + '<span>' + escapeHtml(parts.join(" ") || "This novel may need attention before it can continue.") + '</span>';

  if (sourceUrl) {
    html += ''
      + '<div class="locked-actions">'
      + '<a class="locked-link" href="' + escapeHtml(sourceUrl) + '" target="_blank" rel="noopener noreferrer">Open source</a>'
      + '<button class="locked-link alternate-source-button" type="button">Find alternate source</button>'
      + '</div>';
  }

  html += '</div>';

  return html;
}

function buildNovelCard(novel, index) {
  var title = escapeHtml((novel && novel.title) || "Untitled Novel");
  var site = escapeHtml((novel && novel.site) || "Unknown");
  var cover = escapeHtml(getCoverSrc(novel));
  var detailUrl = "novel.html?slug=" + encodeURIComponent(safeText(novel && novel.slug, ""));
  var status = getNovelStatus(novel);
  var statusClass = getStatusClass(status);
  var lastChapter = getLastChapterNumber(novel);
  var nextChapter = getNextChapterNumber(novel);
  var lastUpdated = escapeHtml(formatDate((novel && (novel.last_updated || novel.created_at)) || ""));
  var downloads = getDownloads(novel);

  return ''
    + '<article class="novel-card" data-novel-index="' + index + '">'
    + '<div class="cover-column">'
    + '<img class="novel-cover" src="' + cover + '" alt="' + title + ' cover" loading="lazy" onerror="this.src=\'covers/default.svg\';" title="Click to update cover image" />'
    + '</div>'
    + '<div class="content-column">'
    + '<div class="top-row">'
    + '<div class="badge-row">'
    + '<span class="site-badge">' + site + '</span>'
    + '<span class="status-badge ' + statusClass + '">' + escapeHtml(status) + '</span>'
    + '<span class="small-badge">' + downloads.length + ' EPUBs</span>'
    + '<span class="small-badge">' + (lastChapter || 0) + ' chapters</span>'
    + '</div>'
    + '</div>'
    + '<h2 class="novel-title">' + title + '</h2>'
    + '<div class="novel-meta">'
    + '<span><strong>Latest chapter:</strong> ' + (lastChapter || 0) + '</span>'
    + '<span><strong>Next:</strong> ' + nextChapter + '</span>'
    + '<span><strong>Updated:</strong> ' + lastUpdated + '</span>'
    + '</div>'
    + '<div class="action-row card-detail-actions">'
    + '<a class="button button-primary" href="' + detailUrl + '">Details</a>'
    + '</div>'
    + '<button class="delete-novel-button" type="button" data-title="' + title + '" aria-label="Delete ' + title + '">×</button>'
    + '</div>'
    + '</article>';
}

function renderSiteFilter(novels) {
  var siteFilter = document.getElementById("siteFilter");

  if (!siteFilter) {
    return;
  }

  var currentValue = siteFilter.value;
  var sites = [];

  novels.forEach(function (novel) {
    var site = safeText(novel.site, "Unknown").trim();

    if (site && sites.indexOf(site) === -1) {
      sites.push(site);
    }
  });

  sites.sort(function (a, b) {
    return a.localeCompare(b);
  });

  siteFilter.innerHTML = '<option value="">All Websites</option>';

  sites.forEach(function (site) {
    var option = document.createElement("option");
    option.value = site;
    option.textContent = site;
    siteFilter.appendChild(option);
  });

  if (sites.indexOf(currentValue) !== -1) {
    siteFilter.value = currentValue;
  }
}

function renderLibraryCount(novels) {
  var libraryCount = document.getElementById("libraryCount");

  if (!libraryCount) {
    return;
  }

  var totalNovels = novels.length;

  var totalDownloads = novels.reduce(function (count, novel) {
    return count + getDownloads(novel).length;
  }, 0);

  var totalChapters = novels.reduce(function (count, novel) {
    return count + (Number(getLastChapterNumber(novel)) || 0);
  }, 0);

  libraryCount.textContent = totalNovels + " novels · " + totalDownloads + " EPUB files · " + totalChapters + " chapters tracked";
}

function filterNovels() {
  var searchBox = document.getElementById("searchBox");
  var siteFilter = document.getElementById("siteFilter");

  var searchValue = searchBox ? searchBox.value.trim().toLowerCase() : "";
  var siteValue = siteFilter ? siteFilter.value.trim() : "";

  return allNovels.filter(function (novel) {
    var title = safeText(novel.title).toLowerCase();
    var site = safeText(novel.site);
    var sourceUrl = safeText(novel.source_url).toLowerCase();

    var matchesSearch =
      !searchValue ||
      title.indexOf(searchValue) !== -1 ||
      site.toLowerCase().indexOf(searchValue) !== -1 ||
      sourceUrl.indexOf(searchValue) !== -1;

    var matchesSite =
      !siteValue ||
      site === siteValue;

    return matchesSearch && matchesSite;
  });
}

function sortNovels(novels) {
  var sortFilter = document.getElementById("sortFilter");
  var sortValue = sortFilter ? sortFilter.value : "updated_desc";

  return novels.slice().sort(function (a, b) {
    var titleA = safeText(a && a.title, "").toLowerCase();
    var titleB = safeText(b && b.title, "").toLowerCase();

    var addedA = new Date(safeText(a && a.created_at, "1970-01-01")).getTime() || 0;
    var addedB = new Date(safeText(b && b.created_at, "1970-01-01")).getTime() || 0;

    var updatedA = new Date(safeText(a && (a.last_updated || a.created_at), "1970-01-01")).getTime() || 0;
    var updatedB = new Date(safeText(b && (b.last_updated || b.created_at), "1970-01-01")).getTime() || 0;

    if (sortValue === "title_asc") {
      return titleA.localeCompare(titleB);
    }

    if (sortValue === "title_desc") {
      return titleB.localeCompare(titleA);
    }

    if (sortValue === "added_asc") {
      return addedA - addedB;
    }

    if (sortValue === "added_desc") {
      return addedB - addedA;
    }

    if (sortValue === "updated_asc") {
      return updatedA - updatedB;
    }

    return updatedB - updatedA;
  });
}

function findNovelFromCard(card, filteredNovels) {
  var indexText = card.getAttribute("data-novel-index");
  var index = Number(indexText);

  if (Number.isNaN(index)) {
    return null;
  }

  return filteredNovels[index] || null;
}

function buildSearchUrl(source, novel) {
  var title = safeText(novel && novel.title, "").trim();
  var nextChapter = getNextChapterNumber(novel);
  var query = title + " chapter " + nextChapter;
  var encodedQuery = encodeURIComponent(query);

  return safeText(source.search_url, "")
    .replace("{query}", encodedQuery)
    .replace("{title}", encodeURIComponent(title))
    .replace("{chapter}", encodeURIComponent(String(nextChapter)));
}

function loadAlternateSources() {
  return fetch(ALTERNATE_SOURCES_URL + "?v=" + Date.now())
    .then(function (response) {
      if (!response.ok) {
        throw new Error("Failed to load alternate-sources.json");
      }

      return response.json();
    })
    .then(function (data) {
      if (!Array.isArray(data)) {
        throw new Error("alternate-sources.json must be an array.");
      }

      alternateSources = data.filter(function (source) {
        return source && source.enabled !== false;
      });

      return alternateSources;
    })
    .catch(function (error) {
      console.error(error);
      alternateSources = [];
      return alternateSources;
    });
}

function openAlternateSources(novel) {
  activeAlternateNovel = novel;

  var modal = document.getElementById("alternateSourceModal");
  var list = document.getElementById("alternateSourceList");
  var subtitle = document.getElementById("alternateSourceSubtitle");

  if (!modal || !list) {
    return;
  }

  var novelTitle = safeText(novel && novel.title, "Untitled Novel");
  var nextChapter = getNextChapterNumber(novel);

  if (subtitle) {
    subtitle.textContent = novelTitle + " — search for chapter " + nextChapter;
  }

  modal.classList.remove("is-hidden");
  list.innerHTML = '<p class="empty-downloads">Loading alternate source list...</p>';

  loadAlternateSources().then(function (sources) {
    if (!sources.length) {
      list.innerHTML = ''
        + '<p class="empty-downloads">'
        + 'No alternate sources found. Add sources in docs/alternate-sources.json.'
        + '</p>';
      return;
    }

    list.innerHTML = sources.map(function (source) {
      var searchUrl = buildSearchUrl(source, novel);
      var name = escapeHtml(source.name || "Unnamed source");
      var engine = escapeHtml(source.engine || "Unknown engine");
      var type = escapeHtml(source.type || "source");

      return ''
        + '<div class="alternate-source-row">'
        + '<div>'
        + '<strong>' + name + '</strong>'
        + '<span>' + type + ' · ' + engine + '</span>'
        + '</div>'
        + '<a class="button button-secondary" href="' + escapeHtml(searchUrl) + '" target="_blank" rel="noopener noreferrer">'
        + 'Search'
        + '</a>'
        + '</div>';
    }).join("");
  });
}

function closeAlternateSources() {
  var modal = document.getElementById("alternateSourceModal");

  if (modal) {
    modal.classList.add("is-hidden");
  }

  activeAlternateNovel = null;
}

function continueWithAlternateUrl() {
  if (!activeAlternateNovel) {
    alert("No novel selected.");
    return;
  }

  var nextChapter = getNextChapterNumber(activeAlternateNovel);

  var sourceUrl = window.prompt(
    "Paste the alternate source chapter URL you selected.\n\nExpected chapter: " + nextChapter,
    ""
  );

  if (sourceUrl === null) {
    return;
  }

  sourceUrl = safeText(sourceUrl, "").trim();

  if (!sourceUrl) {
    alert("Please paste a chapter URL.");
    return;
  }

  var engine = askEngineForContinue();

  if (!engine) {
    return;
  }

  var issueUrl = buildContinueIssueUrl(activeAlternateNovel, engine, sourceUrl);
  openIssueComposer(issueUrl);
}

function getAllDownloadEntries() {
  var entries = [];

  allNovels.forEach(function (novel) {
    getDownloads(novel).forEach(function (download) {
      entries.push({
        novel: novel,
        download: download,
        title: safeText(novel.title, "Untitled Novel"),
        label: safeText(download.label || ("Chapters " + download.start + "-" + download.end), "EPUB"),
        url: safeText(download.url, ""),
        created_at: safeText(download.created_at || novel.last_updated || novel.created_at, "")
      });
    });
  });

  entries.sort(function (a, b) {
    var timeA = new Date(a.created_at || "1970-01-01").getTime() || 0;
    var timeB = new Date(b.created_at || "1970-01-01").getTime() || 0;
    return timeB - timeA;
  });

  return entries;
}

function renderLatestEpubs() {
  var container = document.getElementById("latestEpubs");

  if (!container) {
    return;
  }

  var count = Number(getSetting("latest_epubs_count", 3)) || 3;
  var entries = getAllDownloadEntries().slice(0, count);

  if (!entries.length) {
    container.innerHTML = '<div class="empty-state compact-empty">No EPUB downloads yet.</div>';
    return;
  }

  container.innerHTML = entries.map(function (entry, index) {
    var title = escapeHtml(entry.title);
    var label = escapeHtml(entry.label);
    var url = escapeHtml(entry.url);
    var absoluteUrl = escapeHtml(absoluteSiteUrl(entry.url));
    var created = escapeHtml(formatDate(entry.created_at));
    var coverSrc = escapeHtml(getCoverSrc(entry.novel));

    return ''
      + '<article class="latest-epub-card" data-latest-index="' + index + '">'
      + '<img class="latest-epub-cover" src="' + coverSrc + '" alt="' + title + ' cover" loading="lazy" />'
      + '<div class="latest-epub-overlay">'
      + '<div class="latest-epub-info">'
      + '<strong>' + title + '</strong>'
      + '<span>' + label + ' · ' + created + '</span>'
      + '</div>'
      + '<div class="latest-epub-actions">'
      + '<a class="mini-button gold-mini-button" href="' + url + '" download>Download</a>'
      + '<button class="mini-button copy-epub-link-button" type="button" data-url="' + absoluteUrl + '">Copy Link</button>'
      + '</div>'
      + '</div>'
      + '</article>';
  }).join("");

  container.querySelectorAll(".copy-epub-link-button").forEach(function (button) {
    button.addEventListener("click", function () {
      copyToClipboard(button.getAttribute("data-url") || "", button);
    });
  });
}

function getDownloadFromButton(button, filteredNovels) {
  var card = button.closest(".novel-card");
  var novel = findNovelFromCard(card, filteredNovels);
  var index = Number(button.getAttribute("data-download-index"));

  if (!novel || Number.isNaN(index)) {
    return { novel: null, download: null };
  }

  return { novel: novel, download: getDownloads(novel)[index] || null };
}

function renderLibrary() {
  var library = document.getElementById("library");

  if (!library) {
    return;
  }

  var filteredNovels = sortNovels(filterNovels());

  renderLibraryCount(filteredNovels);
  renderLatestEpubs();

  if (filteredNovels.length === 0) {
    library.innerHTML = ''
      + '<div class="empty-state">'
      + '<h2>No EPUBs found</h2>'
      + '<p>Try changing your search/filter, or create a new EPUB Manager issue.</p>'
      + '</div>';
    return;
  }

  library.innerHTML = filteredNovels.map(function (novel, index) {
    return buildNovelCard(novel, index);
  }).join("");

  var coverImages = library.querySelectorAll(".novel-cover");

  coverImages.forEach(function (image) {
    image.addEventListener("click", function () {
      var card = image.closest(".novel-card");
      var novel = findNovelFromCard(card, filteredNovels);

      if (!novel) {
        alert("Could not find this novel in the current page data.");
        return;
      }

      openUpdateCoverPrompt(novel, image.getAttribute("src") || "");
    });
  });

  var deleteButtons = library.querySelectorAll(".delete-novel-button");

  deleteButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      var title = button.getAttribute("data-title") || "";

      var confirmed = window.confirm(
        "Delete novel from the website and delete its EPUB files?\n\n" + title
      );

      if (!confirmed) {
        return;
      }

      var card = button.closest(".novel-card");
      var novel = findNovelFromCard(card, filteredNovels) || { title: title };
      var issueUrl = buildDeleteNovelIssueUrl(novel);

      openIssueComposer(issueUrl);
    });
  });
}

function showLibraryError(message) {
  var library = document.getElementById("library");

  if (library) {
    library.innerHTML = ''
      + '<div class="empty-state">'
      + '<h2>Could not load library</h2>'
      + '<p>' + escapeHtml(message) + '</p>'
      + '</div>';
  }

  var libraryCount = document.getElementById("libraryCount");

  if (libraryCount) {
    libraryCount.textContent = "Error loading library";
  }
}

function loadSiteSettings() {
  return fetchJsonWithFallback([SITE_SETTINGS_URL, "./" + SITE_SETTINGS_URL, "docs/" + SITE_SETTINGS_URL])
    .then(function (data) {
      if (data && typeof data === "object" && !Array.isArray(data)) {
        siteSettings = Object.assign({}, siteSettings, data);
      }
    })
    .catch(function () {
      // Defaults are enough if the settings file is not available.
    });
}

function loadLibrary() {
  var library = document.getElementById("library");

  if (library) {
    library.innerHTML = ''
      + '<div class="empty-state">'
      + '<h2>Loading library...</h2>'
      + '<p>Please wait while the EPUB library is loaded.</p>'
      + '</div>';
  }

  fetchJsonWithFallback([LIBRARY_URL, "./" + LIBRARY_URL, "docs/" + LIBRARY_URL])
    .then(function (data) {
      if (!Array.isArray(data)) {
        throw new Error("library.json must contain a JSON array.");
      }

      allNovels = data;
      renderSiteFilter(allNovels);
      renderLibrary();
    })
    .catch(function (error) {
      console.error(error);
      showLibraryError(error.message);
    });
}

function loadSiteLastUpdated() {
  var element = document.getElementById("siteLastUpdated");

  if (!element) {
    return;
  }

  fetchTextWithFallback(["last-updated.txt", "./last-updated.txt", "docs/last-updated.txt"])
    .then(function (text) {
      element.textContent = "Website last updated: " + text.trim();
    })
    .catch(function () {
      element.textContent = "Website last updated: not available yet";
    });
}

function fetchJsonWithFallback(urls) {
  return fetchWithFallback(urls).then(function (response) {
    return response.json();
  });
}

function fetchTextWithFallback(urls) {
  return fetchWithFallback(urls).then(function (response) {
    return response.text();
  });
}

function fetchWithFallback(urls) {
  var queue = (Array.isArray(urls) ? urls : []).map(function (url) {
    return safeText(url, "").trim();
  }).filter(Boolean);
  var cacheBuster = "?v=" + Date.now();

  function attempt(index, lastError) {
    if (index >= queue.length) {
      throw lastError || new Error("All fetch attempts failed.");
    }

    var baseUrl = queue[index];
    var url = baseUrl + (baseUrl.indexOf("?") === -1 ? cacheBuster : ("&v=" + Date.now()));

    return fetch(url, { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error(baseUrl + " returned " + response.status);
        }
        return response;
      })
      .catch(function (error) {
        return attempt(index + 1, error);
      });
  }

  return attempt(0);
}

function setupAddNovelForm() {
  var openButton = document.getElementById("openAddNovelForm");
  var closeButton = document.getElementById("closeAddNovelForm");
  var form = document.getElementById("addNovelForm");

  if (!openButton || !closeButton || !form) {
    return;
  }

  openButton.addEventListener("click", function () {
    form.classList.toggle("is-hidden");
  });

  closeButton.addEventListener("click", function () {
    form.classList.add("is-hidden");
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();

    var novelLinkInput = document.getElementById("newNovelLink");
    var novelNameInput = document.getElementById("newNovelName");
    var novelStartInput = document.getElementById("newNovelStart");
    var novelChaptersInput = document.getElementById("newNovelChapters");
    var novelBatchesInput = document.getElementById("newNovelBatches");
    var novelEngineInput = document.getElementById("newNovelEngine");

    var novelLink = safeText(novelLinkInput ? novelLinkInput.value : "").trim();
    var novelName = safeText(novelNameInput ? novelNameInput.value : "").trim();
    var startingChapter = safeText(novelStartInput ? novelStartInput.value : "1").trim();
    var chaptersToDownload = safeText(novelChaptersInput ? novelChaptersInput.value : String(getSetting("default_new_novel_chapters", 10))).trim();
    var batchSize = safeText(novelBatchesInput ? novelBatchesInput.value : String(getSetting("default_new_novel_batches", 1))).trim();
    var engine = safeText(novelEngineInput ? novelEngineInput.value : getSetting("default_engine", "Auto")).trim() || getSetting("default_engine", "Auto");

    if (!novelLink || !novelName) {
      alert("Please enter both Novel link and Novel name.");
      return;
    }

    var issueTitle = "[EPUB MANAGER] " + novelName;

    var issueBody = buildNewNovelIssueBody(
      novelLink,
      novelName,
      startingChapter,
      chaptersToDownload,
      batchSize,
      engine
    );

    var issueUrl = buildIssueUrl(issueTitle, issueBody);

    openIssueComposer(issueUrl);
  });
}

function setupAlternateSourceModal() {
  var closeButton = document.getElementById("closeAlternateSourceModal");
  var cancelButton = document.getElementById("cancelAlternateSources");
  var continueButton = document.getElementById("continueWithAlternateUrl");
  var modal = document.getElementById("alternateSourceModal");

  if (closeButton) {
    closeButton.addEventListener("click", closeAlternateSources);
  }

  if (cancelButton) {
    cancelButton.addEventListener("click", closeAlternateSources);
  }

  if (continueButton) {
    continueButton.addEventListener("click", continueWithAlternateUrl);
  }

  if (modal) {
    modal.addEventListener("click", function (event) {
      if (event.target === modal) {
        closeAlternateSources();
      }
    });
  }
}

function setupEvents() {
  var searchBox = document.getElementById("searchBox");
  var siteFilter = document.getElementById("siteFilter");
  var sortFilter = document.getElementById("sortFilter");
  var updateAllButton = document.getElementById("updateAllNovelsButton");

  if (searchBox) {
    searchBox.addEventListener("input", renderLibrary);
  }

  if (siteFilter) {
    siteFilter.addEventListener("change", renderLibrary);
  }

  if (sortFilter) {
    sortFilter.addEventListener("change", renderLibrary);
  }

  if (updateAllButton) {
    updateAllButton.addEventListener("click", function () {
      var date = window.prompt("Start date (UTC) YYYY-MM-DD", new Date().toISOString().slice(0,10));
      if (date === null) { return; }
      var time = window.prompt("Start time (UTC) HH:MM", "02:00");
      if (time === null) { return; }
      var repeat = window.prompt("Repeat every days: 1, 7, 14, 21, 30", "1");
      if (repeat === null) { return; }
      var repeatDays = Number(repeat);
      if ([1,7,14,21,30].indexOf(repeatDays) === -1) { repeatDays = 1; }
      var startAt = (String(date).trim() || new Date().toISOString().slice(0,10)) + "T" + ((String(time).trim() || "02:00") + ":00Z");
      openIssueComposer(buildScheduleUpdateIssueUrl(startAt, repeatDays));
    });
  }

  setupAddNovelForm();
  setupAlternateSourceModal();
}

document.addEventListener("DOMContentLoaded", function () {
  loadSiteSettings().then(function () {
    setupEvents();
    loadLibrary();
    loadSiteLastUpdated();
  });
});
