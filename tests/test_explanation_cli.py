"""CLI exit status/output-path/forwarding checks with mocked model calls."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from feedctrl.controls import ParserOperationalError

script=Path(__file__).resolve().parents[1]/'scripts/generate_explanations.py'
spec=importlib.util.spec_from_file_location('explanation_cli',script)
cli=importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class ExplanationCliTests(unittest.TestCase):
    def exercise(self,fail):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            data=base/'data.json'
            data.write_text(json.dumps({'items':[{'item_id':1,'categories':['category_0']},
                {'item_id':2,'categories':['category_1']}],
                'users':[{'user_id':7,'train':[1],'request_history':[2]}]}))
            output=base/'new'/'nested'/'explanations.json'
            predictor=Mock();predictor.score.return_value=[.9,.1]
            kwargs={'side_effect':ParserOperationalError('mock unavailable')} if fail else {'return_value':{'source':'mock'}}
            with patch.object(cli,'load_model',return_value=predictor), patch.object(cli,'generate_explanation',**kwargs) as generate:
                with contextlib.redirect_stdout(io.StringIO()):
                    status=cli.main(['--data',str(data),'--output',str(output),'--count','2',
                        '--ollama-model','mock:8b','--base-url','http://127.0.0.1:12345','--timeout','12'])
                self.assertEqual(generate.call_count,2)
                self.assertEqual(generate.call_args.kwargs,{'backend':'ollama','model':'mock:8b',
                    'base_url':'http://127.0.0.1:12345','timeout':12.0,
                    'cache_dir':output.parent/'explanation_cache'})
            return status,json.loads(output.read_text())

    def test_success_creates_parent_and_forwards_options(self):
        status,result=self.exercise(False)
        self.assertEqual(status,0)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(len(result['explanations']),2)

    def test_partial_failure_returns_nonzero_and_preserves_errors(self):
        status,result=self.exercise(True)
        self.assertEqual(status,2)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(len(result['errors']),2)
        self.assertEqual(result['explanations'],[])


if __name__=='__main__':unittest.main()
