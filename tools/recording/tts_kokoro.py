"""Local Kokoro TTS worker. Reads JSON lines {"text": ..., "out": ...} on stdin,
writes a 24 kHz WAV per line and prints {"out": ..., "seconds": ...}.
Run it with a Python that has `kokoro` and `soundfile` installed (Python 3.12 venv)."""
import json
import sys

import numpy as np
import soundfile as sf
from kokoro import KPipeline

VOICE = sys.argv[1] if len(sys.argv) > 1 else "af_heart"
SPEED = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
print(json.dumps({"ready": True, "voice": VOICE}), flush=True)
for line in sys.stdin:
    if not line.strip():
        continue
    job = json.loads(line)
    chunks = [np.asarray(audio) for _, _, audio in pipe(job["text"], voice=job.get("voice", VOICE), speed=job.get("speed", SPEED))]
    audio = np.concatenate(chunks) if chunks else np.zeros(2400, dtype=np.float32)
    pad = np.zeros(int(24000 * 0.12), dtype=np.float32)          # short lead-in and tail so no word is clipped
    audio = np.concatenate([pad, audio.astype(np.float32), pad])
    sf.write(job["out"], audio, 24000)
    print(json.dumps({"out": job["out"], "seconds": round(len(audio) / 24000, 3)}), flush=True)
