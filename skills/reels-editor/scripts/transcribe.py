import json, sys
from faster_whisper import WhisperModel

AUDIO = sys.argv[1] if len(sys.argv) > 1 else "audio16k.wav"
OUT   = sys.argv[2] if len(sys.argv) > 2 else "transcript.json"

model = WhisperModel("large-v3", device="cpu", compute_type="int8")
segments, info = model.transcribe(
    AUDIO, language="uk", word_timestamps=True,
    vad_filter=True, vad_parameters=dict(min_silence_duration_ms=400),
)
out = []
for s in segments:
    out.append({
        "start": s.start, "end": s.end, "text": s.text.strip(),
        "words": [{"word": w.word, "start": w.start, "end": w.end, "prob": w.probability}
                  for w in (s.words or [])],
    })
    print(f"[{s.start:6.2f} - {s.end:6.2f}] {s.text.strip()}", flush=True)
json.dump({"language": info.language, "duration": info.duration, "segments": out},
          open(OUT, "w"), ensure_ascii=False, indent=2)
print(f"\n=== сегментів: {len(out)}, слів: {sum(len(s['words']) for s in out)} ===")
