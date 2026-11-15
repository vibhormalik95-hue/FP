"""Create a local fingerprint for separately reviewed personal CLI files.

This does not approve files, start hooks, run the CLI, or establish managed context.
"""
import argparse,hashlib,json,os
from pathlib import Path
ALLOW=('SYSTEMROOT','WINDIR','APPDATA','LOCALAPPDATA','USERPROFILE','HOMEDRIVE','HOMEPATH','HOME','PATH','TEMP','TMP','TMPDIR')
FIXED={'CLAUDE_CODE_MAX_RETRIES':'0','CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES':'0','MAX_STRUCTURED_OUTPUT_RETRIES':'1','CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK':'1','CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK':'1','DISABLE_AUTOUPDATER':'1'}
def safe(value):
 p=Path(value)
 if not p.is_absolute() or '..' in p.parts:raise ValueError('absolute_path_required')
 for part in (p,*p.parents):
  if part.is_symlink():raise ValueError('link_rejected')
  junction=getattr(part,'is_junction',None)
  if os.name=='nt' and not callable(junction):raise ValueError('junction_check_unavailable')
  if callable(junction) and junction():raise ValueError('junction_rejected')
 return p
def sha(path):return hashlib.sha256(safe(path).read_bytes()).hexdigest()
def unique(pairs):
 result={}
 for k,v in pairs:
  if k in result:raise ValueError('duplicate_json_key')
  result[k]=v
 return result
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('cli','home','plugin','node','output'):parser.add_argument('--'+name,required=True)
 parser.add_argument('--tokens',required=True,type=int,choices=range(1,32769),metavar='1..32768')
 a=parser.parse_args();home=safe(a.home);plugin=safe(a.plugin);out=safe(a.output)
 if out.exists() or not out.parent.is_dir():raise ValueError('new_output_required')
 manifest=plugin/'.claude-plugin'/'plugin.json';value=json.loads(manifest.read_bytes(),object_pairs_hook=unique)
 hooks=value['hooks'];commands={}
 for event in ('SessionStart','UserPromptSubmit'):
  groups=hooks[event]
  if len(groups)!=1 or len(groups[0]['hooks'])!=1:raise ValueError('unsupported_hook_layout')
  command=groups[0]['hooks'][0]['command']
  if not isinstance(command,str):raise ValueError('invalid_hook_command')
  commands[event]=hashlib.sha256(command.encode('utf-8')).hexdigest()
 env={k:os.environ[k] for k in ALLOW if k in os.environ};env.update(FIXED);env['CLAUDE_CODE_MAX_OUTPUT_TOKENS']=str(a.tokens)
 envhash=hashlib.sha256(json.dumps(env,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8')).hexdigest()
 result={'cli_sha256':sha(a.cli),'settings_sha256':sha(home/'.claude'/'settings.json'),'node_sha256':sha(a.node),
  'path_sha256':hashlib.sha256(os.environ.get('PATH','').encode()).hexdigest(),
  'plugin_manifest_sha256':sha(manifest),'plugin_skill_sha256':sha(plugin/'skills'/'caveman'/'SKILL.md'),
  'hook_activate_sha256':sha(plugin/'hooks'/'caveman-activate.js'),'hook_tracker_sha256':sha(plugin/'hooks'/'caveman-mode-tracker.js'),
  'hook_config_sha256':sha(plugin/'hooks'/'caveman-config.js'),'hook_sessionstart_command_sha256':commands['SessionStart'],
  'hook_prompt_command_sha256':commands['UserPromptSubmit'],'child_env_sha256':envhash,'max_output_tokens':str(a.tokens)}
 data=(json.dumps(result,sort_keys=True,indent=2)+'\n').encode('utf-8')
 with out.open('xb') as handle:handle.write(data)
 print('context_sha256='+hashlib.sha256(data).hexdigest())
 print('Local fingerprint only; independent review and action authorization are still required.')
if __name__=='__main__':main()
