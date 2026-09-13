"""Prepare four fixed upstream repositories with authored sequential maintenance requests."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
from agent_product_runner import ARMS

SOURCES={
 'boltons':('https://github.com/mahmoud/boltons.git','961dcff3f42e73b245aef65e377fe82763b257bb'),
 'more-itertools':('https://github.com/more-itertools/more-itertools.git','9ed3dbb0ae527230cd156d91d0af305478558fba'),
 'packaging':('https://github.com/pypa/packaging.git','10590c194edb33c82f84a127883d6097c56b7840'),
 'itsdangerous':('https://github.com/pallets/itsdangerous.git','672971d66a2ef9f85151e53283113f33d642dabd'),
}

SCENARIOS={
 'boltons':{
  'path':'boltons/strutils.py',
  'history':[
   'For future edits in boltons/strutils.py, filename_slug defaults to delimiter underscore and ascii=False. legacy_slug must keep underscore and ascii=False defaults. Both new wrappers return str, unlike the existing slugify ascii=True bytes result.',
   'Correction for future edits in boltons/strutils.py: filename_slug now defaults to delimiter hyphen and ascii=True, replacing its old defaults. This correction does not apply to legacy_slug or the existing slugify API.',
  ],
  'prompts':[
   'Add filename_slug(text, delimiter=None, ascii=None) to boltons/strutils.py, wrapping the existing slugify implementation. Resolve omitted/None options from prior project instructions; preserve explicit empty delimiters and False. Return str for either ascii mode. Keep existing public behavior and document the new function.',
   'Add legacy_slug(text, delimiter=None, ascii=None) in boltons/strutils.py using its own prior project policy. Return str and preserve explicit overrides. Preserve filename_slug and existing APIs. Document the function.',
   'Add filename_slugs(texts, delimiter=None, ascii=None) to boltons/strutils.py, returning a list and accepting one-pass iterables. Reuse filename_slug, bring that helper into the current project policy, and preserve legacy_slug and all existing APIs.',
  ],
  'later':'Correction for future edits in boltons/strutils.py: filename_slug now defaults to delimiter dot and ascii=False, replacing its hyphen/ascii=True defaults. filename_slugs must delegate to filename_slug. legacy_slug and the original slugify defaults remain unchanged.',
 },
 'more-itertools':{
  'path':'more_itertools/more.py',
  'history':[
   'For future edits in more_itertools/more.py, new strict_chunked and compatible_chunked wrappers both default to strict=False. They must delegate to chunked, remain lazy, require positive n and honor explicit strict overrides.',
   'Correction for future edits in more_itertools/more.py: strict_chunked defaults to strict=True instead of False. compatible_chunked and existing chunked and sliced APIs must retain their previous defaults. This is a wrapper-specific change.',
  ],
  'prompts':[
   'Add strict_chunked(iterable, n, strict=None) in more_itertools/more.py and expose it through the package public API. Follow prior project policy for None, preserve explicit overrides, require positive n, and preserve chunked laziness for one-pass iterables. Keep existing APIs and add a docstring.',
   'Add compatible_chunked(iterable, n, strict=None) as a public wrapper with its own prior project default. Preserve one-pass laziness and explicit strict values. Keep strict_chunked and existing chunked/sliced behavior.',
   'Add public strict_chunked_map(iterables, n, strict=None), returning a list of fully materialized chunk lists for each input iterable. Reuse strict_chunked and update its default to current project policy. Preserve explicit False and True, compatible_chunked, and existing APIs.',
  ],
  'later':'Correction for future edits in more_itertools/more.py: strict_chunked now defaults back to strict=False, replacing strict=True; the name does not mandate its default. strict_chunked_map delegates to strict_chunked. compatible_chunked and existing APIs are unchanged.',
 },
 'packaging':{
  'path':'src/packaging/utils.py',
  'history':[
   'For future edits in src/packaging/utils.py, project_version and compat_version both default to strip_trailing_zero=True and pass invalid strings through, matching canonicalize_version. Explicit False must be preserved.',
   'Correction for future edits in src/packaging/utils.py: project_version defaults to strip_trailing_zero=False and must reject invalid strings with InvalidVersion. These replace its previous policies. compat_version and the existing canonicalize_version API retain their original policies.',
  ],
  'prompts':[
   'Add project_version(value, *, strip_trailing_zero=None) to src/packaging/utils.py and its public exports. Accept str or Version, use existing version parsing/canonicalization helpers, follow current project defaults and invalid-input policy, and preserve explicit True/False. Keep existing APIs and document it.',
   'Add public compat_version(value, *, strip_trailing_zero=None) in src/packaging/utils.py using its own prior project policy. Handle str and Version with explicit overrides, preserving project_version and existing APIs.',
   'Add public project_versions(values, *, strip_trailing_zero=None) to src/packaging/utils.py, returning a list from a one-pass iterable using project_version. Bring project_version into the latest project policy. Preserve compat_version and all existing APIs.',
  ],
  'later':'Correction for future edits in src/packaging/utils.py: project_version now defaults to strip_trailing_zero=True again; its InvalidVersion rejection rule remains in force. project_versions delegates to project_version. compat_version and canonicalize_version remain unchanged.',
 },
 'itsdangerous':{
  'path':'src/itsdangerous/timed.py',
  'history':[
   'For future edits in src/itsdangerous/timed.py, module-level loads_session and loads_legacy helpers both default to max_age=3600 seconds when their max_age argument is None. Explicit zero must be honored. Signature and expiration exceptions propagate.',
   'Correction for future edits in src/itsdangerous/timed.py: loads_session now defaults to max_age=60 seconds instead of 3600. loads_legacy keeps 3600. Existing TimedSerializer.loads behavior is unchanged. Explicit zero and exception propagation remain required.',
  ],
  'prompts':[
   'Add module-level loads_session(serializer, token, max_age=None) in src/itsdangerous/timed.py. Delegate to the supplied TimedSerializer using the prior project timeout policy. Preserve explicit zero and propagate signature/expiry errors. Keep existing classes and behavior unchanged. Add a docstring.',
   'Add module-level loads_legacy(serializer, token, max_age=None) in src/itsdangerous/timed.py using its own prior project policy. Preserve explicit overrides and errors, loads_session, and existing classes.',
   'Add module-level loads_sessions(serializer, tokens, max_age=None) in src/itsdangerous/timed.py returning a list from a one-pass iterable via loads_session. Bring loads_session into current project policy; preserve loads_legacy and existing APIs. Propagate errors instead of filtering invalid tokens.',
  ],
  'later':'Correction for future edits in src/itsdangerous/timed.py: loads_session now defaults to max_age=120 seconds, replacing 60. loads_sessions delegates to loads_session. loads_legacy remains at 3600, explicit zero still applies, and exceptions still propagate.',
 },
}


def prepare(root):
    root=root.resolve();sources=root/'sources';sources.mkdir(parents=True,exist_ok=True)
    manifest={'schema':2,'evaluation_mode':'pilot','codex_model':'gpt-5.6-sol','effort':'medium',
              'timeout_seconds':240,'task_source':'authored maintenance scenarios on fixed real repositories',
              'blocked_backends':{},
              'clusters':[]}
    checker=Path(__file__).with_name('real_project_checker.py').resolve()
    for cluster_index,(name,(url,commit)) in enumerate(SOURCES.items()):
        source=sources/name
        if not source.exists():
            subprocess.run(['git','clone','--depth','1',url,str(source)],check=True)
        actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
        if actual!=commit:
            subprocess.run(['git','fetch','origin',commit],cwd=source,check=True)
            subprocess.run(['git','checkout','--detach',commit],cwd=source,check=True)
        cluster={'id':name,'source_url':url,'base_commit':commit,'workspaces':{},'steps':[],
                 'arm_order_offset':cluster_index % 2}
        for arm in ARMS:
            workspace=root/'workspaces'/name/arm;workspace.parent.mkdir(parents=True,exist_ok=True)
            subprocess.run(['git','worktree','add','--detach',str(workspace),commit],cwd=source,check=True,capture_output=True)
            (workspace/'.agent-benchmark-worktree').write_text(name+' '+arm+'\n')
            cluster['workspaces'][arm]=str(workspace)
        spec=SCENARIOS[name]
        for i,prompt in enumerate(spec['prompts']):
            cluster['steps'].append({'id':f'{name}-{i+1}',
                'kind':'same_topic_control' if i==1 else 'necessary_update',
                'prompt':prompt,'paths':[spec['path']],
                'history':spec['history'] if i==0 else [spec['later']] if i==2 else [],
                'checker':[sys.executable,str(checker),name,str(i+1)]})
        # Before coding, old APIs must pass and absent new features must fail.
        result=subprocess.run([sys.executable,str(checker),name,'1'],cwd=source,text=True,capture_output=True)
        observed=json.loads(result.stdout)
        if result.returncode!=1 or not observed['compatibility']['pass']:
            raise RuntimeError(f'invalid checker baseline: {name}: {result.stdout} {result.stderr}')
        cluster['checker_baseline']=observed;manifest['clusters'].append(cluster)
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();prepare(args.root);print(args.root/'manifest.json')
