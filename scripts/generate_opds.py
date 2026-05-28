import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from xml.dom import minidom
from xml.etree import ElementTree as ET

ROOT = Path('.')
DOCS_DIR = ROOT / 'docs'
DATA_DIR = ROOT / 'data'
LIBRARY_FILE = DOCS_DIR / 'library.json'
SETTINGS_FILE = DATA_DIR / 'settings.json'
OPDS_ROOT_FILE = DOCS_DIR / 'opds.xml'
OPDS_DIR = DOCS_DIR / 'opds'


NAV_TYPE = 'application/atom+xml;profile=opds-catalog;kind=navigation'
ACQ_TYPE = 'application/atom+xml;profile=opds-catalog;kind=acquisition'


def clean_text(value):
    return str(value or '').strip()


def slugify(value):
    value = clean_text(value).lower()
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')
    return value or 'item'


def parse_date(value):
    value = clean_text(value)
    if not value:
        return datetime.now(timezone.utc)
    try:
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def iso_date(value):
    return parse_date(value).isoformat().replace('+00:00', 'Z')


def absolute_url(site_url, path):
    path = clean_text(path).replace('\\', '/')
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return site_url.rstrip('/') + '/' + quote(path.lstrip('/'), safe='/:?&=#%.-_~')


def get_site_url():
    configured = clean_text(os.environ.get('SITE_URL'))
    if configured:
        return configured.rstrip('/') + '/'
    repository = clean_text(os.environ.get('GITHUB_REPOSITORY'))
    if repository and '/' in repository:
        owner, repo = repository.split('/', 1)
        return f'https://{owner.lower()}.github.io/{repo.lower()}/'
    return 'https://savv666.github.io/epub-server/'


def mime_for_cover(path):
    ext = Path(clean_text(path)).suffix.lower()
    return {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
    }.get(ext)


def load_library():
    if not LIBRARY_FILE.exists():
        return []
    try:
        data = json.loads(LIBRARY_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load_settings():
    defaults = {'opds_latest_limit': 50, 'opds_all_limit': 0}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                defaults.update(data)
        except Exception:
            pass
    return defaults


def clear_old_opds_files():
    OPDS_DIR.mkdir(parents=True, exist_ok=True)
    for xml_file in OPDS_DIR.rglob('*.xml'):
        xml_file.unlink()


def add_text(parent, tag, text):
    el = ET.SubElement(parent, tag)
    el.text = clean_text(text)
    return el


def entry_id(novel_slug, download_url):
    raw = f'{novel_slug}|{download_url}'
    return 'urn:epub-server:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()


def collect_items(library, site_url):
    items = []
    for novel in library:
        title = clean_text(novel.get('title')) or 'Untitled Novel'
        slug = clean_text(novel.get('slug')) or slugify(title)
        site = clean_text(novel.get('site')) or 'Unknown source'
        status = clean_text(novel.get('status')) or 'Unknown'
        novel_updated = clean_text(novel.get('last_updated') or novel.get('created_at'))
        summary = clean_text(novel.get('summary') or novel.get('description') or novel.get('synopsis'))
        cover = clean_text(novel.get('cover') or novel.get('cover_url') or f'covers/{slug}.webp')
        downloads = novel.get('downloads') if isinstance(novel.get('downloads'), list) else []

        for dl in downloads:
            rel = clean_text(dl.get('url'))
            if not rel:
                continue
            start = dl.get('start')
            end = dl.get('end')
            label = clean_text(dl.get('label')) or (f'Chapters {start}-{end}' if start and end else 'EPUB download')
            updated_raw = clean_text(dl.get('created_at') or novel_updated)
            items.append({
                'title': f'{title} — {label}',
                'novel_title': title,
                'novel_slug': slug,
                'site': site,
                'site_slug': slugify(site),
                'status': status,
                'summary': summary,
                'cover_rel': cover,
                'cover_mime': mime_for_cover(cover),
                'epub_url': absolute_url(site_url, rel),
                'entry_id': entry_id(slug, rel),
                'updated': iso_date(updated_raw),
                'updated_dt': parse_date(updated_raw),
                'start': int(start) if isinstance(start, int) or str(start).isdigit() else 0,
            })
    return items


def make_feed(title, feed_rel_path, site_url, kind, entries_builder):
    feed = ET.Element('feed', {'xmlns': 'http://www.w3.org/2005/Atom', 'xmlns:opds': 'http://opds-spec.org/2010/catalog'})
    feed_url = absolute_url(site_url, feed_rel_path)
    add_text(feed, 'id', feed_url)
    add_text(feed, 'title', title)
    add_text(feed, 'updated', iso_date(datetime.now(timezone.utc).isoformat()))
    ET.SubElement(feed, 'link', {'rel': 'self', 'href': feed_url, 'type': NAV_TYPE if kind == 'navigation' else ACQ_TYPE})
    ET.SubElement(feed, 'link', {'rel': 'start', 'href': absolute_url(site_url, 'opds.xml'), 'type': NAV_TYPE})
    entries_builder(feed)
    rough = ET.tostring(feed, encoding='utf-8')
    return minidom.parseString(rough).toprettyxml(indent='  ', encoding='utf-8')


def add_acq_entry(parent, item):
    e = ET.SubElement(parent, 'entry')
    add_text(e, 'title', item['title'])
    add_text(e, 'id', item['entry_id'])
    add_text(e, 'updated', item['updated'])
    author = ET.SubElement(e, 'author')
    add_text(author, 'name', item['site'])
    add_text(e, 'content', item['summary'] or f"{item['novel_title']} ({item['status']})")
    ET.SubElement(e, 'link', {'rel': 'http://opds-spec.org/acquisition', 'href': item['epub_url'], 'type': 'application/epub+zip'})
    if item['cover_mime']:
        cover_url = absolute_url(get_site_url(), item['cover_rel'])
        ET.SubElement(e, 'link', {'rel': 'http://opds-spec.org/image', 'href': cover_url, 'type': item['cover_mime']})
        ET.SubElement(e, 'link', {'rel': 'http://opds-spec.org/image/thumbnail', 'href': cover_url, 'type': item['cover_mime']})


def write_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main():
    site_url = get_site_url()
    settings = load_settings()
    latest_limit = int(settings.get('opds_latest_limit') or 50)
    all_limit = int(settings.get('opds_all_limit') or 0)
    library = load_library()
    items = collect_items(library, site_url)
    items_newest = sorted(items, key=lambda x: x['updated_dt'], reverse=True)

    clear_old_opds_files()

    generated = []

    def write(rel_path, data):
        p = DOCS_DIR / rel_path
        write_file(p, data)
        generated.append(rel_path)

    root = make_feed('Epub Library OPDS Catalog', 'opds.xml', site_url, 'navigation', lambda feed: [
        (lambda entry: (
            add_text(entry, 'title', title),
            add_text(entry, 'id', absolute_url(site_url, href)),
            add_text(entry, 'updated', iso_date(datetime.now(timezone.utc).isoformat())),
            ET.SubElement(entry, 'link', {'rel': 'subsection', 'href': absolute_url(site_url, href), 'type': typ})
        ))(ET.SubElement(feed, 'entry'))
        for title, href, typ in [
            ('Latest EPUBs', 'opds/latest.xml', ACQ_TYPE),
            ('Novels', 'opds/novels.xml', NAV_TYPE),
            ('Sites', 'opds/sites.xml', NAV_TYPE),
            ('Built / Complete', 'opds/status-built.xml', ACQ_TYPE),
            ('Partial / Problem States', 'opds/status-partial.xml', ACQ_TYPE),
            ('All EPUBs', 'opds/all-epubs.xml', ACQ_TYPE),
        ]
    ])
    write('opds.xml', root)

    write('opds/latest.xml', make_feed('Latest EPUBs', 'opds/latest.xml', site_url, 'acquisition', lambda f: [add_acq_entry(f, i) for i in items_newest[:max(1, latest_limit)]]))
    all_items = items_newest[:all_limit] if all_limit > 0 else items_newest
    write('opds/all-epubs.xml', make_feed('All EPUBs', 'opds/all-epubs.xml', site_url, 'acquisition', lambda f: [add_acq_entry(f, i) for i in all_items]))

    novels = {}
    for i in items:
        novels.setdefault(i['novel_slug'], {'title': i['novel_title'], 'items': []})['items'].append(i)
    novels_nav = make_feed('Novels', 'opds/novels.xml', site_url, 'navigation', lambda f: [
        (lambda e, slug=slug, title=data['title']: (
            add_text(e, 'title', title), add_text(e, 'id', absolute_url(site_url, f'opds/novels/{slug}.xml')), add_text(e, 'updated', iso_date(datetime.now(timezone.utc).isoformat())), ET.SubElement(e, 'link', {'rel': 'subsection', 'href': absolute_url(site_url, f'opds/novels/{slug}.xml'), 'type': ACQ_TYPE})
        ))(ET.SubElement(f, 'entry')) for slug, data in sorted(novels.items(), key=lambda x: x[1]['title'].lower())
    ])
    write('opds/novels.xml', novels_nav)
    for slug, data in novels.items():
        sorted_novel = sorted(data['items'], key=lambda x: x['start'])
        write(f'opds/novels/{slug}.xml', make_feed(data['title'], f'opds/novels/{slug}.xml', site_url, 'acquisition', lambda f, s=sorted_novel: [add_acq_entry(f, i) for i in s]))

    sites = {}
    for i in items_newest:
        sites.setdefault(i['site_slug'], {'name': i['site'], 'items': []})['items'].append(i)
    write('opds/sites.xml', make_feed('Sites', 'opds/sites.xml', site_url, 'navigation', lambda f: [
        (lambda e, slug=slug, d=data: (add_text(e, 'title', d['name']), add_text(e, 'id', absolute_url(site_url, f'opds/sites/{slug}.xml')), add_text(e, 'updated', iso_date(datetime.now(timezone.utc).isoformat())), ET.SubElement(e, 'link', {'rel': 'subsection', 'href': absolute_url(site_url, f'opds/sites/{slug}.xml'), 'type': ACQ_TYPE})))(ET.SubElement(f, 'entry')) for slug, data in sorted(sites.items(), key=lambda x: x[1]['name'].lower())
    ]))
    for slug, data in sites.items():
        write(f'opds/sites/{slug}.xml', make_feed(data['name'], f'opds/sites/{slug}.xml', site_url, 'acquisition', lambda f, s=data['items']: [add_acq_entry(f, i) for i in s]))

    built = [i for i in items_newest if any(k in i['status'].lower() for k in ['built', 'complete'])]
    partial = [i for i in items_newest if any(k in i['status'].lower() for k in ['partial', 'lock', 'fail', 'error', 'problem'])]
    write('opds/status-built.xml', make_feed('Built / Complete', 'opds/status-built.xml', site_url, 'acquisition', lambda f: [add_acq_entry(f, i) for i in built]))
    write('opds/status-partial.xml', make_feed('Partial / Problem States', 'opds/status-partial.xml', site_url, 'acquisition', lambda f: [add_acq_entry(f, i) for i in partial]))

    print('Generated docs/opds.xml')
    print(f'Generated {len(generated)} OPDS feeds')
    print(f'OPDS root URL: {absolute_url(site_url, "opds.xml")}')


if __name__ == '__main__':
    main()
