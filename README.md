# Epub Server

A GitHub-based EPUB library system for creating downloadable EPUB files from online web novel chapter links.

This project uses:

- **GitHub Issues** as the request form
- **GitHub Actions** to build EPUB files automatically
- **GitHub Pages** to display your EPUB library
- **Python** to collect chapters, create EPUBs, detect covers, and update the library

> Important: Only use this project for content you are legally allowed to download. Do not use it to bypass paywalls, login restrictions, CAPTCHA, locked chapters, or website access controls.

---

# Table of Contents

1. [What this project does](#what-this-project-does)
2. [How the system works](#how-the-system-works)
3. [Final file structure](#final-file-structure)
4. [Important files](#important-files)
5. [Settings file](#settings-file)
6. [How to use EPUB Manager](#how-to-use-epub-manager)
7. [Mode 1: Single Novel](#mode-1-single-novel)
8. [Mode 2: Batch](#mode-2-batch)
9. [Mode 3: Test Batch](#mode-3-test-batch)
10. [How to check workflow progress](#how-to-check-workflow-progress)
11. [How to check the website](#how-to-check-the-website)
12. [How to clear the website library](#how-to-clear-the-website-library)
13. [How to delete EPUB files](#how-to-delete-epub-files)
14. [How covers work](#how-covers-work)
15. [How website names are detected](#how-website-names-are-detected)
16. [How chapter links are followed](#how-chapter-links-are-followed)
17. [Changing download limits](#changing-download-limits)
18. [Common examples](#common-examples)
19. [Troubleshooting](#troubleshooting)
20. [What not to delete](#what-not-to-delete)
21. [Legal and ethical notice](#legal-and-ethical-notice)
22. [Simplification roadmap](#simplification-roadmap)

---

# What this project does

This project lets you paste one or more web novel chapter links into a GitHub Issue form.

The GitHub Action then:

1. Reads the issue request.
2. Opens the starting chapter link.
3. Extracts chapter text.
4. Finds the next chapter link.
5. Continues collecting chapters.
6. Splits the novel into EPUB batches.
7. Saves EPUB files into `docs/epubs/`.
8. Tries to detect and save a cover image into `docs/covers/`.
9. Updates `docs/library.json`.
10. The GitHub Pages website displays the novel and download links.

Example result on the website:

```text
Nine Star Hegemon Body Art

Website: WuxiaWorld

Available EPUB downloads:
- Chapters 1-100
- Chapters 101-200
````

---

# How the system works

The system has four main parts:

```text
GitHub Issue
↓
GitHub Action
↓
Python EPUB builder
↓
GitHub Pages website
```

## 1. GitHub Issue

You use:

```text
Issues → New issue → EPUB Manager (or Update Cover Image)
```

This is where you paste novel links.

## 2. GitHub Action

The workflow file:

```text
.github/workflows/epub-manager.yml
```

runs automatically when an issue title starts with:

```text
[EPUB MANAGER]
```

## 3. Python EPUB builder

The main builder file is:

```text
scripts/epub_from_link.py
```

It downloads chapters and creates EPUB files.

## 4. GitHub Pages website

The website is inside:

```text
docs/
```

It reads:

```text
docs/library.json
```

and displays the EPUB library.

---

# Final file structure

The simplified final project should look like this:

```text
.github/
  ISSUE_TEMPLATE/
    epub-manager.yml

  workflows/
    epub-manager.yml

data/
  settings.json

scripts/
  epub_from_link.py

docs/
  index.html
  app.js
  style.css
  library.json
  covers/
  epubs/

requirements.txt
README.md
```

---

# Important files

## `data/settings.json`

Controls download limits.

This is the main file to edit when you want to change how many chapters are downloaded.

---

## `.github/ISSUE_TEMPLATE/epub-manager.yml`

Creates the GitHub Issue form called:

```text
EPUB Manager
```

This is the form you use for:

* Single Novel
* Batch
* Test Batch

There is also a dedicated template for cover-only updates:

## `.github/ISSUE_TEMPLATE/update-cover-image.yml`

Creates a focused form for:

* Update Cover Image

---

## `.github/workflows/epub-manager.yml`

This is the GitHub Action workflow.

It runs automatically when you submit an EPUB Manager issue.

---

## `scripts/epub_from_link.py`

This is the main Python builder.

It handles:

* reading the issue request
* reading settings
* downloading chapters
* creating EPUBs
* detecting website name
* detecting cover image
* updating `docs/library.json`

---

## `docs/library.json`

This is the library index used by the website.

If this file is empty:

```json
[]
```

then the website will show no novels.

---

## `docs/epubs/`

This folder stores generated EPUB files.

Example:

```text
docs/epubs/nine-star-hegemon-body-art_ch001-100.epub
```

---

## `docs/covers/`

This folder stores downloaded cover images.

Example:

```text
docs/covers/nine-star-hegemon-body-art.jpg
```

---

## `docs/index.html`

The main website page.

---

## `docs/app.js`

Controls the website behaviour.

It loads `library.json`, displays novel cards, search, filter, and download buttons.

---

## `docs/style.css`

Controls the website design.

---

# Settings file

Open:

```text
data/settings.json
```

Default example:

```json
{
  "normal_chapters_per_epub": 100,
  "normal_max_batches": 2,
  "test_chapters_per_epub": 10,
  "test_max_batches": 1,
  "request_delay_seconds": 1.5
}
```

## Meaning of each setting

| Setting                    | Meaning                                                                |
| -------------------------- | ---------------------------------------------------------------------- |
| `normal_chapters_per_epub` | Number of chapters inside each normal EPUB file                        |
| `normal_max_batches`       | Number of EPUB files to create per novel in Single Novel or Batch mode |
| `test_chapters_per_epub`   | Number of chapters inside each test EPUB                               |
| `test_max_batches`         | Number of test EPUB files to create                                    |
| `request_delay_seconds`    | Delay between chapter requests                                         |

---

# How chapter batching works

If your settings are:

```json
{
  "normal_chapters_per_epub": 100,
  "normal_max_batches": 2
}
```

then the system creates:

```text
Chapters 1-100
Chapters 101-200
```

That means:

```text
100 chapters per EPUB × 2 batches = 200 chapters total
```

If your settings are:

```json
{
  "normal_chapters_per_epub": 100,
  "normal_max_batches": 5
}
```

then the system creates:

```text
Chapters 1-100
Chapters 101-200
Chapters 201-300
Chapters 301-400
Chapters 401-500
```

That means:

```text
100 chapters per EPUB × 5 batches = 500 chapters total
```

---

# How to use EPUB Manager

Go to your repository on GitHub.

Then go to:

```text
Issues → New issue
```

Choose:

```text
EPUB Manager
```

The issue title must start with:

```text
[EPUB MANAGER]
```

Example title:

```text
[EPUB MANAGER] Add Wuxia Novels
```

Then choose one request mode:

```text
Single Novel
Batch
Test Batch
```

---

# Mode 1: Single Novel

Use this when you want to generate EPUBs for **one novel only**.

## Format

```text
Novel Link; Novel Name; Starting Chapter
```

## Example

```text
https://www.wuxiaworld.com/novel/nine-star-hegemon/nshba-chapter-1; Nine Star Hegemon Body Art; 1
```

## What happens

If your settings are:

```json
{
  "normal_chapters_per_epub": 100,
  "normal_max_batches": 2
}
```

then this creates:

```text
Nine Star Hegemon Body Art
- Chapters 1-100
- Chapters 101-200
```

## When to use this

Use Single Novel when:

* you only want one novel
* you know the chapter link works
* you do not want to paste multiple novels

---

# Mode 2: Batch

Use this when you want to generate EPUBs for **multiple novels** from one issue.

## Format

Each novel must be on a new line.

```text
Novel Link; Novel Name; Starting Chapter
Novel Link; Novel Name; Starting Chapter
Novel Link; Novel Name; Starting Chapter
```

## Example

```text
https://www.wuxiaworld.com/novel/nine-star-hegemon/nshba-chapter-1; Nine Star Hegemon Body Art; 1
https://example.com/novel-two/chapter-1; Novel Two Name; 1
https://example.com/novel-three/chapter-101; Novel Three Name; 101
```

## What happens

Each line is treated as a separate novel.

If the settings are:

```json
{
  "normal_chapters_per_epub": 100,
  "normal_max_batches": 2
}
```

then each novel can generate:

```text
Chapters 1-100
Chapters 101-200
```

or, if starting from chapter 101:

```text
Chapters 101-200
Chapters 201-300
```

## When to use this

Use Batch when:

* you want to add several novels at the same time
* you already tested them
* you want the website to update with multiple entries

---

# Mode 3: Test Batch

Use this when you only want to check whether a novel can be read properly.

This is the safest first test.

## Format

```text
Novel Link; Novel Name
```

or:

```text
Novel Link; Novel Name; 1
```

The starting chapter is ignored in Test Batch mode and always treated as:

```text
1
```

## Example

```text
https://www.wuxiaworld.com/novel/nine-star-hegemon/nshba-chapter-1; Nine Star Hegemon Body Art
```

## What happens

If your settings are:

```json
{
  "test_chapters_per_epub": 10,
  "test_max_batches": 1
}
```

then this creates:

```text
Chapters 1-10
```

## When to use this

Use Test Batch when:

* trying a new website
* checking if the chapter text extracts properly
* checking if the next chapter link works
* checking if the EPUB looks readable
* checking if the cover is detected

Recommended process:

```text
Test Batch first
↓
If successful, use Single Novel or Batch
```

---

# How to check workflow progress

After submitting an issue:

```text
Actions → EPUB Manager
```

Open the latest run.

You should see steps like:

```text
Checkout repo
Set up Python
Install dependencies
Extract issue request
Build EPUBs
Commit EPUB and library updates
Comment on issue
Close issue
```

Wait for the green tick.

If it fails, open the failed step and read the error.

---

# How to check the website

Your website is hosted from:

```text
docs/
```

GitHub Pages should be set to:

```text
Settings → Pages
Source: Deploy from a branch
Branch: main
Folder: /docs
```

Website URL format:

```text
https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/
```

Example:

```text
https://savv666.github.io/Epub-Server/
```

After a successful EPUB build, open the website and refresh with:

```text
Ctrl + F5
```

On mobile, close and reopen the browser page or pull down to refresh.

---

# How the website displays novels

The website reads:

```text
docs/library.json
```

Example entry:

```json
[
  {
    "title": "Nine Star Hegemon Body Art",
    "slug": "nine-star-hegemon-body-art",
    "site": "WuxiaWorld",
    "cover": "covers/nine-star-hegemon-body-art.jpg",
    "chapters": 200,
    "source_url": "https://www.wuxiaworld.com/novel/nine-star-hegemon/nshba-chapter-1",
    "downloads": [
      {
        "label": "Chapters 1-100",
        "start": 1,
        "end": 100,
        "url": "epubs/nine-star-hegemon-body-art_ch001-100.epub"
      },
      {
        "label": "Chapters 101-200",
        "start": 101,
        "end": 200,
        "url": "epubs/nine-star-hegemon-body-art_ch101-200.epub"
      }
    ]
  }
]
```

The website shows:

* title
* website name
* cover
* total indexed chapters
* download buttons
* chapter batch list

---

# How to clear the website library

If you want the website to show nothing, reset this file:

```text
docs/library.json
```

Replace everything with:

```json
[]
```

Commit the change.

The website will show:

```text
No EPUBs found.
```

This only hides the entries from the website. It does not necessarily delete the actual EPUB files.

---

# How to delete EPUB files

To delete generated EPUB files completely:

Go to:

```text
docs/epubs/
```

Delete the `.epub` files.

Then also reset:

```text
docs/library.json
```

to:

```json
[]
```

Commit the changes.

---

# How to delete covers

Go to:

```text
docs/covers/
```

Delete unwanted cover images.

Do not delete:

```text
docs/covers/default.svg
```

if your website uses it as fallback.

---

# How covers work

The script tries to detect cover images from the chapter page.

It checks:

```text
og:image
twitter:image
.novel-cover img
.book-cover img
.cover img
.poster img
.thumb img
.novel img
img
```

If a cover is found, it is saved into:

```text
docs/covers/
```

Example:

```text
docs/covers/nine-star-hegemon-body-art.jpg
```

Then `library.json` gets:

```json
"cover": "covers/nine-star-hegemon-body-art.jpg"
```

If no cover is found, it uses:

```text
covers/default.svg
```

## Cover limitation

Some chapter pages do not include the novel cover.

In that case, the system may not find the proper cover.

---

# How website names are detected

The script detects common domains automatically.

Known websites include:

```text
WuxiaWorld
RoyalRoad
ScribbleHub
NovelBin
NovelFull
WebNovel
LightNovelWorld
ReadNovelFull
FanFiction.Net
Archive of Our Own
```

If the website is unknown, it creates a name from the domain.

Example:

```text
example-novel-site.com
```

becomes:

```text
Example Novel Site
```

---

# How chapter links are followed

The script first looks for links with text or metadata like:

```text
Next
Next Chapter
›
»
Older
Continue
Forward
```

If it cannot find a next button, it tries to increase the chapter number in the URL.

Example:

```text
chapter-1
chapter-2
chapter-3
```

For WuxiaWorld-style links, this helps with URLs like:

```text
nshba-chapter-1
nshba-chapter-2
nshba-chapter-3
```

---

# Changing download limits

Edit:

```text
data/settings.json
```

## Normal download limit

These settings affect:

```text
Single Novel
Batch
```

```json
"normal_chapters_per_epub": 100,
"normal_max_batches": 2
```

## Test download limit

These settings affect:

```text
Test Batch
```

```json
"test_chapters_per_epub": 10,
"test_max_batches": 1
```

---

# Common examples

## Example 1: Keep normal downloads to 200 chapters

```json
{
  "normal_chapters_per_epub": 100,
  "normal_max_batches": 2,
  "test_chapters_per_epub": 10,
  "test_max_batches": 1,
  "request_delay_seconds": 1.5
}
```

Creates:

```text
Chapters 1-100
Chapters 101-200
```

---

## Example 2: Allow 500 chapters

```json
{
  "normal_chapters_per_epub": 100,
  "normal_max_batches": 5,
  "test_chapters_per_epub": 10,
  "test_max_batches": 1,
  "request_delay_seconds": 1.5
}
```

Creates:

```text
Chapters 1-100
Chapters 101-200
Chapters 201-300
Chapters 301-400
Chapters 401-500
```

---

## Example 3: Create smaller EPUB files with 50 chapters each

```json
{
  "normal_chapters_per_epub": 50,
  "normal_max_batches": 4,
  "test_chapters_per_epub": 10,
  "test_max_batches": 1,
  "request_delay_seconds": 1.5
}
```

Creates:

```text
Chapters 1-50
Chapters 51-100
Chapters 101-150
Chapters 151-200
```

---

## Example 4: Test first 20 chapters

```json
{
  "normal_chapters_per_epub": 100,
  "normal_max_batches": 2,
  "test_chapters_per_epub": 20,
  "test_max_batches": 1,
  "request_delay_seconds": 1.5
}
```

Test Batch creates:

```text
Chapters 1-20
```

---

## Example 5: Slow down requests

If a website blocks or fails, increase delay:

```json
{
  "normal_chapters_per_epub": 100,
  "normal_max_batches": 2,
  "test_chapters_per_epub": 10,
  "test_max_batches": 1,
  "request_delay_seconds": 3
}
```

This waits 3 seconds between chapter requests.

---

# Recommended workflow

Best way to use the system:

```text
1. Use Test Batch first.
2. Download the test EPUB.
3. Open it and check readability.
4. If it looks good, use Single Novel or Batch.
5. Start with 200 chapters.
6. Increase limits only after confirming the website works.
```

Recommended starting settings:

```json
{
  "normal_chapters_per_epub": 100,
  "normal_max_batches": 2,
  "test_chapters_per_epub": 10,
  "test_max_batches": 1,
  "request_delay_seconds": 1.5
}
```

---

# Troubleshooting

## Workflow did not start

Check the issue title.

It must start with:

```text
[EPUB MANAGER]
```

Correct:

```text
[EPUB MANAGER] Add Novel
```

Wrong:

```text
Add Novel
```

Also check that this file exists:

```text
.github/workflows/epub-manager.yml
```

---

## Issue form does not appear

Check that this file exists:

```text
.github/ISSUE_TEMPLATE/epub-manager.yml
```

Then go to:

```text
Issues → New issue
```

You should see:

```text
EPUB Manager
```

---

## EPUB does not appear on website

Check the workflow:

```text
Actions → EPUB Manager
```

If the workflow failed, open the failed step.

Then check:

```text
docs/library.json
```

If it is still:

```json
[]
```

then no library entry was created.

---

## EPUB file exists but website does not update

GitHub Pages may not have redeployed yet.

Wait 1–2 minutes.

Then refresh:

```text
Ctrl + F5
```

Also check:

```text
docs/library.json
```

If the entry is there, the website should show it after refresh.

---

## Only one chapter was downloaded

The script probably could not find the next chapter link.

Check the workflow log:

```text
Actions → EPUB Manager → latest run → Build EPUBs
```

Look for:

```text
No next chapter link found.
```

or:

```text
Trying URL fallback.
```

If URL fallback works, it will try to change:

```text
chapter-1
```

to:

```text
chapter-2
```

If it still stops, the site may use a different link structure.

---

## EPUB contains unwanted text

Some websites include ads, comments, navigation, or extra text inside the same content area.

The script removes common elements like:

```text
script
style
nav
header
footer
aside
ads
comments
chapter navigation
breadcrumbs
```

But some websites may need custom cleanup.

---

## Cover does not show

Possible reasons:

* the chapter page has no cover image
* the image is loaded with JavaScript
* the website blocks image downloads
* the cover is on the novel homepage, not the chapter page

Fallback:

```text
covers/default.svg
```

---

## Website says `No EPUBs found`

Check:

```text
docs/library.json
```

If it contains:

```json
[]
```

then the website is working, but the library is empty.

Submit a new EPUB Manager issue to add novels again.

---

## Git push failed in workflow

If GitHub Actions fails at the commit/push step, check the workflow log.

Usually this happens when the repo changed while the workflow was running.

The workflow already uses:

```bash
git pull --rebase origin main
git push origin main
```

If it still fails, rerun the workflow or create a new issue.

---

## Batch mode partly works

If you submit multiple novels and some fail, check:

```text
data/epub_manager_results.json
```

It records success or failure for each novel.

Example:

```json
[
  {
    "title": "Novel One",
    "status": "success"
  },
  {
    "title": "Novel Two",
    "status": "failed",
    "error": "..."
  }
]
```

---

# Files created automatically

The system may automatically create or update:

```text
data/epub_manager_request.json
data/epub_manager_results.json
docs/library.json
docs/epubs/
docs/covers/
```

These are normal.

You can delete generated request/result files if you want, but they may be recreated later:

```text
data/epub_manager_request.json
data/epub_manager_results.json
```

---

# What not to delete

Do not delete these unless you know what you are doing:

```text
.github/ISSUE_TEMPLATE/epub-manager.yml
.github/workflows/epub-manager.yml
data/settings.json
scripts/epub_from_link.py
docs/index.html
docs/app.js
docs/style.css
requirements.txt
```

If you delete them, the system may stop working.

---

# What can be safely cleared

You can clear the visible website library by resetting:

```text
docs/library.json
```

to:

```json
[]
```

You can delete EPUB files from:

```text
docs/epubs/
```

You can delete generated covers from:

```text
docs/covers/
```

but keep:

```text
docs/covers/default.svg
```

if your site depends on it.

---

# Requirements

The `requirements.txt` file should contain at least:

```text
requests
beautifulsoup4
ebooklib
lxml
python-slugify
```

Optional but okay to keep:

```text
fanficfare
Pillow
```

---

# GitHub Pages setup

To enable the website:

1. Go to repository **Settings**.
2. Go to **Pages**.
3. Set source to:

```text
Deploy from a branch
```

4. Select:

```text
Branch: main
Folder: /docs
```

5. Click **Save**.

Your site will be available at:

```text
https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/
```

---

# GitHub Actions permissions

If the workflow cannot commit files, check permissions:

Go to:

```text
Settings → Actions → General
```

Under **Workflow permissions**, select:

```text
Read and write permissions
```

Then save.

The workflow needs write permission so it can update:

```text
docs/library.json
docs/epubs/
docs/covers/
```

---

# Branch safety advice

If you want to test major changes safely:

1. Create a new branch.
2. Make changes there.
3. Test or review.
4. Create a pull request.
5. Merge into `main` only when happy.

Recommended branch name examples:

```text
test-new-builder
update-website-design
change-epub-settings
```

---

# Limitations

This project may fail on websites that:

* require login
* use CAPTCHA
* use Cloudflare or anti-bot protection
* load chapter text using JavaScript
* do not expose text in normal HTML
* have no clear next-chapter link
* use paid or locked chapters
* block automated requests
* use unusual chapter numbering
* change their HTML structure

If a website fails, first try **Test Batch** with one novel.

---

# Legal and ethical notice

This project is intended only for personal use with content you are legally allowed to download.

Do not use this project to:

* bypass paywalls
* bypass login systems
* bypass CAPTCHA
* download locked or paid chapters without permission
* scrape private content
* ignore website terms of service
* redistribute copyrighted works without permission

Respect authors, translators, publishers, and website rules.

````

