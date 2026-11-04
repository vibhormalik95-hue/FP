"""Bounded served-API development smokes, not a held-out or human evaluation.

Run an already configured local app, then supply its loopback URL and a NEW
output JSON path. No dataset, checkpoint, existing receipt or experiment is edited.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feedctrl.controls import _local_endpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("output", type=Path)
    parser.add_argument("--user", type=int, default=14)
    args = parser.parse_args()
    base = _local_endpoint(args.base_url)
    if args.output.exists():
        raise SystemExit("Output already exists; preserve it and choose a new receipt path")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def call(path, body=None, headers=None):
        req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with opener.open(req, timeout=120) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
    status_code, status = call("/api/status")
    _, session = call("/api/session", {})
    h = {"X-Session-ID": session["session_id"]}
    user = args.user
    _, before = call(f"/api/compare?user_id={user}", headers=h)
    record = {"scope": "development mechanism smokes, no human relevance or scientific superiority claim",
        "started_utc": datetime.now(timezone.utc).isoformat(), "base_url": base,
        "user": user, "status_code": status_code, "status": status, "cases": []}
    def redact(value):
        if isinstance(value, dict):
            return {k:redact(v) for k,v in value.items() if k not in {"plan_id", "session_id"}}
        return [redact(v) for v in value] if isinstance(value,list) else value
    def save():
        args.output.write_text(json.dumps(redact(record), ensure_ascii=True, indent=2)+"\n",encoding="utf-8")
    def run(name, path, body=None):
        started=time.monotonic()
        code,result=call(path,body,h)
        _,after=call(f"/api/compare?user_id={user}",headers=h)
        item={"name":name,"status_code":code,"seconds":round(time.monotonic()-started,3),
            "all_ae_unchanged":after==before,"request":body,"response":result}
        record["cases"].append(item);save()
        print(json.dumps({"name":name,"status_code":code,"ready":result.get("ready"),
            "applied":result.get("applied"),"all_ae_unchanged":after==before,
            "topics":result.get("preview",result.get("feed",{})).get("topic_exposure"),
            "question":result.get("question")},ensure_ascii=True),flush=True)
        return result
    actions=[{"topic":"\u9752\u5c9b","operation":"boost","strength":"strong"},
        {"topic":"\u6e38\u620f","operation":"reduce","strength":"light"},
        {"topic":"\u65c5\u6e38","operation":"exclude","strength":"none"}]
    manual=run("manual_three_controls","/api/steering/preview",
        {"user_id":user,"backend":"manual","mode":"replace","actions":actions})
    english=run("english_three_controls","/api/steering/preview",
        {"user_id":user,"text":"A lot more Qingdao, a little less gaming, and hide travel completely.","mode":"replace"})
    record["manual_equals_live_english"]=(manual.get("preview")==english.get("preview")) if english.get("ready") else False
    if english.get("ready"):
        run("apply_reviewed_english","/api/steering/apply",{"user_id":user,"plan_id":english["plan_id"]})
    for name,text in [
        ("chinese_three_controls","\u8bf7\u5927\u91cf\u589e\u52a0\u9752\u5c9b\u89c6\u9891\uff0c\u7a0d\u5fae\u51cf\u5c11\u6e38\u620f\u89c6\u9891\uff0c\u5e76\u5b8c\u5168\u5c4f\u853d\u65c5\u6e38\u89c6\u9891\u3002"),
        ("english_light_increase","A little more Qingdao."),
        ("english_light_decrease","A little less Qingdao."),
        ("chinese_strong_decrease","\u8bf7\u5927\u91cf\u51cf\u5c11\u9752\u5c9b\u89c6\u9891\u3002"),
        ("english_hard_exclusion","Hide Qingdao completely."),
        ("ambiguity","Make it better."),
        ("unsupported_quota","Exactly three gaming videos."),
        ("cooking_scope_check","A lot more Qingdao and a little less gaming. Hide cooking completely.")]:
        result=run(name,"/api/steering/preview",{"user_id":user,"text":text,"mode":"replace"})
        if name=="chinese_three_controls":
            record["manual_equals_live_chinese"]=manual.get("preview")==result.get("preview")
    profile=run("editable_profile_replace","/api/steering/preview",
        {"user_id":user,"text":"A little more Qingdao. Hide gaming completely.","mode":"replace"})
    if profile.get("ready"):
        run("apply_edited_profile","/api/steering/apply",{"user_id":user,"plan_id":profile["plan_id"]})
    run("remove_one_subject","/api/steering/remove",{"user_id":user,"topic":"\u9752\u5c9b"})
    _,other=call("/api/session",{})
    _,isolated=call(f"/api/steering?user_id={user}",headers={"X-Session-ID":other["session_id"]})
    record["other_session_empty"]=isolated.get("commands")==[]
    run("reset_this_user","/api/reset",{"user_id":user})
    final=run("final_profile","/api/steering?user_id="+str(user))
    record["final_profile_empty"]=final.get("commands")==[]
    record["all_ae_checks_equal"]=all(x["all_ae_unchanged"] for x in record["cases"])
    record["finished_utc"]=datetime.now(timezone.utc).isoformat();save()
    print(str(args.output),flush=True)


if __name__ == "__main__":
    main()
