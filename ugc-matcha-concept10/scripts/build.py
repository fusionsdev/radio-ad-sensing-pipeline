#!/usr/bin/env python3
"""Assemble Concept 10 'Matcha Skeptic Twist' — 15s 9:16 UGC ad.

Main render: 4 generated 9:16 keyframes with handheld zoompan (guaranteed
framing/wardrobe). Motion render: the two Hailuo clips center-cropped to 9:16.
Dialogue is verbatim from the brief; shot slots are re-timed to sum to 15.0s
because the scripted lines cannot fit 3/4/4/4 at intelligible pace
(see ../README.md deviation note).
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
A = ROOT / "assets"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
FONT = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
FPS = 30

# slot durations (sum = 15.0): re-timed from 3/4/4/4 for dialogue pace
SHOTS = [
    {"img": "shot1_skeptic_hook.jpg", "vo": "vo_shot1.wav", "dur": 4.2, "zoom": 0.0007,
     "top": ["a formal apology", "to matcha lovers"],
     "cap": ["I used to judge anyone", "who ordered matcha ice cream...", "but I officially owe", "everyone an apology."]},
    {"img": "shot2_first_bite.jpg", "vo": "vo_shot2.wav", "dur": 4.2, "zoom": 0.0016,
     "top": ["not sweet grass...", "pure creamy velvet"],
     "cap": ["I thought it would taste", "like sweet grass, but real", "Japanese street soft-serve", "is crazy creamy and rich."]},
    {"img": "shot3_bestie_banter.jpg", "vo": "vo_shot3.wav", "dur": 2.8, "zoom": 0.0007,
     "top": ["hands off my cone"],
     "cap": ["Hey! Get your own cone,", "this one’s mine!"]},
    {"img": "shot4_golden_payoff.jpg", "vo": "vo_shot4.wav", "dur": 3.8, "zoom": 0.0010,
     "top": ["do NOT sleep on this in Japan"],
     "cap": ["If you’re coming to Japan,", "do not sleep on street", "soft-serve. Trust me", "on this one!"]},
]


def run(cmd):
    print("+", " ".join(cmd[:6]), "...")
    subprocess.run(cmd, check=True)


def probe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def fit_voice(src, dst, slot):
    """Trim head/tail silence, then atempo-fit exactly into the slot."""
    trimmed = dst.with_suffix(".trim.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
         "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse",
         str(trimmed)])
    dur = probe_dur(trimmed)
    speed = max(0.7, min(1.6, dur / slot))
    run(["ffmpeg", "-y", "-v", "error", "-i", str(trimmed), "-af",
         f"atempo={speed:.3f},apad,atrim=0:{slot},aresample=48000", str(dst)])
    print(f"  voice {src.name}: {dur:.2f}s -> slot {slot}s at {speed:.2f}x")
    return dst


def drawtext_lines(lines, y, size, color="white", border=3, step=None):
    step = step or int(size * 1.25)
    return ",".join(
        f"drawtext=fontfile={FONT}:text='{line}':fontsize={size}:fontcolor={color}:"
        f"borderw={border}:bordercolor=black:x=(w-text_w)/2:y={y + i * step}"
        for i, line in enumerate(lines))


def build_main(voices):
    segs = []
    for i, s in enumerate(SHOTS):
        frames = int(s["dur"] * FPS)
        seg = OUT / f"main_seg{i+1}.mp4"
        vf = (f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              f"zoompan=z='min(zoom+{s['zoom']},1.15)':"
              f"x='iw/2-(iw/zoom/2)+5*sin(on/9+{i})':y='ih/2-(ih/zoom/2)+4*cos(on/11+{i})':"
              f"d={frames}:s=1080x1920:fps={FPS},"
              + drawtext_lines(s["top"], 110, 50) + "," + drawtext_lines(s["cap"], 1560, 38, "yellow"))
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(A / s["img"]),
             "-i", str(voices[i]), "-vf", vf, "-t", str(s["dur"]),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", str(seg)])
        segs.append(seg)
    concat(OUT / "matcha-concept10-15s-9x16.mp4", segs)


def build_motion(voices):
    # Part 1 -> shots 1-2 (8.4s from 5.875s, slowed), Part 2 -> shots 3-4 (6.6s)
    parts = [("part1_raw.mp4", [467, 467], 8.4, [0, 1]), ("part2_raw.mp4", [450, 600], 6.6, [2, 3])]
    segs = []
    for name, xoffs, total, idxs in parts:
        src_dur = probe_dur(A / name)
        slow = total / src_dur
        for j, idx in enumerate(idxs):
            s = SHOTS[idx]
            # slice of the slowed part corresponding to this shot
            start = sum(SHOTS[k]["dur"] for k in idxs[:j])
            seg = OUT / f"motion_seg{idx+1}.mp4"
            vf = (f"setpts={slow:.3f}*PTS,crop=432:768:{xoffs[j]}:0,scale=1080:1920,"
                  f"fps={FPS},trim=start={start}:duration={s['dur']},setpts=PTS-STARTPTS,"
                  + drawtext_lines(s["top"], 110, 50) + "," + drawtext_lines(s["cap"], 1560, 38, "yellow"))
            run(["ffmpeg", "-y", "-v", "error", "-i", str(A / name), "-i", str(voices[idx]),
                 "-vf", vf, "-t", str(s["dur"]), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "48000", str(seg)])
            segs.append(seg)
    concat(OUT / "matcha-concept10-motion-15s-9x16.mp4", segs)


def concat(dst, segs):
    lst = OUT / "concat.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in segs))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(dst)])
    print("built", dst)


if __name__ == "__main__":
    voices = [fit_voice(A / s["vo"], OUT / f"vo_fit{i+1}.wav", s["dur"])
              for i, s in enumerate(SHOTS)]
    build_main(voices)
    build_motion(voices)
