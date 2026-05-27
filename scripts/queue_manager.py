import json, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('.')
DATA = ROOT / 'data'
QUEUE_FILE = DATA / 'queue.json'
REQUEST_FILE = DATA / 'epub_manager_request.json'


def now():
    return datetime.now(timezone.utc).isoformat()


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
    QUEUE_FILE.write_text(json.dumps(q, indent=2, ensure_ascii=False), encoding='utf-8')


def enqueue_from_request(source='workflow'):
    if not REQUEST_FILE.exists():
        return None
    req = json.loads(REQUEST_FILE.read_text(encoding='utf-8'))
    q = load_queue()
    job = {
        'id': str(uuid.uuid4()), 'created_at': now(), 'source': source,
        'mode': req.get('mode'), 'engine': req.get('engine', 'Auto'), 'status': 'queued',
        'overrides': req.get('overrides', {}), 'items': req.get('items', []), 'delete': req.get('delete', {}),
        'update_cover': req.get('update_cover', {}), 'error': '', 'started_at': '', 'finished_at': ''
    }
    q.append(job)
    save_queue(q)
    return job


def pop_next_job_to_request():
    q = load_queue()
    for i, job in enumerate(q):
        if job.get('status') == 'queued':
            job['status'] = 'running'; job['started_at'] = now()
            req = {k: job.get(k) for k in ['mode','engine','overrides','items','delete','update_cover']}
            REQUEST_FILE.write_text(json.dumps(req, indent=2, ensure_ascii=False), encoding='utf-8')
            q[i] = job
            save_queue(q)
            return job
    return None
