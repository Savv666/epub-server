import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scripts.queue_manager as queue_manager

SAMPLE_REQUESTS = [
    {
        'mode': 'New Novel',
        'engine': 'Auto',
        'overrides': {'chapters_per_epub': 10, 'max_batches': 1},
        'items': [{'start_url': 'https://example.invalid/new', 'novel_title': 'New Novel', 'start_chapter': 1}],
    },
    {
        'mode': 'Delete Novel',
        'delete': {'novel_name': 'Delete Novel', 'delete_files': 'Yes'},
    },
    {
        'mode': 'Delete EPUB',
        'delete_epub': {
            'novel_name': 'Delete EPUB Novel',
            'start_chapter': 1,
            'end_chapter': 10,
            'epub_url': 'epubs/delete-epub-novel_ch001-010.epub',
        },
    },
    {
        'mode': 'Update Cover Image',
        'update_cover': {'novel_name': 'Cover Novel', 'image_url': 'https://example.invalid/cover.webp'},
    },
    {
        'mode': 'Combine EPUB Chunks',
        'combine': {
            'novel_name': 'Combine Novel',
            'novel_slug': 'combine-novel',
            'files': ['epubs/combine-novel_ch001-010.epub', 'epubs/combine-novel_ch011-020.epub'],
            'start': 1,
            'end': 20,
            'overwrite': 'No',
        },
    },
    {
        'mode': 'Schedule Update All',
        'schedule': {'start_at': '2026-01-01T00:00:00Z', 'repeat_days': 1},
    },
]

ALL_SECTIONS = ['delete', 'delete_epub', 'update_cover', 'combine', 'schedule']


def configure_temp_queue(tmpdir):
    root = Path(tmpdir)
    queue_manager.ROOT = root
    queue_manager.DATA = root / 'data'
    queue_manager.QUEUE_FILE = queue_manager.DATA / 'queue.json'
    queue_manager.REQUEST_FILE = queue_manager.DATA / 'epub_manager_request.json'
    queue_manager.SCHEDULES_FILE = queue_manager.DATA / 'schedules.json'
    queue_manager.DATA.mkdir(parents=True, exist_ok=True)


def complete_request(sample):
    request = {
        'mode': sample['mode'],
        'engine': sample.get('engine', 'Auto'),
        'overrides': sample.get('overrides', {'chapters_per_epub': 10, 'max_batches': 1}),
        'items': sample.get('items', []),
        'delete': sample.get('delete', {}),
        'update_cover': sample.get('update_cover', {}),
        'combine': sample.get('combine', {}),
        'schedule': sample.get('schedule', {}),
        'delete_epub': sample.get('delete_epub', {}),
        'rebuild': sample.get('rebuild', {}),
        'alternate_source': sample.get('alternate_source', {}),
    }
    return request


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_temp_queue(tmpdir)
        for sample in SAMPLE_REQUESTS:
            expected = complete_request(sample)
            queue_manager.QUEUE_FILE.write_text('[]', encoding='utf-8')
            queue_manager.REQUEST_FILE.write_text(json.dumps(expected, indent=2), encoding='utf-8')

            queue_manager.enqueue_from_request('smoke')
            queue_manager.pop_next_job_to_request()
            actual = json.loads(queue_manager.REQUEST_FILE.read_text(encoding='utf-8'))

            assert actual['mode'] == expected['mode'], f"mode changed: {expected['mode']} -> {actual['mode']}"
            for key in ALL_SECTIONS:
                assert key in actual, f"{expected['mode']} dropped {key} section"
                assert actual[key] == expected[key], f"{expected['mode']} changed {key}: {actual[key]!r}"

    print('queue roundtrip smoke tests passed for', ', '.join(req['mode'] for req in SAMPLE_REQUESTS))


if __name__ == '__main__':
    main()
