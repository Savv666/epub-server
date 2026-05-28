import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scripts.queue_manager as queue_manager
from scripts.queue_manager import SUPPORTED_MODES, map_mode

EXPECTED_MODE_MAPPINGS = {
    'New Novel': 'New Novel',
    'new_novel': 'New Novel',
    'Add New Novel': 'New Novel',
    'Continue Novel': 'Continue Novel',
    'continue_novel': 'Continue Novel',
    'Rebuild EPUB': 'Rebuild EPUB',
    'rebuild_epub': 'Rebuild EPUB',
    'Delete EPUB': 'Delete EPUB',
    'delete_epub': 'Delete EPUB',
    'Delete Novel': 'Delete Novel',
    'delete_novel': 'Delete Novel',
    'Update Cover Image': 'Update Cover Image',
    'update_cover': 'Update Cover Image',
    'update_cover_image': 'Update Cover Image',
    'Update All Existing Novels': 'Update All Existing Novels',
    'update_all_existing_novels': 'Update All Existing Novels',
    'Schedule Update All': 'Schedule Update All',
    'scheduled_update_all': 'Schedule Update All',
    'Combine EPUB Chunks': 'Combine EPUB Chunks',
    'combine_epub_chunks': 'Combine EPUB Chunks',
    'alternate_source_update': 'alternate_source_update',
    'Alternate Source Update': 'alternate_source_update',
}

ROUNDTRIP_REQUEST = {
    'mode': 'Delete EPUB',
    'engine': 'Auto',
    'overrides': {'chapters_per_epub': 25, 'max_batches': 2},
    'items': [{'start_url': 'https://example.invalid/novel', 'novel_title': 'Example Novel', 'start_chapter': 3}],
    'delete': {'novel_name': 'Delete Me', 'delete_files': 'Yes'},
    'update_cover': {'novel_name': 'Cover Me', 'image_url': 'https://example.invalid/cover.jpg'},
    'combine': {
        'novel_name': 'Combine Me',
        'novel_slug': 'combine-me',
        'files': ['epubs/a.epub', 'epubs/b.epub'],
        'start': 1,
        'end': 20,
        'overwrite': 'No',
    },
    'schedule': {'start_at': '2026-01-01T00:00:00Z', 'repeat_days': 7},
    'delete_epub': {
        'novel_name': 'Delete EPUB Me',
        'start_chapter': 1,
        'end_chapter': 10,
        'epub_url': 'epubs/delete-me.epub',
    },
    'rebuild': {
        'novel_name': 'Rebuild Me',
        'source_url': 'https://example.invalid/rebuild',
        'start_chapter': 1,
        'end_chapter': 10,
        'existing_epub_url': 'epubs/rebuild-me.epub',
    },
    'alternate_source': {'novel_name': 'Alt Me', 'source_url': 'https://example.invalid/alt'},
}


def configure_temp_queue(tmpdir):
    root = Path(tmpdir)
    queue_manager.ROOT = root
    queue_manager.DATA = root / 'data'
    queue_manager.QUEUE_FILE = queue_manager.DATA / 'queue.json'
    queue_manager.REQUEST_FILE = queue_manager.DATA / 'epub_manager_request.json'
    queue_manager.SCHEDULES_FILE = queue_manager.DATA / 'schedules.json'
    queue_manager.DATA.mkdir(parents=True, exist_ok=True)


def test_supported_mode_mappings():
    for source, expected in EXPECTED_MODE_MAPPINGS.items():
        actual = map_mode(source)
        assert actual == expected, f'{source!r} mapped to {actual!r}, expected {expected!r}'
        assert actual in SUPPORTED_MODES, f'{source!r} mapped to unsupported mode {actual!r}'

    for mode in SUPPORTED_MODES:
        assert map_mode(mode) == mode, f'supported mode {mode!r} did not map to itself'


def test_queue_roundtrip_preserves_payload_sections():
    with tempfile.TemporaryDirectory() as tmpdir:
        configure_temp_queue(tmpdir)
        queue_manager.REQUEST_FILE.write_text(json.dumps(ROUNDTRIP_REQUEST, indent=2), encoding='utf-8')

        job = queue_manager.enqueue_from_request('test')
        assert job is not None, 'enqueue_from_request returned no job'
        popped = queue_manager.pop_next_job_to_request()
        assert popped is not None, 'pop_next_job_to_request returned no job'

        result = json.loads(queue_manager.REQUEST_FILE.read_text(encoding='utf-8'))
        for key, expected in ROUNDTRIP_REQUEST.items():
            assert result.get(key) == expected, f'{key!r} changed after queue roundtrip: {result.get(key)!r}'


def main():
    test_supported_mode_mappings()
    test_queue_roundtrip_preserves_payload_sections()
    print('queue mode mapping and payload roundtrip tests passed')


if __name__ == '__main__':
    main()
