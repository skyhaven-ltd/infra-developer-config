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

BUG_PREFIX='[BUG] - '; DEFAULT_LABEL='use-type-field-instead'; DEFAULT_ASSIGNEE='liam-goodchild'; PROJECT_ID='PVT_kwHOB9ID-s4BU_KB'; TYPE_FIELD_ID='PVTSSF_lAHOB9ID-s4BU_KBzhRbk2o'; BUG_OPTION_ID='951d9251'
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
def normalize_title(t, template=None):
    t=t.strip(); prefix=BUG_PREFIX
    if template:
        raw=template.get('frontmatter',{}).get('title','')
        m=re.match(r'(\[[^]]+\]\s*-\s*)', raw)
        if m: prefix=m.group(1)
    return t if t.lower().startswith(prefix.lower()) else prefix+t
def build_body(desc, steps, expected, template):
    if not template: raise SkillError('Shared bug issue template not found: .github/.github/ISSUE_TEMPLATE/bug-report.md')
    body=template['body']
    body=body.replace('A clear and concise description of what the bug is.', desc.strip())
    body=re.sub(r"1\. Go to '.*?'\n2\. Click on '.*?'\n3\. Scroll down to '.*?'\n4\. See error", steps.strip(), body)
    body=body.replace('A clear and concise description of what you expected to happen.', expected.strip())
    return body.strip()
def inspect(t):
    p=target_dir(t); gh=exe('gh'); remote=remote_origin(p); repo=parse_github(remote); auth={'ok':False,'summary':'gh not found'}
    if gh:
        cp=run([gh,'auth','status','-h','github.com']); auth={'ok':cp.returncode==0,'summary':'authenticated' if cp.returncode==0 else 'not authenticated'}
    template=find_issue_template(p,'bug-report.md'); fm=template.get('frontmatter',{}) if template else {}; return {'target':str(p),'git_remote_origin':remote,'inferred_repository':repo,'gh_path':gh,'gh_auth':auth,'issue_template':template,'project':{'id':PROJECT_ID,'type_field_id':TYPE_FIELD_ID,'bug_option_id':BUG_OPTION_ID},'required_plan_fields':['repository','title','description','steps','expected','approved'],'defaults':{'label':DEFAULT_LABEL,'assignee':fm.get('assignees',DEFAULT_ASSIGNEE),'title_prefix':fm.get('title',BUG_PREFIX+'Placeholder')},'risk_flags':[k for k,b in {'repository_not_inferred':not repo,'gh_not_found':not gh,'gh_not_authenticated':gh and not auth['ok'],'issue_template_not_found':not template}.items() if b]}
def req(plan,k):
    v=plan.get(k)
    if not isinstance(v,str) or not v.strip(): raise SkillError(f'{k} must be a non-empty string')
    return v.strip()
def gh_graphql(gh,query,fields):
    args=[gh,'api','graphql','-f',f'query={query}']
    for k,v in fields.items(): args += ['-f',f'{k}={v}']
    cp=run(args,check=True); return json.loads(cp.stdout)
def apply(t, plan_path, dry):
    p=target_dir(t); plan=load_plan(plan_path); require_approved(plan); gh=exe('gh')
    if not gh: raise SkillError('gh executable not found')
    repo=req(plan,'repository'); template=find_issue_template(p,'bug-report.md'); fm=template.get('frontmatter',{}) if template else {}; title=normalize_title(req(plan,'title'),template); body=build_body(req(plan,'description'),req(plan,'steps'),req(plan,'expected'),template)
    summary={'repository':repo,'title':title,'body_preview':body,'label':plan.get('label',DEFAULT_LABEL),'assignee':plan.get('assignee',fm.get('assignees',DEFAULT_ASSIGNEE)),'project':{'id':PROJECT_ID,'type':'Bug'}}
    if dry: return {**summary,'dry_run':True,'would_create_issue':True,'would_set_project_type':True}
    cp=run([gh,'issue','create','--repo',repo,'--title',title,'--label',summary['label'],'--assignee',summary['assignee'],'--body',body],check=True)
    url=cp.stdout.strip().splitlines()[-1]; m=re.search(r'/issues/(\d+)',url)
    if not m: raise SkillError(f'Could not parse issue URL: {url}')
    node=run([gh,'api',f'repos/{repo}/issues/{m.group(1)}','--jq','.node_id'],check=True).stdout.strip()
    add='mutation($projectId: ID!, $contentId: ID!) { addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) { item { id } } }'
    item=gh_graphql(gh,add,{'projectId':PROJECT_ID,'contentId':node}).get('data',{}).get('addProjectV2ItemById',{}).get('item',{}).get('id')
    setq='mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) { updateProjectV2ItemFieldValue(input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: { singleSelectOptionId: $optionId }}) { projectV2Item { id } } }'
    if item: gh_graphql(gh,setq,{'projectId':PROJECT_ID,'itemId':item,'fieldId':TYPE_FIELD_ID,'optionId':BUG_OPTION_ID})
    return {**summary,'created_issue_url':url,'issue_number':m.group(1),'project_item_id':item,'project_type_set':'Bug'}
def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--target',required=True); i.add_argument('--json',action='store_true'); a=sub.add_parser('apply'); a.add_argument('--target',required=True); a.add_argument('--plan',required=True); a.add_argument('--dry-run',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect(ns.target) if ns.cmd=='inspect' else apply(ns.target,ns.plan,ns.dry_run)); return 0
    except (SkillError,json.JSONDecodeError) as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
