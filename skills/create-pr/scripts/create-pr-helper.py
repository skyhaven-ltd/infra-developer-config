#!/usr/bin/env python3
"""Deterministic helper for the create-pr skill (VCS-aware).

Detects whether the target repository is hosted on GitHub or Azure DevOps from
its ``origin`` remote and dispatches pull-request creation to the right backend
(``gh`` or ``az``). The LLM remains responsible for judgement: drafting the PR
title/body from the diff, confirming the VCS when it cannot be inferred, and
obtaining explicit approval before the side-effecting ``apply`` command.
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys
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

def current_branch(cwd: Path) -> str|None:
    if not git_root(cwd): return None
    b=git(cwd,'branch','--show-current').stdout.strip()
    return b or None

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

def detect_vcs(remote: str|None) -> str|None:
    if parse_github(remote): return 'github'
    if parse_ado(remote): return 'ado'
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
                k,v=line.split(':',1); meta[k.strip()]=v.strip().strip('"')
    return {'path':str(path),'frontmatter':meta,'body':body.strip()}

def find_shared_template(start: Path, *parts: str) -> dict[str,Any]|None:
    for parent in [start, *start.parents]:
        for root in (parent, parent.parent):
            candidate=root.joinpath('.github','.github',*parts)
            if candidate.exists(): return parse_template(candidate)
    return None

def pull_request_template(start: Path) -> dict[str,Any]|None:
    return find_shared_template(start,'PULL_REQUEST_TEMPLATE','pull-request.md')

def branch_kind(branch: str) -> dict[str,str]|None:
    table=[(('feature/',),'feature'),(('major/','breaking/'),'feature'),(('fix/','hotfix/','bug/'),'bug_fix'),(('minor/','patch/','chore/','docs/'),'maintenance')]
    for prefixes,template in table:
        for prefix in prefixes:
            if branch.startswith(prefix):
                return {'template':template,'title_prefix':f"[{prefix.rstrip('/').upper()}]"}
    return None

def diff_stat(cwd: Path, base: str) -> dict[str,Any]:
    cp=git(cwd,'diff','--shortstat',f'{base}...HEAD')
    txt=cp.stdout.strip(); nums=[int(x) for x in re.findall(r'\d+',txt)]
    return {'shortstat':txt,'numbers':nums}

# ---- GitHub backend ---------------------------------------------------------

def gh_default_branch(gh: str, repo: str, cwd: Path) -> str|None:
    cp=run([gh,'api',f'repos/{repo}','--jq','.default_branch'],cwd=cwd)
    return cp.stdout.strip() if cp.returncode==0 else None

def gh_inspect(p: Path, remote: str|None) -> dict[str,Any]:
    gh=exe('gh'); repo=parse_github(remote); branch=current_branch(p); default=None; existing=[]
    if gh and repo:
        default=gh_default_branch(gh,repo,p)
        if branch:
            pr=run([gh,'pr','list','--repo',repo,'--head',branch,'--state','open','--json','url,number,title'],cwd=p)
            try: existing=json.loads(pr.stdout) if pr.returncode==0 and pr.stdout else []
            except json.JSONDecodeError: existing=[]
    flags={'gh_not_found':not gh,'repository_not_inferred':not repo,'default_branch_unknown':not default,'on_default_branch':bool(default and branch==default),'branch_prefix_unclear':not branch_kind(branch or ''),'pull_request_template_not_found':not pull_request_template(p)}
    return {'repository':repo,'current_branch':branch,'default_branch':default,'on_default_branch':bool(default and branch==default),'existing_pull_requests':existing,'risk_flags':[k for k,b in flags.items() if b]}

def gh_apply(p: Path, plan: dict[str,Any], dry: bool) -> dict[str,Any]:
    gh=exe('gh'); repo=plan.get('repository') or parse_github(remote_origin(p)); base=plan.get('base')
    if not gh or not repo: raise SkillError('gh and a GitHub repository are required')
    head=current_branch(p)
    if not head: raise SkillError('Could not determine the current branch in --target to use as the PR head')
    title=plan.get('title'); body=plan.get('body')
    if not isinstance(title,str) or not isinstance(body,str): raise SkillError('title and body are required')
    if not base:
        base=gh_default_branch(gh,repo,p)
        if not base: raise SkillError('Could not determine the base branch; set "base" in the plan')
    cmd=[gh,'pr','create','--repo',repo,'--head',head,'--base',base,'--title',title,'--body',body]
    if dry: return {'dry_run':True,'vcs':'github','would_run':cmd[1:]}
    cp=run(cmd,check=True,cwd=p); return {'vcs':'github','created_pr_url':cp.stdout.strip().splitlines()[-1]}

# ---- Azure DevOps backend ---------------------------------------------------

def ado_org_url(ado: dict[str,str]) -> str: return f"https://dev.azure.com/{ado['org']}"

def ado_inspect(p: Path, remote: str|None) -> dict[str,Any]:
    az=exe('az'); ado=parse_ado(remote); branch=current_branch(p); default=None; existing=[]
    if az and ado:
        org=ado_org_url(ado)
        cp=run([az,'repos','show','--org',org,'--project',ado['project'],'--repository',ado['repo'],'--query','defaultBranch','-o','tsv'],cwd=p)
        default=cp.stdout.strip().replace('refs/heads/','') if cp.returncode==0 else None
        if branch:
            pr=run([az,'repos','pr','list','--org',org,'--project',ado['project'],'--repository',ado['repo'],'--source-branch',branch,'--status','active','-o','json'],cwd=p)
            try: existing=json.loads(pr.stdout) if pr.returncode==0 and pr.stdout else []
            except json.JSONDecodeError: existing=[]
    flags={'az_not_found':not az,'repository_not_inferred':not ado,'default_branch_unknown':not default,'on_default_branch':bool(default and branch==default),'branch_prefix_unclear':not branch_kind(branch or ''),'pull_request_template_not_found':not pull_request_template(p)}
    return {'ado':ado,'current_branch':branch,'default_branch':default,'on_default_branch':bool(default and branch==default),'existing_pull_requests':existing,'risk_flags':[k for k,b in flags.items() if b]}

def ado_apply(p: Path, plan: dict[str,Any], dry: bool) -> dict[str,Any]:
    az=exe('az'); ado=plan.get('ado') or parse_ado(remote_origin(p))
    if not az or not isinstance(ado,dict): raise SkillError('az and ADO repo details (org/project/repo) are required')
    title=plan.get('title'); desc=plan.get('description') or plan.get('body')
    if not isinstance(title,str) or not isinstance(desc,str): raise SkillError('title and description/body are required')
    org=ado_org_url(ado)
    cmd=[az,'repos','pr','create','--org',org,'--project',ado['project'],'--repository',ado['repo'],'--target-branch',plan.get('target_branch') or plan.get('base') or 'main','--title',title,'--description',desc,'-o','json']
    for wi in plan.get('work_items',[]) or []: cmd.extend(['--work-items',str(wi)])
    if dry: return {'dry_run':True,'vcs':'ado','would_run':cmd[1:]}
    cp=run(cmd,check=True,cwd=p); data=json.loads(cp.stdout)
    pid=data.get('pullRequestId')
    return {'vcs':'ado','pullRequestId':pid,'url':f"{org}/{ado['project']}/_git/{ado['repo']}/pullrequest/{pid}"}

# ---- dispatch ---------------------------------------------------------------

def resolve_vcs(p: Path, override: str|None) -> str|None:
    if override in ('github','ado'): return override
    return detect_vcs(remote_origin(p))

def inspect(t: str, vcs_override: str|None) -> dict[str,Any]:
    p=target_dir(t); remote=remote_origin(p); vcs=resolve_vcs(p,vcs_override)
    base={'target':str(p),'git_remote_origin':remote,'vcs':vcs,'branch_mapping':branch_kind(current_branch(p) or ''),'pull_request_template':pull_request_template(p)}
    if vcs=='github': payload=gh_inspect(p,remote)
    elif vcs=='ado': payload=ado_inspect(p,remote)
    else:
        return {**base,'risk_flags':['vcs_not_detected'],'note':'Could not detect GitHub or Azure DevOps from origin; pass "vcs" in the plan or set origin.'}
    payload.setdefault('risk_flags',[])
    payload['diff_stat']=diff_stat(p,payload['default_branch']) if payload.get('default_branch') else None
    payload['plan_shape']={'vcs':vcs,'title':'Short title with branch_mapping.title_prefix','body':'Markdown body based on pull_request_template.body','approved':True,**({'work_items':[]} if vcs=='ado' else {})}
    return {**base,**payload}

def apply(t: str, plan_path: str, dry: bool) -> dict[str,Any]:
    p=target_dir(t); template=pull_request_template(p)
    if not template: raise SkillError('Shared pull request template not found: .github/.github/PULL_REQUEST_TEMPLATE/pull-request.md')
    plan=load_plan(plan_path); require_approved(plan)
    vcs=resolve_vcs(p,plan.get('vcs'))
    if vcs=='github': return gh_apply(p,plan,dry)
    if vcs=='ado': return ado_apply(p,plan,dry)
    raise SkillError('Could not detect VCS; set "vcs" to "github" or "ado" in the plan')

def main(argv=None):
    ap=argparse.ArgumentParser(description='VCS-aware pull request helper (GitHub or Azure DevOps).')
    sub=ap.add_subparsers(dest='cmd',required=True)
    i=sub.add_parser('inspect'); i.add_argument('--target',required=True); i.add_argument('--vcs',choices=['github','ado']); i.add_argument('--json',action='store_true')
    a=sub.add_parser('apply'); a.add_argument('--target',required=True); a.add_argument('--plan',required=True); a.add_argument('--dry-run',action='store_true')
    ns=ap.parse_args(argv)
    try: out(inspect(ns.target,ns.vcs) if ns.cmd=='inspect' else apply(ns.target,ns.plan,ns.dry_run)); return 0
    except (SkillError,json.JSONDecodeError) as e: return fail(str(e))

if __name__=='__main__': raise SystemExit(main())
