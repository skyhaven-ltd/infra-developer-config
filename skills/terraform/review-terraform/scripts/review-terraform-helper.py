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
    p=target_dir(t); files=[x for x in list(p.rglob('*.tf'))+list(p.rglob('*.tfvars'))+list((p/'.github'/'workflows').glob('*.yml') if (p/'.github'/'workflows').exists() else []) if '.terraform' not in x.parts]
    signals=[]
    pats=[('state_file',r'terraform\.tfstate'),('hardcoded_secret',r'(?i)(password|client_secret|api[_-]?key)\s*=\s*"[^"]+"'),('owner_or_contributor',r'Owner|Contributor'),('dynamic_block',r'\bdynamic\s+"'),('explicit_depends_on',r'\bdepends_on\s*=')]
    for f in files:
        txt=read_text(f); rel=str(f.relative_to(p)).replace('\\','/')
        for name,pat in pats:
            for m in re.finditer(pat,txt): signals.append({'signal':name,'file':rel,'line':txt[:m.start()].count('\n')+1})
    return {'target':str(p),'files_scanned':len(files),'signals':signals[:300],'signal_count':len(signals),'review_areas':['minimalism','variables','state','outputs','security','resource design','modules','CI/CD'], 'llm_tasks':['turn signals into justified findings','avoid nitpicks','prioritise every-line-is-a-liability improvements']}
def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--target',required=True); i.add_argument('--json',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect(ns.target)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
