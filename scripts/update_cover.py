import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from slugify import slugify


ROOT = Path('.')
REQUEST_FILE = ROOT / 'data' / 'epub_manager_request.json'
RESULTS_FILE = ROOT / 'data' / 'epub_manager_results.json'

DOCS_DIR = ROOT / 'docs'
COVERS_DIR = DOCS_DIR / 'covers'
LIBRARY_FILE = DOCS_DIR / 'library.json'

MAX_COVER_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 compatible; EPUBBuilder/1.0',
    'Accept': 'image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8',
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clean_text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def load_request():
    if not REQUEST_FILE.exists():
        raise SystemExit('Missing data/epub_manager_request.json')

    return json.loads(REQUEST_FILE.read_text(encoding='utf-8'))


def load_library():
    if not LIBRARY_FILE.exists():
        raise SystemExit('Missing docs/library.json')

    data = json.loads(LIBRARY_FILE.read_text(encoding='utf-8'))

    if not isinstance(data, list):
        raise SystemExit('docs/library.json must be a JSON array')

    return data


def save_library(library):
    LIBRARY_FILE.write_text(
        json.dumps(library, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )


def save_results(results):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )


def find_novel(library, novel_name):
    wanted = clean_text(novel_name).lower()
    wanted_slug = slugify(novel_name)

    for item in library:
        if clean_text(item.get('title', '')).lower() == wanted:
            return item

    for item in library:
        if clean_text(item.get('slug', '')).lower() == wanted_slug:
            return item

    for item in library:
        title = clean_text(item.get('title', '')).lower()

        if wanted and (wanted in title or title in wanted):
            return item

    return None


def extension_from_response(response, image_url):
    content_type = response.headers.get('content-type', '').lower()

    if 'jpeg' in content_type or 'jpg' in content_type:
        return '.jpg'

    if 'png' in content_type:
        return '.png'

    if 'webp' in content_type:
        return '.webp'

    parsed = urlparse(image_url)
    suffix = Path(parsed.path).suffix.lower()

    if suffix in ALLOWED_EXTENSIONS:
        return '.jpg' if suffix == '.jpeg' else suffix

    guessed = mimetypes.guess_extension(content_type.split(';')[0].strip())

    if guessed in ALLOWED_EXTENSIONS:
        return '.jpg' if guessed == '.jpeg' else guessed

    return '.jpg'


def download_cover(image_url, novel_title):
    if not image_url:
        raise ValueError('Missing cover image URL')

    if not image_url.lower().startswith(('http://', 'https://')):
        raise ValueError('Cover image URL must start with http:// or https://')

    parsed = urlparse(image_url)
    url_suffix = Path(parsed.path).suffix.lower()

    if url_suffix == '.svg':
        raise ValueError('External SVG covers are not allowed. Use jpg, jpeg, png, or webp.')

    response = requests.get(image_url, headers=HEADERS, timeout=45)
    response.raise_for_status()

    content_type = response.headers.get('content-type', '').lower()

    if content_type and not content_type.startswith('image/'):
        raise ValueError(f'URL did not return an image. Content-Type was: {content_type}')

    if len(response.content) > MAX_COVER_BYTES:
        raise ValueError('Cover image is too large. Maximum size is 5 MB.')

    ext = extension_from_response(response, image_url)

    if ext not in {'.jpg', '.png', '.webp'}:
        raise ValueError('Unsupported cover format. Use jpg, jpeg, png, or webp.')

    COVERS_DIR.mkdir(parents=True, exist_ok=True)

    safe_title = slugify(novel_title) or 'novel'
    cover_path = COVERS_DIR / f'{safe_title}{ext}'
    cover_path.write_bytes(response.content)

    return str(cover_path.relative_to(DOCS_DIR)).replace('\\', '/')


def main():
    request = load_request()

    update_data = request.get('update_cover', {}) or {}

    novel_name = clean_text(update_data.get('novel_name'))
    image_url = clean_text(update_data.get('image_url'))

    if not novel_name:
        raise SystemExit('Missing update_cover.novel_name')

    if not image_url:
        raise SystemExit('Missing update_cover.image_url')

    library = load_library()
    item = find_novel(library, novel_name)

    if not item:
        result = [{
            'status': 'failed',
            'mode': 'Update Cover Image',
            'title': novel_name,
            'image_url': image_url,
            'error': f'Novel not found in docs/library.json: {novel_name}'
        }]
        save_results(result)
        raise SystemExit(result[0]['error'])

    old_cover = item.get('cover', '')
    novel_title = item.get('title', novel_name)
    new_cover = download_cover(image_url, novel_title)

    item['cover'] = new_cover
    item['cover_updated_at'] = now_iso()
    item['status'] = item.get('status') or 'Built'

    save_library(library)

    result = [{
        'status': 'success',
        'mode': 'Update Cover Image',
        'title': novel_title,
        'old_cover': old_cover,
        'new_cover': new_cover,
        'image_url': image_url,
        'message': 'Cover image updated successfully.'
    }]

    save_results(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
