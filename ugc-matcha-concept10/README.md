# Concept 10 — "The Matcha Skeptic Twist" (15s, 9:16 UGC)

## Deliverables (`out/`)

| File | What |
|---|---|
| `matcha-concept10-15s-9x16.mp4` | **Main render** — 1080×1920, 30 fps, H.264 + AAC, 15.0s. Four generated 9:16 keyframes with handheld zoom/shake, verbatim dialogue VO, burned-in platform text (top) + dialogue captions (bottom). Exact shot composition and wardrobe lock. |
| `matcha-concept10-motion-15s-9x16.mp4` | **Motion render** — same timeline/audio/text, built from two real AI-motion clips (`assets/part1_raw.mp4`, `assets/part2_raw.mp4`, Hailuo 2.3) cropped to 9:16. Use when true camera motion matters more than exact framing. |
| `captions.srt` | Timed captions with the full emoji platform text for TikTok/Reels/Shorts upload. |

## Shot map (as rendered)

| Shot | Slot | Dialogue (verbatim) | Platform text |
|---|---|---|---|
| 1 Skeptic Hook | 0.0–4.2s | "I used to judge anyone who ordered matcha ice cream... but I officially owe everyone an apology." | a formal apology to matcha lovers 🍵🙏 |
| 2 First Bite | 4.2–8.4s | "I thought it would taste like sweet grass, but real Japanese street soft-serve is crazy creamy and rich." | not sweet grass... pure creamy velvet 🤤 |
| 3 Bestie Banter | 8.4–11.2s | "Hey! Get your own cone, this one's mine!" | hands off my cone 😂🙅‍♀️ |
| 4 Payoff / CTA | 11.2–15.0s | "If you're coming to Japan, do not sleep on street soft-serve. Trust me on this one!" | do NOT sleep on this in Japan 📌🍦 |

## Deviations from the brief (read before judging)

1. **Reference photos not used as pixels.** The three `C:\Users\Barbara\...` reference sheets live on a Windows machine and are not reachable from this cloud workspace. Maya, the street, and the product were locked by the brief's own text description in every generation prompt instead. To get a true face-lock, re-run `flow/FLOW_PROMPTS.md` in Flow with those files attached (Assets 1–4), then drop the clips in as `assets/part1_raw.mp4` / `part2_raw.mp4` and re-run `python3 scripts/build.py`.
2. **Shot slots re-timed 3/4/4/4 → 4.2/4.2/2.8/3.8 (still 15.0s total).** The scripted lines need ~270–380 wpm in the original slots; even sped-up VO (1.18–1.45× after pause-trimming) would be unintelligible chipmunk pace. Words are unchanged.
3. **Emoji not burned into pixels.** The Linux caption font renders emoji as boxes, so burned-in top text omits them; the exact emoji strings are in `captions.srt` and above for native in-app text (the authentic creator workflow anyway).
4. **Hailuo outputs 1366×768 landscape** (no aspect-ratio control), so the motion render is a 432×768 center-region crop upscaled to 1080×1920 — softer, but genuinely UGC-looking. The main render is native 9:16 throughout.

## Rebuild

```bash
python3 ugc-matcha-concept10/scripts/build.py   # needs ffmpeg + Noto Sans Bold
```

Generation cost on this run: Hailuo 2 × $0.28 + Gemini TTS ≈ $0.57 total (Treg balance-metered).
Negative prompt from the brief (corporate/glossy/16:9/dolly/drone/plastic-skin/morphing/extra-fingers, etc.) is embedded in every generation prompt in `flow/FLOW_PROMPTS.md`.
