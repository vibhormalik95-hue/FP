"""Checks of a finished take: silence, transcript against the script, frames every 30 s.

    python tools/recording/check_take.py <take folder> --tts-python <python with faster_whisper>

1. ffmpeg silencedetect at -45 dB for 5 s: passes when no silence of 5 s or more is found.
2. faster-whisper (small.en) transcript compared with the narration timeline: word-sequence
   similarity of the whole script, and the share of script sentences found in the transcript.
3. One frame every 30 s (frames/), plus a contact sheet.
Writes check.json in the take folder and prints a summary.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
from pathlib import Path

VIDEO = "COMP9500-Feed-Control-Lab-demo.mp4"
ASR = r'''
import sys, json, subprocess, soundfile as sf
from faster_whisper import WhisperModel
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", sys.argv[1], "-ac", "1", "-ar", "16000", sys.argv[2] + ".wav"], check=True)
audio, _ = sf.read(sys.argv[2] + ".wav", dtype="float32")
segs, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(audio, vad_filter=False)
json.dump([{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs], open(sys.argv[2], "w"), indent=1)
'''


def words(text):
    text = text.lower().replace("sass-rec", "sasrec").replace("kwai-rec", "kuairec")
    return re.findall(r"[a-z0-9]+", text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("take")
    ap.add_argument("--tts-python", required=True)
    args = ap.parse_args()
    take = Path(args.take)
    video = take / VIDEO
    duration = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                                    capture_output=True, text=True).stdout.strip())
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", str(video)],
                           capture_output=True, text=True).stdout
    sd = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-af", "silencedetect=noise=-45dB:d=5", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    silences = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", sd)]
    (take / "frames").mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vf", "fps=1/30",
                    str(take / "frames" / "f%02d.png")], check=True)
    frames = sorted((take / "frames").glob("f*.png"))
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(take / "frames" / "f%02d.png"),
                    "-filter_complex", "scale=640:-1,tile=4x6", "-frames:v", "1", str(take / "contact.png")], check=True)
    script_py = take / "asr.py"
    script_py.write_text(ASR, encoding="utf-8")
    subprocess.run([args.tts_python, str(script_py), str(video), str(take / "transcript.json")], check=True)
    transcript = json.loads((take / "transcript.json").read_text(encoding="utf-8"))
    take_log = json.loads((take / "timeline.json").read_text(encoding="utf-8"))
    timeline = take_log["timeline"]
    cjk = [e for e in take_log.get("events", []) if "cjk_checks" in e or "cjk_hit" in e]
    cjk_checks = sum(e.get("cjk_checks", 0) for e in cjk)
    cjk_hits = [e for e in cjk if "cjk_hit" in e]
    said = words(" ".join(c["text"] for c in timeline))
    heard = words(" ".join(s["text"] for s in transcript))
    similarity = difflib.SequenceMatcher(None, said, heard, autojunk=False).ratio()
    heard_text = " ".join(heard)
    found = 0
    for c in timeline:
        w = words(c["text"])
        if not w:
            continue
        hits = sum(1 for x in w if x in heard_text)
        found += hits / len(w) >= 0.7
    result = {"duration_s": duration, "streams": json.loads(probe)["streams"], "silences_5s": silences,
              "silence_pass": not silences, "transcript_similarity": round(similarity, 3),
              "sentences_found": f"{found}/{len(timeline)}", "transcript_pass": similarity >= 0.85,
              "frames": len(frames), "duration_pass": duration <= 720,
              "cjk_live_checks": cjk_checks, "cjk_hits": cjk_hits, "cjk_pass": cjk_checks > 0 and not cjk_hits}
    (take / "check.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    return 0 if all(result[k] for k in ("silence_pass", "transcript_pass", "duration_pass", "cjk_pass")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
