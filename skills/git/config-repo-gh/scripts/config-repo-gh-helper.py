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


def inspect(t: str) -> dict[str,Any]:
    p=target_dir(t); remote=remote_origin(p); gh=exe('gh'); g=exe('git')
    auth={'ok': False, 'summary': 'gh not found'}
    if gh:
        cp=run([gh,'auth','status','-h','github.com']); auth={'ok': cp.returncode==0, 'summary': 'authenticated' if cp.returncode==0 else 'not authenticated'}
    root=git_root(p)
    branch=None
    if root:
        cp=git(p,'branch','--show-current'); branch=cp.stdout.strip() if cp.returncode==0 else None
    return {'target':str(p),'git_root':str(root) if root else None,'current_branch':branch,'origin':remote,'inferred_repository':parse_github(remote),'gh_path':gh,'git_path':g,'gh_auth':auth,'risk_flags':[x for x,bad in {'gh_not_found':not gh,'git_not_found':not g,'repository_not_inferred':not parse_github(remote)}.items() if bad], 'plan_shape': {'repository':'owner/repo','visibility':'private|public','rename_to':None,'link_project':True,'approved':True}}

def apply(t: str, plan_path: str, dry: bool) -> dict[str,Any]:
    p=target_dir(t); plan=load_plan(plan_path); require_approved(plan); gh=exe('gh')
    if not gh: raise SkillError('gh executable not found')
    repo=plan.get('repository')
    if not isinstance(repo,str) or not re.match(r'^[\w.-]+/[\w.-]+$',repo): raise SkillError('repository must be owner/repo')
    commands=[['repo','edit',repo,'--enable-auto-merge=false','--delete-branch-on-merge=true','--enable-issues=true'], ['api',f'repos/{repo}/private-vulnerability-reporting','--method','PUT'], ['api',f'repos/{repo}/vulnerability-alerts','--method','PUT'], ['api',f'repos/{repo}/automated-security-fixes','--method','PUT']]
    if plan.get('rename_to'): commands.append(['api',f'repos/{repo}','--method','PATCH','--field',f"name={plan['rename_to']}"])
    if dry: return {'target':str(p),'dry_run':True,'would_run':commands}
    results=[]
    for c in commands:
        cp=run([gh,*c]); results.append({'command':['gh',*c],'returncode':cp.returncode,'stderr':cp.stderr.strip()[:500]})
    return {'target':str(p),'repository':repo,'results':results}

def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    i=sub.add_parser('inspect'); i.add_argument('--target',required=True); i.add_argument('--json',action='store_true')
    a=sub.add_parser('apply'); a.add_argument('--target',required=True); a.add_argument('--plan',required=True); a.add_argument('--dry-run',action='store_true')
    ns=ap.parse_args(argv)
    try: out(inspect(ns.target) if ns.cmd=='inspect' else apply(ns.target,ns.plan,ns.dry_run)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
