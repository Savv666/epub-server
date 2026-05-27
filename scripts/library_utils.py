import json
from pathlib import Path

ROOT = Path('.')
DOCS_DIR = ROOT / 'docs'
LIBRARY_FILE = DOCS_DIR / 'library.json'


def load_library():
    if not LIBRARY_FILE.exists():
        return []
    try:
        data = json.loads(LIBRARY_FILE.read_text(encoding='utf-8'))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def save_library(library):
    LIBRARY_FILE.write_text(json.dumps(library, indent=2, ensure_ascii=False), encoding='utf-8')


def get_existing_ranges(library, novel_slug):
    for novel in library:
        if novel.get('slug') == novel_slug:
            return [
                (int(d.get('start', 0) or 0), int(d.get('end', 0) or 0), d)
                for d in (novel.get('downloads') or [])
                if d.get('start') and d.get('end')
            ]
    return []


def range_overlaps(start, end, existing_start, existing_end):
    return start <= existing_end and end >= existing_start


def range_already_covered(start, end, existing_ranges):
    for s, e, _ in existing_ranges:
        if s <= start and e >= end:
            return True
    return False


def find_duplicate_epub(library, novel_slug, start, end):
    for s, e, d in get_existing_ranges(library, novel_slug):
        if s == start and e == end:
            return d
    return None
