import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path('.')
DATA = ROOT / 'data'
QUEUE_FILE = DATA / 'queue.json'
REQUEST_FILE = DATA / 'epub_manager_request.json'
SCHEDULES_FILE = DATA / 'schedules.json'

SUPPORTED_MODES = {
    'New Novel',
    'Continue Novel',
    'Rebuild EPUB',
    'Delete EPUB',
    'Delete Novel',
    'Update Cover Image',
    'Update All Existing Novels',
    'Schedule Update All',
    'Combine EPUB Chunks',
    'alternate_source_update',
}

MODE_ALIASES = {
    'new novel': 'New Novel',
    'new_novel': 'New Novel',
    'add new novel': 'New Novel',
    'add_new_novel': 'New Novel',
    'continue novel': 'Continue Novel',
    'continue_novel': 'Continue Novel',
    'rebuild epub': 'Rebuild EPUB',
    'rebuild_epub': 'Rebuild EPUB',
    'delete epub': 'Delete EPUB',
    'delete_epub': 'Delete EPUB',
    'delete novel': 'Delete Novel',
    'delete_novel': 'Delete Novel',
    'update cover image': 'Update Cover Image',
    'update_cover_image': 'Update Cover Image',
    'update_cover': 'Update Cover Image',
    'update all existing novels': 'Update All Existing Novels',
    'update_all_existing_novels': 'Update All Existing Novels',
    'update all': 'Update All Existing Novels',
    'update_all': 'Update All Existing Novels',
    'schedule update all': 'Schedule Update All',
    'schedule_update_all': 'Schedule Update All',
    'scheduled_update_all': 'Schedule Update All',
    'combine epub chunks': 'Combine EPUB Chunks',
    'combine_epub_chunks': 'Combine EPUB Chunks',
    'alternate_source_update': 'alternate_source_update',
    'alternate source update': 'alternate_source_update',
}

REQUEST_PAYLOAD_FIELDS = [
    'mode',
    'engine',
    'overrides',
    'items',
    'delete',
    'update_cover',
    'combine',
    'schedule',
    'delete_epub',
    'rebuild',
    'alternate_source',
]

_PAYLOAD_DEFAULTS = {
    'mode': 'New Novel',
    'engine': 'Auto',
    'overrides': {},
    'items': [],
    'delete': {},
    'update_cover': {},
    'combine': {},
    'schedule': {},
    'delete_epub': {},
    'rebuild': {},
    'alternate_source': {},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def map_mode(mode):
    value = str(mode or '').strip()
    if value in SUPPORTED_MODES:
        return value

    key = ' '.join(value.replace('-', ' ').split()).lower()
    mapped = MODE_ALIASES.get(key)
    if mapped:
        return mapped

    snake_key = '_'.join(key.split())
    return MODE_ALIASES.get(snake_key, value)


def ensure_queue():
    DATA.mkdir(exist_ok=True)
    if not QUEUE_FILE.exists():
        QUEUE_FILE.write_text('[]', encoding='utf-8')


def load_queue():
    ensure_queue()
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding='utf-8'))
    except Exception:
        data = []
    return data if isinstance(data, list) else []


def save_queue(q):
    DATA.mkdir(exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(q, indent=2, ensure_ascii=False), encoding='utf-8')


def _request_payload(req):
    payload = {}
    for field in REQUEST_PAYLOAD_FIELDS:
        default = _PAYLOAD_DEFAULTS[field]
        if field in req:
            payload[field] = req.get(field)
        elif isinstance(default, (dict, list)):
            payload[field] = default.copy()
        else:
            payload[field] = default

    payload['mode'] = map_mode(payload.get('mode'))
    payload['engine'] = payload.get('engine') or 'Auto'
    return payload


def enqueue_from_request(source='workflow'):
    if not REQUEST_FILE.exists():
        return None

    req = json.loads(REQUEST_FILE.read_text(encoding='utf-8'))
    payload = _request_payload(req if isinstance(req, dict) else {})
    q = load_queue()
    job = {
        'id': str(uuid.uuid4()),
        'created_at': now(),
        'source': source,
        'status': 'queued',
        'error': '',
        'started_at': '',
        'finished_at': '',
        **payload,
    }
    q.append(job)
    save_queue(q)
    return job


def pop_next_job_to_request():
    q = load_queue()
    for i, job in enumerate(q):
        if job.get('status') == 'queued':
            job['status'] = 'running'
            job['started_at'] = now()
            job['mode'] = map_mode(job.get('mode'))
            req = _request_payload(job)
            DATA.mkdir(exist_ok=True)
            REQUEST_FILE.write_text(json.dumps(req, indent=2, ensure_ascii=False), encoding='utf-8')
            q[i] = job
            save_queue(q)
            return job
    return None


def load_schedules():
    DATA.mkdir(exist_ok=True)
    if not SCHEDULES_FILE.exists():
        return {'schedules': []}
    try:
        data = json.loads(SCHEDULES_FILE.read_text(encoding='utf-8'))
    except Exception:
        data = {'schedules': []}
    if isinstance(data, list):
        return {'schedules': data}
    if not isinstance(data.get('schedules'), list):
        data['schedules'] = []
    return data


def save_schedules(data):
    DATA.mkdir(exist_ok=True)
    SCHEDULES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def add_schedule(start_at, repeat_days=1):
    data = load_schedules()
    schedule = {
        'id': str(uuid.uuid4()),
        'start_at': str(start_at or '').strip(),
        'repeat_days': int(repeat_days or 1),
        'enabled': True,
        'created_at': now(),
        'last_enqueued_at': '',
    }
    data['schedules'].append(schedule)
    save_schedules(data)
    return schedule


def _parse_dt(value):
    if not value:
        return None
    text = str(value).strip().replace('Z', '+00:00')
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def sync_due_schedules_to_queue():
    data = load_schedules()
    current = datetime.now(timezone.utc)
    due_count = 0

    for schedule in data.get('schedules', []):
        if schedule.get('enabled') is False:
            continue

        start_at = _parse_dt(schedule.get('start_at'))
        if not start_at or start_at > current:
            continue

        last_enqueued = _parse_dt(schedule.get('last_enqueued_at'))
        repeat_days = int(schedule.get('repeat_days') or 1)
        repeat_days = max(repeat_days, 1)
        if last_enqueued and last_enqueued + timedelta(days=repeat_days) > current:
            continue

        request = {
            'mode': 'Update All Existing Novels',
            'engine': 'Auto',
            'overrides': {'chapters_per_epub': 10, 'max_batches': 1},
            'items': [],
            'schedule': schedule,
        }
        DATA.mkdir(exist_ok=True)
        REQUEST_FILE.write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding='utf-8')
        enqueue_from_request('scheduled')
        schedule['last_enqueued_at'] = now()
        due_count += 1

    save_schedules(data)
    return due_count
