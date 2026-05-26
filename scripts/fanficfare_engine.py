import json
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from ebooklib import epub, ITEM_DOCUMENT
from slugify import slugify


ROOT = Path(".")
DOCS_DIR = ROOT / "docs"
EPUB_DIR = DOCS_DIR / "epubs"
LIBRARY_FILE = DOCS_DIR / "library.json"
TEMP_DIR = ROOT / "data" / "fanficfare_tmp"


def now_ts():
    return int(time.time())


def now_iso_like():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clean_text(value):
    return str(value or "").strip()


def detect_site_name(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    known_sites = {
        "archiveofourown.org": "Archive of Our Own",
        "fanfiction.net": "FanFiction.Net",
        "fictionpress.com": "FictionPress",
        "royalroad.com": "RoyalRoad",
        "scribblehub.com": "ScribbleHub",
        "wattpad.com": "Wattpad",
        "fimfiction.net": "Fimfiction",
        "spacebattles.com": "SpaceBattles",
        "forums.spacebattles.com": "SpaceBattles",
        "sufficientvelocity.com": "SufficientVelocity",
        "forums.sufficientvelocity.com": "SufficientVelocity",
        "questionablequesting.com": "QuestionableQuesting",
        "forum.questionablequesting.com": "QuestionableQuesting",
        "alternatehistory.com": "AlternateHistory",
        "althistory.com": "AlternateHistory",
        "the-sietch.com": "The Sietch",
        "storiesonline.net": "StoriesOnline",
        "syosetu.com": "Syosetu",
        "ncode.syosetu.com": "Syosetu",
        "novel18.syosetu.com": "Syosetu",
        "squidgeworld.org": "SquidgeWorld",
        "cfaarchive.org": "CFA Archive",
        "adastrafanfic.com": "Ad Astra Fanfic",
        "tthfanfic.org": "TTHFanfic",
        "asianfanfics.com": "AsianFanfics",
        "fanficauthors.net": "FanficAuthors",
        "fanfiktion.de": "Fanfiktion.de",
        "fanfictions.fr": "Fanfictions.fr",
        "fictionhunt.com": "FictionHunt",
        "ficbook.net": "Ficbook",
        "quotev.com": "Quotev",
        "kakuyomu.jp": "Kakuyomu",
        "literotica.com": "Literotica"
    }

    for key, name in known_sites.items():
        if domain == key or domain.endswith("." + key):
            return name

    parts = domain.split(".")

    if len(parts) >= 2:
        return parts[-2].replace("-", " ").replace("_", " ").title()

    return domain.title() or "Unknown"


def load_library():
    if not LIBRARY_FILE.exists():
        return []

    try:
        data = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(data, list):
        return data

    return []


def save_library(library):
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_FILE.write_text(
        json.dumps(library, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def count_epub_documents(epub_path):
    try:
        book = epub.read_epub(str(epub_path))
        count = 0

        for item in book.get_items_of_type(ITEM_DOCUMENT):
            name = str(item.get_name()).lower()

            if "nav" in name or "toc" in name or "cover" in name:
                continue

            count += 1

        return count
    except Exception:
        return 0


def run_fanficfare(url, work_dir, begin_chapter, end_chapter):
    command = [
        "fanficfare",
        "--non-interactive",
        "-f",
        "epub",
        "-b",
        str(begin_chapter),
        "-e",
        str(end_chapter),
        url
    ]

    print("Running FanFicFare command:")
    print(" ".join(command))

    result = subprocess.run(
        command,
        cwd=str(work_dir),
        text=True,
        capture_output=True,
        timeout=1800
    )

    return result


def find_created_epub(work_dir):
    epubs = sorted(
        work_dir.glob("*.epub"),
        key=lambda path: path.stat().st_mtime,
        reverse=True
    )

    if not epubs:
        return None

    return epubs[0]


def update_library_for_fanficfare(
    novel_title,
    source_url,
    output_path,
    start_chapter,
    end_chapter,
    chapter_count,
    status
):
    library = load_library()

    safe_title = slugify(novel_title) or "fanficfare-story"
    site_name = detect_site_name(source_url)
    relative_epub = str(output_path.relative_to(DOCS_DIR)).replace("\\", "/")

    download_item = {
        "label": f"Chapters {start_chapter}-{end_chapter}",
        "start": start_chapter,
        "end": end_chapter,
        "url": relative_epub,
        "mode": "FanFicFare",
        "created_at": now_iso_like()
    }

    existing = None

    for item in library:
        if item.get("slug") == safe_title:
            existing = item
            break

    if existing:
        downloads = existing.setdefault("downloads", [])

        matching = None

        for download in downloads:
            if download.get("url") == relative_epub:
                matching = download
                break

        if matching:
            matching.update(download_item)
        else:
            downloads.append(download_item)

        downloads.sort(key=lambda d: int(d.get("start", 0)))

        existing["title"] = existing.get("title") or novel_title
        existing["site"] = site_name
        existing["status"] = status
        existing["last_mode"] = "FanFicFare"
        existing["last_updated"] = now_iso_like()
        existing["source_url"] = source_url
        existing["chapters"] = max(int(existing.get("chapters", 0) or 0), end_chapter)
        existing["last_chapter_number"] = max(
            int(existing.get("last_chapter_number", 0) or 0),
            end_chapter
        )

        existing.pop("locked_chapter_number", None)
        existing.pop("locked_chapter_url", None)
        existing.pop("locked_reason", None)

        if not existing.get("cover"):
            existing["cover"] = "covers/default.svg"

    else:
        library.append({
            "title": novel_title,
            "slug": safe_title,
            "site": site_name,
            "cover": "covers/default.svg",
            "chapters": end_chapter,
            "source_url": source_url,
            "next_url": "",
            "last_chapter_url": "",
            "last_chapter_number": end_chapter,
            "status": status,
            "last_mode": "FanFicFare",
            "created_at": now_iso_like(),
            "last_updated": now_iso_like(),
            "downloads": [download_item]
        })

    library.sort(key=lambda item: item.get("title", "").lower())
    save_library(library)


def download_one_fanficfare_batch(
    source_url,
    novel_title,
    batch_start,
    batch_end,
    batch_index
):
    safe_title = slugify(novel_title) or "fanficfare-story"
    work_dir = TEMP_DIR / f"{safe_title}-{batch_start}-{batch_end}-{now_ts()}"

    if work_dir.exists():
        shutil.rmtree(work_dir)

    work_dir.mkdir(parents=True, exist_ok=True)
    EPUB_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("FanFicFare engine batch")
    print(f"Title: {novel_title}")
    print(f"URL: {source_url}")
    print(f"Batch index: {batch_index}")
    print(f"Chapter range: {batch_start}-{batch_end}")
    print("=" * 80)

    try:
        result = run_fanficfare(
            url=source_url,
            work_dir=work_dir,
            begin_chapter=batch_start,
            end_chapter=batch_end
        )

        print("FanFicFare STDOUT:")
        print(result.stdout)

        print("FanFicFare STDERR:")
        print(result.stderr)

        if result.returncode != 0:
            return {
                "title": novel_title,
                "status": "failed",
                "engine": "fanficfare",
                "start_url": source_url,
                "start_chapter": batch_start,
                "end_chapter": batch_end,
                "error": result.stderr.strip() or result.stdout.strip() or "FanFicFare failed"
            }

        created_epub = find_created_epub(work_dir)

        if not created_epub:
            return {
                "title": novel_title,
                "status": "failed",
                "engine": "fanficfare",
                "start_url": source_url,
                "start_chapter": batch_start,
                "end_chapter": batch_end,
                "error": "FanFicFare completed but no EPUB file was created"
            }

        output_path = EPUB_DIR / f"{safe_title}_ch{batch_start:03d}-{batch_end:03d}_fanficfare.epub"

        if output_path.exists():
            output_path.unlink()

        shutil.move(str(created_epub), str(output_path))

        chapter_count = count_epub_documents(output_path)

        if chapter_count <= 0:
            return {
                "title": novel_title,
                "status": "failed",
                "engine": "fanficfare",
                "start_url": source_url,
                "start_chapter": batch_start,
                "end_chapter": batch_end,
                "error": "FanFicFare created an EPUB but no readable chapters were detected"
            }

        actual_end = batch_start + chapter_count - 1

        if actual_end > batch_end:
            actual_end = batch_end

        status = "Built with FanFicFare"

        if chapter_count < (batch_end - batch_start + 1):
            status = "Partial with FanFicFare"

        update_library_for_fanficfare(
            novel_title=novel_title,
            source_url=source_url,
            output_path=output_path,
            start_chapter=batch_start,
            end_chapter=actual_end,
            chapter_count=chapter_count,
            status=status
        )

        return {
            "title": novel_title,
            "status": "success",
            "engine": "fanficfare",
            "start_url": source_url,
            "start_chapter": batch_start,
            "end_chapter": actual_end,
            "requested_end_chapter": batch_end,
            "files": [str(output_path)],
            "chapters_detected": chapter_count,
            "message": "Built using FanFicFare chapter range"
        }

    except subprocess.TimeoutExpired:
        return {
            "title": novel_title,
            "status": "failed",
            "engine": "fanficfare",
            "start_url": source_url,
            "start_chapter": batch_start,
            "end_chapter": batch_end,
            "error": "FanFicFare timed out"
        }

    except Exception as exc:
        return {
            "title": novel_title,
            "status": "failed",
            "engine": "fanficfare",
            "start_url": source_url,
            "start_chapter": batch_start,
            "end_chapter": batch_end,
            "error": str(exc)
        }

    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)


def download_with_fanficfare(
    item,
    chapters_per_epub=10,
    max_batches=1
):
    source_url = clean_text(item.get("start_url"))
    novel_title = clean_text(item.get("novel_title")) or "FanFicFare Story"

    try:
        start_chapter = int(item.get("start_chapter", 1) or 1)
    except Exception:
        start_chapter = 1

    try:
        chapters_per_epub = int(chapters_per_epub or 10)
    except Exception:
        chapters_per_epub = 10

    try:
        max_batches = int(max_batches or 1)
    except Exception:
        max_batches = 1

    if chapters_per_epub < 1:
        chapters_per_epub = 1

    if max_batches < 1:
        max_batches = 1

    if not source_url:
        return {
            "title": novel_title,
            "status": "failed",
            "engine": "fanficfare",
            "error": "Missing source URL"
        }

    created_files = []
    batch_results = []
    last_successful_end = start_chapter - 1

    for batch_index in range(max_batches):
        batch_start = start_chapter + (batch_index * chapters_per_epub)
        batch_end = batch_start + chapters_per_epub - 1

        batch_result = download_one_fanficfare_batch(
            source_url=source_url,
            novel_title=novel_title,
            batch_start=batch_start,
            batch_end=batch_end,
            batch_index=batch_index + 1
        )

        batch_results.append(batch_result)

        if batch_result.get("status") != "success":
            if batch_index == 0:
                return batch_result

            return {
                "title": novel_title,
                "status": "success",
                "engine": "fanficfare",
                "start_url": source_url,
                "files": created_files,
                "start_chapter": start_chapter,
                "last_successful_chapter": last_successful_end,
                "batch_results": batch_results,
                "message": "Some FanFicFare batches completed before a later batch failed or reached the end."
            }

        files = batch_result.get("files", [])
        created_files.extend(files)

        last_successful_end = int(batch_result.get("end_chapter", batch_end))

        detected = int(batch_result.get("chapters_detected", 0) or 0)

        if detected < chapters_per_epub:
            break

    return {
        "title": novel_title,
        "status": "success",
        "engine": "fanficfare",
        "start_url": source_url,
        "files": created_files,
        "start_chapter": start_chapter,
        "last_successful_chapter": last_successful_end,
        "batch_results": batch_results,
        "message": "Built using FanFicFare with generic-style chapter batching"
    }
