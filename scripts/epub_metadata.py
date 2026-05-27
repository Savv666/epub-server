from datetime import datetime, timezone
import re
from ebooklib import epub


def clean_chapter_title(title, chapter_number=None, novel_title=''):
    text = re.sub(r'\s+', ' ', str(title or '')).strip()
    text = re.sub(r'\s*\|\s*(NovelBin|WuxiaWorld|Read Novel Online Free).*$','', text, flags=re.I)
    text = re.sub(r'\s*-\s*(NovelBin|WuxiaWorld|Read Novel Online Free).*$','', text, flags=re.I)
    if novel_title:
        text = re.sub(re.escape(novel_title), '', text, flags=re.I).strip()
    text = re.sub(r'^(Chapter\s*0*\d+)\s+\1', r'\1', text, flags=re.I)
    text = re.sub(r'Chapter\s*0*(\d+)\s+Chapter\s*0*(\d+)', lambda m: f'Chapter {int(m.group(2))}', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip(' -:|')
    if not text:
        if chapter_number is not None:
            return f'Chapter {int(chapter_number)}'
        return 'Untitled Chapter'
    return text


def apply_standard_metadata(book: epub.EpubBook, meta: dict):
    uid = meta.get('uid') or f"epub-server-{meta.get('slug','novel')}-{int(datetime.now(timezone.utc).timestamp())}"
    book.set_identifier(uid)
    book.set_title(meta.get('title') or 'Unknown Title')
    book.set_language(meta.get('language') or 'en')
    book.add_author(meta.get('author') or 'Unknown')
    book.add_metadata('DC', 'description', meta.get('description') or '')
    book.add_metadata('DC', 'source', meta.get('source_url') or '')
    book.add_metadata(None, 'meta', '', {'name': 'source_site', 'content': meta.get('source_site') or ''})
    book.add_metadata(None, 'meta', '', {'name': 'series_name', 'content': meta.get('series_name') or meta.get('title') or ''})
    book.add_metadata(None, 'meta', '', {'name': 'chapter_range', 'content': meta.get('chapter_range') or ''})
    book.add_metadata(None, 'meta', '', {'name': 'build_timestamp', 'content': datetime.now(timezone.utc).isoformat()})
