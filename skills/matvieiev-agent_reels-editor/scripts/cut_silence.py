import json, subprocess, sys

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tools import FFMPEG, FFPROBE  # noqa: E402


SRC = sys.argv[1] if len(sys.argv) > 1 else "base_1080.mp4"
OUT = sys.argv[2] if len(sys.argv) > 2 else "tight_1080.mp4"
TRANSCRIPT = sys.argv[3] if len(sys.argv) > 3 else "transcript.json"

DUR = float(subprocess.run([FFPROBE,"-v","error","-show_entries","format=duration",
                           "-of","default=nw=1:nk=1",SRC],
                          capture_output=True,text=True).stdout.strip())
GAP_MIN  = 0.30   # що коротше — не чіпаємо, це природне дихання
GAP_KEEP = 0.18   # скільки тиші лишаємо на місці вирізаної паузи
LEAD_IN  = 0.15   # перед першим словом
TAIL_OUT = 0.45   # після останнього

d = json.load(open(TRANSCRIPT))
W = [w for s in d["segments"] for w in s["words"]]

cuts = []
if W[0]["start"] - LEAD_IN > 0:
    cuts.append((0.0, W[0]["start"] - LEAD_IN))
for a, b in zip(W, W[1:]):
    gap = b["start"] - a["end"]
    if gap > GAP_MIN:
        half = GAP_KEEP / 2
        cuts.append((a["end"] + half, b["start"] - half))
if DUR - (W[-1]["end"] + TAIL_OUT) > 0:
    cuts.append((W[-1]["end"] + TAIL_OUT, DUR))

# keep = доповнення до cuts
keeps, pos = [], 0.0
for cs, ce in cuts:
    if cs > pos: keeps.append((pos, cs))
    pos = ce
if pos < DUR: keeps.append((pos, DUR))

removed = sum(e - s for s, e in cuts)
newdur  = DUR - removed
print(f"вирізаємо {len(cuts)} фрагментів, разом {removed:.2f} с")
for s, e in cuts: print(f"   {s:6.2f} → {e:6.2f}  ({e-s:.2f} с)")
print(f"було {DUR:.2f} с → стане {newdur:.2f} с\n")

# ---- перерахунок таймкодів слів у нову таймлінію ----
def remap(t):
    shift = 0.0
    for cs, ce in cuts:
        if t >= ce: shift += ce - cs
        elif t > cs: return cs - shift   # всередині вирізаного — тягнемо до краю
    return t - shift

segs = []
for s in d["segments"]:
    ws = [{"word": w["word"], "start": remap(w["start"]), "end": remap(w["end"])}
          for w in s["words"]]
    ws = [w for w in ws if w["end"] > w["start"]]
    if ws:
        segs.append({"start": ws[0]["start"], "end": ws[-1]["end"],
                     "text": s["text"], "words": ws})
json.dump({"language": d["language"], "duration": newdur, "segments": segs},
          open("transcript_tight.json", "w"), ensure_ascii=False, indent=2)

# ---- ffmpeg: trim + concat ----
parts = []
for i, (s, e) in enumerate(keeps):
    parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}];")
    parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}];")
concat_in = "".join(f"[v{i}][a{i}]" for i in range(len(keeps)))
fc = "".join(parts) + f"{concat_in}concat=n={len(keeps)}:v=1:a=1[v][a]"

cmd = [FFMPEG, "-v", "error", "-y", "-i", SRC, "-filter_complex", fc,
       "-map", "[v]", "-map", "[a]",
       "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", OUT]
subprocess.run(cmd, check=True)
print(f"✅ {OUT}")
