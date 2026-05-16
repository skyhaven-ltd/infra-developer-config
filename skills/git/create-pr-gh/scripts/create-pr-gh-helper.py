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

def parse_template(path: Path) -> dict[str,Any]:
    text=path.read_text(encoding='utf-8')
    meta: dict[str,str]={}; body=text
    if text.startswith('---\n'):
        _, fm, body = text.split('---\n', 2)
        for line in fm.splitlines():
            if ':' in line:
                k,v=line.split(':',1); meta[k.strip()]=v.strip().strip('\"')
    return {'path':str(path),'frontmatter':meta,'body':body.strip()}

def find_shared_template(start: Path, *parts: str) -> dict[str,Any]|None:
    for parent in [start, *start.parents]:
        candidate=parent.joinpath('.github','.github',*parts)
        if candidate.exists(): return parse_template(candidate)
        candidate=parent.parent.joinpath('.github','.github',*parts) if parent.parent else candidate
        if candidate.exists(): return parse_template(candidate)
    return None

def pull_request_template(start: Path) -> dict[str,Any]|None:
    return find_shared_template(start,'PULL_REQUEST_TEMPLATE','pull-request.md')

def branch_kind(branch: str) -> dict[str,str]|None:
    table=[(('feature/',),'feature'),(('major/','breaking/'),'feature'),(('fix/','hotfix/','bug/'),'bug_fix'),(('minor/','patch/','chore/','docs/'),'maintenance')]
    for prefixes,template in table:
        for prefix in prefixes:
            if branch.startswith(prefix):
                title_prefix=f"[{prefix.rstrip('/').upper()}]"
                return {'template':template,'title_prefix':title_prefix}
    return None

def diff_stat(cwd: Path, base: str) -> dict[str,Any]:
    cp=git(cwd,'diff','--shortstat',f'{base}...HEAD')
    txt=cp.stdout.strip(); nums=[int(x) for x in re.findall(r'\d+',txt)]
    return {'shortstat':txt,'numbers':nums}


def inspect(t: str) -> dict[str,Any]:
    p=target_dir(t); gh=exe('gh'); remote=remote_origin(p); repo=parse_github(remote); branch=(git(p,'branch','--show-current').stdout.strip() if git_root(p) else None)
    default=None; existing=[]
    if gh and repo:
        cp=run([gh,'api',f'repos/{repo}','--jq','.default_branch']); default=cp.stdout.strip() if cp.returncode==0 else None
        if branch:
            pr=run([gh,'pr','list','--repo',repo,'--head',branch,'--state','open','--json','url,number,title']);
            try: existing=json.loads(pr.stdout) if pr.returncode==0 and pr.stdout else []
            except json.JSONDecodeError: existing=[]
    kind=branch_kind(branch or '')
    return {'target':str(p),'repository':repo,'current_branch':branch,'default_branch':default,'on_default_branch':bool(default and branch==default),'existing_pull_requests':existing,'branch_mapping':kind,'diff_stat':diff_stat(p,default) if default else None,'risk_flags':[k for k,b in {'gh_not_found':not gh,'repository_not_inferred':not repo,'default_branch_unknown':not default,'on_default_branch':bool(default and branch==default),'branch_prefix_unclear':not kind,'pull_request_template_not_found':not pull_request_template(p)}.items() if b], 'pull_request_template':pull_request_template(p), 'plan_shape': {'title':'Short title with branch_mapping.title_prefix','body':'Markdown body based on pull_request_template.body','approved':True}}

def apply(t, plan_path, dry):
    p=target_dir(t); template=pull_request_template(p);
    if not template: raise SkillError('Shared pull request template not found: .github/.github/PULL_REQUEST_TEMPLATE/pull-request.md')
    plan=load_plan(plan_path); require_approved(plan); gh=exe('gh'); repo=plan.get('repository') or parse_github(remote_origin(p)); base=plan.get('base')
    if not gh or not repo: raise SkillError('gh and repository are required')
    title=plan.get('title'); body=plan.get('body')
    if not isinstance(title,str) or not isinstance(body,str): raise SkillError('title and body are required')
    if not base:
        cp=run([gh,'api',f'repos/{repo}','--jq','.default_branch'],check=True); base=cp.stdout.strip()
    cmd=[gh,'pr','create','--repo',repo,'--base',base,'--title',title,'--body',body]
    if dry: return {'dry_run':True,'would_run':cmd[1:]}
    cp=run(cmd,check=True); return {'created_pr_url':cp.stdout.strip().splitlines()[-1]}

def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--target',required=True); i.add_argument('--json',action='store_true'); a=sub.add_parser('apply'); a.add_argument('--target',required=True); a.add_argument('--plan',required=True); a.add_argument('--dry-run',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect(ns.target) if ns.cmd=='inspect' else apply(ns.target,ns.plan,ns.dry_run)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
