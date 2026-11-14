"""Full source descriptions in uncited review rows; offline synthetic evidence."""
import csv
from pathlib import Path
import tempfile
import unittest
from feedctrl.api import DemoState, create_app
from feedctrl.semantic_controls import TEXT_FIELDS
from feedctrl.semantic_review import SemanticPreview, SemanticApply

class FullReviewDescriptionTests(unittest.TestCase):
    def test_full_field_preserves_whitespace_and_distant_qualifier(self):
        state=object.__new__(DemoState)
        original="  "+"x"*500+" NOT food.  "
        state.topic_index={"items":{1:{"fields":{"caption":original}}}}
        self.assertEqual(state.source_text(1, full=True),original)
        self.assertEqual(len(state.source_text(1)),400)

    def test_fallback_and_absent_description(self):
        state=object.__new__(DemoState)
        text="y"*500+" END"
        state.topic_index={"items":{1:{"fields":{"caption":" ", "manual_cover_text":text}}}}
        self.assertEqual(state.source_text(1,full=True),text)
        self.assertIsNone(state.source_text(2,full=True))

    def test_uncited_scope_row_retains_full_description_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"synthetic.csv"
            text="Neutral context. "*50+"This item is NOT about food."
            with path.open("w",encoding="utf-8",newline="") as handle:
                writer=csv.DictWriter(handle,fieldnames=["video_id",*TEXT_FIELDS])
                writer.writeheader()
                for item in range(1,37):
                    writer.writerow({"video_id":item,"caption":text if item==2 else "Synthetic neutral description."})
            app=create_app(fixture=True,semantic_path=path,allow_local_models=False,allow_local_recommender=False)
            def ep(p):
                return next(r.endpoint for r in app.routes if getattr(r,"path",None)==p)
            session=ep("/api/session")()["session_id"]
            before=ep("/api/semantic/groups")(1,session)
            result=ep("/api/semantic/preview")(SemanticPreview(user_id=1,candidate_ids=list(range(1,9)),label="Manual",backend="manual_category",action_source="manual",category="category_1",operation="exclude",strength="none"),session)
            self.assertEqual(result["proposal"]["evidence"],[])
            self.assertEqual(result["evidence_context"],[])
            row=next(x for x in result["scope_items"] if x["item_id"]==2)
            self.assertEqual(row["source_text"],text)
            self.assertEqual(ep("/api/semantic/groups")(1,session)["feed"],before["feed"])
            row["source_text"]="TAMPER"
            applied=ep("/api/semantic/apply")(SemanticApply(user_id=1,plan_id=result["plan_id"]),session)
            self.assertTrue(applied["applied"])
            self.assertEqual(applied["groups"][0]["proposal"]["item_ids"],[1,7])
