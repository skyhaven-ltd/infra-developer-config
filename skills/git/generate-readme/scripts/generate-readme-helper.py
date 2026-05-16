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

def inspect(t):
    p=target_dir(t)
    files=[x for x in p.rglob('*') if x.is_file() and '.git' not in x.parts and x.name!='README.md'][:300]
    langs={}
    for f in files:
        langs[f.suffix or '[none]']=langs.get(f.suffix or '[none]',0)+1
    candidates=[str(f.relative_to(p)) for f in files if f.name.lower() in {'pyproject.toml','package.json','go.mod','main.py','app.py','README.md'}]
    return {'target':str(p),'repo_name':p.name,'file_count_sampled':len(files),'extensions':langs,'important_files':candidates,'readme_exists':(p/'README.md').exists(),'llm_tasks':['read representative code','write two or three factual sentences','omit setup, badges, inventories and Terraform docs']}
def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--target',required=True); i.add_argument('--json',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect(ns.target)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
