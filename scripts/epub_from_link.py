import json
import re
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from slugify import slugify


ROOT = Path(".")
REQUEST_FILE = ROOT / "data" / "epub_manager_request.json"
SETTINGS_FILE = ROOT / "data" / "settings.json"

DOCS_DIR = ROOT / "docs"
EPUB_DIR = DOCS_DIR / "epubs"
COVER_DIR = DOCS_DIR / "covers"
LIBRARY_FILE = DOCS_DIR / "library.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 compatible; EPUBBuilder/1.0"
}

ROYALROAD_CACHE = {}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_settings():
    defaults = {
        "normal_chapters_per_epub": 10,
        "normal_max_batches": 1,
        "test_chapters_per_epub": 10,
        "test_max_batches": 1,
        "update_all_chapters_per_epub": 10,
        "update_all_max_batches": 1,
        "request_delay_seconds": 1.5
    }

    if SETTINGS_FILE.exists():
        try:
            custom = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            defaults.update(custom)
        except Exception as exc:
            print(f"Could not read settings.json. Using defaults. Error: {exc}")

    return defaults


SETTINGS = load_settings()


def clean_text(text):
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def detect_site_name(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    known_sites = {
        "wuxiaworld.com": "WuxiaWorld",
        "royalroad.com": "RoyalRoad",
        "scribblehub.com": "ScribbleHub",
        "novelbin.me": "NovelBin",
        "novelbin.com": "NovelBin",
        "novelfull.com": "NovelFull",
        "webnovel.com": "WebNovel",
        "lightnovelworld.co": "LightNovelWorld",
        "lightnovelworld.com": "LightNovelWorld",
        "readnovelfull.com": "ReadNovelFull",
        "fanfiction.net": "FanFiction.Net",
        "archiveofourown.org": "Archive of Our Own"
    }

    for key, name in known_sites.items():
        if domain.endswith(key):
            return name

    parts = domain.split(".")

    if len(parts) >= 2:
        return parts[-2].replace("-", " ").replace("_", " ").title()

    return domain.title() or "Unknown"


def fetch_page(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def get_page_title(soup):
    h1 = soup.find("h1")

    if h1:
        return clean_text(h1.get_text())

    title = soup.find("title")

    if title:
        return clean_text(title.get_text())

    return "Untitled Chapter"


def detect_novel_title(soup, fallback_url):
    selectors = [
        ".novel-title",
        ".book-title",
        ".entry-title",
        ".post-title",
        ".breadcrumb",
        "h1"
    ]

    for selector in selectors:
        item = soup.select_one(selector)

        if item:
            text = clean_text(item.get_text())

            if text and len(text) < 120:
                return text

    parsed = urlparse(fallback_url)
    parts = [p for p in parsed.path.split("/") if p]

    if len(parts) >= 2:
        return parts[-2].replace("-", " ").title()

    return parsed.netloc.replace("www.", "")


def find_cover_url(soup, page_url):
    selectors = [
        'meta[property="og:image"]',
        'meta[name="twitter:image"]',
        ".novel-cover img",
        ".book-cover img",
        ".cover img",
        ".poster img",
        ".thumb img",
        ".novel img",
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

        cover_url = urljoin(page_url, src)

        if cover_url.startswith("http"):
            return cover_url

    return None


def download_cover(cover_url, novel_title):
    if not cover_url:
        return "covers/default.svg"

    COVER_DIR.mkdir(parents=True, exist_ok=True)
    safe_title = slugify(novel_title) or "novel"

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

        cover_path = COVER_DIR / f"{safe_title}{ext}"
        cover_path.write_bytes(response.content)

        return str(cover_path.relative_to(DOCS_DIR)).replace("\\", "/")

    except Exception as exc:
        print(f"Failed to download cover: {exc}")
        return "covers/default.svg"


def remove_bad_elements(soup):
    bad_selectors = [
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "iframe",
        "button",
        ".ads",
        ".advertisement",
        ".ad",
        ".comments",
        "#comments",
        ".nav-links",
        ".chapter-nav",
        ".breadcrumb",
        ".login",
        ".register",
        ".modal",
        ".popup",
        ".paywall",
        ".locked",
        ".unlock",
        ".subscription",
        ".chapter-comments",
        ".comment-section",
        "[class*='login']",
        "[class*='Login']",
        "[class*='paywall']",
        "[class*='Paywall']",
        "[class*='unlock']",
        "[class*='Unlock']",
        "[class*='subscribe']",
        "[class*='Subscribe']"
    ]

    for selector in bad_selectors:
        for tag in soup.select(selector):
            tag.decompose()


def is_bad_paragraph(text):
    cleaned = clean_text(text).lower()

    if not cleaned:
        return True

    bad_phrases = [
        "log in to continue your adventure",
        "other benefits you will get",
        "unlock free chapters every day",
        "bookmark your novel and never lose track",
        "share your thoughts with your favorite translator",
        "please log in",
        "login to continue",
        "sign in to continue",
        "subscribe to continue",
        "unlock this chapter",
        "unlock chapter",
        "purchase this chapter",
        "become a vip",
        "join wuxiaworld",
        "download the app",
        "use karma",
        "watch an ad",
        "translator in the comments",
        "this work is only available to registered users",
        "only available to registered users of the archive",
        "if you already have an archive of our own account",
        "request an invitation to join",
        "forgot your password or username"
    ]

    for phrase in bad_phrases:
        if phrase in cleaned:
            return True

    return False


def detect_locked_or_partial_page(soup):
    page_text = clean_text(soup.get_text(" ")).lower()

    locked_phrases = [
        "log in to continue your adventure",
        "unlock free chapters every day",
        "other benefits you will get",
        "unlock this chapter",
        "purchase this chapter",
        "subscribe to continue",
        "please log in",
        "login to continue",
        "sign in to continue",
        "use karma",
        "watch an ad to continue",
        "become a vip",
        "this work is only available to registered users",
        "only available to registered users of the archive",
        "if you already have an archive of our own account",
        "request an invitation to join",
        "forgot your password or username"
    ]

    for phrase in locked_phrases:
        if phrase in page_text:
            return {
                "locked": True,
                "reason": phrase
            }

    return {
        "locked": False,
        "reason": ""
    }


def extract_chapter_content(soup):
    remove_bad_elements(soup)

    selectors = [
        ".chapter-content",
        ".chapter-body",
        ".chapter",
        ".entry-content",
        ".post-content",
        ".reading-content",
        ".fr-view",
        "[class*='chapter-content']",
        "[class*='ChapterContent']",
        "[class*='chapter-body']",
        "[class*='ChapterBody']",
        "article",
        "main"
    ]

    selected_container = None

    for selector in selectors:
        item = soup.select_one(selector)

        if item:
            selected_container = item
            break

    if not selected_container:
        selected_container = soup.find("body")

    if not selected_container:
        return []

    text_parts = []
    seen = set()

    paragraph_tags = selected_container.find_all(["p"])

    if not paragraph_tags:
        paragraph_tags = selected_container.find_all(["p", "div"])

    for tag in paragraph_tags:
        txt = clean_text(tag.get_text(" "))

        if len(txt) < 25:
            continue

        if is_bad_paragraph(txt):
            continue

        lowered = txt.lower()

        if "log in to continue your adventure" in lowered:
            break

        if "unlock free chapters every day" in lowered:
            break

        fingerprint = re.sub(r"[^a-z0-9]+", "", lowered)[:160]

        if fingerprint in seen:
            continue

        seen.add(fingerprint)
        text_parts.append(txt)

    return text_parts


def increment_chapter_url(current_url):
    patterns = [
        r"(chapter[-_/]?)(\d+)(/?$)",
        r"(\D)(\d+)(/?$)"
    ]

    for pattern in patterns:
        match = re.search(pattern, current_url, re.I)

        if match:
            number_text = match.group(2)
            number = int(number_text)
            next_number = number + 1

            if number_text.startswith("0"):
                next_number_text = str(next_number).zfill(len(number_text))
            else:
                next_number_text = str(next_number)

            start, end = match.span(2)
            return current_url[:start] + next_number_text + current_url[end:]

    return None


def set_chapter_number_in_url(url, target_number):
    patterns = [
        r"(chapter[-_/]?)(\d+)(/?$)",
        r"(\D)(\d+)(/?$)"
    ]

    for pattern in patterns:
        match = re.search(pattern, url, re.I)

        if match:
            number_text = match.group(2)

            if number_text.startswith("0"):
                target_text = str(target_number).zfill(len(number_text))
            else:
                target_text = str(target_number)

            start, end = match.span(2)
            return url[:start] + target_text + url[end:]

    return None


def is_royalroad_url(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    return domain.endswith("royalroad.com")


def royalroad_fiction_url_from_any_url(url):
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]

    if len(parts) >= 3 and parts[0] == "fiction":
        fiction_id = parts[1]
        fiction_slug = parts[2]
        return f"{parsed.scheme}://{parsed.netloc}/fiction/{fiction_id}/{fiction_slug}"

    return None


def extract_chapter_number_from_text_or_url(text, url):
    combined = f"{text} {url}".lower()

    patterns = [
        r"\bchapter\s+(\d+)\b",
        r"\bch\.?\s*(\d+)\b",
        r"chapter[-_](\d+)\b"
    ]

    for pattern in patterns:
        match = re.search(pattern, combined, re.I)

        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None

    return None


def get_royalroad_chapter_links(source_url):
    fiction_url = royalroad_fiction_url_from_any_url(source_url)

    if not fiction_url:
        return []

    if fiction_url in ROYALROAD_CACHE:
        return ROYALROAD_CACHE[fiction_url]

    print(f"RoyalRoad detected. Fetching chapter list from: {fiction_url}")

    html = fetch_page(fiction_url)
    soup = BeautifulSoup(html, "lxml")

    chapter_links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()

        if "/chapter/" not in href:
            continue

        full_url = urljoin(fiction_url, href)
        normalized = full_url.rstrip("/")

        if normalized in seen:
            continue

        seen.add(normalized)

        text = clean_text(a.get_text(" "))
        chapter_number = extract_chapter_number_from_text_or_url(text, full_url)

        chapter_links.append({
            "url": full_url,
            "normalized_url": normalized,
            "text": text,
            "chapter_number": chapter_number
        })

    print(f"Found {len(chapter_links)} RoyalRoad chapter links.")

    ROYALROAD_CACHE[fiction_url] = chapter_links
    return chapter_links


def find_royalroad_chapter_url(source_url, target_chapter):
    chapter_links = get_royalroad_chapter_links(source_url)

    if not chapter_links:
        return None

    for item in chapter_links:
        if item.get("chapter_number") == target_chapter:
            print(f"Matched RoyalRoad chapter {target_chapter}: {item['url']}")
            return item["url"]

    index = target_chapter - 1

    if 0 <= index < len(chapter_links):
        guessed = chapter_links[index]["url"]
        print(f"Using RoyalRoad chapter list position {target_chapter}: {guessed}")
        return guessed

    print(f"RoyalRoad chapter {target_chapter} not found in chapter list.")
    return None


def find_next_link(soup, current_url, next_chapter_number=None):
    # RoyalRoad uses unique chapter IDs, so use the fiction chapter list.
    if is_royalroad_url(current_url) and next_chapter_number:
        royalroad_next = find_royalroad_chapter_url(current_url, next_chapter_number)

        if royalroad_next:
            return royalroad_next

    # 1. Standard HTML rel="next"
    rel_next = soup.find("a", rel=lambda value: value and "next" in value)

    if rel_next and rel_next.get("href"):
        next_url = urljoin(current_url, rel_next.get("href"))

        if next_url != current_url:
            return next_url

    # 2. Common next-button selectors used by novel websites including NovelFull.
    next_selectors = [
        "a#next_chap",
        "a.next",
        "a.nextchap",
        "a.next-chapter",
        "a[title*='Next']",
        "a[title*='next']",
        "li.next a",
        ".next a",
        ".next-chapter a",
        ".chapter-next a",
        ".chapter-nav a.next",
        ".chapter-nav .next a",
        ".nav-next a",
        ".btn-next",
        "a.btn-next",
        "a[class*='next']",
        "a[id*='next']"
    ]

    for selector in next_selectors:
        item = soup.select_one(selector)

        if item and item.get("href"):
            next_url = urljoin(current_url, item.get("href"))

            if next_url != current_url:
                print(f"Found next chapter using selector {selector}: {next_url}")
                return next_url

    links = soup.find_all("a", href=True)

    next_words = [
        "next chapter",
        "next",
        "›",
        "»",
        "older",
        "continue",
        "forward"
    ]

    # 3. Search all links by text, aria-label, title, class and href.
    for a in links:
        text = clean_text(a.get_text(" ")).lower()
        href = a.get("href", "")
        aria = clean_text(a.get("aria-label", "")).lower()
        title = clean_text(a.get("title", "")).lower()
        css_class = " ".join(a.get("class", [])).lower()
        element_id = clean_text(a.get("id", "")).lower()

        combined = " ".join([text, aria, title, css_class, element_id, href.lower()])

        if any(word in combined for word in next_words):
            next_url = urljoin(current_url, href)

            if next_url != current_url:
                print(f"Found next chapter by link text/class/title: {next_url}")
                return next_url

    # 4. NovelFull fallback:
    # Current URL may look like:
    # /against-the-gods/chapter-52-title.html
    # The next chapter has a different slug, so we cannot simply replace the whole URL.
    # But if the page contains any link with /chapter-53- in href, use it.
    if next_chapter_number:
        chapter_patterns = [
            f"chapter-{next_chapter_number}-",
            f"chapter-{next_chapter_number}.",
            f"chapter_{next_chapter_number}_",
            f"chapter/{next_chapter_number}",
            f"chapter-{next_chapter_number}"
        ]

        for a in links:
            href = a.get("href", "").lower()

            if any(pattern in href for pattern in chapter_patterns):
                next_url = urljoin(current_url, a.get("href"))

                if next_url != current_url:
                    print(f"Found next chapter by chapter number {next_chapter_number}: {next_url}")
                    return next_url

    # 5. Simple numeric URL fallback.
    # This works only for URLs like chapter-52 or chapter/52.
    fallback_url = increment_chapter_url(current_url)

    if fallback_url and fallback_url != current_url:
        print(f"No next button found. Trying URL fallback: {fallback_url}")
        return fallback_url

    print("No next chapter link found.")
    return None


def create_epub(novel_title, chapters, start_chapter, end_chapter, cover_path="covers/default.svg"):
    EPUB_DIR.mkdir(parents=True, exist_ok=True)

    safe_title = slugify(novel_title) or "novel"
    filename = f"{safe_title}_ch{start_chapter:03d}-{end_chapter:03d}.epub"
    output_path = EPUB_DIR / filename

    book = epub.EpubBook()
    book.set_identifier(f"{safe_title}-{start_chapter}-{end_chapter}")
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
        chapter_title = chapter["title"]
        paragraphs = chapter["paragraphs"]

        html = f"<h1>{chapter_title}</h1>"
        html += f"<p><em>Original URL: {chapter['url']}</em></p>"

        for para in paragraphs:
            html += f"<p>{para}</p>"

        epub_chapter = epub.EpubHtml(
            title=chapter_title,
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


def load_library():
    if LIBRARY_FILE.exists():
        try:
            library = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            library = []
    else:
        library = []

    if not isinstance(library, list):
        library = []

    return library


def save_library(library):
    DOCS_DIR.mkdir(exist_ok=True)

    LIBRARY_FILE.write_text(
        json.dumps(library, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def find_existing_library_item(library, novel_title):
    safe_title = slugify(novel_title) or "novel"
    wanted_title = clean_text(novel_title).lower()

    for item in library:
        if item.get("slug") == safe_title:
            return item

    for item in library:
        if clean_text(item.get("title", "")).lower() == wanted_title:
            return item

    return None


def save_locked_notice_to_library(
    novel_title,
    source_url,
    locked_chapter_number,
    locked_chapter_url,
    locked_reason
):
    if not locked_chapter_number:
        return

    library = load_library()
    item = find_existing_library_item(library, novel_title)

    if not item:
        safe_title = slugify(novel_title) or "novel"
        site_name = detect_site_name(source_url)

        item = {
            "title": novel_title,
            "slug": safe_title,
            "site": site_name,
            "cover": "covers/default.svg",
            "chapters": max(0, int(locked_chapter_number) - 1),
            "source_url": source_url,
            "next_url": locked_chapter_url or "",
            "last_chapter_url": "",
            "last_chapter_number": max(0, int(locked_chapter_number) - 1),
            "status": "Partial / locked",
            "last_mode": "Locked check",
            "created_at": now_iso(),
            "last_updated": now_iso(),
            "progress_state": "locked",
            "progress_reason": locked_reason or "Source requires login/unlock",
            "source_history": [
                {
                    "site": site_name,
                    "url": source_url,
                    "used_from_chapter": max(1, int(locked_chapter_number)),
                    "used_until_chapter": max(0, int(locked_chapter_number) - 1),
                    "updated_at": now_iso()
                }
            ],
            "downloads": []
        }

        library.append(item)

    item["status"] = "Partial / locked"
    item["last_updated"] = now_iso()
    item["progress_state"] = "locked"
    item["progress_reason"] = locked_reason or "Source requires login/unlock"
    item["locked_chapter_number"] = locked_chapter_number
    item["locked_chapter_url"] = locked_chapter_url or ""
    item["locked_reason"] = locked_reason or "Source requires login/unlock"

    if locked_chapter_url:
        item["next_url"] = locked_chapter_url

    history = item.setdefault("source_history", [])
    history.append({
        "site": detect_site_name(source_url),
        "url": source_url,
        "used_from_chapter": max(1, int(locked_chapter_number)),
        "used_until_chapter": max(0, int(locked_chapter_number) - 1),
        "updated_at": now_iso()
    })

    library.sort(key=lambda x: x.get("title", "").lower())
    save_library(library)


def get_last_downloaded_chapter(library_item):
    downloads = library_item.get("downloads", [])

    if not downloads:
        return int(library_item.get("chapters", 0) or 0)

    max_end = 0

    for download in downloads:
        try:
            max_end = max(max_end, int(download.get("end", 0)))
        except Exception:
            continue

    return max_end


def resolve_existing_novel_start(library_item):
    title = library_item.get("title", "Untitled Novel")
    last_chapter = get_last_downloaded_chapter(library_item)

    if last_chapter <= 0:
        raise ValueError(f"{title}: no valid downloaded chapter range found.")

    next_chapter = last_chapter + 1

    stored_next_url = library_item.get("next_url", "").strip()

    if stored_next_url:
        print(f"{title}: using stored next_url for chapter {next_chapter}.")
        return stored_next_url, next_chapter

    source_url = library_item.get("source_url", "").strip()

    if source_url and is_royalroad_url(source_url):
        royalroad_url = find_royalroad_chapter_url(source_url, next_chapter)

        if royalroad_url:
            return royalroad_url, next_chapter

    last_chapter_url = library_item.get("last_chapter_url", "").strip()

    if last_chapter_url:
        try:
            html = fetch_page(last_chapter_url)
            soup = BeautifulSoup(html, "lxml")
            next_url = find_next_link(soup, last_chapter_url, next_chapter)

            if next_url:
                return next_url, next_chapter
        except Exception as exc:
            print(f"Could not use last_chapter_url for {title}: {exc}")

    if source_url:
        calculated_url = set_chapter_number_in_url(source_url, next_chapter)

        if calculated_url:
            return calculated_url, next_chapter

    raise ValueError(
        f"{title}: could not find next URL for chapter {next_chapter}. "
        "Run a normal update once with the correct next chapter link, or add next_url manually."
    )


def update_library(
    novel_title,
    start_chapter,
    end_chapter,
    epub_path,
    source_url,
    cover_path,
    next_url,
    last_chapter_url,
    mode,
    status,
    locked_chapter_number=None,
    locked_chapter_url=None,
    locked_reason=""
):
    library = load_library()

    safe_title = slugify(novel_title) or "novel"
    relative_epub = str(epub_path.relative_to(DOCS_DIR)).replace("\\", "/")
    site_name = detect_site_name(source_url)

    download_item = {
        "label": f"Chapters {start_chapter}-{end_chapter}",
        "start": start_chapter,
        "end": end_chapter,
        "url": relative_epub,
        "mode": mode,
        "created_at": now_iso()
    }

    existing = None

    for item in library:
        if item.get("slug") == safe_title:
            existing = item
            break

    if existing:
        downloads = existing.setdefault("downloads", [])

        if not any(d.get("url") == relative_epub for d in downloads):
            downloads.append(download_item)

        downloads.sort(key=lambda d: int(d.get("start", 0)))

        existing["chapters"] = max(int(existing.get("chapters", 0)), end_chapter)
        existing["source_url"] = source_url or existing.get("source_url", "")
        existing["last_successful_source_url"] = source_url or existing.get("last_successful_source_url", "")
        existing["last_successful_site"] = site_name
        existing["site"] = site_name
        existing["status"] = status
        existing["last_mode"] = mode
        existing["last_updated"] = now_iso()
        existing["last_chapter_number"] = end_chapter
        existing["progress_state"] = (
            "locked" if locked_chapter_number else
            "complete" if not next_url else
            "available"
        )
        existing["progress_reason"] = locked_reason or ""

        history = existing.setdefault("source_history", [])
        history.append({
            "site": site_name,
            "url": source_url,
            "used_from_chapter": start_chapter,
            "used_until_chapter": end_chapter,
            "updated_at": now_iso()
        })

        if locked_chapter_number:
            existing["locked_chapter_number"] = locked_chapter_number
            existing["locked_chapter_url"] = locked_chapter_url or ""
            existing["locked_reason"] = locked_reason or "Source requires login/unlock"
        else:
            existing.pop("locked_chapter_number", None)
            existing.pop("locked_chapter_url", None)
            existing.pop("locked_reason", None)

        if last_chapter_url:
            existing["last_chapter_url"] = last_chapter_url

        if next_url:
            existing["next_url"] = next_url
        else:
            existing.pop("next_url", None)

        if cover_path and cover_path != "covers/default.svg":
            existing["cover"] = cover_path

    else:
        new_item = {
            "title": novel_title,
            "slug": safe_title,
            "site": site_name,
            "cover": cover_path,
            "chapters": end_chapter,
            "source_url": source_url,
            "next_url": next_url or "",
            "last_chapter_url": last_chapter_url or "",
            "last_chapter_number": end_chapter,
            "status": status,
            "last_mode": mode,
            "created_at": now_iso(),
            "last_updated": now_iso(),
            "progress_state": (
                "locked" if locked_chapter_number else
                "complete" if not next_url else
                "available"
            ),
            "progress_reason": locked_reason or "",
            "last_successful_source_url": source_url,
            "last_successful_site": site_name,
            "source_history": [
                {
                    "site": site_name,
                    "url": source_url,
                    "used_from_chapter": start_chapter,
                    "used_until_chapter": end_chapter,
                    "updated_at": now_iso()
                }
            ],
            "downloads": [download_item]
        }

        if locked_chapter_number:
            new_item["locked_chapter_number"] = locked_chapter_number
            new_item["locked_chapter_url"] = locked_chapter_url or ""
            new_item["locked_reason"] = locked_reason or "Source requires login/unlock"

        library.append(new_item)

    library.sort(key=lambda item: item.get("title", "").lower())
    save_library(library)


def build_novel(start_url, novel_title, start_chapter, chapters_per_epub, max_batches, request_delay, mode):
    current_url = start_url
    current_chapter_number = start_chapter

    existing_library = load_library()
    existing_item = find_existing_library_item(existing_library, novel_title)

    if existing_item:
        last_downloaded = get_last_downloaded_chapter(existing_item)

        saved_next_url = str(existing_item.get("next_url", "")).strip()
        existing_source_url = str(existing_item.get("source_url", "")).strip()
        incoming_url = str(start_url or "").strip()

        manual_source_switch = False

        if incoming_url:
            if saved_next_url and incoming_url != saved_next_url:
                manual_source_switch = True

            if existing_source_url and incoming_url != existing_source_url:
                manual_source_switch = True

        if manual_source_switch:
            print("=" * 80)
            print("Manual source switch detected")
            print(f"Novel: {novel_title}")
            print(f"Existing source_url: {existing_source_url}")
            print(f"Saved next_url: {saved_next_url}")
            print(f"New source URL supplied: {incoming_url}")
            print("=" * 80)

        if last_downloaded and start_chapter <= last_downloaded:
            if manual_source_switch and incoming_url:
                print("=" * 80)
                print("Duplicate / overlap detected, but manual source switch was supplied.")
                print(f"Novel: {novel_title}")
                print(f"Requested start chapter: {start_chapter}")
                print(f"Already downloaded up to: {last_downloaded}")
                print(f"Continuing as chapter: {last_downloaded + 1}")
                print(f"Using manually supplied URL: {incoming_url}")
                print("=" * 80)

                current_url = incoming_url
                current_chapter_number = last_downloaded + 1
                start_chapter = current_chapter_number

            elif saved_next_url:
                print("=" * 80)
                print("Duplicate / overlap detected")
                print(f"Novel: {novel_title}")
                print(f"Requested start chapter: {start_chapter}")
                print(f"Already downloaded up to: {last_downloaded}")
                print(f"Switching to chapter: {last_downloaded + 1}")
                print(f"Using saved next_url: {saved_next_url}")
                print("=" * 80)

                current_url = saved_next_url
                current_chapter_number = last_downloaded + 1
                start_chapter = current_chapter_number

            else:
                print("=" * 80)
                print("Duplicate / overlap detected, but no saved next_url exists.")
                print(f"Novel: {novel_title}")
                print(f"Requested start chapter: {start_chapter}")
                print(f"Already downloaded up to: {last_downloaded}")
                print("Stopping to avoid creating duplicate EPUBs.")
                print("=" * 80)

                return {
                    "files": [],
                    "next_url": "",
                    "last_chapter_url": existing_item.get("last_chapter_url", ""),
                    "reached_end": False,
                    "locked_chapter_number": None,
                    "locked_chapter_url": None,
                    "locked_reason": "",
                    "skipped_duplicate": True,
                    "duplicate_message": (
                        f"Requested chapter {start_chapter}, but this novel is already "
                        f"downloaded up to chapter {last_downloaded}."
                    ),
                    "library_updated": False,
                    "error": ""
                }

        elif manual_source_switch and incoming_url:
            print("=" * 80)
            print("Manual source switch accepted")
            print(f"Novel: {novel_title}")
            print(f"Starting chapter: {start_chapter}")
            print(f"Using manually supplied URL: {incoming_url}")
            print("=" * 80)

            current_url = incoming_url
            current_chapter_number = start_chapter

    detected_title = None
    detected_cover_url = None
    cover_path = str(existing_item.get("cover", "covers/default.svg")).strip() if existing_item else "covers/default.svg"
    created_files = []
    last_next_url = None
    last_chapter_url = None
    reached_end = False
    locked_chapter_number = None
    locked_chapter_url = None
    locked_reason = ""

    for batch_index in range(max_batches):
        batch_start = current_chapter_number
        batch_chapters = []

        print("=" * 80)
        print(f"Novel: {novel_title}")
        print(f"Mode: {mode}")
        print(f"Starting EPUB batch {batch_index + 1}/{max_batches}")
        print(f"Batch starts at chapter {batch_start}")
        print(f"Chapters per EPUB: {chapters_per_epub}")
        print("=" * 80)

        for _ in range(chapters_per_epub):
            chapter_number = current_chapter_number

            if not current_url:
                print("No current URL available. Stopping.")
                reached_end = True
                break

            print(f"Fetching chapter {chapter_number}: {current_url}")

            try:
                html = fetch_page(current_url)
            except Exception as exc:
                print(f"Failed to fetch chapter {chapter_number}: {exc}")
                current_url = None
                reached_end = True
                break

            soup = BeautifulSoup(html, "lxml")

            locked_info = detect_locked_or_partial_page(soup)

            if locked_info["locked"]:
                print("=" * 80)
                print("LOCKED OR PARTIAL CHAPTER DETECTED")
                print(f"Chapter: {chapter_number}")
                print(f"URL: {current_url}")
                print(f"Reason: {locked_info['reason']}")
                print("=" * 80)

            if not detected_title:
                detected_title = detect_novel_title(soup, current_url)

            if cover_path == "covers/default.svg" and not detected_cover_url:
                detected_cover_url = find_cover_url(soup, current_url)

                if detected_cover_url:
                    title_for_cover = novel_title or detected_title or "Online Novel"
                    cover_path = download_cover(detected_cover_url, title_for_cover)

            chapter_title = get_page_title(soup)

            # IMPORTANT:
            # Find the next chapter link BEFORE extracting content.
            # extract_chapter_content() removes navigation/buttons from the soup.
            # On NovelFull, the next chapter link can be removed before find_next_link() sees it.
            next_url = find_next_link(
                soup=soup,
                current_url=current_url,
                next_chapter_number=current_chapter_number + 1
            )

            paragraphs = extract_chapter_content(soup)

            if locked_info["locked"]:
                print(
                    f"Chapter {chapter_number} appears locked/partial. "
                    "Stopping before adding this chapter as a normal full chapter."
                )

                locked_chapter_number = chapter_number
                locked_chapter_url = current_url
                locked_reason = locked_info["reason"]

                save_locked_notice_to_library(
                    novel_title=novel_title or detected_title or "Online Novel",
                    source_url=start_url,
                    locked_chapter_number=locked_chapter_number,
                    locked_chapter_url=locked_chapter_url,
                    locked_reason=locked_reason
                )

                current_url = None
                reached_end = True
                break

            if not paragraphs:
                print(f"No readable content found for chapter {chapter_number}. Stopping.")
                current_url = None
                reached_end = True
                break

            batch_chapters.append({
                "number": chapter_number,
                "url": current_url,
                "title": chapter_title,
                "paragraphs": paragraphs
            })

            last_chapter_url = current_url

            if not next_url:
                print("No next chapter link found after this chapter. Ending current batch.")
                current_url = None
                last_next_url = None
                reached_end = True
                break

            current_url = next_url
            last_next_url = next_url
            current_chapter_number += 1

            time.sleep(request_delay)

        if not batch_chapters:
            print("No chapters collected in this batch. Stopping.")
            break

        final_title = novel_title or detected_title or "Online Novel"
        batch_end = batch_start + len(batch_chapters) - 1

        if locked_chapter_number:
            status = "Partial / locked"
        elif reached_end:
            status = "Complete or stopped at source"
        elif len(batch_chapters) < chapters_per_epub:
            status = "Partial"
        else:
            status = "Built"

        epub_path = create_epub(
            final_title,
            batch_chapters,
            batch_start,
            batch_end,
            cover_path=cover_path
        )

        update_library(
            novel_title=final_title,
            start_chapter=batch_start,
            end_chapter=batch_end,
            epub_path=epub_path,
            source_url=start_url,
            cover_path=cover_path,
            next_url=last_next_url,
            last_chapter_url=last_chapter_url,
            mode=mode,
            status=status,
            locked_chapter_number=locked_chapter_number,
            locked_chapter_url=locked_chapter_url,
            locked_reason=locked_reason
        )

        created_files.append(str(epub_path))
        print(f"Created EPUB: {epub_path}")

        if current_url is None:
            print("No more chapters available. Finished.")
            break

    error_message = ""

    if not created_files and not locked_chapter_number:
        error_message = (
            "No EPUB files were created. The source may be blocked, forbidden, unsupported, "
            "or no readable chapter content was found."
        )

    return {
        "files": created_files,
        "next_url": last_next_url,
        "last_chapter_url": last_chapter_url,
        "reached_end": reached_end,
        "locked_chapter_number": locked_chapter_number,
        "locked_chapter_url": locked_chapter_url,
        "locked_reason": locked_reason,
        "skipped_duplicate": False,
        "duplicate_message": "",
        "library_updated": bool(created_files or locked_chapter_number),
        "error": error_message
    }


def get_limits_for_mode(mode, overrides=None):
    overrides = overrides or {}

    if mode == "Update All Existing Novels":
        chapters_per_epub = int(SETTINGS.get("update_all_chapters_per_epub", 10))
        max_batches = int(SETTINGS.get("update_all_max_batches", 1))
    else:
        chapters_per_epub = int(SETTINGS.get("normal_chapters_per_epub", 10))
        max_batches = int(SETTINGS.get("normal_max_batches", 1))

    request_delay = float(SETTINGS.get("request_delay_seconds", 1.5))

    override_chapters = overrides.get("chapters_per_epub")
    override_batches = overrides.get("max_batches")

    if override_chapters is not None:
        chapters_per_epub = int(override_chapters)

    if override_batches is not None:
        max_batches = int(override_batches)

    if chapters_per_epub < 1:
        chapters_per_epub = 1

    if max_batches < 1:
        max_batches = 1

    if request_delay < 0:
        request_delay = 0

    return chapters_per_epub, max_batches, request_delay


def build_update_all_existing(chapters_per_epub, max_batches, request_delay):
    library = load_library()

    if not library:
        raise ValueError("docs/library.json is empty. No novels to update.")

    results = []

    for item in library:
        title = item.get("title", "").strip()

        if not title:
            continue

        print("#" * 80)
        print(f"Updating existing novel: {title}")
        print("#" * 80)

        try:
            start_url, start_chapter = resolve_existing_novel_start(item)

            build_result = build_novel(
                start_url=start_url,
                novel_title=title,
                start_chapter=start_chapter,
                chapters_per_epub=chapters_per_epub,
                max_batches=max_batches,
                request_delay=request_delay,
                mode="Update All Existing Novels"
            )

            result_status = "success"

            if not build_result.get("files") and not build_result.get("skipped_duplicate") and not build_result.get("locked_chapter_number"):
                result_status = "failed"

            if build_result.get("skipped_duplicate"):
                result_status = "skipped_duplicate"

            if build_result.get("locked_chapter_number"):
                result_status = "partial_locked"

            results.append({
                "title": title,
                "status": result_status,
                "start_chapter": start_chapter,
                "files": build_result["files"],
                "next_url": build_result["next_url"],
                "last_chapter_url": build_result["last_chapter_url"],
                "reached_end": build_result["reached_end"],
                "locked_chapter_number": build_result.get("locked_chapter_number"),
                "locked_chapter_url": build_result.get("locked_chapter_url"),
                "locked_reason": build_result.get("locked_reason"),
                "skipped_duplicate": build_result.get("skipped_duplicate", False),
                "duplicate_message": build_result.get("duplicate_message", ""),
                "library_updated": build_result.get("library_updated", False),
                "error": build_result.get("error", "")
            })

        except Exception as exc:
            print(f"Failed to update {title}: {exc}")
            traceback.print_exc()

            results.append({
                "title": title,
                "status": "failed",
                "error": str(exc)
            })

    return results


def main():
    if not REQUEST_FILE.exists():
        raise SystemExit("Missing data/epub_manager_request.json")

    request = json.loads(REQUEST_FILE.read_text(encoding="utf-8"))

    mode = request.get("mode", "New Novel")
    items = request.get("items", [])
    overrides = request.get("overrides", {})

    chapters_per_epub, max_batches, request_delay = get_limits_for_mode(
        mode,
        overrides
    )

    print("=" * 80)
    print("Runtime settings")
    print(f"Mode: {mode}")
    print(f"Chapters per EPUB: {chapters_per_epub}")
    print(f"Max batches: {max_batches}")
    print(f"Request delay seconds: {request_delay}")
    print("=" * 80)

    if mode == "Update All Existing Novels":
        results = build_update_all_existing(
            chapters_per_epub=chapters_per_epub,
            max_batches=max_batches,
            request_delay=request_delay
        )
    else:
        if not isinstance(items, list) or not items:
            raise SystemExit("No items found in request.")

        results = []

        for index, item in enumerate(items, start=1):
            start_url = item.get("start_url", "").strip()
            novel_title = item.get("novel_title", "").strip()
            start_chapter = int(item.get("start_chapter", 1))

            print("=" * 80)
            print(f"Processing item {index}/{len(items)}")
            print(f"Mode: {mode}")
            print(f"Title: {novel_title}")
            print(f"Start URL: {start_url}")
            print(f"Start chapter: {start_chapter}")
            print("=" * 80)

            if not start_url:
                results.append({
                    "title": novel_title,
                    "status": "failed",
                    "error": "Missing start URL"
                })
                continue

            try:
                build_result = build_novel(
                    start_url=start_url,
                    novel_title=novel_title,
                    start_chapter=start_chapter,
                    chapters_per_epub=chapters_per_epub,
                    max_batches=max_batches,
                    request_delay=request_delay,
                    mode=mode
                )

                result_status = "success"

                if not build_result.get("files") and not build_result.get("skipped_duplicate") and not build_result.get("locked_chapter_number"):
                    result_status = "failed"

                if build_result.get("skipped_duplicate"):
                    result_status = "skipped_duplicate"

                if build_result.get("locked_chapter_number"):
                    result_status = "partial_locked"

                results.append({
                    "title": novel_title,
                    "start_url": start_url,
                    "start_chapter": start_chapter,
                    "status": result_status,
                    "mode": mode,
                    "files": build_result["files"],
                    "next_url": build_result["next_url"],
                    "last_chapter_url": build_result["last_chapter_url"],
                    "reached_end": build_result["reached_end"],
                    "locked_chapter_number": build_result.get("locked_chapter_number"),
                    "locked_chapter_url": build_result.get("locked_chapter_url"),
                    "locked_reason": build_result.get("locked_reason"),
                    "skipped_duplicate": build_result.get("skipped_duplicate", False),
                    "duplicate_message": build_result.get("duplicate_message", ""),
                    "error": build_result.get("error", "")
                })

            except Exception as exc:
                print(f"Failed to build {novel_title}: {exc}")
                traceback.print_exc()

                results.append({
                    "title": novel_title,
                    "start_url": start_url,
                    "status": "failed",
                    "mode": mode,
                    "error": str(exc)
                })

    Path("data/epub_manager_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Results:")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    successful = [
        r for r in results
        if r.get("status") in ["success", "skipped_duplicate"]
        or (r.get("status") == "partial_locked" and r.get("library_updated"))
    ]

    if not successful:
        raise SystemExit("All EPUB builds failed.")


if __name__ == "__main__":
    main()
