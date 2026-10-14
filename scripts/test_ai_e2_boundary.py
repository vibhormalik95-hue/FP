"""No-case subprocess checks of trusted worker boundaries; never calls inference."""
import importlib.util,json,os,socket,subprocess,sys,tempfile
from pathlib import Path

def child(root):
    source=Path(__file__).with_name('ai_e2_inference_worker.py')
    spec=importlib.util.spec_from_file_location('worker',source);w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
    root=Path(root);allowed=root/'allowed';private=root/'private.json'
    private.write_text('private no-case canary');allowed.mkdir()
    w.install_guard([allowed,Path(sys.base_prefix),Path(os.environ['SystemRoot'])])
    checks={}
    for name,path in [('private',private),('traversal',allowed/'..'/'private.json'),('case_alias',Path(str(private).upper()))]:
        try:path.read_bytes()
        except PermissionError:checks[name]='denied'
        else:raise AssertionError(name)
    for name,address in [('external',('1.1.1.1',443)),('other_loopback_port',('127.0.0.1',11435))]:
        try:
            with socket.socket() as s:s.connect(address)
        except PermissionError:checks[name]='denied'
        else:raise AssertionError(name)
    try:subprocess.run([sys.executable,'-V'],capture_output=True)
    except PermissionError:checks['subprocess']='denied'
    else:raise AssertionError('subprocess')
    w.save(allowed/'journal.json',{'status':'no-case durable write'})
    assert json.loads((allowed/'journal.json').read_text())['status']=='no-case durable write'
    try:w.save(allowed/'journal.json',{})
    except FileExistsError:checks['overwrite']='denied'
    else:raise AssertionError('overwrite')
    fake={'categories':[f'category_{i}' for i in range(31)],'questions':[{'id':f'q_{i:012x}','text':f'non-case boundary fixture {i}'} for i in range(100)]}
    assert len(w.packet(fake)[1])==100
    fake['questions'][0]['gold']={}
    try:w.packet(fake)
    except ValueError:checks['label_field']='denied'
    else:raise AssertionError('label field')
    print(json.dumps({'status':'passed','checks':checks,'scope':'no formal cases or model inference'}))

if __name__=='__main__':
    if len(sys.argv)>1:child(sys.argv[1])
    else:
        with tempfile.TemporaryDirectory(prefix='ai-e2-boundary-') as temp:
            result=subprocess.run([sys.executable,__file__,temp],text=True,capture_output=True)
            print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr)
            raise SystemExit(result.returncode)
