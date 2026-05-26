import json
from pathlib import Path
from slugify import slugify


ROOT = Path(".")
REQUEST_FILE = ROOT / "data" / "epub_manager_request.json"
RESULTS_FILE = ROOT / "data" / "epub_manager_results.json"

DOCS_DIR = ROOT / "docs"
LIBRARY_FILE = DOCS_DIR / "library.json"


def load_json(path, fallback):
    if not path.exists():
        return fallback

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def normalise(value):
    return str(value or "").strip().lower()


def get_file_path_from_docs_url(url):
    if not url:
        return None

    url = str(url).strip()

    if url.startswith("http://") or url.startswith("https://"):
        return None

    clean_url = url.lstrip("/")

    return DOCS_DIR / clean_url


def main():
    if not REQUEST_FILE.exists():
        raise SystemExit("Missing data/epub_manager_request.json")

    request = load_json(REQUEST_FILE, {})
    delete_request = request.get("delete", {})

    novel_name = str(delete_request.get("novel_name", "")).strip()
    delete_files = str(delete_request.get("delete_files", "Yes")).strip().lower() in [
        "yes",
        "true",
        "1"
    ]

    if not novel_name:
        raise SystemExit("No novel name supplied for deletion.")

    library = load_json(LIBRARY_FILE, [])

    if not isinstance(library, list):
        raise SystemExit("docs/library.json must contain a list.")

    wanted_slug = slugify(novel_name)
    wanted_name = normalise(novel_name)

    target = None
    remaining = []

    for item in library:
        item_title = str(item.get("title", "")).strip()
        item_slug = str(item.get("slug", "")).strip()

        title_matches = normalise(item_title) == wanted_name
        slug_matches = item_slug == wanted_slug

        if target is None and (title_matches or slug_matches):
            target = item
        else:
            remaining.append(item)

    if target is None:
        result = {
            "mode": "Delete Novel",
            "status": "failed",
            "novel_name": novel_name,
            "error": "Novel not found in docs/library.json"
        }

        save_json(RESULTS_FILE, [result])
        raise SystemExit(result["error"])

    deleted_files = []
    skipped_files = []

    if delete_files:
        downloads = target.get("downloads", [])

        if isinstance(downloads, list):
            for download in downloads:
                file_path = get_file_path_from_docs_url(download.get("url"))

                if not file_path:
                    continue

                if file_path.exists() and file_path.is_file():
                    file_path.unlink()
                    deleted_files.append(str(file_path).replace("\\", "/"))
                else:
                    skipped_files.append(str(file_path).replace("\\", "/"))

        cover = str(target.get("cover", "")).strip()

        if cover and cover != "covers/default.svg":
            cover_path = DOCS_DIR / cover

            cover_is_used_by_other_novel = False

            for item in remaining:
                if str(item.get("cover", "")).strip() == cover:
                    cover_is_used_by_other_novel = True
                    break

            if cover_path.exists() and cover_path.is_file() and not cover_is_used_by_other_novel:
                cover_path.unlink()
                deleted_files.append(str(cover_path).replace("\\", "/"))
            elif cover_path.exists() and cover_is_used_by_other_novel:
                skipped_files.append(
                    f"{str(cover_path).replace(chr(92), '/')} - still used by another novel"
                )

    save_json(LIBRARY_FILE, remaining)

    result = {
        "mode": "Delete Novel",
        "status": "success",
        "novel_name": target.get("title", novel_name),
        "delete_files": delete_files,
        "deleted_files": deleted_files,
        "skipped_files": skipped_files,
        "message": "Novel removed from website library."
    }

    save_json(RESULTS_FILE, [result])

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
