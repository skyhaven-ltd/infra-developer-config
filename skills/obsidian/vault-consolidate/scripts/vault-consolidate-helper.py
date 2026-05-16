from __future__ import annotations
import argparse, json, re, sys, os
from pathlib import Path
from typing import Any
class SkillError(RuntimeError): pass
def out(d: dict[str, Any]): print(json.dumps(d, indent=2, sort_keys=True))
def fail(m: str): print(json.dumps({'error':m}, indent=2), file=sys.stderr); return 1
def target_dir(s: str) -> Path:
    p=Path(s).expanduser().resolve()
    if not p.exists() or not p.is_dir(): raise SkillError(f'Target directory does not exist: {p}')
    return p
def md_files(p: Path): return [x for x in p.rglob('*.md') if '.git' not in x.parts]
def read_text(p: Path) -> str:
    return p.read_text(encoding='utf-8', errors='replace')
def frontmatter(text: str) -> str|None:
    return text.split('---',2)[1] if text.startswith('---') and text.count('---')>=2 else None

def find_vault(arg=None):
    if arg: return target_dir(arg)
    p=Path.home()/'Documents'/'Second Brain'
    if p.exists(): return p.resolve()
    raise SkillError('Vault not found; ask for the vault path')
def wikilinks(txt): return [m.split('|',1)[0].split('#',1)[0].strip() for m in re.findall(r'\[\[([^\]]+)\]\]',txt)]
def inspect(vault=None):
    v=find_vault(vault); scan_dirs=[v/'02 - Notes',v/'01 - MOCs',v/'99 - Meta'/'Archived Journal']; files=[f for d in scan_dirs if d.exists() for f in d.glob('*.md')]
    names={f.stem for f in files}; dead=[]; backlinks={n:0 for n in names}; tags={}
    for f in files:
        txt=read_text(f)
        for link in wikilinks(txt):
            if link and link not in names: dead.append({'file':str(f.relative_to(v)),'target':link})
            elif link in backlinks: backlinks[link]+=1
        for tag in re.findall(r'(?<!\w)#([-\w/]+)',txt): tags[tag]=tags.get(tag,0)+1
    orphans=[n for n,c in backlinks.items() if c==0 and (v/'02 - Notes'/f'{n}.md').exists()]
    return {'vault':str(v),'files_scanned':len(files),'dead_wikilinks':dead[:200],'dead_wikilink_count':len(dead),'orphan_note_titles':orphans[:200],'orphan_count':len(orphans),'applied_tags':tags,'report_path_suggestion':str(v/'99 - Meta'/'AI Formatting'/'vault-consolidation-YYYY-MM-DD.report.md'),'llm_decisions':['similarity judgement','MOC tag mapping','merge/delete recommendations']}
def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--vault',default=None); i.add_argument('--json',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect(ns.vault)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
