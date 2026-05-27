# Epub Server — Stable Version v2

A GitHub-based EPUB library system that lets you build and manage EPUB files from web novel chapter links using GitHub Issues, GitHub Actions, and GitHub Pages.

This stable v2 build is designed so you can manage the library mostly from the GitHub website without using command line tools.

> **Important legal notice**  
> Only use this project for content you are legally allowed to access and download. Do not use it to bypass paywalls, login systems, locked chapters, CAPTCHA, or website access controls.

---

## What this project does

This project allows you to:

- Submit a novel chapter link through a GitHub Issue form.
- Automatically build EPUB files using GitHub Actions.
- Split novels into chapter batches, such as chapters `1-10`, `11-50`, or `101-200`.
- Display the EPUBs on a GitHub Pages website.
- Copy EPUB download links from the website.
- Rebuild EPUB batches.
- Delete a full novel from the library.
- Delete individual EPUB files.
- Update cover images.
- Generate an RSS feed and direct EPUB links page.

---

## How the system works

```text
GitHub Issue Form
      ↓
GitHub Actions Workflow
      ↓
Python EPUB Builder
      ↓
docs/library.json
      ↓
GitHub Pages Website
```

The main workflow is:

1. You open a new GitHub Issue using the **EPUB Manager** form.
2. GitHub Actions reads the issue.
3. Python scripts build or update the EPUB files.
4. New EPUBs are saved inside `docs/epubs/`.
5. Cover images are saved inside `docs/covers/`.
6. `docs/library.json` is updated.
7. GitHub Pages shows the updated library website.
8. The issue is automatically commented on and closed.

---

## Main folders and files

```text
.github/
  ISSUE_TEMPLATE/
    epub-manager.yml
    update-cover-image.yml
    delete-novel.yml

  workflows/
    epub-manager.yml
    pages.yml

data/
  settings.json

docs/
  index.html
  app.js
  style.css
  library.json
  feed.xml
  epub-links.html
  last-updated.txt
  alternate-sources.json
  site-settings.json
  covers/
  epubs/
  rss-items/

scripts/
  engine_router.py
  epub_from_link.py
  pattern_engine.py
  freewebnovel_engine.py
  fanficfare_engine.py
  generate_rss.py
  validate_library.py
  update_cover.py
  delete_novel.py
  delete_epub.py
  common.py
  constants.py

requirements.txt
README.md
```

---

## Important files explained

### `.github/workflows/epub-manager.yml`

This is the main GitHub Actions workflow. It runs when you create an issue with a title starting with:

```text
[EPUB MANAGER]
```

It can:

- Build new EPUBs.
- Update all existing novels.
- Update cover images.
- Delete novels.
- Delete individual EPUBs.
- Generate RSS and direct EPUB links.
- Validate the library.
- Commit changes back to the repository.

### `.github/workflows/pages.yml`

This workflow helps publish the `docs/` folder as the GitHub Pages website.

### `.github/ISSUE_TEMPLATE/epub-manager.yml`

This creates the **EPUB Manager** issue form.

Use it for:

- New Novel
- Update All Existing Novels

### `.github/ISSUE_TEMPLATE/update-cover-image.yml`

Use this when you only want to change or fix a novel cover image.

### `.github/ISSUE_TEMPLATE/delete-novel.yml`

Use this when you want to remove a full novel from the library.

### `data/settings.json`

This controls the default build limits.

Current stable v2 defaults:

```json
{
  "normal_chapters_per_epub": 10,
  "normal_max_batches": 1,
  "test_chapters_per_epub": 10,
  "test_max_batches": 1,
  "update_all_chapters_per_epub": 10,
  "update_all_max_batches": 1,
  "request_delay_seconds": 1.5,
  "default_engine": "Auto",
  "default_new_novel_chapters": 10,
  "default_new_novel_batches": 1,
  "default_continue_chapters": 100,
  "default_continue_batches": 1,
  "latest_epubs_count": 10,
  "rss_item_limit": 50
}
```

### `docs/`

This is the website folder. GitHub Pages should be pointed to this folder.

Important website files:

- `docs/index.html` — main page
- `docs/app.js` — website behaviour
- `docs/style.css` — website design
- `docs/library.json` — list of novels and EPUB downloads
- `docs/epubs/` — generated EPUB files
- `docs/covers/` — cover images
- `docs/feed.xml` — RSS feed
- `docs/epub-links.html` — direct EPUB links page

### `scripts/engine_router.py`

Chooses which download engine to use.

Available engines:

- Auto
- Generic Scraper
- Pattern Scraper
- FreeWebNovel
- FanFicFare

### `scripts/epub_from_link.py`

Main generic EPUB builder.

### `scripts/pattern_engine.py`

Pattern-based chapter downloader.

### `scripts/freewebnovel_engine.py`

Downloader for FreeWebNovel-style sources.

### `scripts/fanficfare_engine.py`

Downloader using FanFicFare where supported.

### `scripts/generate_rss.py`

Creates:

- `docs/feed.xml`
- `docs/epub-links.html`
- files inside `docs/rss-items/`

### `scripts/validate_library.py`

Checks that `docs/library.json` and linked files are valid.

---

## First-time setup after uploading to GitHub

### 1. Upload all files

Upload the full stable v2 folder contents to your GitHub repository.

The files must be at the repository root, like this:

```text
.github/
data/
docs/
scripts/
requirements.txt
README.md
```

Do not upload the parent folder itself if it creates this structure:

```text
Epub-Server-main/.github/
Epub-Server-main/docs/
```

That is wrong. The `.github`, `docs`, `scripts`, and `data` folders must be directly visible on the main page of the repository.

---

### 2. Enable GitHub Actions

Go to:

```text
Repository → Actions
```

If GitHub asks you to enable workflows, click:

```text
I understand my workflows, go ahead and enable them
```

---

### 3. Enable GitHub Pages

Go to:

```text
Repository → Settings → Pages
```

Set:

```text
Source: Deploy from a branch
Branch: main
Folder: /docs
```

Then click **Save**.

Your website will normally be available at:

```text
https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPOSITORY-NAME/
```

Example:

```text
https://savv666.github.io/Epub-Server/
```

---

### 4. Check workflow permissions

Go to:

```text
Repository → Settings → Actions → General
```

Under **Workflow permissions**, select:

```text
Read and write permissions
```

Also enable:

```text
Allow GitHub Actions to create and approve pull requests
```

Then click **Save**.

This is important because the workflow needs permission to commit EPUB files and update `docs/library.json`.

---

## How to add a new novel

Go to:

```text
Issues → New issue → EPUB Manager → Get started
```

Select:

```text
Request mode: New Novel
Engine: Auto
Chapters to download: 10
Batch size: 1
```

Then fill:

```text
Novel 1 Link: paste the first chapter link
Novel 1 Name: type the novel name
Novel 1 Starting Chapter: 1
```

Submit the issue.

GitHub Actions should start automatically.

---

## How to add multiple novels at once

Use the same **EPUB Manager** form.

Fill:

```text
Novel 1 Link
Novel 1 Name
Novel 1 Starting Chapter

Novel 2 Link
Novel 2 Name
Novel 2 Starting Chapter

Novel 3 Link
Novel 3 Name
Novel 3 Starting Chapter
```

You can add up to the number of novel fields available in the form.

Recommended safe setting:

```text
Chapters to download: 10
Batch size: 1
```

This keeps each run small and reduces the chance of failure.

---

## How to continue existing novels

Go to:

```text
Issues → New issue → EPUB Manager
```

Select:

```text
Request mode: Update All Existing Novels
Engine: Auto
Chapters to download: 10
Batch size: 1
```

Leave the novel link boxes empty.

Submit the issue.

The system will try to continue existing novels from the saved next chapter/source information in `docs/library.json`.

---

## How to update a cover image

Go to:

```text
Issues → New issue → Update Cover Image
```

Fill:

```text
Novel name: exact novel name from the website
Cover image URL: direct image URL ending in .jpg, .jpeg, .png, or .webp
```

Submit the issue.

The workflow will download the image into `docs/covers/` and update `docs/library.json`.

---

## How to delete a full novel

Go to:

```text
Issues → New issue → Delete Novel
```

Fill the novel name.

Choose whether to delete EPUB files as well.

Submit the issue.

This removes the novel from `docs/library.json`. If selected, it also removes its EPUB files from `docs/epubs/`.

---

## How to delete one EPUB file

On the website, open a novel card and use the **Delete EPUB** button next to the EPUB batch.

This should create a GitHub issue request that removes only that selected EPUB batch and updates the library.

---

## How to rebuild one EPUB batch

On the website, open a novel card and use the **Rebuild** button next to the EPUB batch.

This creates a GitHub issue request to rebuild that chapter range.

---

## How to copy an EPUB link

On the website, open a novel card and click the **Copy** button next to an EPUB download.

The direct EPUB link will be copied to your clipboard.

---

## Website features in stable v2

The stable v2 website supports:

- Novel cards with cover images.
- One-column download list inside each novel card.
- Status badges such as complete, partial, failed, test, or built.
- EPUB count badges.
- Source link button.
- Alternate sources button.
- Copy EPUB link button.
- Rebuild EPUB button.
- Delete EPUB button.
- RSS/direct links support.

---

## RSS and direct EPUB links

The workflow generates:

```text
docs/feed.xml
docs/epub-links.html
```

Your RSS feed should be available at:

```text
https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPOSITORY-NAME/feed.xml
```

The direct EPUB links page should be available at:

```text
https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPOSITORY-NAME/epub-links.html
```

---

## Recommended safe settings

For normal use, keep:

```text
Chapters to download: 10
Batch size: 1
Engine: Auto
```

This is slower, but more stable.

After confirming a source works, you can try:

```text
Chapters to download: 50
Batch size: 1
```

For big updates, avoid very large runs unless you are sure the source works reliably.

---

## Engine guide

### Auto

Recommended default. The system chooses the best available method.

### Generic Scraper

General HTML chapter extraction.

### Pattern Scraper

Useful where chapter URLs follow a predictable pattern.

### FreeWebNovel

Used for FreeWebNovel-style websites.

### FanFicFare

Used for sources supported by FanFicFare.

---

## What to check after submitting an issue

Go to:

```text
Repository → Actions
```

Open the latest workflow run.

Check these steps:

```text
Extract issue request
Run EPUB Manager
Generate RSS and direct EPUB links
Validate library
Commit EPUB and website updates
Comment on issue
Close issue
```

If it succeeds, check:

```text
docs/library.json
docs/epubs/
docs/covers/
```

Then open your GitHub Pages website.

---

## If GitHub Actions does not start

Check these points:

1. The issue title must start with:

```text
[EPUB MANAGER]
```

2. The workflow file must exist here:

```text
.github/workflows/epub-manager.yml
```

3. GitHub Actions must be enabled.

4. Workflow permissions must be set to read and write.

5. The files must be on the `main` branch.

6. The `.github` folder must be at the repository root, not inside another folder.

---

## If the website does not update

Check:

```text
Repository → Settings → Pages
```

Make sure it is set to:

```text
Branch: main
Folder: /docs
```

Then check whether the latest workflow committed changes to:

```text
docs/library.json
docs/epubs/
docs/covers/
docs/last-updated.txt
```

Sometimes GitHub Pages takes a short time to show the latest update.

---

## If EPUB creation fails

Open:

```text
Repository → Actions → latest failed run
```

Check the log under:

```text
Run EPUB Manager
```

Common causes:

- The website blocks scraping.
- The chapter is locked.
- The chapter needs login access.
- The website changed its layout.
- The next chapter link cannot be found.
- The source URL is not a chapter page.
- Too many chapters were requested at once.

Try again with:

```text
Engine: Auto
Chapters to download: 10
Batch size: 1
```

Or try a different source/alternate chapter link.

---

## Files you should not delete

Do not delete these unless you know exactly what you are doing:

```text
.github/workflows/epub-manager.yml
.github/workflows/pages.yml
.github/ISSUE_TEMPLATE/epub-manager.yml
data/settings.json
docs/index.html
docs/app.js
docs/style.css
docs/library.json
scripts/
requirements.txt
```

Deleting these can stop Actions, the website, or EPUB generation.

---

## Safe way to restore stable v2

If your repository breaks, the safest method is:

1. Download or keep a copy of the stable v2 zip.
2. Delete the broken repository files.
3. Upload the stable v2 files again.
4. Make sure `.github`, `docs`, `scripts`, and `data` are at the root of the repo.
5. Re-enable Actions if GitHub asks.
6. Set Pages to `main / docs`.
7. Set Actions permission to read and write.
8. Test using one small novel request first.

Recommended test:

```text
Chapters to download: 10
Batch size: 1
Engine: Auto
```

---

## Stable v2 quick checklist

After uploading, confirm:

- [ ] `.github/workflows/epub-manager.yml` exists.
- [ ] `.github/workflows/pages.yml` exists.
- [ ] `.github/ISSUE_TEMPLATE/epub-manager.yml` exists.
- [ ] `docs/index.html` exists.
- [ ] `docs/app.js` exists.
- [ ] `docs/style.css` exists.
- [ ] `docs/library.json` exists.
- [ ] `scripts/engine_router.py` exists.
- [ ] `requirements.txt` exists.
- [ ] GitHub Actions is enabled.
- [ ] Workflow permissions are read and write.
- [ ] GitHub Pages is set to `main / docs`.
- [ ] A test issue triggers the workflow.
- [ ] The website loads after the workflow completes.

---

## Final note

This stable v2 version is intended to be a simple GitHub-hosted EPUB library manager. Keep changes small, test one feature at a time, and keep a backup zip before making major edits.

## v2.1 features

- Scheduled daily update checks (safe-limited via `data/settings.json`).
- Queue processing (`data/queue.json`, `scripts/queue_manager.py`).
- Novel details page (`docs/novel.html`).
- Better Auto engine routing with domain plan fallbacks.
- Combine EPUB chunks (`scripts/combine_epubs.py`).
- Duplicate/overlap-aware validation improvements.
- Metadata/title cleanup helper module (`scripts/epub_metadata.py`).

## v2.1 finishing tweaks

- Novel details page now mirrors card actions (continue, source, rebuild, delete EPUB/novel, update cover, copy links).
- Update All can be scheduled from the website (start datetime + repeat interval) through an issue/queue flow.
- Queue modes are normalized and validated, with safe handling for unknown modes.
- Engine selector is available on novel details and is injected into build/rebuild issue payloads.
- Combine chunks now uses standalone issue form `combine-epub-chunks.yml` and supports selected files.
