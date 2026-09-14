"""Preserve a reviewable working-tree snapshot alongside an agent receipt."""
from pathlib import Path
from backend import run_command


def capture_changes(workspace: Path, evidence: Path, state: Path):
    revision=run_command(['git','rev-parse','HEAD'],workspace,10)
    if revision['returncode']!=0:
        return {'status':'not_git','scope':'working_tree_against_HEAD'}
    tracked=run_command(['git','diff','--binary','HEAD'],workspace,10)
    untracked=run_command(['git','ls-files','--others','--exclude-standard','-z'],workspace,10)
    if tracked['returncode']!=0 or untracked['returncode']!=0:
        return {'status':'unavailable','scope':'working_tree_against_HEAD'}
    patches=[tracked['stdout']];omitted=[]
    for name in untracked['stdout'].split('\0'):
        if not name:continue
        path=workspace/name
        if path.is_symlink() or path.resolve().is_relative_to(state.resolve()):
            omitted.append({'path':name,'reason':'symlink_or_private_state'});continue
        if not path.is_file() or path.stat().st_size>1024*1024:
            omitted.append({'path':name,'reason':'not_regular_or_over_1MiB'});continue
        result=run_command(['git','diff','--no-index','--binary','--','/dev/null',name],workspace,10)
        if result['returncode'] in (0,1):patches.append(result['stdout'])
        else:omitted.append({'path':name,'reason':'diff_failed'})
    path=evidence/'changes.diff';path.write_text('\n'.join(patches))
    return {'status':'captured','base_commit':revision['stdout'].strip(),'diff':str(path),
            'scope':'working_tree_against_HEAD_including_preexisting_edits','omitted':omitted}
