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

def inspect_file(path):
    p=Path(path).expanduser().resolve()
    if not p.exists() or p.suffix.lower()!='.md': raise SkillError(f'Markdown file does not exist: {p}')
    txt=read_text(p); headings=re.findall(r'(?m)^#\s+(.+)$',txt); h1_expected=' '.join(w.capitalize() for w in p.stem.split())
    return {'file':str(p),'bytes':len(txt.encode()),'has_frontmatter':frontmatter(txt) is not None,'h1_headings':headings,'expected_h1':h1_expected,'wikilink_count':len(re.findall(r'\[\[[^\]]+\]\]',txt)),'tag_count':len(re.findall(r'(?<!\w)#[-\w/]+',txt)),'contains_em_dash':'—' in txt,'trailing_whitespace_lines':[i+1 for i,l in enumerate(txt.splitlines()) if l.rstrip()!=l][:50],'llm_must_preserve':['frontmatter','wikilinks','tags','embeds','tasks','code fences','dates','paths','quoted text']}
def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--file',required=True); i.add_argument('--json',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect_file(ns.file)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
