#!/usr/bin/env python3
"""Deterministic helper for the raise-issue skill.

Raises a GitHub issue classified as a bug, feature, or task: it picks the
matching shared issue template, sets the native (root-level) GitHub issue type,
adds the issue to the Sky Haven Project Board, and can create linked sub-issues.

The LLM is responsible for judgement: classifying the user's request as
bug/feature/task, expanding terse input into meaningful prose, deciding whether
to break the work into sub-issues, and obtaining explicit approval before the
side-effecting ``apply`` command runs.
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BOARD_ID = "PVT_kwDOEbaq0c4BcELw"   # Sky Haven Project Board
DEFAULT_ASSIGNEE = "liam-goodchild"
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Per-kind configuration: shared template, title prefix, native issue type, and
# the ordered (placeholder -> plan field) substitutions applied to the template.
KINDS: dict[str, dict[str, Any]] = {
    "feature": {
        "template": "feature-request.md",
        "prefix": "[FEATURE] - ",
        "issue_type": "Feature",
        "fields": ["problem", "solution"],
        "subs": [
            ("A clear and concise description of what the problem is. Ex. I'm always frustrated when [...]", "problem"),
            ("A clear and concise description of what you want to happen.", "solution"),
        ],
    },
    "bug": {
        "template": "bug-report.md",
        "prefix": "[BUG] - ",
        "issue_type": "Bug",
        "fields": ["description", "steps", "expected"],
        "subs": [
            ("A clear and concise description of what the bug is.", "description"),
            (re.compile(r"1\. Go to '.*?'\n2\. Click on '.*?'\n3\. Scroll down to '.*?'\n4\. See error"), "steps"),
            ("A clear and concise description of what you expected to happen.", "expected"),
        ],
    },
    "task": {
        "template": "task.md",
        "prefix": "[TASK] - ",
        "issue_type": "Task",
        "fields": ["what", "why"],
        "subs": [
            ("A clear and concise description of the work.", "what"),
            ("The reason this task is needed and the outcome it unblocks.", "why"),
        ],
    },
}


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

def git(cwd: Path, *args: str):
    g=exe('git')
    if not g: raise SkillError('git executable not found')
    return run([g,*args], cwd=cwd)

def remote_origin(cwd: Path) -> str|None:
    cp=git(cwd,'remote','get-url','origin')
    return cp.stdout.strip() if cp.returncode==0 else None

def parse_github(remote: str|None) -> str|None:
    if not remote: return None
    m=re.match(r'(?:git@|ssh://git@)github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$', remote.strip())
    if m: return m.group(1)
    u=urlparse(remote.strip())
    if u.netloc.lower()=='github.com':
        path=u.path.strip('/'); path=path[:-4] if path.endswith('.git') else path
        return path if REPO_PATTERN.match(path) else None
    return None

def gh_auth(gh: str|None) -> dict[str,Any]:
    if not gh: return {'ok':False,'summary':'gh not found'}
    cp=run([gh,'auth','status','-h','github.com'])
    return {'ok':cp.returncode==0,'summary':'authenticated' if cp.returncode==0 else 'not authenticated'}

def parse_template(path: Path) -> dict[str,Any]:
    text=path.read_text(encoding='utf-8'); meta: dict[str,str]={}; body=text
    if text.startswith('---\n'):
        _, fm, body=text.split('---\n',2)
        for line in fm.splitlines():
            if ':' in line:
                k,v=line.split(':',1); meta[k.strip()]=v.strip().strip('"')
    return {'path':str(path),'frontmatter':meta,'body':body.strip()}

def find_issue_template(start: Path, name: str) -> dict[str,Any]|None:
    for parent in [start,*start.parents]:
        for root in (parent, parent.parent):
            candidate=root.joinpath('.github','.github','ISSUE_TEMPLATE',name)
            if candidate.exists(): return parse_template(candidate)
    return None

def require_kind(plan: dict[str,Any]) -> str:
    kind=plan.get('kind')
    if kind not in KINDS: raise SkillError(f"Plan field 'kind' must be one of {sorted(KINDS)}")
    return kind

def req(plan: dict[str,Any], field: str) -> str:
    v=plan.get(field)
    if not isinstance(v,str) or not v.strip(): raise SkillError(f"Plan field '{field}' must be a non-empty string for this kind")
    return v.strip()

def normalize_title(title: str, prefix: str) -> str:
    t=title.strip()
    return t if t.lower().startswith(prefix.lower()) else prefix+t

def build_body(plan: dict[str,Any], kind: str, start: Path) -> str:
    cfg=KINDS[kind]; template=find_issue_template(start, cfg['template'])
    if not template:
        raise SkillError(f"Shared issue template not found: .github/.github/ISSUE_TEMPLATE/{cfg['template']}")
    body=template['body']
    for placeholder, field in cfg['subs']:
        value=req(plan, field)
        if isinstance(placeholder, re.Pattern): body=placeholder.sub(value.replace('\\','\\\\'), body, count=1)
        else: body=body.replace(placeholder, value, 1)
    if kind=='task' and plan.get('acceptance'):
        acc=plan['acceptance']
        items='\n'.join(f"- [ ] {a}" for a in acc) if isinstance(acc,list) else str(acc)
        body=re.sub(r"- \[ \] \.\.\.\n- \[ \] \.\.\.", items, body, count=1)
    return body.strip()

# ---- GitHub side effects ----------------------------------------------------

def create_issue(gh: str, repo: str, title: str, body: str, assignee: str, cwd: Path) -> dict[str,str]:
    cp=run([gh,'issue','create','--repo',repo,'--title',title,'--assignee',assignee,'--body',body],cwd=cwd,check=True)
    url=cp.stdout.strip().splitlines()[-1].strip(); m=re.search(r'/issues/(\d+)',url)
    if not m: raise SkillError(f'Could not parse issue URL: {url}')
    return {'url':url,'number':m.group(1)}

def set_issue_type(gh: str, repo: str, number: str, type_name: str, cwd: Path) -> None:
    run([gh,'api','-X','PATCH',f'repos/{repo}/issues/{number}','-f',f'type={type_name}'],cwd=cwd,check=True)

def issue_node_id(gh: str, repo: str, number: str, cwd: Path) -> str:
    nid=run([gh,'api',f'repos/{repo}/issues/{number}','--jq','.node_id'],cwd=cwd,check=True).stdout.strip()
    if not nid: raise SkillError('Could not read created issue node id')
    return nid

def graphql(gh: str, query: str, fields: dict[str,str], cwd: Path) -> dict[str,Any]:
    args=[gh,'api','graphql','-f',f'query={query}']
    for k,v in fields.items(): args+=['-f',f'{k}={v}']
    return json.loads(run(args,cwd=cwd,check=True).stdout)

def add_to_board(gh: str, node: str, cwd: Path) -> str:
    q='mutation($p: ID!, $c: ID!){ addProjectV2ItemById(input:{projectId:$p, contentId:$c}){ item{ id } } }'
    item=graphql(gh,q,{'p':BOARD_ID,'c':node},cwd).get('data',{}).get('addProjectV2ItemById',{}).get('item',{}).get('id')
    if not item: raise SkillError('Could not add issue to the project board')
    return item

def link_sub_issue(gh: str, parent_node: str, child_node: str, cwd: Path) -> None:
    q='mutation($p: ID!, $s: ID!){ addSubIssue(input:{issueId:$p, subIssueId:$s}){ issue{ id } } }'
    graphql(gh,q,{'p':parent_node,'s':child_node},cwd)

def raise_one(gh: str, repo: str, spec: dict[str,Any], start: Path, cwd: Path) -> dict[str,Any]:
    kind=require_kind(spec); cfg=KINDS[kind]
    title=normalize_title(req(spec,'title'), cfg['prefix'])
    body=build_body(spec, kind, start)
    assignee=spec.get('assignee') or DEFAULT_ASSIGNEE
    issue=create_issue(gh,repo,title,body,assignee,cwd)
    set_issue_type(gh,repo,issue['number'],cfg['issue_type'],cwd)
    node=issue_node_id(gh,repo,issue['number'],cwd)
    item=add_to_board(gh,node,cwd)
    return {'kind':kind,'issue_type':cfg['issue_type'],'url':issue['url'],'number':issue['number'],'node_id':node,'board_item_id':item}

# ---- commands ---------------------------------------------------------------

def inspect(t: str) -> dict[str,Any]:
    p=target_dir(t); gh=exe('gh'); remote=remote_origin(p); repo=parse_github(remote); auth=gh_auth(gh)
    templates={k:bool(find_issue_template(p,cfg['template'])) for k,cfg in KINDS.items()}
    flags=[]
    if not repo: flags.append('repository_not_inferred')
    if not gh: flags.append('gh_not_found')
    elif not auth['ok']: flags.append('gh_not_authenticated')
    if not all(templates.values()): flags.append('issue_template_not_found')
    return {
        'target':str(p),'git_remote_origin':remote,'inferred_repository':repo,'gh_path':gh,'gh_auth':auth,
        'kinds':sorted(KINDS),'templates_found':templates,
        'project':{'id':BOARD_ID,'issue_types':{k:cfg['issue_type'] for k,cfg in KINDS.items()}},
        'required_plan_fields':{k:['kind','title',*cfg['fields'],'approved'] for k,cfg in KINDS.items()},
        'defaults':{'assignee':DEFAULT_ASSIGNEE},
        'supports':{'sub_issues':True},
        'risk_flags':flags,
    }

def apply(t: str, plan_path: str, dry: bool) -> dict[str,Any]:
    p=target_dir(t)
    try: plan=json.loads(Path(plan_path).expanduser().read_text(encoding='utf-8'))
    except Exception as e: raise SkillError(f'Could not read valid JSON plan: {e}') from e
    if not isinstance(plan,dict): raise SkillError('Plan must be a JSON object')
    if plan.get('approved') is not True: raise SkillError('Plan must include approved=true after explicit user approval')
    gh=exe('gh')
    if not gh: raise SkillError('gh executable not found')
    repo=plan.get('repository') or parse_github(remote_origin(p))
    if not repo or not REPO_PATTERN.match(repo): raise SkillError("A valid 'repository' (owner/repo) is required")
    kind=require_kind(plan)
    # Validate everything (parent + subs) before any side effects.
    cfg=KINDS[kind]; preview_title=normalize_title(req(plan,'title'),cfg['prefix']); preview_body=build_body(plan,kind,p)
    subs=plan.get('sub_issues') or []
    if not isinstance(subs,list): raise SkillError("'sub_issues' must be a list")
    for s in subs:
        sk=require_kind(s); normalize_title(req(s,'title'),KINDS[sk]['prefix']); build_body(s,sk,p)
    if dry:
        return {'dry_run':True,'repository':repo,'kind':kind,'issue_type':cfg['issue_type'],'title':preview_title,
                'body_preview':preview_body,'board':BOARD_ID,'sub_issue_count':len(subs),
                'would_create_issue':True,'would_set_issue_type':cfg['issue_type'],'would_add_to_board':True}
    parent=raise_one(gh,repo,plan,p,p)
    children=[]
    for s in subs:
        child=raise_one(gh,repo,s,p,p)
        try: link_sub_issue(gh,parent['node_id'],child['node_id'],p); child['linked']=True
        except SkillError as e: child['linked']=False; child['link_error']=str(e)
        children.append(child)
    return {'repository':repo,'created_issue_url':parent['url'],'issue_number':parent['number'],
            'issue_type_set':parent['issue_type'],'board_item_id':parent['board_item_id'],'sub_issues':children}

def main(argv=None):
    ap=argparse.ArgumentParser(description='Raise a classified GitHub issue (bug/feature/task) with native type and board linking.')
    sub=ap.add_subparsers(dest='cmd',required=True)
    i=sub.add_parser('inspect'); i.add_argument('--target',required=True); i.add_argument('--json',action='store_true')
    a=sub.add_parser('apply'); a.add_argument('--target',required=True); a.add_argument('--plan',required=True); a.add_argument('--dry-run',action='store_true')
    ns=ap.parse_args(argv)
    try: out(inspect(ns.target) if ns.cmd=='inspect' else apply(ns.target,ns.plan,ns.dry_run)); return 0
    except (SkillError,json.JSONDecodeError) as e: return fail(str(e))

if __name__=='__main__': raise SystemExit(main())
