import email.utils
import hashlib
import html
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
FEED_FILE = DOCS_DIR / 'feed.xml'
EPUB_LINKS_FILE = DOCS_DIR / 'epub-links.html'
RSS_ITEMS_DIR = DOCS_DIR / 'rss-items'


def clean_text(value):
    return str(value or '').strip()


def slugify_basic(value):
    value = clean_text(value).lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = value.strip('-')
    return value or 'item'


def load_settings():
    defaults = {
        'rss_item_limit': 50,
    }

    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                defaults.update(data)
        except Exception:
            pass

    return defaults


def get_site_url():
    configured = clean_text(os.environ.get('SITE_URL'))

    if configured:
        return configured.rstrip('/') + '/'

    repository = clean_text(os.environ.get('GITHUB_REPOSITORY'))

    if repository and '/' in repository:
        owner, repo = repository.split('/', 1)
        return f'https://{owner.lower()}.github.io/{repo.lower()}/'

    return 'https://savv666.github.io/epub-server/'


def parse_date(value):
    value = clean_text(value)

    if not value:
        return datetime.now(timezone.utc)

    try:
        if value.endswith('Z'):
            value = value.replace('Z', '+00:00')

        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def rss_date(value):
    return email.utils.format_datetime(parse_date(value))


def absolute_url(site_url, relative_path):
    relative_path = clean_text(relative_path).replace('\\', '/')

    if relative_path.startswith('http://') or relative_path.startswith('https://'):
        return relative_path

    return site_url.rstrip('/') + '/' + quote(relative_path.lstrip('/'), safe='/:?&=#%.-_~')


def get_file_info(relative_path):
    relative_path = clean_text(relative_path)

    if not relative_path:
        return {'size': 0, 'modified_iso': datetime.now(timezone.utc).isoformat()}

    path = DOCS_DIR / relative_path

    try:
        if path.exists() and path.is_file():
            stat = path.stat()
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            return {'size': stat.st_size, 'modified_iso': modified.isoformat()}
    except Exception:
        pass

    return {'size': 0, 'modified_iso': datetime.now(timezone.utc).isoformat()}


def make_guid(epub_url, page_url, file_info):
    raw = '|'.join([
        epub_url,
        page_url,
        str(file_info.get('size', 0)),
        clean_text(file_info.get('modified_iso')),
    ])
    digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]
    return f'{page_url}?item={digest}'


def load_library():
    if not LIBRARY_FILE.exists():
        return []

    try:
        data = json.loads(LIBRARY_FILE.read_text(encoding='utf-8'))
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    return data


def make_item_page(site_url, item):
    RSS_ITEMS_DIR.mkdir(parents=True, exist_ok=True)

    output_path = RSS_ITEMS_DIR / item['page_file']

    title = html.escape(item['title'])
    novel_title = html.escape(item['novel_title'])
    label = html.escape(item['label'])
    site = html.escape(item['site'])
    status = html.escape(item['status'])
    epub_url = html.escape(item['epub_url'])
    library_url = html.escape(absolute_url(site_url, 'index.html'))
    links_url = html.escape(absolute_url(site_url, 'epub-links.html'))

    page = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:#080604; color:#f7e59a; font-family:Georgia,serif; }}
    main {{ width:min(760px, calc(100% - 32px)); border:1px solid rgba(244,216,107,.45); border-radius:22px; padding:28px; background:#17100c; box-shadow:0 20px 60px rgba(0,0,0,.45); }}
    h1 {{ margin-top:0; font-size:32px; line-height:1.1; color:#f4d86b; }}
    p {{ color:#fff3bf; font-size:17px; line-height:1.5; }}
    .download {{ display:inline-flex; margin-top:16px; padding:14px 22px; border-radius:999px; background:linear-gradient(90deg,#f6d66d,#ee9d23); color:#160b02; text-decoration:none; font-weight:900; }}
    .url-box {{ margin-top:18px; padding:14px; border:1px solid rgba(244,216,107,.35); border-radius:14px; background:#080604; color:#fff3bf; overflow-wrap:anywhere; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:14px; user-select:all; }}
    .secondary-link {{ color:#f7e59a; font-weight:700; }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p><strong>Novel:</strong> {novel_title}</p>
    <p><strong>EPUB:</strong> {label}</p>
    <p><strong>Source:</strong> {site}</p>
    <p><strong>Status:</strong> {status}</p>
    <a class="download" href="{epub_url}" download>Download EPUB</a>
    <p><strong>Direct EPUB URL:</strong></p>
    <div class="url-box">{epub_url}</div>
    <p><a class="secondary-link" href="{links_url}">Open all EPUB links</a></p>
    <p><a class="secondary-link" href="{library_url}">Open Epub Library</a></p>
  </main>
</body>
</html>
'''

    output_path.write_text(page, encoding='utf-8')


def get_download_items(library, site_url):
    items = []

    for novel in library:
        novel_title = clean_text(novel.get('title')) or 'Untitled Novel'
        novel_slug = clean_text(novel.get('slug')) or slugify_basic(novel_title)
        site = clean_text(novel.get('site')) or 'Unknown source'
        status = clean_text(novel.get('status')) or 'Unknown'
        novel_updated = clean_text(novel.get('last_updated') or novel.get('created_at'))
        downloads = novel.get('downloads') or []

        if not isinstance(downloads, list):
            continue

        for download in downloads:
            epub_path = clean_text(download.get('url'))

            if not epub_path:
                continue

            start = download.get('start')
            end = download.get('end')
            label = clean_text(download.get('label'))

            if not label:
                if start and end:
                    label = f'Chapters {start}-{end}'
                else:
                    label = 'EPUB download'

            item_title = f'{novel_title} — {label}'
            epub_url = absolute_url(site_url, epub_path)
            file_info = get_file_info(epub_path)
            created_at = clean_text(download.get('created_at') or file_info.get('modified_iso') or novel_updated)
            page_slug = slugify_basic(f'{novel_slug}-{label}')
            page_file = f'{page_slug}.html'
            page_path = f'rss-items/{page_file}'
            page_url = absolute_url(site_url, page_path)
            guid = make_guid(epub_url, page_url, file_info)

            items.append({
                'title': item_title,
                'novel_title': novel_title,
                'label': label,
                'site': site,
                'status': status,
                'epub_url': epub_url,
                'page_file': page_file,
                'page_url': page_url,
                'guid': guid,
                'pub_date': created_at,
                'file_size': file_info.get('size', 0),
            })

    items.sort(key=lambda item: parse_date(item.get('pub_date')), reverse=True)
    return items


def add_text(parent, tag, text):
    element = ET.SubElement(parent, tag)
    element.text = clean_text(text)
    return element


def build_rss(site_url, items, rss_item_limit):
    RSS_ITEMS_DIR.mkdir(parents=True, exist_ok=True)

    for old_page in RSS_ITEMS_DIR.glob('*.html'):
        old_page.unlink()

    for item in items:
        make_item_page(site_url, item)

    rss_items = items[:max(1, int(rss_item_limit or 50))]

    rss = ET.Element('rss', {
        'version': '2.0',
        'xmlns:atom': 'http://www.w3.org/2005/Atom',
    })

    channel = ET.SubElement(rss, 'channel')
    add_text(channel, 'title', 'Epub Library')
    add_text(channel, 'link', site_url)
    add_text(channel, 'description', 'Latest EPUB batches generated from the Epub Library.')
    add_text(channel, 'language', 'en-gb')
    add_text(channel, 'lastBuildDate', email.utils.format_datetime(datetime.now(timezone.utc)))
    add_text(channel, 'generator', 'epub-server')
    add_text(channel, 'ttl', '5')

    atom_link = ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link')
    atom_link.set('href', absolute_url(site_url, 'feed.xml'))
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')

    for feed_item in rss_items:
        item = ET.SubElement(channel, 'item')
        add_text(item, 'title', feed_item['title'])
        add_text(item, 'link', feed_item['page_url'])

        guid = add_text(item, 'guid', feed_item['guid'])
        guid.set('isPermaLink', 'false')

        description = (
            f"{html.escape(feed_item['novel_title'])}<br />"
            f"{html.escape(feed_item['label'])}<br />"
            f"Source: {html.escape(feed_item['site'])}<br />"
            f"Status: {html.escape(feed_item['status'])}<br />"
            f"File size: {feed_item['file_size']} bytes<br />"
            f"<br />"
            f"<a href=\"{html.escape(feed_item['page_url'])}\">Open download page</a>"
        )

        add_text(item, 'description', description)
        add_text(item, 'pubDate', rss_date(feed_item['pub_date']))

    rough = ET.tostring(rss, encoding='utf-8')
    parsed = minidom.parseString(rough)
    FEED_FILE.write_bytes(parsed.toprettyxml(indent='  ', encoding='utf-8'))


def build_epub_links_page(site_url, items):
    library_url = absolute_url(site_url, 'index.html')
    feed_url = absolute_url(site_url, 'feed.xml')
    opds_url = absolute_url(site_url, 'opds.xml')
    rows = []

    for index, item in enumerate(items):
        title = html.escape(item['title'])
        epub_url = html.escape(item['epub_url'])
        page_url = html.escape(item['page_url'])
        pub_date = html.escape(rss_date(item['pub_date']))

        rows.append(f'''
        <article class="link-card">
          <h2>{title}</h2>
          <p class="date">{pub_date}</p>
          <div class="actions">
            <a class="button" href="{epub_url}" download>Download EPUB</a>
            <a class="button secondary" href="{page_url}">Open item page</a>
          </div>
          <p class="label">Direct EPUB URL:</p>
          <div class="url-row">
            <div id="epub-url-{index}" class="url-box">{epub_url}</div>
            <button class="copy-button" type="button" onclick="copyEpubUrl('epub-url-{index}', this)" aria-label="Copy EPUB URL" title="Copy EPUB URL">📋 Copy</button>
          </div>
        </article>
        ''')

    body = '\n'.join(rows) or '<p>No EPUB links found.</p>'

    page = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Direct EPUB Links</title>
  <style>
    :root {{ --gold:#f4d86b; --orange:#ee9d23; --bg:#080604; --card:#17100c; --border:rgba(244,216,107,.42); --text:#fff3bf; --muted:#d9c985; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:radial-gradient(circle at top,#211008,var(--bg) 45%); color:var(--text); font-family:Georgia,serif; }}
    header {{ max-width:980px; margin:0 auto; padding:36px 18px 18px; text-align:center; }}
    h1 {{ margin:0; color:var(--gold); font-size:clamp(34px,7vw,72px); line-height:1; }}
    .subtitle {{ color:#fff4c1; font-size:18px; font-weight:700; }}
    .top-links {{ display:flex; gap:12px; justify-content:center; flex-wrap:wrap; margin-top:18px; }}
    .grid {{ max-width:980px; margin:0 auto 60px; padding:18px; display:grid; grid-template-columns:1fr; gap:18px; }}
    .link-card {{ border:1px solid var(--border); border-radius:22px; background:var(--card); padding:22px; box-shadow:0 20px 50px rgba(0,0,0,.35); }}
    h2 {{ margin:0 0 8px; color:var(--gold); font-size:28px; line-height:1.15; }}
    .date {{ margin:0 0 14px; color:var(--muted); font-size:14px; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }}
    .button {{ display:inline-flex; align-items:center; justify-content:center; margin:4px 0; padding:11px 16px; border-radius:999px; background:linear-gradient(90deg,var(--gold),var(--orange)); color:#140901; text-decoration:none; font-weight:900; border:0; cursor:pointer; font-family:Georgia,serif; font-size:16px; }}
    .button.secondary {{ background:#302822; color:#fff3bf; border:1px solid rgba(255,255,255,.18); }}
    .label {{ margin:12px 0 6px; font-weight:900; }}
    .url-row {{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:10px; align-items:stretch; }}
    .url-box {{ padding:12px; border:1px solid rgba(244,216,107,.3); border-radius:12px; background:#050403; color:#fff3bf; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:13px; overflow-wrap:anywhere; user-select:all; min-height:46px; display:flex; align-items:center; }}
    .copy-button {{ border-radius:12px; border:1px solid rgba(244,216,107,.35); background:#302822; color:#fff3bf; padding:0 16px; font-weight:900; cursor:pointer; font-family:Georgia,serif; font-size:15px; min-height:46px; }}
    .copy-button:hover {{ background:#41352d; }}
    .copy-button.copied {{ background:linear-gradient(90deg,var(--gold),var(--orange)); color:#140901; }}
    @media (max-width:700px) {{ .grid {{ max-width:100%; padding:14px; }} .link-card {{ padding:18px; }} h2 {{ font-size:23px; }} .actions {{ flex-direction:column; }} .button {{ width:100%; }} .url-row {{ grid-template-columns:1fr; }} .copy-button {{ width:100%; padding:13px 16px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Direct EPUB Links</h1>
    <p class="subtitle">Copy a direct EPUB URL and paste it into XTEINK Import from link.</p>
    <div class="top-links">
      <a class="button secondary" href="{html.escape(library_url)}">Open Library</a>
      <a class="button secondary" href="{html.escape(feed_url)}">Open RSS Feed</a>
      <a class="button secondary" href="{html.escape(opds_url)}">Open OPDS Catalogue</a>
    </div>
  </header>
  <main class="grid">
    {body}
  </main>
  <script>
    function fallbackCopy(text) {{
      var textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.setAttribute('readonly', '');
      textArea.style.position = 'fixed';
      textArea.style.top = '-1000px';
      textArea.style.left = '-1000px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {{ document.execCommand('copy'); }} finally {{ document.body.removeChild(textArea); }}
    }}
    function copyEpubUrl(elementId, button) {{
      var element = document.getElementById(elementId);
      if (!element) return;
      var text = element.textContent.trim();
      if (!text) return;
      function markCopied() {{
        var originalText = button.textContent;
        button.classList.add('copied');
        button.textContent = 'Copied';
        setTimeout(function () {{ button.classList.remove('copied'); button.textContent = originalText; }}, 1400);
      }}
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(text).then(markCopied).catch(function () {{ fallbackCopy(text); markCopied(); }});
      }} else {{ fallbackCopy(text); markCopied(); }}
    }}
  </script>
</body>
</html>
'''

    EPUB_LINKS_FILE.write_text(page, encoding='utf-8')


def main():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    rss_item_limit = settings.get('rss_item_limit', 50)
    site_url = get_site_url()
    library = load_library()
    items = get_download_items(library, site_url)
    build_rss(site_url, items, rss_item_limit)
    build_epub_links_page(site_url, items)
    print(f'Generated {FEED_FILE} with {min(len(items), int(rss_item_limit or 50))} RSS items.')
    print(f'Generated {EPUB_LINKS_FILE} with {len(items)} EPUB links.')
    print(f'RSS URL: {absolute_url(site_url, "feed.xml")}')
    print(f'EPUB links URL: {absolute_url(site_url, "epub-links.html")}')


if __name__ == '__main__':
    main()
