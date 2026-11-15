"""Synthetic qualification checks; no native, app, CLI or provider execution."""
import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
BLOCKED=[]
def guard(event,args):
    if (event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.spawn','os.posix_spawn','os.exec','os.fork','ctypes.dlopen'}
        or (event=='import' and args and (str(args[0]).split('.')[0] in {'anthropic','openai','ollama','torch','transformers'} or str(args[0])=='feedctrl.windows_job_native'))):
        BLOCKED.append(event); raise RuntimeError('blocked offline operation')
sys.addaudithook(guard)
from diagnostic import qualification as q
from diagnostic import bootstrap
from diagnostic import stream_projection as projector
from diagnostic import rejection_observer as observer
from diagnostic import diagnostic_transport as transport

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def put(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return digest(path)
def js(obj):return json.dumps(obj,separators=(',',':')).encode()

class Checks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name).absolute()
        self.home=root/'home';self.work=root/'work';self.work.mkdir();self.cli=root/'cli';self.node=root/'node'
        self.context=root/'context.json';self.cli.write_bytes(b'synthetic cli');self.node.write_bytes(b'synthetic node')
        plugin=self.home/'.claude'/'plugins'/'cache'/'test-plugin'
        activate=plugin/'hooks'/'caveman-activate.js';track=plugin/'hooks'/'caveman-mode-tracker.js';conf=plugin/'hooks'/'caveman-config.js';skill=plugin/'skills'/'caveman'/'SKILL.md';manifest=plugin/'.claude-plugin'/'plugin.json'
        hooks={'SessionStart':[{'hooks':[{'command':'synthetic-session-hook'}]}], 'UserPromptSubmit':[{'hooks':[{'command':'synthetic-prompt-hook'}]}]}
        manifest_sha=put(manifest,js({'hooks':hooks}))
        settings=self.home/'.claude'/'settings.json';settings_sha=put(settings,js({'enabledPlugins':{'test':True}}))
        put(self.home/'.claude'/'plugins'/'installed_plugins.json',js({'plugins':{'test':[{'installPath':str(plugin)}]}}))
        self.hashes={'cli_sha256':digest(self.cli),'settings_sha256':settings_sha,'node_sha256':digest(self.node),
          'path_sha256':hashlib.sha256(b'synthetic-path').hexdigest(),'plugin_manifest_sha256':manifest_sha,
          'plugin_skill_sha256':put(skill,b'synthetic skill'),'hook_activate_sha256':put(activate,b'activate'),
          'hook_tracker_sha256':put(track,b'tracker'),'hook_config_sha256':put(conf,b'config'),
          'hook_sessionstart_command_sha256':hashlib.sha256(b'synthetic-session-hook').hexdigest(),
          'hook_prompt_command_sha256':hashlib.sha256(b'synthetic-prompt-hook').hexdigest()}
        ambient={'PATH':'synthetic-path','HOME':str(self.home),'USERPROFILE':str(self.home),
          'HOMEDRIVE':self.home.drive,'HOMEPATH':str(self.home)[len(self.home.drive):],
          'APPDATA':str(self.home/'AppData'/'Roaming'),'LOCALAPPDATA':str(self.home/'AppData'/'Local')}
        self.env=patch.dict(os.environ,ambient,clear=True);self.env.start()
        self.which=patch.object(q.shutil,'which',return_value=str(self.node));self.which.start()
        self.real_bootstrap=q._require_bootstrap;self.boot=patch.object(q,'_require_bootstrap');self.boot.start()
        self.child=dict(ambient,CLAUDE_CODE_MAX_RETRIES='0',CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES='0',
          MAX_STRUCTURED_OUTPUT_RETRIES='1',CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK='1',
          CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK='1',DISABLE_AUTOUPDATER='1',CLAUDE_CODE_MAX_OUTPUT_TOKENS='4096')
        self.hashes['max_output_tokens']='4096'
        self.hashes['child_env_sha256']=hashlib.sha256(json.dumps(self.child,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
        self.context.write_bytes(js(self.hashes));self.args={'context_file':self.context,'context_sha256':digest(self.context),'cli':self.cli,'workdir':self.work,'home':self.home}
    def tearDown(self):self.boot.stop();self.which.stop();self.env.stop();self.tmp.cleanup()
    def test_valid_context_is_inert_and_does_not_authorize(self):
        self.assertEqual(q.preflight(**self.args),{'qualified':True,'authorization_established':False,'managed_context_verified':False,'live_calls':0})
    def test_context_wrong_hash_and_duplicate_key_fail_closed(self):
        args=dict(self.args,context_sha256='0'*64)
        with self.assertRaises(q.QualificationError):q.preflight(**args)
        self.context.write_bytes(b'{"cli_sha256":"a","cli_sha256":"b"}')
        with self.assertRaises(q.QualificationError):q.preflight(**dict(self.args,context_sha256=digest(self.context)))
    def test_hook_settings_and_cli_mutations_fail(self):
        self.cli.write_bytes(b'changed')
        with self.assertRaises(q.QualificationError):q.preflight(**self.args)
        self.cli.write_bytes(b'synthetic cli');(self.home/'.claude'/'settings.json').write_bytes(b'{}')
        with self.assertRaises(q.QualificationError):q.preflight(**self.args)
    def test_nonempty_workdir_and_instructions_fail(self):
        (self.work/'x').write_text('x')
        with self.assertRaises(q.QualificationError):q.preflight(**self.args)
        (self.work/'x').unlink();(self.work/'CLAUDE.md').write_text('x')
        with self.assertRaises(q.QualificationError):q.preflight(**self.args)
        (self.work/'CLAUDE.md').unlink();(self.home/'CLAUDE.md').write_text('x')
        with self.assertRaises(q.QualificationError):q.preflight(**self.args)
    def test_pin_mismatch_is_rejected(self):
        with patch.dict(q.PINS,{'diagnostic/stream_projection.py':'0'*64}):
            with self.assertRaises(q.QualificationError):q.preflight(**self.args)
    def test_no_default_activation(self):
        with self.assertRaises(q.QualificationError):q.bind_once(marker=self.context.parent/'marker',**self.args)
        self.assertNotIn('feedctrl.windows_job_native',sys.modules)
        with self.assertRaises(q.QualificationError):q.bind_once(marker=self.context.parent/'marker',enable_live=True,**self.args)
        self.assertFalse((self.context.parent/'marker').exists())
    def test_one_call_and_failed_calls_consume(self):
        calls=[]
        def fake(*args):calls.append(1);return 'synthetic'
        wrapped=q._OneCall(fake,self.args,self.context.parent/'marker')
        call=([str(self.cli)],b'',dict(self.child),str(self.work),1,100)
        self.assertEqual(wrapped(*call),'synthetic')
        with self.assertRaises(q.QualificationError):wrapped(*call)
        self.assertEqual(calls,[1]);self.assertEqual((self.context.parent/'marker').read_bytes(),b'consumed\n')
        other=q._OneCall(fake,self.args,self.context.parent/'marker')
        with self.assertRaises(q.QualificationError):other(*call)
        wrong=q._OneCall(fake,self.args,self.context.parent/'other-marker')
        with self.assertRaises(q.QualificationError):wrong([str(self.cli)+'x'],*call[1:])
        with self.assertRaises(q.QualificationError):wrong(*call)
        self.assertEqual(calls,[1])
    def test_child_environment_mismatches_stop_before_dispatch_and_marker(self):
        calls=[]
        for index,key in enumerate(('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','HOMEDRIVE','HOMEPATH','PATH','CLAUDE_CODE_MAX_OUTPUT_TOKENS')):
            with self.subTest(key=key):
                marker=self.context.parent/('bad-'+str(index))
                wrapped=q._OneCall(lambda *args:calls.append(1),self.args,marker)
                bad=dict(self.child);bad[key]='synthetic-mismatch'
                with self.assertRaises(q.QualificationError):wrapped([str(self.cli)],b'',bad,str(self.work),1,100)
                self.assertFalse(marker.exists())
        marker=self.context.parent/'extra-env';wrapped=q._OneCall(lambda *args:calls.append(1),self.args,marker)
        bad=dict(self.child,UNREVIEWED='synthetic')
        with self.assertRaises(q.QualificationError):wrapped([str(self.cli)],b'',bad,str(self.work),1,100)
        self.assertFalse(marker.exists());self.assertEqual(calls,[])
    def test_missing_and_mutated_security_environment_rejected(self):
        calls=[]
        for index,key in enumerate(('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','HOMEDRIVE','HOMEPATH','CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK')):
            marker=self.context.parent/('missing-'+str(index));wrapped=q._OneCall(lambda *args:calls.append(1),self.args,marker)
            bad=dict(self.child);del bad[key]
            with self.assertRaises(q.QualificationError):wrapped([str(self.cli)],b'',bad,str(self.work),1,100)
            self.assertFalse(marker.exists())
        self.assertEqual(calls,[])
    def test_direct_qualification_identity_fails_closed(self):
        with self.assertRaises(q.QualificationError):self.real_bootstrap()
    def test_bootstrap_rejects_preloaded_and_wrong_pin(self):
        with self.assertRaises(bootstrap.BootstrapError):bootstrap._load()
        with patch.object(bootstrap,'QUALIFICATION_SHA256','0'*64):
            with self.assertRaises(bootstrap.BootstrapError):bootstrap._load()
        self.assertNotIn('feedctrl.windows_job_native',sys.modules)
    def test_home_must_match_preflight_home(self):
        with patch.dict(os.environ,{'HOME':str(self.home/'different')}):
            with self.assertRaises(q.QualificationError):q.preflight(**self.args)
    def test_marker_sync_failure_stops_before_runner(self):
        calls=[]; marker=self.context.parent/'sync-marker'
        wrapped=q._OneCall(lambda *args:calls.append(1),self.args,marker)
        call=([str(self.cli)],b'',dict(self.child),str(self.work),1,100)
        with patch.object(q.os,'fsync',side_effect=OSError('synthetic')):
            with self.assertRaises(q.QualificationError):wrapped(*call)
        self.assertTrue(marker.exists());self.assertEqual(calls,[])
    def test_rejects_parent_traversal(self):
        with self.assertRaises(q.QualificationError):q._safe(self.work/'..'/'other')
    def test_relative_import_identity_and_refusal_veto(self):
        self.assertIs(observer.strict,projector);self.assertIs(transport.rejection_observer,observer)
        refusal={'type':'assistant','message':{'role':'assistant','content':[{'type':'refusal','refusal':'SYNTHETIC_CANARY'}]}}
        terminal={'type':'result','subtype':'success','is_error':False,'num_turns':1,'stop_reason':'end_turn','permission_denials':[], 'usage':{'input_tokens':1,'output_tokens':1},'modelUsage':{'claude-test':{}},'total_cost_usd':0,'result':'{}'}
        stream=js(refusal)+b'\n'+js(terminal)+b'\n'; result=projector.project_stream(stream)
        self.assertFalse(result['ok']);self.assertNotIn('SYNTHETIC_CANARY',json.dumps(result))
    def test_guard_events_empty(self):self.assertEqual(BLOCKED,[])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    print('guard_events=',json.dumps(BLOCKED));sys.exit(not result.wasSuccessful())