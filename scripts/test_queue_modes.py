import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.queue_manager import map_mode, SUPPORTED_MODES

MODES = [
    'New Novel','Continue Novel','Rebuild EPUB','Delete EPUB','Delete Novel','Update Cover Image',
    'Update All Existing Novels','Schedule Update All','Combine EPUB Chunks','alternate_source_update'
]

bad = 0
for m in MODES:
    mm = map_mode(m)
    ok = mm in SUPPORTED_MODES
    print(m, '=>', mm, 'OK' if ok else 'NOT_SUPPORTED')
    bad += 0 if ok else 1

raise SystemExit(1 if bad else 0)
