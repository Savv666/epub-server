import json
import subprocess
from pathlib import Path

from common import (
    FREEWEBNOVEL_DOMAINS,
    GENERIC_FIRST_DOMAINS,
    LOCKED_ERROR_PHRASES,
    domain_matches,
    load_json,
    looks_like_phrase_match,
    save_json,
)
from fanficfare_engine import download_with_fanficfare
from freewebnovel_engine import download_with_freewebnovel
from pattern_engine import download_with_pattern


ROOT = Path('.')
REQUEST_FILE = ROOT / 'data' / 'epub_manager_request.json'
RESULTS_FILE = ROOT / 'data' / 'epub_manager_results.json'


def clear_results():
    if RESULTS_FILE.exists():
        RESULTS_FILE.unlink()


def load_request():
    if not REQUEST_FILE.exists():
        raise SystemExit('Missing data/epub_manager_request.json')

    data = load_json(REQUEST_FILE, default={})
    if not data:
        raise SystemExit('Request file exists but could not be parsed.')
    return data


def save_request(data):
    save_json(REQUEST_FILE, data)


def save_results(results):
    save_json(RESULTS_FILE, results)


def load_results():
    data = load_json(RESULTS_FILE, default=[])
    if isinstance(data, list):
        return data
    return [data] if data else []


def is_freewebnovel(url):
    return domain_matches(url, FREEWEBNOVEL_DOMAINS)


def should_use_generic_first(url):
    return domain_matches(url, GENERIC_FIRST_DOMAINS)


def looks_like_locked_error(text):
    return looks_like_phrase_match(text, LOCKED_ERROR_PHRASES)


def is_success(result):
    status = result.get('status')

    if status == 'success':
        return True

    if status == 'skipped_duplicate':
        return True

    if status == 'partial_locked':
        return bool(
            result.get('locked_chapter_number')
            or result.get('files')
            or result.get('created_files')
            or result.get('new_files')
            or result.get('library_updated')
        )

    return False


def get_engine(request_data):
    engine = str(request_data.get('engine', 'Auto')).strip()

    valid = [
        'Generic Scraper',
        'FanFicFare',
        'FreeWebNovel',
        'Pattern Scraper',
        'Auto'
    ]

    if engine not in valid:
        return 'Auto'

    return engine


def get_chapter_settings(request_data):
    overrides = request_data.get('overrides', {})

    try:
        chapters_per_epub = int(overrides.get('chapters_per_epub', 10))
    except Exception:
        chapters_per_epub = 10

    try:
        max_batches = int(overrides.get('max_batches', 1))
    except Exception:
        max_batches = 1

    if chapters_per_epub < 1:
        chapters_per_epub = 1

    if max_batches < 1:
        max_batches = 1

    return chapters_per_epub, max_batches


def first_result_or_failed(results, engine_name):
    if not results:
        return {
            'status': 'failed',
            'engine': engine_name,
            'selected_engine': engine_name,
            'error': f'{engine_name} returned no result'
        }

    return results[0]


def run_generic_scraper(request_data, item):
    generic_request = dict(request_data)
    generic_request['items'] = [item]

    save_request(generic_request)
    clear_results()

    result = subprocess.run(
        ['python', 'scripts/epub_from_link.py'],
        text=True,
        capture_output=True,
        timeout=3600
    )

    print('Generic scraper STDOUT:')
    print(result.stdout)

    print('Generic scraper STDERR:')
    print(result.stderr)

    if result.returncode != 0:
        return {
            'status': 'failed',
            'engine': 'generic',
            'selected_engine': 'Generic Scraper',
            'error': result.stderr.strip() or result.stdout.strip() or 'Generic scraper failed'
        }

    results = load_results()
    first = first_result_or_failed(results, 'Generic Scraper')
    first['selected_engine'] = 'Generic Scraper'
    return first


def run_fanficfare(request_data, item):
    chapters_per_epub, max_batches = get_chapter_settings(request_data)

    result = download_with_fanficfare(
        item=item,
        chapters_per_epub=chapters_per_epub,
        max_batches=max_batches
    )

    result['selected_engine'] = 'FanFicFare'

    if result.get('status') != 'success' and looks_like_locked_error(json.dumps(result, ensure_ascii=False)):
        result['status'] = 'partial_locked'
        result['locked_reason'] = (
            'The source page is login-only, private, restricted, age-gated, '
            'or otherwise not publicly readable.'
        )

    return result


def run_freewebnovel(request_data, item):
    chapters_per_epub, max_batches = get_chapter_settings(request_data)

    result = download_with_freewebnovel(
        item=item,
        chapters_per_epub=chapters_per_epub,
        max_batches=max_batches
    )

    result['selected_engine'] = 'FreeWebNovel'
    return result


def run_pattern(request_data, item):
    chapters_per_epub, max_batches = get_chapter_settings(request_data)

    result = download_with_pattern(
        item=item,
        chapters_per_epub=chapters_per_epub,
        max_batches=max_batches
    )

    result['selected_engine'] = 'Pattern Scraper'
    return result


def run_order(request_data, item, order):
    failures = []

    for engine_name in order:
        print('=' * 80)
        print(f'Trying engine: {engine_name}')
        print('=' * 80)

        clear_results()

        if engine_name == 'pattern':
            result = run_pattern(request_data, item)
        elif engine_name == 'freewebnovel':
            result = run_freewebnovel(request_data, item)
        elif engine_name == 'fanficfare':
            result = run_fanficfare(request_data, item)
        else:
            result = run_generic_scraper(request_data, item)

        if is_success(result):
            result['engine_order'] = ' → '.join(order)
            return result

        failures.append({
            'engine': engine_name,
            'error': result.get('error', ''),
            'status': result.get('status', 'failed')
        })

        print('=' * 80)
        print(f'Engine failed: {engine_name}')
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print('=' * 80)

    return {
        'title': item.get('novel_title', ''),
        'status': 'failed',
        'engine': 'router',
        'selected_engine': ' → '.join(order),
        'start_url': item.get('start_url', ''),
        'failures': failures,
        'error': 'All selected/fallback engines failed.'
    }


def choose_order(request_data, item):
    engine = get_engine(request_data)
    start_url = item.get('start_url', '')

    if engine == 'Pattern Scraper':
        return ['pattern', 'freewebnovel', 'generic', 'fanficfare']

    if engine == 'FreeWebNovel':
        return ['freewebnovel', 'pattern', 'generic', 'fanficfare']

    if engine == 'FanFicFare':
        if is_freewebnovel(start_url):
            return ['fanficfare', 'pattern', 'freewebnovel', 'generic']
        return ['fanficfare', 'generic']

    if engine == 'Generic Scraper':
        if is_freewebnovel(start_url):
            return ['generic', 'pattern', 'freewebnovel', 'fanficfare']
        return ['generic', 'fanficfare']

    if is_freewebnovel(start_url):
        return ['pattern', 'freewebnovel', 'generic', 'fanficfare']

    if should_use_generic_first(start_url):
        return ['generic', 'pattern', 'fanficfare']

    return ['fanficfare', 'generic', 'pattern']


def process_new_novel(request_data):
    items = request_data.get('items', [])

    if not isinstance(items, list) or not items:
        raise SystemExit('No items found in request.')

    results = []

    for item in items:
        order = choose_order(request_data, item)
        result = run_order(request_data, item, order)
        results.append(result)

    return results


def main():
    clear_results()
    original_request = load_request()
    original_request_text = json.dumps(original_request, indent=2, ensure_ascii=False)

    mode = original_request.get('mode', 'New Novel')
    engine = get_engine(original_request)

    print('=' * 80)
    print('EPUB Engine Router')
    print(f'Mode: {mode}')
    print(f'Selected engine: {engine}')
    print('=' * 80)

    try:
        if mode == 'Update All Existing Novels':
            clear_results()

            result = subprocess.run(
                ['python', 'scripts/epub_from_link.py'],
                text=True,
                capture_output=True,
                timeout=3600
            )

            print('Generic scraper STDOUT:')
            print(result.stdout)

            print('Generic scraper STDERR:')
            print(result.stderr)

            results = load_results()

            if result.returncode != 0 and not results:
                results = [{
                    'status': 'failed',
                    'engine': 'generic',
                    'error': result.stderr.strip() or result.stdout.strip() or 'Generic scraper failed'
                }]

        elif mode == 'New Novel':
            results = process_new_novel(original_request)

        else:
            results = [{
                'status': 'failed',
                'engine': 'router',
                'selected_engine': engine,
                'error': f'Unsupported router mode: {mode}'
            }]

        save_results(results)

        successful = [result for result in results if is_success(result)]

        if not successful:
            raise SystemExit('All engine attempts failed.')

    finally:
        REQUEST_FILE.write_text(original_request_text, encoding='utf-8')


if __name__ == '__main__':
    main()
