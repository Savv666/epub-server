import json
import sys
from pathlib import Path

ROOT = Path('.')
DOCS_DIR = ROOT / 'docs'
LIBRARY_FILE = DOCS_DIR / 'library.json'


def fail(message, errors):
    errors.append(message)


def warn(message, warnings):
    warnings.append(message)


def load_library(errors):
    if not LIBRARY_FILE.exists():
        fail('docs/library.json does not exist.', errors)
        return []

    try:
        data = json.loads(LIBRARY_FILE.read_text(encoding='utf-8'))
    except Exception as exc:
        fail(f'docs/library.json is not valid JSON: {exc}', errors)
        return []

    if not isinstance(data, list):
        fail('docs/library.json must contain a JSON array.', errors)
        return []

    return data


def normalise(value):
    return str(value or '').strip().lower()


def path_exists(relative_path):
    if not relative_path:
        return False

    path = DOCS_DIR / str(relative_path)
    try:
        path.resolve().relative_to(DOCS_DIR.resolve())
    except Exception:
        return False

    return path.exists() and path.is_file()


def validate():
    errors = []
    warnings = []
    library = load_library(errors)

    titles = {}
    slugs = {}

    for index, novel in enumerate(library, start=1):
        title = str(novel.get('title') or '').strip()
        slug = str(novel.get('slug') or '').strip()

        if not title:
            fail(f'Entry #{index} has no title.', errors)
            title = f'<missing-title-{index}>'

        title_key = normalise(title)
        if title_key in titles:
            fail(f'Duplicate novel title: {title!r}', errors)
        else:
            titles[title_key] = index

        if not slug:
            warn(f'{title}: missing slug.', warnings)
        else:
            slug_key = normalise(slug)
            if slug_key in slugs:
                fail(f'Duplicate novel slug: {slug!r}', errors)
            else:
                slugs[slug_key] = index

        cover = str(novel.get('cover') or '').strip()
        if cover and cover != 'covers/default.svg' and not path_exists(cover):
            fail(f'{title}: cover file is missing: {cover}', errors)

        downloads = novel.get('downloads') or []
        if not isinstance(downloads, list):
            fail(f'{title}: downloads must be a list.', errors)
            downloads = []

        seen_ranges = set()
        seen_urls = set()
        ranges = []
        max_end = 0

        for dindex, download in enumerate(downloads, start=1):
            url = str(download.get('url') or '').strip()
            label = str(download.get('label') or '').strip()

            try:
                start = int(download.get('start'))
                end = int(download.get('end'))
            except Exception:
                fail(f'{title}: download #{dindex} has invalid start/end: {label or url}', errors)
                continue

            if start < 1 or end < start:
                fail(f'{title}: download #{dindex} has invalid range {start}-{end}.', errors)
                continue

            max_end = max(max_end, end)
            range_key = (start, end)

            if range_key in seen_ranges:
                warn(f'{title}: duplicate chapter range {start}-{end}.', warnings)
            else:
                seen_ranges.add(range_key)

            if url:
                if url in seen_urls:
                    fail(f'{title}: duplicate EPUB URL: {url}', errors)
                else:
                    seen_urls.add(url)

                if not path_exists(url):
                    fail(f'{title}: EPUB file is missing: {url}', errors)
            else:
                fail(f'{title}: download #{dindex} has no URL.', errors)

            if download.get('combined') and not isinstance(download.get('combined_from'), list):
                warn(f'{title}: combined EPUB {url} missing combined_from list.', warnings)

            ranges.append((start, end))

        ranges.sort()
        for previous, current in zip(ranges, ranges[1:]):
            prev_start, prev_end = previous
            cur_start, cur_end = current
            if cur_start <= prev_end:
                warn(f"{title}: overlapping chapter ranges {prev_start}-{prev_end} and {cur_start}-{cur_end}.", warnings)

        declared_last = novel.get('last_chapter_number') or novel.get('chapters') or 0
        try:
            declared_last = int(declared_last)
        except Exception:
            declared_last = 0

        locked_chapter = novel.get('locked_chapter_number')
        try:
            locked_chapter = int(locked_chapter) if locked_chapter else 0
        except Exception:
            locked_chapter = 0

        if max_end and declared_last and declared_last < max_end:
            fail(f'{title}: last_chapter_number {declared_last} is lower than highest EPUB end {max_end}.', errors)

        if locked_chapter and declared_last >= locked_chapter:
            warn(
                f'{title}: locked_chapter_number {locked_chapter} is not above last_chapter_number {declared_last}.',
                warnings
            )

    if warnings:
        print('Library validation warnings:')
        for item in warnings:
            print(f'  - {item}')

    if errors:
        print('Library validation failed:')
        for item in errors:
            print(f'  - {item}')
        return 1

    print(f'Library validation passed: {len(library)} novels checked.')
    return 0


if __name__ == '__main__':
    sys.exit(validate())
