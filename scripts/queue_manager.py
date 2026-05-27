import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('.')
DATA = ROOT / 'data'
QUEUE_FILE = DATA / 'queue.json'
SCHEDULES_FILE = DATA / 'schedules.json'
REQUEST_FILE = DATA / 'epub_manager_request.json'
SETTINGS_FILE = DATA / 'settings.json'

VALID_STATUSES = {'queued', 'running', 'success', 'partial', 'failed', 'skipped'}
SUPPORTED_MODES = {
    'new_novel', 'continue_novel', 'rebuild_epub', 'delete_epub', 'delete_novel',
    'update_cover', 'update_all', 'scheduled_update_all', 'combine_epubs', 'alternate_source_update'
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def ensure_files():
    DATA.mkdir(exist_ok=True)
    if not QUEUE_FILE.exists():
        _save_json(QUEUE_FILE, [])
    if not SCHEDULES_FILE.exists():
        _save_json(SCHEDULES_FILE, {'schedules': []})


def map_mode(mode):
    m = str(mode or '').strip().lower()
    return {
        'new novel': 'new_novel',
        'update all existing novels': 'update_all',
        'delete novel': 'delete_novel',
        'update cover image': 'update_cover',
        'delete epub': 'delete_epub',
        'rebuild epub': 'rebuild_epub',
        'combine epub chunks': 'combine_epubs',
        'schedule update all': 'scheduled_update_all',
        'scheduled_update_all': 'scheduled_update_all',
    }.get(m, m.replace(' ', '_'))


def enqueue_from_request(source='workflow'):
    ensure_files()
    req = _load_json(REQUEST_FILE, {})
    if not req:
        return None
    mode = map_mode(req.get('mode'))
    job = {
        'id': str(uuid.uuid4()), 'created_at': now_iso(), 'source': source,
        'mode': mode, 'engine': req.get('engine', 'Auto'), 'status': 'queued',
        'overrides': req.get('overrides', {}), 'items': req.get('items', []),
        'delete': req.get('delete', {}), 'update_cover': req.get('update_cover', {}),
        'combine': req.get('combine', {}), 'schedule': req.get('schedule', {}),
        'error': '', 'started_at': '', 'finished_at': ''
    }
    queue = _load_json(QUEUE_FILE, [])
    queue.append(job)
    _save_json(QUEUE_FILE, queue)
    return job


def _settings_enabled():
    settings = _load_json(SETTINGS_FILE, {})
    return bool(settings.get('scheduled_update_enabled', True))


def sync_due_schedules_to_queue(now=None):
    ensure_files()
    if not _settings_enabled():
        return []
    now = now or datetime.now(timezone.utc)
    data = _load_json(SCHEDULES_FILE, {'schedules': []})
    schedules = data.get('schedules', []) if isinstance(data, dict) else []
    queue = _load_json(QUEUE_FILE, [])
    created = []
    for s in schedules:
        if not s.get('enabled', True):
            continue
        due_at = s.get('next_run_at') or s.get('start_at')
        try:
            due = datetime.fromisoformat(due_at.replace('Z', '+00:00'))
        except Exception:
            continue
        if due <= now:
            queue.append({
                'id': str(uuid.uuid4()), 'created_at': now_iso(), 'source': 'schedule',
                'mode': 'update_all', 'engine': 'Auto', 'status': 'queued',
                'overrides': {}, 'items': [], 'delete': {}, 'update_cover': {},
                'combine': {}, 'schedule': {'schedule_id': s.get('id')},
                'error': '', 'started_at': '', 'finished_at': ''
            })
            s['last_run_at'] = now_iso()
            repeat = int(s.get('repeat_days', 1) or 1)
            s['next_run_at'] = (due + timedelta(days=repeat)).isoformat()
            created.append(s.get('id'))
    _save_json(QUEUE_FILE, queue)
    _save_json(SCHEDULES_FILE, {'schedules': schedules})
    return created


def pop_next_job_to_request():
    ensure_files()
    queue = _load_json(QUEUE_FILE, [])
    for i, job in enumerate(queue):
        if job.get('status') != 'queued':
            continue
        mode = map_mode(job.get('mode'))
        if mode not in SUPPORTED_MODES:
            job['status'] = 'failed'
            job['error'] = f'Unsupported mode: {job.get("mode")}'
            job['finished_at'] = now_iso()
            queue[i] = job
            continue
        job['status'] = 'running'
        job['started_at'] = now_iso()
        queue[i] = job
        req = {
            'mode': mode,
            'engine': job.get('engine', 'Auto'),
            'overrides': job.get('overrides', {}),
            'items': job.get('items', []),
            'delete': job.get('delete', {}),
            'update_cover': job.get('update_cover', {}),
            'combine': job.get('combine', {}),
            'schedule': job.get('schedule', {})
        }
        _save_json(REQUEST_FILE, req)
        _save_json(QUEUE_FILE, queue)
        return job
    _save_json(QUEUE_FILE, queue)
    return None


def add_schedule(start_at, repeat_days=1):
    ensure_files()
    data = _load_json(SCHEDULES_FILE, {'schedules': []})
    schedule = {
        'id': f'schedule-{uuid.uuid4()}', 'mode': 'scheduled_update_all', 'created_at': now_iso(),
        'start_at': start_at, 'repeat_days': int(repeat_days), 'enabled': True,
        'last_run_at': '', 'next_run_at': start_at, 'status': 'active'
    }
    data.setdefault('schedules', []).append(schedule)
    _save_json(SCHEDULES_FILE, data)
    return schedule
