from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

class SkillError(RuntimeError): pass

def out(d: dict[str, Any]): print(json.dumps(d, indent=2, sort_keys=True))
def fail(msg: str) -> int:
    print(json.dumps({"error": msg}, indent=2), file=sys.stderr); return 1

def run(args: list[str], cwd: Path|None=None, check: bool=False) -> subprocess.CompletedProcess[str]:
    try:
        cp=subprocess.run(args,cwd=str(cwd) if cwd else None,capture_output=True,text=True,encoding='utf-8',errors='replace')
    except FileNotFoundError as e:
        raise SkillError(f"Required executable not found: {args[0]}") from e
    if check and cp.returncode!=0:
        raise SkillError((cp.stderr or cp.stdout or f"Command failed: {' '.join(args)}").strip())
    return cp

def exe(name: str) -> str|None:
    found=shutil.which(name)
    if found: return found
    if name=='gh':
        p=Path(os.environ.get('ProgramFiles', r'C:\Program Files'))/'GitHub CLI'/'gh.exe'
        if p.exists(): return str(p)
    return None

def target_dir(s: str) -> Path:
    p=Path(s).expanduser().resolve()
    if not p.exists() or not p.is_dir(): raise SkillError(f"Target directory does not exist: {p}")
    return p

def git(cwd: Path, *args: str, check: bool=False):
    g=exe('git')
    if not g: raise SkillError('git executable not found')
    return run([g,*args], cwd=cwd, check=check)

def git_root(cwd: Path) -> Path|None:
    try:
        cp=git(cwd,'rev-parse','--show-toplevel')
        return Path(cp.stdout.strip()).resolve() if cp.returncode==0 and cp.stdout.strip() else None
    except SkillError:
        return None

def remote_origin(cwd: Path) -> str|None:
    try:
        cp=git(cwd,'remote','get-url','origin')
        return cp.stdout.strip() if cp.returncode==0 else None
    except SkillError:
        return None

def parse_github(remote: str|None) -> str|None:
    if not remote: return None
    m=re.match(r'(?:git@|ssh://git@)github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$', remote.strip())
    if m: return m.group(1)
    u=urlparse(remote.strip())
    if u.netloc.lower()=='github.com':
        path=u.path.strip('/'); path=path[:-4] if path.endswith('.git') else path
        return path if re.match(r'^[\w.-]+/[\w.-]+$', path) else None
    return None

def parse_ado(remote: str|None) -> dict[str,str]|None:
    if not remote: return None
    u=urlparse(remote.strip())
    if 'dev.azure.com' in u.netloc.lower():
        parts=[x for x in u.path.strip('/').split('/') if x]
        if len(parts)>=4 and parts[-2]=='_git': return {'org': parts[0], 'project': parts[1], 'repo': parts[-1]}
    m=re.match(r'https://([^@/]+@)?([^/]+)@dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+)', remote.strip())
    if m: return {'org': m.group(3), 'project': m.group(4), 'repo': m.group(5)}
    return None

def load_plan(path: str) -> dict[str, Any]:
    p=Path(path).expanduser().resolve()
    try: data=json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: raise SkillError(f'Could not read valid JSON plan: {e}') from e
    if not isinstance(data, dict): raise SkillError('Plan must be a JSON object')
    return data

def require_approved(plan: dict[str, Any]):
    if plan.get('approved') is not True: raise SkillError('Plan must include approved=true after explicit user approval')


def default_branch(p: Path) -> str:
    cp=git(p,'symbolic-ref','refs/remotes/origin/HEAD')
    if cp.returncode==0 and cp.stdout.strip(): return cp.stdout.strip().replace('refs/remotes/origin/','')
    return 'main'
def inspect(t):
    p=target_dir(t); root=git_root(p); 
    if not root: raise SkillError('Target is not inside a git repository')
    d=default_branch(root); branches=[x.strip().lstrip('* ').strip() for x in git(root,'branch','--format','%(refname:short)').stdout.splitlines() if x.strip()]
    tags=[x.strip() for x in git(root,'tag').stdout.splitlines() if x.strip()]
    deletable=[b for b in branches if b not in {d,'main','master'}]
    return {'repo':str(root),'default_branch':d,'local_branches':branches,'local_tags':tags,'deletable_branches':deletable,'deletable_tags':tags,'risk_flags':['destructive_local_delete'] if deletable or tags else [],'plan_shape':{'delete_branches':deletable,'delete_tags':tags,'pull':True,'approved':True}}
def apply(t, plan_path, dry):
    p=target_dir(t); root=git_root(p) or p; plan=load_plan(plan_path); require_approved(plan); d=default_branch(root); cmds=[['checkout',d],['fetch','--prune','--prune-tags']]
    for b in plan.get('delete_branches',[]): cmds.append(['branch','-D',b])
    for tag in plan.get('delete_tags',[]): cmds.append(['tag','-d',tag])
    if plan.get('pull',True): cmds.append(['pull'])
    if dry: return {'repo':str(root),'dry_run':True,'would_run':[['git',*c] for c in cmds]}
    results=[]
    for c in cmds:
        cp=git(root,*c); results.append({'command':['git',*c],'returncode':cp.returncode,'stdout':cp.stdout.strip()[:500],'stderr':cp.stderr.strip()[:500]})
    return {'repo':str(root),'results':results}
def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--target',required=True); i.add_argument('--json',action='store_true'); a=sub.add_parser('apply'); a.add_argument('--target',required=True); a.add_argument('--plan',required=True); a.add_argument('--dry-run',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect(ns.target) if ns.cmd=='inspect' else apply(ns.target,ns.plan,ns.dry_run)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
