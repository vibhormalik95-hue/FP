"""Checks of a finished take: silence, transcript against the script, frames every 30 s.

    python tools/recording/check_take.py <take folder> --tts-python <python with faster_whisper>

1. ffmpeg silencedetect at -45 dB for 5 s: passes when no silence of 5 s or more is found.
2. faster-whisper (small.en) transcript compared with the narration timeline: word-sequence
   similarity of the whole script, and an ORDERED alignment: one monotonic word alignment of the
   script against the transcript; a script sentence counts as aligned when at least 70% of its words
   are matched in that ordered alignment, and its sync offset is the transcript time of its first
   matched word minus the time the recorder started that sentence. (The older metric
   "sentences_found", word presence anywhere in the transcript, is kept under the honest name
   "sentences_with_words_present_anywhere"; it is not order or sync evidence.)
   The UI workflow itself is not verified by the transcript; the recorder's timeline events and the
   frames are the UI evidence.
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
segs, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(audio, vad_filter=False, word_timestamps=True)
json.dump([{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
            "words": [{"w": w.word, "start": round(w.start, 2)} for w in (s.words or [])]} for s in segs], open(sys.argv[2], "w"), indent=1)
'''


UNITS = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                          "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: str(i) for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
DROP = {"point", "hundred", "percent"}


def words(text):
    """Lower-case words with numbers normalised the same way on both sides: spelled numbers become digits, every
    digit is its own token and "point", "hundred" and "percent" are dropped, so "five point five 17" (script) and
    "5.517" (ASR) both become 5 5 1 7."""
    text = text.lower().replace("sass-rec", "sasrec").replace("kwai-rec", "kuairec")
    raw = re.findall(r"[a-z]+|[0-9]+", text)
    out, i = [], 0
    while i < len(raw):
        w = raw[i]
        if w in TENS:
            nxt = raw[i + 1] if i + 1 < len(raw) else ""
            if nxt in UNITS and len(UNITS[nxt]) == 1 and nxt != "zero":
                out += [TENS[w], UNITS[nxt]]
                i += 2
                continue
            out += [TENS[w], "0"]
        elif w in UNITS:
            out += list(UNITS[w])
        elif w.isdigit():
            out += list(w)
        elif w not in DROP:
            out.append(w)
        i += 1
    return out


def heard_words(transcript):
    """Transcript words with a time each: the ASR word timestamp when the transcript has one, else the segment time
    spread evenly over its words (approximate: one segment can hold several script sentences)."""
    out = []
    for seg in transcript:
        if seg.get("words"):
            for item in seg["words"]:
                for x in words(item["w"]):
                    out.append((x, item["start"]))
            continue
        w = words(seg["text"])
        for i, x in enumerate(w):
            out.append((x, seg["start"] + (seg["end"] - seg["start"]) * i / max(1, len(w))))
    return out


def ordered_alignment(timeline, transcript, threshold=0.7):
    """One monotonic alignment of all script words against the transcript (difflib matching blocks are in order).
    Returns per-sentence matched share and sync offset (seconds), plus totals."""
    said, owner = [], []
    for n, c in enumerate(timeline):
        for x in words(c["text"]):
            said.append(x)
            owner.append(n)
    heard = heard_words(transcript)
    sm = difflib.SequenceMatcher(None, said, [h[0] for h in heard], autojunk=False)
    matched = {}
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            matched[a + k] = b + k
    rows = []
    for n, c in enumerate(timeline):
        idx = [i for i, o in enumerate(owner) if o == n]
        if not idx:
            continue
        hits = [i for i in idx if i in matched]
        share = len(hits) / len(idx)
        offset = round(heard[matched[hits[0]]][1] - c["at"], 2) if hits else None
        rows.append({"n": n, "share": round(share, 2), "aligned": share >= threshold, "offset_s": offset})
    offsets = [abs(r["offset_s"]) for r in rows if r["aligned"] and r["offset_s"] is not None]
    return {"sentences": rows, "aligned": sum(r["aligned"] for r in rows), "total": len(rows),
            "timing": "word" if any(seg.get("words") for seg in transcript) else "segment (approximate)",
            "max_abs_offset_s": max(offsets) if offsets else None,
            "median_abs_offset_s": sorted(offsets)[len(offsets) // 2] if offsets else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("take")
    ap.add_argument("--tts-python", required=True)
    ap.add_argument("--reuse-transcript", action="store_true", help="re-check with the existing transcript.json (no ASR, no frames)")
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
    if not args.reuse_transcript:
        (take / "frames").mkdir(exist_ok=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vf", "fps=1/30",
                        str(take / "frames" / "f%02d.png")], check=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(take / "frames" / "f%02d.png"),
                        "-filter_complex", "scale=640:-1,tile=4x6", "-frames:v", "1", str(take / "contact.png")], check=True)
        script_py = take / "asr.py"
        script_py.write_text(ASR, encoding="utf-8")
        subprocess.run([args.tts_python, str(script_py), str(video), str(take / "transcript.json")], check=True)
    frames = sorted((take / "frames").glob("f*.png"))
    transcript = json.loads((take / "transcript.json").read_text(encoding="utf-8"))
    take_log = json.loads((take / "timeline.json").read_text(encoding="utf-8"))
    if take_log.get("failed"):
        print(json.dumps({"failed": take_log["failed"], "cjk_hits": [e for e in take_log["events"] if "cjk_hit" in e],
                          "cjk_pass": False}, indent=1))
        return 1
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
    align = ordered_alignment(timeline, transcript)
    # Sync: with word timestamps every aligned sentence must start within 2 s of the recorder's time; with
    # segment timestamps only (older transcripts) the per-sentence time is approximate, so the median must be <= 1 s.
    if align["timing"] == "word":
        sync_ok = align["max_abs_offset_s"] is not None and align["max_abs_offset_s"] <= 2.0
    else:
        sync_ok = align["median_abs_offset_s"] is not None and align["median_abs_offset_s"] <= 1.0
    aligned_pass = align["total"] > 0 and align["aligned"] == align["total"] and sync_ok
    ui_events = [e for e in take_log.get("events", []) if any(k in e for k in ("new_category", "new_item"))]
    result = {"duration_s": duration, "streams": json.loads(probe)["streams"], "silences_5s": silences,
              "silence_pass": not silences, "transcript_similarity": round(similarity, 3),
              "sentences_with_words_present_anywhere": f"{found}/{len(timeline)}",
              "sentences_aligned_in_order": f"{align['aligned']}/{align['total']}",
              "sync_offset_s": {"max_abs": align["max_abs_offset_s"], "median_abs": align["median_abs_offset_s"],
                                "timing": align["timing"]},
              "unaligned_sentences": [{"n": r["n"], "share": r["share"], "text": timeline[r["n"]]["text"][:120]}
                                      for r in align["sentences"] if not r["aligned"]],
              "aligned_pass": aligned_pass, "ui_events": ui_events,
              "transcript_pass": similarity >= 0.85,
              "frames": len(frames), "duration_pass": duration <= 720,
              "cjk_live_checks": cjk_checks, "cjk_hits": cjk_hits, "cjk_pass": cjk_checks > 0 and not cjk_hits}
    (take / "check.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    return 0 if all(result[k] for k in ("silence_pass", "transcript_pass", "aligned_pass", "duration_pass", "cjk_pass")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
