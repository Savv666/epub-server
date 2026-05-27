import json
from pathlib import Path
from ebooklib import epub
from slugify import slugify
from library_utils import load_library, save_library

ROOT=Path('.')
REQ=ROOT/'data/epub_manager_request.json'
DOCS=ROOT/'docs'
EPUBS=DOCS/'epubs'

def main():
    req=json.loads(REQ.read_text(encoding='utf-8'))
    items=req.get('items') or []
    if not items:
        name=req.get('combine',{}).get('novel_name') or req.get('delete',{}).get('novel_name') or ''
        start=int(req.get('combine',{}).get('start',1) or 1); end=int(req.get('combine',{}).get('end',999999) or 999999)
    else:
        i=items[0]; name=i.get('novel_title',''); start=int(i.get('start_chapter',1)); end=int(i.get('end_chapter',999999) or 999999)
    lib=load_library(); slug=slugify(name)
    novel=next((n for n in lib if n.get('slug')==slug or n.get('title','').lower()==name.lower()),None)
    if not novel: raise SystemExit('novel not found')
    parts=[d for d in novel.get('downloads',[]) if int(d.get('start',0))>=start and int(d.get('end',0))<=end]
    parts=sorted(parts,key=lambda d:int(d.get('start',0)))
    if len(parts)<2: raise SystemExit('need >=2 chunks')
    combined_name=f"{novel['slug']}_ch{parts[0]['start']:03d}-{parts[-1]['end']:03d}_combined.epub"
    out=EPUBS/combined_name
    if out.exists(): raise SystemExit('combined already exists')
    book=epub.EpubBook(); book.set_identifier(combined_name); book.set_title(f"{novel['title']} Combined") ; book.set_language('en'); book.add_author('Unknown')
    spine=['nav']; toc=[]; idx=1
    for p in parts:
        src=DOCS/p['url']
        old=epub.read_epub(str(src))
        for item in old.get_items():
            if item.get_type()==9 and 'nav' not in item.get_name():
                ch=epub.EpubHtml(title=item.get_name(), file_name=f'ch_{idx:05d}.xhtml', content=item.get_content())
                book.add_item(ch); spine.append(ch); toc.append(ch); idx+=1
    book.toc=tuple(toc); book.spine=spine; book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav()); epub.write_epub(str(out),book)
    novel.setdefault('downloads',[]).append({'label':f"Chapters {parts[0]['start']}-{parts[-1]['end']} (Combined)", 'start':parts[0]['start'],'end':parts[-1]['end'],'url':f"epubs/{combined_name}",'mode':'Combined','combined':True,'combined_from':[p['url'] for p in parts]})
    save_library(lib)

if __name__=='__main__': main()
