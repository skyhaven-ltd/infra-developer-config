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
    try: cp=subprocess.run(args,cwd=str(cwd) if cwd else None,capture_output=True,text=True,encoding='utf-8',errors='replace')
    except FileNotFoundError as e: raise SkillError(f"Required executable not found: {args[0]}") from e
    if check and cp.returncode!=0: raise SkillError((cp.stderr or cp.stdout or f"Command failed: {' '.join(args)}").strip())
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
    except SkillError: return None
def remote_origin(cwd: Path) -> str|None:
    try:
        cp=git(cwd,'remote','get-url','origin')
        return cp.stdout.strip() if cp.returncode==0 else None
    except SkillError: return None
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
    return None
def load_plan(path: str) -> dict[str, Any]:
    p=Path(path).expanduser().resolve()
    try: data=json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: raise SkillError(f'Could not read valid JSON plan: {e}') from e
    if not isinstance(data, dict): raise SkillError('Plan must be a JSON object')
    return data
def require_approved(plan: dict[str, Any]):
    if plan.get('approved') is not True: raise SkillError('Plan must include approved=true after explicit user approval')

def parse_arg(arg: str|None) -> dict[str,Any]:
    if not arg: return {'input':None,'number':None,'provider':None}
    s=arg.strip()
    if re.fullmatch(r'\d+',s): return {'input':s,'number':s,'provider':None}
    if 'github.com' in s:
        m=re.search(r'/pull/(\d+)',s); return {'input':s,'number':m.group(1) if m else None,'provider':'github'}
    if 'dev.azure.com' in s:
        m=re.search(r'/pullrequest/(\d+)',s); return {'input':s,'number':m.group(1) if m else None,'provider':'ado'}
    return {'input':s,'number':None,'provider':None}
def inspect(t,arg=None):
    p=target_dir(t); root=git_root(p); remote=remote_origin(p); provider='github' if parse_github(remote) else ('ado' if parse_ado(remote) else None); parsed=parse_arg(arg); number=parsed['number']
    branch=None; stat=None
    if root:
        branch=git(root,'branch','--show-current').stdout.strip(); cp=git(root,'diff','--shortstat','HEAD~1..HEAD'); stat=cp.stdout.strip() if cp.returncode==0 else None
    return {'target':str(p),'git_root':str(root) if root else None,'origin':remote,'current_branch':branch,'provider':parsed['provider'] or provider,'parsed_argument':parsed,'pr_number':number,'diff_stat_sample':stat,'risk_flags':[k for k,b in {'not_git_repo':not root,'provider_unknown':not (parsed['provider'] or provider),'pr_number_unknown':not number}.items() if b], 'review_focus':['scope','correctness','security','IaC','testing'], 'large_diff_threshold_lines':500}
def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--target',required=True); i.add_argument('--pr',default=None); i.add_argument('--json',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect(ns.target,ns.pr)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
