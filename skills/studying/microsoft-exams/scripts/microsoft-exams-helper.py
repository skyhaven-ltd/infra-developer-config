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

def inspect_url(url):
    from urllib.parse import urlparse
    u=urlparse(url)
    if u.netloc.lower()!='learn.microsoft.com': raise SkillError('Use a learn.microsoft.com URL as the source of truth')
    return {'url':url,'host':u.netloc,'path':u.path,'is_learning_path':'/training/paths/' in u.path,'is_module':'/training/modules/' in u.path,'risk_flags':['learning_path_confirm_scope'] if '/training/paths/' in u.path else [],'llm_tasks':['fetch module landing page and unit pages','extract themes','build mental models','produce scenario reasoning with source links']}
def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--url',required=True); i.add_argument('--json',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect_url(ns.url)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
