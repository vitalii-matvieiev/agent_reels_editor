#!/usr/bin/env python3
"""Transcribes speech with word-level timestamps. Everything downstream needs them.

    python transcribe.py audio.wav transcript.json
    python transcribe.py audio.wav transcript.json --model medium   # ~3x faster
    python transcribe.py audio.wav transcript.json --language uk

Default model is large-v3 — the most accurate, and the most patient. It runs
roughly 15-20x slower than real time on CPU, so a one-minute clip takes 15-20
minutes. The script prints an estimate before starting; pass that estimate on
to the user and offer the faster models.
"""
import argparse
import json
import subprocess
import sys
import time

MODELS = {
    # name:      (speed vs large-v3, what you give up)
    "large-v3":  (1.0,  "найточніша — краще за всіх чує власні назви"),
    "medium":    (3.0,  "утричі швидша, іноді плутає імена й рідкі слова"),
    "small":     (6.0,  "вшестеро швидша, помітно більше помилок у назвах"),
    "base":      (12.0, "найшвидша, годиться лише для чернетки"),
}


def audio_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("output", nargs="?", default="transcript.json")
    ap.add_argument("--model", default="large-v3", choices=list(MODELS))
    ap.add_argument("--language", default="auto",
                    help="ISO code (uk, en, pl…) or 'auto' to detect")
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    dur = audio_duration(a.audio)
    speed, tradeoff = MODELS[a.model]

    print(f"Модель: {a.model} — {tradeoff}", flush=True)
    if dur:
        mins = dur * 17 / speed / 60          # ~17x real time for large-v3 on CPU
        print(f"Аудіо: {dur:.0f} с. Орієнтовний час розшифровки: ~{mins:.0f} хв.", flush=True)
        if a.model == "large-v3" and mins > 5:
            print()
            print("  Якщо потрібно швидше — можу перемкнути модель:", flush=True)
            for name, (sp, note) in MODELS.items():
                if name == "large-v3":
                    continue
                print(f"    --model {name:8} ~{dur*17/sp/60:.0f} хв — {note}", flush=True)
            print("  Точність на власних назвах при цьому падає — імена перевіряй уважніше.", flush=True)
    print(flush=True)

    from faster_whisper import WhisperModel  # imported late so --help stays instant

    t0 = time.time()
    model = WhisperModel(a.model, device=a.device, compute_type="int8")
    segments, info = model.transcribe(
        a.audio,
        language=None if a.language == "auto" else a.language,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400),
    )

    out = []
    for s in segments:
        out.append({
            "start": s.start, "end": s.end, "text": s.text.strip(),
            "words": [{"word": w.word, "start": w.start, "end": w.end,
                       "prob": w.probability} for w in (s.words or [])],
        })
        print(f"[{s.start:6.2f} - {s.end:6.2f}] {s.text.strip()}", flush=True)

    json.dump({"language": info.language, "duration": info.duration,
               "model": a.model, "segments": out},
              open(a.output, "w"), ensure_ascii=False, indent=2)

    words = sum(len(s["words"]) for s in out)
    print(f"\n=== мова: {info.language}, сегментів: {len(out)}, слів: {words}, "
          f"зайняло {(time.time()-t0)/60:.1f} хв ===")
    print("Прочитай власні назви користувачу — Whisper їх регулярно псує.")

    if not out:
        sys.exit("мови не розпізнано — перевір, чи є звук у файлі")


if __name__ == "__main__":
    main()
