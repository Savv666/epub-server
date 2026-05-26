import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from slugify import slugify


ROOT = Path(".")
DOCS_DIR = ROOT / "docs"
EPUB_DIR = DOCS_DIR / "epubs"
COVER_DIR = DOCS_DIR / "covers"
LIBRARY_FILE = DOCS_DIR / "library.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 compatible; EPUBBuilder/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clean_text(value):
    value = re.sub(r"\s+", " ", str(value or ""))
    return value.strip()


def is_freewebnovel_url(url):
    domain = urlparse(str(url or "")).netloc.lower().replace("www.", "")
    return domain == "freewebnovel.com" or domain.endswith(".freewebnovel.com")


def fetch_page(url):
    response = requests.get(url, headers=HEADERS, timeout=30)

    if response.status_code == 403:
        raise PermissionError(
            "freewebnovel.com returned 403 Forbidden. "
            "The website is blocking the GitHub Actions runner."
        )

    response.raise_for_status()
    return response.text


def load_library():
    if not LIBRARY_FILE.exists():
        return []

    try:
        data = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    return data if isinstance(data, list) else []


def save_library(library):
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_FILE.write_text(
        json.dumps(library, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def find_existing_library_item(library, novel_title):
    wanted_slug = slugify(novel_title) or "novel"
    wanted_title = clean_text(novel_title).lower()

    for item in library:
        if item.get("slug") == wanted_slug:
            return item

    for item in library:
        if clean_text(item.get("title", "")).lower() == wanted_title:
            return item

    return None


def get_last_downloaded_chapter(library_item):
    downloads = library_item.get("downloads", [])

    if not downloads:
        return int(library_item.get("last_chapter_number", 0) or library_item.get("chapters", 0) or 0)

    max_end = 0

    for item in downloads:
        try:
            max_end = max(max_end, int(item.get("end", 0)))
        except Exception:
            continue

    return max_end


def detect_site_name(url):
    return "FreeWebNovel"


def detect_title(soup, fallback_title):
    selectors = [
        "h1",
        ".chapter-title",
        ".chr-title",
        ".novel-title",
        ".book-title",
        "title"
    ]

    for selector in selectors:
        item = soup.select_one(selector)

        if item:
            text = clean_text(item.get_text(" "))

            if text:
                text = re.sub(r"\s*-\s*Free\s*Web\s*Novel.*$", "", text, flags=re.I)
                text = re.sub(r"\s*-\s*FreeWebNovel.*$", "", text, flags=re.I)

                if len(text) < 180:
                    return text

    return fallback_title or "FreeWebNovel Story"


def find_cover_url(soup, page_url):
    selectors = [
        'meta[property="og:image"]',
        'meta[name="twitter:image"]',
        ".book img",
        ".novel img",
        ".cover img",
        ".book-cover img",
        ".pic img",
        "img"
    ]

    for selector in selectors:
        item = soup.select_one(selector)

        if not item:
            continue

        if item.name == "meta":
            src = item.get("content")
        else:
            src = item.get("src") or item.get("data-src") or item.get("data-original")

        if not src:
            continue

        full_url = urljoin(page_url, src)

        if full_url.startswith("http"):
            return full_url

    return None


def download_cover(cover_url, novel_title):
    if not cover_url:
        return "covers/default.svg"

    COVER_DIR.mkdir(parents=True, exist_ok=True)
    safe_title = slugify(novel_title) or "freewebnovel-story"

    try:
        response = requests.get(cover_url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()

        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        else:
            ext = ".jpg"

        output_path = COVER_DIR / f"{safe_title}{ext}"
        output_path.write_bytes(response.content)

        return str(output_path.relative_to(DOCS_DIR)).replace("\\", "/")

    except Exception:
        return "covers/default.svg"


def remove_bad_elements(soup):
    bad_selectors = [
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "iframe",
        "form",
        "button",
        ".ads",
        ".ad",
        ".advertisement",
        ".comments",
        "#comments",
        ".chapter-nav",
        ".breadcrumb",
        ".nav",
        ".login",
        ".modal",
        ".popup",
        ".recommend",
        ".related",
        "[class*='ads']",
        "[class*='advert']",
        "[class*='comment']",
        "[class*='breadcrumb']",
        "[class*='recommend']"
    ]

    for selector in bad_selectors:
        for tag in soup.select(selector):
            tag.decompose()


def is_bad_paragraph(text):
    lower = clean_text(text).lower()

    if not lower:
        return True

    bad_phrases = [
        "freewebnovel.com",
        "please enable javascript",
        "chapter navigation",
        "previous chapter",
        "next chapter",
        "tip: you can use left",
        "if you find any errors",
        "report chapter",
        "bookmark",
        "login",
        "register",
        "advertisement",
        "please turn off adblock",
    ]

    for phrase in bad_phrases:
        if phrase in lower:
            return True

    return False


def extract_content(soup):
    remove_bad_elements(soup)

    selectors = [
        "#article",
        "#chapter-content",
        ".chapter-content",
        ".chapter-c",
        ".chapter-body",
        ".chr-c",
        ".entry-content",
        ".post-content",
        ".novel-content",
        "article",
        "main"
    ]

    container = None

    for selector in selectors:
        item = soup.select_one(selector)

        if item:
            container = item
            break

    if not container:
        container = soup.find("body")

    if not container:
        return []

    paragraphs = []
    seen = set()

    tags = container.find_all(["p"])

    if not tags:
        tags = container.find_all(["p", "div"])

    for tag in tags:
        text = clean_text(tag.get_text(" "))

        if len(text) < 25:
            continue

        if is_bad_paragraph(text):
            continue

        fingerprint = re.sub(r"[^a-z0-9]+", "", text.lower())[:180]

        if fingerprint in seen:
            continue

        seen.add(fingerprint)
        paragraphs.append(text)

    return paragraphs


def increment_url(url):
    patterns = [
        r"(chapter[-_/]?)(\d+)(/?$)",
        r"(\D)(\d+)(/?$)"
    ]

    for pattern in patterns:
        match = re.search(pattern, url, re.I)

        if not match:
            continue

        number_text = match.group(2)
        number = int(number_text)
        next_number = number + 1

        if number_text.startswith("0"):
            next_text = str(next_number).zfill(len(number_text))
        else:
            next_text = str(next_number)

        start, end = match.span(2)
        return url[:start] + next_text + url[end:]

    return None


def find_next_link(soup, current_url):
    links = soup.find_all("a", href=True)

    for link in links:
        text = clean_text(link.get_text(" ")).lower()
        href = link.get("href", "")

        combined = text + " " + href.lower()

        if "next chapter" in combined or text in ["next", "next >"] or "chapter-next" in combined:
            next_url = urljoin(current_url, href)

            if next_url != current_url:
                return next_url

    fallback = increment_url(current_url)

    if fallback and fallback != current_url:
        return fallback

    return None


def create_epub(novel_title, chapters, start_chapter, end_chapter, cover_path="covers/default.svg"):
    EPUB_DIR.mkdir(parents=True, exist_ok=True)

    safe_title = slugify(novel_title) or "freewebnovel-story"
    output_path = EPUB_DIR / f"{safe_title}_ch{start_chapter:03d}-{end_chapter:03d}_freewebnovel.epub"

    book = epub.EpubBook()
    book.set_identifier(f"{safe_title}-{start_chapter}-{end_chapter}-freewebnovel")
    book.set_title(f"{novel_title} Chapters {start_chapter}-{end_chapter}")
    book.set_language("en")
    book.add_author("Online Novel")
    cover_file = DOCS_DIR / str(cover_path or "")

    if cover_path and cover_path != "covers/default.svg" and cover_file.exists() and cover_file.is_file():
        try:
            book.set_cover(cover_file.name, cover_file.read_bytes())
        except Exception as exc:
            print(f"Failed to embed cover into EPUB: {exc}")

    epub_chapters = []

    for index, chapter in enumerate(chapters, start=1):
        html = f"<h1>{chapter['title']}</h1>"
        html += f"<p><em>Original URL: {chapter['url']}</em></p>"

        for para in chapter["paragraphs"]:
            html += f"<p>{para}</p>"

        epub_chapter = epub.EpubHtml(
            title=chapter["title"],
            file_name=f"chapter_{index:03d}.xhtml",
            lang="en"
        )

        epub_chapter.content = html

        book.add_item(epub_chapter)
        epub_chapters.append(epub_chapter)

    book.toc = tuple(epub_chapters)
    book.spine = ["nav"] + epub_chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(str(output_path), book)

    return output_path


def update_library(
    novel_title,
    source_url,
    cover_path,
    epub_path,
    start_chapter,
    end_chapter,
    next_url,
    last_chapter_url,
    status
):
    library = load_library()
    safe_title = slugify(novel_title) or "freewebnovel-story"
    relative_epub = str(epub_path.relative_to(DOCS_DIR)).replace("\\", "/")

    download_item = {
        "label": f"Chapters {start_chapter}-{end_chapter}",
        "start": start_chapter,
        "end": end_chapter,
        "url": relative_epub,
        "mode": "FreeWebNovel",
        "created_at": now_iso()
    }

    existing = find_existing_library_item(library, novel_title)

    if existing:
        downloads = existing.setdefault("downloads", [])

        if not any(item.get("url") == relative_epub for item in downloads):
            downloads.append(download_item)

        downloads.sort(key=lambda item: int(item.get("start", 0)))

        existing["site"] = detect_site_name(source_url)
        existing["source_url"] = source_url or existing.get("source_url", "")
        existing["status"] = status
        existing["last_mode"] = "FreeWebNovel"
        existing["last_updated"] = now_iso()
        existing["chapters"] = max(int(existing.get("chapters", 0) or 0), end_chapter)
        existing["last_chapter_number"] = max(int(existing.get("last_chapter_number", 0) or 0), end_chapter)

        if next_url:
            existing["next_url"] = next_url

        if last_chapter_url:
            existing["last_chapter_url"] = last_chapter_url

        if cover_path and cover_path != "covers/default.svg":
            existing["cover"] = cover_path

        existing.pop("locked_chapter_number", None)
        existing.pop("locked_chapter_url", None)
        existing.pop("locked_reason", None)

    else:
        library.append({
            "title": novel_title,
            "slug": safe_title,
            "site": detect_site_name(source_url),
            "cover": cover_path,
            "chapters": end_chapter,
            "source_url": source_url,
            "next_url": next_url or "",
            "last_chapter_url": last_chapter_url or "",
            "last_chapter_number": end_chapter,
            "status": status,
            "last_mode": "FreeWebNovel",
            "created_at": now_iso(),
            "last_updated": now_iso(),
            "downloads": [download_item]
        })

    library.sort(key=lambda item: item.get("title", "").lower())
    save_library(library)


def prepare_start(item):
    source_url = clean_text(item.get("start_url"))
    novel_title = clean_text(item.get("novel_title")) or "FreeWebNovel Story"

    try:
        start_chapter = int(item.get("start_chapter", 1) or 1)
    except Exception:
        start_chapter = 1

    library = load_library()
    existing = find_existing_library_item(library, novel_title)

    if not existing:
        return source_url, novel_title, start_chapter

    last_downloaded = get_last_downloaded_chapter(existing)
    saved_next_url = clean_text(existing.get("next_url", ""))
    old_source_url = clean_text(existing.get("source_url", ""))

    manual_source_switch = False

    if source_url:
        if saved_next_url and source_url != saved_next_url:
            manual_source_switch = True

        if old_source_url and source_url != old_source_url:
            manual_source_switch = True

    if last_downloaded and start_chapter <= last_downloaded:
        if manual_source_switch:
            print("=" * 80)
            print("FreeWebNovel manual source switch accepted")
            print(f"Novel: {novel_title}")
            print(f"Already downloaded up to: {last_downloaded}")
            print(f"Using supplied URL as chapter {last_downloaded + 1}: {source_url}")
            print("=" * 80)
            return source_url, novel_title, last_downloaded + 1

        if saved_next_url:
            print("=" * 80)
            print("FreeWebNovel duplicate / overlap detected")
            print(f"Novel: {novel_title}")
            print(f"Already downloaded up to: {last_downloaded}")
            print(f"Using saved next_url as chapter {last_downloaded + 1}: {saved_next_url}")
            print("=" * 80)
            return saved_next_url, novel_title, last_downloaded + 1

    return source_url, novel_title, start_chapter


def download_with_freewebnovel(item, chapters_per_epub=10, max_batches=1):
    source_url, novel_title, start_chapter = prepare_start(item)

    try:
        chapters_per_epub = int(chapters_per_epub or 10)
    except Exception:
        chapters_per_epub = 10

    try:
        max_batches = int(max_batches or 1)
    except Exception:
        max_batches = 1

    if not source_url:
        return {
            "title": novel_title,
            "status": "failed",
            "engine": "freewebnovel",
            "error": "Missing source URL"
        }

    if not is_freewebnovel_url(source_url):
        return {
            "title": novel_title,
            "status": "failed",
            "engine": "freewebnovel",
            "start_url": source_url,
            "error": "URL is not a freewebnovel.com URL"
        }

    created_files = []
    batch_results = []
    current_url = source_url
    current_chapter = start_chapter
    existing_item = find_existing_library_item(load_library(), novel_title)
    cover_path = str(existing_item.get("cover", "covers/default.svg")).strip() if existing_item else "covers/default.svg"

    for batch_index in range(max_batches):
        batch_start = current_chapter
        batch_chapters = []

        print("=" * 80)
        print("FreeWebNovel engine batch")
        print(f"Title: {novel_title}")
        print(f"URL: {current_url}")
        print(f"Batch: {batch_index + 1}/{max_batches}")
        print(f"Chapter range target: {batch_start}-{batch_start + chapters_per_epub - 1}")
        print("=" * 80)

        for _ in range(chapters_per_epub):
            if not current_url:
                break

            print(f"Fetching chapter {current_chapter}: {current_url}")

            try:
                html = fetch_page(current_url)
            except Exception as exc:
                error = str(exc)

                return {
                    "title": novel_title,
                    "status": "failed",
                    "engine": "freewebnovel",
                    "start_url": source_url,
                    "failed_url": current_url,
                    "failed_chapter": current_chapter,
                    "files": created_files,
                    "batch_results": batch_results,
                    "error": error
                }

            soup = BeautifulSoup(html, "lxml")

            if batch_index == 0 and not created_files and not batch_chapters:
                detected_title = detect_title(soup, novel_title)

                if detected_title:
                    novel_title = novel_title or detected_title

                if cover_path == "covers/default.svg":
                    cover_url = find_cover_url(soup, current_url)

                    if cover_url:
                        cover_path = download_cover(cover_url, novel_title)

            chapter_title = detect_title(soup, f"Chapter {current_chapter}")
            paragraphs = extract_content(soup)

            if not paragraphs:
                return {
                    "title": novel_title,
                    "status": "failed",
                    "engine": "freewebnovel",
                    "start_url": source_url,
                    "failed_url": current_url,
                    "failed_chapter": current_chapter,
                    "files": created_files,
                    "batch_results": batch_results,
                    "error": "No readable chapter content found on FreeWebNovel page."
                }

            batch_chapters.append({
                "number": current_chapter,
                "title": chapter_title,
                "url": current_url,
                "paragraphs": paragraphs
            })

            last_chapter_url = current_url
            next_url = find_next_link(soup, current_url)

            current_url = next_url
            current_chapter += 1

            time.sleep(1.5)

        if not batch_chapters:
            break

        batch_end = batch_start + len(batch_chapters) - 1

        epub_path = create_epub(
            novel_title=novel_title,
            chapters=batch_chapters,
            start_chapter=batch_start,
            end_chapter=batch_end,
            cover_path=cover_path
        )

        status = "Built with FreeWebNovel"

        if len(batch_chapters) < chapters_per_epub:
            status = "Partial with FreeWebNovel"

        update_library(
            novel_title=novel_title,
            source_url=source_url,
            cover_path=cover_path,
            epub_path=epub_path,
            start_chapter=batch_start,
            end_chapter=batch_end,
            next_url=current_url,
            last_chapter_url=last_chapter_url,
            status=status
        )

        created_files.append(str(epub_path))

        batch_results.append({
            "start": batch_start,
            "end": batch_end,
            "file": str(epub_path),
            "chapters": len(batch_chapters)
        })

        if len(batch_chapters) < chapters_per_epub or not current_url:
            break

    if not created_files:
        return {
            "title": novel_title,
            "status": "failed",
            "engine": "freewebnovel",
            "start_url": source_url,
            "files": [],
            "error": "No EPUB files were created by FreeWebNovel engine."
        }

    return {
        "title": novel_title,
        "status": "success",
        "engine": "freewebnovel",
        "selected_engine": "FreeWebNovel",
        "start_url": source_url,
        "files": created_files,
        "start_chapter": start_chapter,
        "last_successful_chapter": batch_results[-1]["end"] if batch_results else start_chapter,
        "batch_results": batch_results,
        "message": "Built using FreeWebNovel engine"
    }
