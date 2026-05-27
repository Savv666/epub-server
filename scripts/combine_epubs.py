import argparse
from pathlib import Path
from ebooklib import epub
from slugify import slugify
from library_utils import load_library, save_library

ROOT = Path('.')
DOCS = ROOT / 'docs'
EPUBS = DOCS / 'epubs'


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--novel-slug', default='')
    p.add_argument('--novel-name', default='')
    p.add_argument('--files', default='')
    p.add_argument('--start-chapter', type=int, default=1)
    p.add_argument('--end-chapter', type=int, default=999999)
    p.add_argument('--overwrite', default='no')
    return p.parse_args()


def resolve_from_request(args):
    req = ROOT / 'data' / 'epub_manager_request.json'
    if req.exists() and (not args.novel_slug and not args.novel_name and not args.files):
        import json
        r = json.loads(req.read_text(encoding='utf-8'))
        c = r.get('combine', {})
        args.novel_slug = c.get('novel_slug', '')
        args.novel_name = c.get('novel_name', '')
        args.files = '\n'.join(c.get('files', []))
        args.start_chapter = int(c.get('start', args.start_chapter) or args.start_chapter)
        args.end_chapter = int(c.get('end', args.end_chapter) or args.end_chapter)
        args.overwrite = c.get('overwrite', args.overwrite)
    return args


def main():
    args = resolve_from_request(parse_args())
    lib = load_library()
    slug = args.novel_slug or slugify(args.novel_name)
    novel = next((n for n in lib if n.get('slug') == slug or n.get('title', '').lower() == args.novel_name.lower()), None)
    if not novel:
        raise SystemExit('novel not found')

    downloads = novel.get('downloads', [])
    files = [x.strip() for x in (args.files or '').splitlines() if x.strip()]
    if files:
        parts = [d for d in downloads if Path(d.get('url', '')).name in files or d.get('url', '') in files]
    else:
        parts = [d for d in downloads if int(d.get('start', 0)) >= args.start_chapter and int(d.get('end', 0)) <= args.end_chapter]

    parts = sorted(parts, key=lambda d: int(d.get('start', 0)))
    if len(parts) < 2:
        raise SystemExit('need >=2 chunks')

    out_name = f"{novel['slug']}_ch{int(parts[0]['start']):03d}-{int(parts[-1]['end']):03d}_combined.epub"
    out = EPUBS / out_name
    if out.exists() and str(args.overwrite).lower() != 'yes':
        raise SystemExit('combined already exists; set overwrite yes')

    book = epub.EpubBook()
    book.set_identifier(out_name)
    book.set_title(f"{novel['title']} Combined")
    book.set_language('en')
    book.add_author('Unknown')

    toc, spine, idx = [], ['nav'], 1
    for part in parts:
        old = epub.read_epub(str(DOCS / part['url']))
        for it in old.get_items():
            if it.get_type() == 9 and 'nav' not in it.get_name().lower():
                ch = epub.EpubHtml(title=it.get_name(), file_name=f'ch_{idx:05d}.xhtml', content=it.get_content())
                book.add_item(ch)
                toc.append(ch)
                spine.append(ch)
                idx += 1

    book.toc = tuple(toc)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(out), book)

    novel.setdefault('downloads', []).append({
        'label': f"Chapters {parts[0]['start']}-{parts[-1]['end']} (Combined)",
        'start': parts[0]['start'], 'end': parts[-1]['end'], 'url': f'epubs/{out_name}',
        'mode': 'Combined', 'combined': True,
        'combined_from': [p['url'] for p in parts]
    })
    save_library(lib)


if __name__ == '__main__':
    main()
