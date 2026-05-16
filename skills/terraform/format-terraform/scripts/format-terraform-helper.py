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

def line_no(text, idx): return text[:idx].count('\n')+1
def inspect(t):
    p=target_dir(t); tf=[x for x in p.rglob('*.tf') if '.terraform' not in x.parts]; tfvars=[x for x in p.rglob('*.tfvars')]
    findings=[]
    for f in tf:
        rel=str(f.relative_to(p)).replace('\\','/')
        if not rel.startswith('infra/'): findings.append({'rule':1,'file':rel,'line':1,'finding':'.tf file outside infra/'})
        txt=read_text(f)
        if 'terraform.lock.hcl' in rel: findings.append({'rule':6,'file':rel,'line':1,'finding':'Terraform lock file present'})
        for m in re.finditer(r'(?m)^\s*count\s*=\s*(.+)$',txt):
            expr=m.group(1).strip();
            if '?' not in expr or ':' not in expr: findings.append({'rule':10,'file':rel,'line':line_no(txt,m.start()),'finding':'Non-conditional count; prefer for_each'})
        for m in re.finditer(r'(?m)^\s*variable\s+"([^"]+)"\s*{',txt):
            block=txt[m.start():txt.find('\n}',m.start())+2]
            if 'type' not in block: findings.append({'rule':11,'file':rel,'line':line_no(txt,m.start()),'finding':f'Variable {m.group(1)} has no type constraint'})
        if re.search(r'(?m)^\s*#\s*(resource|variable|output|locals|data)\b',txt): findings.append({'rule':5,'file':rel,'line':1,'finding':'Commented-out Terraform block detected'})
    for f in tfvars:
        rel=str(f.relative_to(p)).replace('\\','/')
        if not rel.startswith('infra/vars/'): findings.append({'rule':1,'file':rel,'line':1,'finding':'.tfvars file outside infra/vars/'})
        txt=read_text(f)
        if txt.strip() and '#########################################' not in txt: findings.append({'rule':12,'file':rel,'line':1,'finding':'Missing tfvars area comment blocks'})
    return {'target':str(p),'tf_files':len(tf),'tfvars_files':len(tfvars),'findings':findings,'finding_count':len(findings),'llm_tasks':['judge grouping by functional purpose','confirm CAF abbreviations','offer safe auto-fix plan']}
def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--target',required=True); i.add_argument('--json',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect(ns.target)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
