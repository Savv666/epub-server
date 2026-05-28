(async function () {
  var slug = new URLSearchParams(location.search).get("slug");
  var el = document.getElementById("novelDetail");

  function showError(message) {
    if (el) {
      el.innerHTML = '<div class="empty-state"><h2>Could not load novel</h2><p>' + escapeHtml(message) + '</p></div>';
    }
  }

  if (!el) {
    return;
  }

  try {
    var library = await (await fetch("library.json?v=" + Date.now(), { cache: "no-store" })).json();
    var history = await (await fetch("build-history.json?v=" + Date.now(), { cache: "no-store" })).json().catch(function () { return []; });
    var novel = (library || []).find(function (item) { return item.slug === slug; });

    if (!novel) {
      showError("Novel not found.");
      return;
    }

    var downloads = getDownloads(novel);
    var highestChapter = downloads.reduce(function (max, item) {
      return Math.max(max, Number(item.end || item.start || 0));
    }, Number(novel.last_chapter_number || novel.chapters || 0));
    var lastBuild = (history || []).filter(function (item) { return item.novel_slug === slug; }).slice(-1)[0] || {};
    var title = safeText(novel.title || slug, "Untitled Novel");
    var cover = getCoverSrc(novel);
    var status = getNovelStatus(novel);
    var sourceUrl = getLastSuccessfulSourceUrl(novel) || safeText(novel.source_url || "#", "#");
    var nextUrl = safeText(novel.next_url || getPreferredSourceUrl(novel), "").trim();
    var nextChapter = getNextChapterNumber(novel);

    el.innerHTML = ''
      + '<section class="detail-hero-card">'
      + '<div class="detail-cover-panel">'
      + '<img id="detailCover" class="novel-cover detail-cover" src="' + escapeHtml(cover) + '" alt="' + escapeHtml(title) + ' cover" onerror="this.src=\'covers/default.svg\';" title="Click to update cover image">'
      + '<span class="detail-cover-hint">Click cover to replace it</span>'
      + '</div>'
      + '<div class="detail-hero-content">'
      + '<div class="badge-row">'
      + '<span class="site-badge">' + escapeHtml(novel.source_site || novel.site || "Unknown") + '</span>'
      + '<span class="status-badge ' + getStatusClass(status) + '">' + escapeHtml(status) + '</span>'
      + '<span class="small-badge">' + downloads.length + ' EPUBs</span>'
      + '<span class="small-badge">' + (highestChapter || 0) + ' chapters</span>'
      + '</div>'
      + '<h1 class="detail-title">' + escapeHtml(title) + '</h1>'
      + '<p class="detail-subtitle">Manage updates, alternate sources, chapter files, and maintenance actions for this novel.</p>'
      + '<dl class="detail-stats-grid">'
      + '<div><dt>Highest chapter</dt><dd>' + escapeHtml(highestChapter || 0) + '</dd></div>'
      + '<div><dt>Next chapter</dt><dd>' + escapeHtml(nextChapter) + '</dd></div>'
      + '<div><dt>Last built</dt><dd>' + escapeHtml(formatDate(novel.last_updated || lastBuild.created_at || "")) + '</dd></div>'
      + '<div><dt>Last checked</dt><dd>' + escapeHtml(formatDate(novel.last_checked || "")) + '</dd></div>'
      + '</dl>'
      + buildLockedNotice(novel)
      + '<div class="detail-action-row">'
      + '<button id="continueNovelButton" class="button button-primary" type="button">Continue from Chapter ' + escapeHtml(nextChapter) + '</button>'
      + '<button id="alternateSourcesButton" class="button button-secondary" type="button">Alternate sources</button>'
      + '<a id="sourceButton" class="button button-secondary" href="' + escapeHtml(sourceUrl) + '" target="_blank" rel="noopener noreferrer">Sources</a>'
      + '<button id="chaptersToggleButton" class="button button-secondary" type="button">Chapters Available</button>'
      + '<button id="combineChunksButton" class="button button-secondary" type="button">Combine chunks</button>'
      + '</div>'
      + '</div>'
      + '</section>'
      + '<section id="chaptersSection" class="detail-section">'
      + '<div class="section-heading-row"><h2>Chapters downloaded</h2><span class="detail-section-count">' + downloads.length + ' files</span></div>'
      + buildDetailDownloadList(novel)
      + '</section>';

    var coverImage = document.getElementById("detailCover");
    if (coverImage) {
      coverImage.addEventListener("click", function () {
        openUpdateCoverPrompt(novel, coverImage.getAttribute("src") || "");
      });
    }

    var continueButton = document.getElementById("continueNovelButton");
    if (continueButton) {
      continueButton.addEventListener("click", function () {
        openIssueComposer(buildContinueIssueUrl(novel, getSetting("default_engine", "Auto"), nextUrl || "PASTE_NEXT_CHAPTER_URL_HERE"));
      });
    }

    document.querySelectorAll("#alternateSourcesButton, .alternate-source-button").forEach(function (button) {
      button.addEventListener("click", function () {
        openAlternateSources(novel);
      });
    });

    var combineButton = document.getElementById("combineChunksButton");
    if (combineButton) {
      combineButton.addEventListener("click", function () {
        openIssueComposer(buildCombineChunksIssueUrl(novel));
      });
    }

    var chaptersButton = document.getElementById("chaptersToggleButton");
    var chaptersSection = document.getElementById("chaptersSection");
    if (chaptersButton && chaptersSection) {
      chaptersButton.addEventListener("click", function () {
        chaptersSection.classList.toggle("is-hidden");
        chaptersButton.textContent = chaptersSection.classList.contains("is-hidden") ? "Show Chapters" : "Hide Chapters";
      });
    }

    document.querySelectorAll(".copy-epub-link-button").forEach(function (button) {
      button.addEventListener("click", function () {
        copyToClipboard(button.getAttribute("data-url") || "", button);
      });
    });

    document.querySelectorAll(".rebuild-epub-button").forEach(function (button) {
      button.addEventListener("click", function () {
        var index = Number(button.getAttribute("data-download-index"));
        var download = downloads[index];
        if (!download) { return; }
        openIssueComposer(buildRebuildEpubIssueUrl(novel, download));
      });
    });

    document.querySelectorAll(".delete-epub-button").forEach(function (button) {
      button.addEventListener("click", function () {
        var index = Number(button.getAttribute("data-download-index"));
        var download = downloads[index];
        if (!download) { return; }
        var confirmed = window.confirm("Delete this EPUB file from the website?\n\n" + (download.label || ("Chapters " + download.start + "-" + download.end)));
        if (confirmed) {
          openIssueComposer(buildDeleteEpubIssueUrl(novel, download));
        }
      });
    });
  } catch (error) {
    console.error(error);
    showError(error.message || "Unknown error");
  }

  function buildDetailDownloadList(novel) {
    var rows = getDownloads(novel);

    if (!rows.length) {
      return '<p class="empty-downloads">No EPUB downloads available yet.</p>';
    }

    return '<div class="download-list detail-download-list">' + rows.map(function (download, index) {
      var label = escapeHtml(download.label || ("Chapters " + download.start + "-" + download.end));
      var relativeUrl = safeText(download.url || "#", "#");
      var absoluteUrl = escapeHtml(absoluteSiteUrl(relativeUrl));
      var meta = [download.mode, formatDate(download.created_at || "")].filter(Boolean).join(" · ");

      return ''
        + '<div class="download-row enhanced-download-row detail-download-row" data-download-index="' + index + '">'
        + '<div class="download-main">'
        + '<span class="download-label">' + label + '</span>'
        + '<span class="download-meta">' + escapeHtml(meta) + '</span>'
        + '<span class="download-action">Ready</span>'
        + '</div>'
        + '<div class="download-actions">'
        + '<a class="mini-button gold-mini-button" href="' + escapeHtml(relativeUrl) + '" download>Download</a>'
        + '<button class="mini-button gold-mini-button copy-epub-link-button" type="button" data-url="' + absoluteUrl + '">Copy</button>'
        + '<button class="mini-button danger-mini-button rebuild-epub-button" type="button" data-download-index="' + index + '">Rebuild</button>'
        + '<button class="mini-button danger-mini-button delete-epub-button" type="button" data-download-index="' + index + '">Delete</button>'
        + '</div>'
        + '</div>';
    }).join("") + '</div>';
  }
})();
