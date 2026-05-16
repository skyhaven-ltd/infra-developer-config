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

def find_vault(arg=None):
    if arg: return target_dir(arg)
    cand=[Path.home()/'Documents'/'Second Brain']
    for p in cand:
        if p.exists(): return p.resolve()
    raise SkillError('Vault not found; ask for the vault path')
def inspect(vault=None):
    v=find_vault(vault); inbox=v/'00 - Inbox'; notes=v/'02 - Notes'; mocs=v/'01 - MOCs'; vocab=v/'99 - Meta'/'AI Formatting'/'tag-vocabulary.md'
    inbox_files=[x for x in inbox.glob('*.md')] if inbox.exists() else []
    return {'vault':str(v),'inbox_exists':inbox.exists(),'inbox_files':[{'path':str(x.relative_to(v)),'bytes':x.stat().st_size,'has_frontmatter':frontmatter(read_text(x)) is not None} for x in inbox_files],'note_titles':[x.stem for x in notes.glob('*.md')] if notes.exists() else [],'moc_titles':[x.stem for x in mocs.glob('*.md')] if mocs.exists() else [],'tag_vocabulary_exists':vocab.exists(),'tag_vocabulary_path':str(vocab) if vocab.exists() else None,'risk_flags':[k for k,b in {'missing_inbox':not inbox.exists(),'missing_notes':not notes.exists(),'missing_tag_vocabulary':not vocab.exists()}.items() if b], 'llm_decisions':['new permanent note','append to existing','split','discard with confirmation']}
def main(argv=None):
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); i=sub.add_parser('inspect'); i.add_argument('--vault',default=None); i.add_argument('--json',action='store_true'); ns=ap.parse_args(argv)
    try: out(inspect(ns.vault)); return 0
    except SkillError as e: return fail(str(e))
if __name__=='__main__': raise SystemExit(main())
