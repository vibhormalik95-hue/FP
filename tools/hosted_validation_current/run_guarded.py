import sys, unittest, socket
from pathlib import Path
root=Path(sys.argv[1]).resolve();sys.path[:0]=[str(root),str(root/'tests'),str(Path(__file__).parent)]
blocked=[]
def guard(event,args):
    deny=event in {'subprocess.Popen','os.system','os.fork','os.forkpty','os.exec','os.spawn','os.posix_spawn','socket.connect','socket.bind','socket.listen','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr'}
    if event=='socket.__new__' and (len(args)<2 or args[1]!=socket.AF_UNIX): deny=True
    if event=='ctypes.dlopen' and args and args[0] is not None: deny=True
    if event=='import' and args and str(args[0]).split('.')[0] in {'torch','transformers','ollama','anthropic','openai'}: deny=True
    if event=='open' and args and isinstance(args[0],(str,bytes)) and str(args[0]).lower().endswith(('.pt','.pth','.ckpt','.safetensors','.onnx','.gguf')): deny=True
    if deny:
        blocked.append(event);raise RuntimeError('Blocked offline: '+event)
sys.addaudithook(guard)
modules=sys.argv[2:] or ['test_definition_context_offline','test_apostrophe_constraints_offline','test_counted_conditions_offline','test_definition_modality_offline','test_numbered_source_constraints_offline','test_current_driver','test_personal_ui_index_offline','test_category_resolution_offline','test_hosted_synthetic_offline','test_hosted_app_offline','test_claude_personal_offline','test_personal_boundary_offline','test_transport_errors_offline','test_review_state_labels_offline','test_evidence_context_offline']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(modules))
print('GUARD: AF_UNIX allocation for internal event-loop wakeup only; all socket connect/bind/DNS, IP socket construction, subprocesses, provider/model imports, and checkpoint reads blocked.')
print('GUARD intercepted events:',blocked)
sys.exit(not r.wasSuccessful())
