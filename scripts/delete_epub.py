import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path('.')
DOCS_DIR = ROOT / 'docs'
LIBRARY_FILE = DOCS_DIR / 'library.json'
REQUEST_FILE = ROOT / 'data' / 'epub_manager_request.json'
RESULTS_FILE = ROOT / 'data' / 'epub_manager_results.json'


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clean_text(value):
    return str(value or '').strip()


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def find_novel(library, title):
    wanted = clean_text(title).lower()
    for item in library:
        if clean_text(item.get('title')).lower() == wanted:
            return item
    for item in library:
        current = clean_text(item.get('title')).lower()
        if wanted and (wanted in current or current in wanted):
            return item
    return None


def safe_doc_file(relative_path):
    relative_path = clean_text(relative_path).replace('\\', '/')
    if not relative_path:
        return None
    path = DOCS_DIR / relative_path
    try:
        path.resolve().relative_to(DOCS_DIR.resolve())
    except Exception:
        return None
    return path


def recalc_novel(item):
    downloads = item.get('downloads') or []
    max_end = 0
    last_url = ''
    for download in downloads:
        try:
            end = int(download.get('end', 0) or 0)
        except Exception:
            end = 0
        if end >= max_end:
            max_end = end
            last_url = clean_text(download.get('url'))

    item['chapters'] = max_end
    item['last_chapter_number'] = max_end
    item['last_updated'] = now_iso()

    if max_end <= 0:
        item['status'] = 'No EPUBs'
    elif item.get('locked_chapter_number'):
        item['status'] = 'Partial / locked'
    else:
        item['status'] = item.get('status') or 'Built'

    if last_url:
        item['last_epub_url'] = last_url


def main():
    request = load_json(REQUEST_FILE, {})
    data = request.get('delete_epub') or {}

    novel_name = clean_text(data.get('novel_name'))
    epub_url = clean_text(data.get('epub_url'))

    try:
        start_chapter = int(data.get('start_chapter') or 0)
    except Exception:
        start_chapter = 0

    try:
        end_chapter = int(data.get('end_chapter') or 0)
    except Exception:
        end_chapter = 0

    if not novel_name:
        raise SystemExit('Delete EPUB mode requires delete_epub.novel_name')

    library = load_json(LIBRARY_FILE, [])
    if not isinstance(library, list):
        raise SystemExit('docs/library.json must be a JSON array')

    item = find_novel(library, novel_name)
    if not item:
        result = [{
            'status': 'failed',
            'mode': 'Delete EPUB',
            'title': novel_name,
            'error': f'Novel not found: {novel_name}',
        }]
        save_json(RESULTS_FILE, result)
        raise SystemExit(result[0]['error'])

    downloads = item.get('downloads') or []
    kept = []
    removed = []

    for download in downloads:
        matches_url = epub_url and clean_text(download.get('url')) == epub_url
        try:
            d_start = int(download.get('start', 0) or 0)
            d_end = int(download.get('end', 0) or 0)
        except Exception:
            d_start = d_end = 0
        matches_range = start_chapter and end_chapter and d_start == start_chapter and d_end == end_chapter

        if matches_url or matches_range:
            removed.append(download)
        else:
            kept.append(download)

    if not removed:
        result = [{
            'status': 'failed',
            'mode': 'Delete EPUB',
            'title': item.get('title', novel_name),
            'epub_url': epub_url,
            'start_chapter': start_chapter,
            'end_chapter': end_chapter,
            'error': 'No matching EPUB download entry was found.',
        }]
        save_json(RESULTS_FILE, result)
        raise SystemExit(result[0]['error'])

    deleted_files = []
    for download in removed:
        file_path = safe_doc_file(download.get('url'))
        if file_path and file_path.exists() and file_path.is_file():
            file_path.unlink()
            deleted_files.append(str(file_path.relative_to(DOCS_DIR)).replace('\\', '/'))

    item['downloads'] = kept
    recalc_novel(item)
    save_json(LIBRARY_FILE, library)

    result = [{
        'status': 'success',
        'mode': 'Delete EPUB',
        'title': item.get('title', novel_name),
        'removed_entries': removed,
        'deleted_files': deleted_files,
        'message': 'Selected EPUB batch was removed from the website library.',
    }]
    save_json(RESULTS_FILE, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
