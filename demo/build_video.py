"""Build the CapyBrain demo video.

  python demo/build_video.py audio     # narration (ElevenLabs TTS), music bed and a "plop" -> demo/out/audio
  node demo/record.js                  # record the real app -> demo/out/raw (frames + marks.json)
  python demo/build_video.py video     # edit -> demo/capybrain-demo.mp4

Editing rules: every scene plays at real speed except the stretches where the app waits for the LLM, which are
fast-forwarded to at most 2.5 s and marked on screen. Scenes are held on their last frame if the narration runs
longer than the footage.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
OUT = DEMO / "out"
AUDIO = OUT / "audio"
RAW = OUT / "raw"
TMP = OUT / "tmp"
FINAL = DEMO / "capybrain-demo.mp4"
FPS = 30
MAX_WAIT_SHOWN = 2.5
LEAD = 0.35      # silence before narration starts in a scene
BADGE_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

load_dotenv(ROOT / ".env")
KEY = os.getenv("ELEVENLABS_API_KEY", "")


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def eleven(url: str, body: dict, dest: Path) -> None:
    r = requests.post(url, json=body, headers={"xi-api-key": KEY, "Content-Type": "application/json"}, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
    dest.write_bytes(r.content)


# --------------------------------------------------------------------------- audio
def build_audio() -> None:
    if not KEY:
        sys.exit("ELEVENLABS_API_KEY is not set")
    AUDIO.mkdir(parents=True, exist_ok=True)
    script = yaml.safe_load((DEMO / "script.yaml").read_text())
    durations = {}
    for s in script["scenes"]:
        text = " ".join(s["text"].split())
        h = hashlib.sha1(f"{script['voice_id']}|{script['model_id']}|{text}".encode()).hexdigest()[:10]
        dest = AUDIO / f"{s['id']}-{h}.mp3"
        if not dest.exists():
            print("tts", s["id"])
            eleven(f"https://api.elevenlabs.io/v1/text-to-speech/{script['voice_id']}?output_format=mp3_44100_192",
                   {"text": text, "model_id": script["model_id"],
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True}},
                   dest)
        link = AUDIO / f"{s['id']}.mp3"
        link.unlink(missing_ok=True)
        link.symlink_to(dest.name)
        durations[s["id"]] = round(duration(dest), 2)
    (AUDIO / "durations.json").write_text(json.dumps(durations, indent=2))
    total = sum(durations.values())
    print("narration", durations, f"total {total:.1f}s")

    music = AUDIO / "music.mp3"
    if not music.exists():
        print("music")
        eleven("https://api.elevenlabs.io/v1/music",
               {"prompt": "calm cozy lo-fi instrumental for a product demo, soft warm electric piano, gentle brushed drums, "
                          "light warm bass, relaxed hot spring evening mood, steady and unobtrusive, no vocals",
                "music_length_ms": int((total + 40) * 1000)}, music)
    plop = AUDIO / "plop.mp3"
    if not plop.exists():
        print("plop")
        eleven("https://api.elevenlabs.io/v1/sound-generation",
               {"text": "a single soft water drop plop into a calm hot spring, gentle ripple, cute", "duration_seconds": 1.5,
                "prompt_influence": 0.6}, plop)


# --------------------------------------------------------------------------- video
def sentences(text: str) -> list[str]:
    text = " ".join(text.split())
    parts = re.split(r"(?<=[.?!:])\s+", text)
    out = []
    for p in parts:
        while len(p) > 90:  # keep captions to about two lines
            cut = p.rfind(", ", 0, 90)
            if cut < 30:
                cut = p.rfind(" ", 0, 90)
            out.append(p[: cut + 1].strip())
            p = p[cut + 1:].strip()
        if p:
            out.append(p)
    return out


def ass_time(t: float) -> str:
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def build_video() -> None:
    marks = json.loads((RAW / "marks.json").read_text())
    durations = json.loads((AUDIO / "durations.json").read_text())
    script = {s["id"]: s for s in yaml.safe_load((DEMO / "script.yaml").read_text())["scenes"]}
    TMP.mkdir(parents=True, exist_ok=True)

    raw = TMP / "raw.mp4"
    print("encoding raw frames")
    run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(RAW / "frames" / "%06d.jpg"),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p", str(raw)])

    clips, timeline, t_final = [], [], 0.0
    for n, sc in enumerate(marks["scenes"]):
        segs, cursor = [], sc["start"]
        for w in sc["waits"]:
            if w["start"] > cursor:
                segs.append((cursor, w["start"], 1.0))
            d = w["end"] - w["start"]
            segs.append((w["start"], w["end"], max(1.0, d / MAX_WAIT_SHOWN)))
            cursor = w["end"]
        if sc["end"] > cursor:
            segs.append((cursor, sc["end"], 1.0))
        parts, labels = [], []
        for i, (a, b, k) in enumerate(segs):
            f = f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{k:.4f}"
            if k > 1.05:
                f += (f",drawtext=fontfile={BADGE_FONT}:text='▶▶  {k:.0f}x   waiting on the LLM':fontsize=26:fontcolor=white"
                      f":box=1:boxcolor=0x0d1a18@0.78:boxborderw=12:x=w-tw-560:y=86")
            parts.append(f + f"[s{i}]")
            labels.append(f"[s{i}]")
        shown = sum((b - a) / k for a, b, k in segs)
        target = max(shown, durations.get(sc["id"], 0) + LEAD + 0.5)
        pad = target - shown
        graph = ";".join(parts) + f";{''.join(labels)}concat=n={len(labels)}:v=1:a=0[c];[c]tpad=stop_mode=clone:stop_duration={pad:.3f},fps={FPS}[v]"
        clip = TMP / f"scene{n:02d}-{sc['id']}.mp4"
        print(f"scene {sc['id']}: footage {sc['end'] - sc['start']:.1f}s -> {shown:.1f}s shown, narration {durations.get(sc['id'])}s, clip {target:.1f}s")
        run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-filter_complex", graph, "-map", "[v]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", "-t", f"{target:.3f}", str(clip)])
        drop = sc.get("events", {}).get("drop")
        timeline.append({"id": sc["id"], "start": t_final, "len": target,
                         "drop": (t_final + (drop - sc["start"])) if drop is not None else None})
        clips.append(clip)
        t_final += target

    concat_list = TMP / "clips.txt"
    concat_list.write_text("".join(f"file '{c.name}'\n" for c in clips))
    video = TMP / "video.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(video)])
    total = duration(video)

    # captions
    lines = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 0", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
             "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             "Style: Cap,Inter,34,&H00FFFFFF,&H00FFFFFF,&H64181A0D,&H64181A0D,-1,0,0,0,100,100,0,0,3,14,0,2,500,500,34,1",
             "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for tl in timeline:
        text = script[tl["id"]]["text"]
        chunks = sentences(text)
        total_chars = sum(len(c) for c in chunks) or 1
        t = tl["start"] + LEAD
        speech = durations.get(tl["id"], 0)
        for c in chunks:
            dt = speech * len(c) / total_chars
            lines.append(f"Dialogue: 0,{ass_time(t)},{ass_time(t + dt - 0.05)},Cap,,0,0,0,,{c}")
            t += dt
    subs = TMP / "captions.ass"
    subs.write_text("\n".join(lines) + "\n")

    # audio: narration placed per scene + plop at the ripple drop + quiet music bed
    inputs, filters, mix = [], [], []

    def add_input(*args: str) -> int:
        add_input.n += 1
        inputs.extend(args)
        return add_input.n - 1
    add_input.n = 0

    for i, tl in enumerate(timeline):
        f = AUDIO / f"{tl['id']}.mp3"
        if not f.exists():
            continue
        idx = add_input("-i", str(f))
        ms = int((tl["start"] + LEAD) * 1000)
        filters.append(f"[{idx}:a]adelay={ms}|{ms}[n{i}]")
        mix.append(f"[n{i}]")
    drop = next((tl["drop"] for tl in timeline if tl["drop"] is not None), None)
    if drop is not None and (AUDIO / "plop.mp3").exists():
        idx = add_input("-i", str(AUDIO / "plop.mp3"))
        ms = int(drop * 1000)
        filters.append(f"[{idx}:a]adelay={ms}|{ms},volume=0.9[plop]")
        mix.append("[plop]")
    if (AUDIO / "music.mp3").exists():
        idx = add_input("-stream_loop", "-1", "-i", str(AUDIO / "music.mp3"))
        filters.append(f"[{idx}:a]atrim=0:{total:.2f},afade=t=in:d=2,afade=t=out:st={max(total - 4, 0):.2f}:d=4,"
                       f"volume=0.14[music]")
        mix.append("[music]")
    audio = TMP / "audio.m4a"
    graph = ";".join(filters) + f";{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=longest,loudnorm=I=-16:TP=-1.5:LRA=11,atrim=0:{total:.2f}[a]"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[a]", "-c:a", "aac", "-b:a", "192k", str(audio)])

    print("final encode")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio), "-vf", f"ass={subs}",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-tune", "animation",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", str(FINAL)])
    print(f"wrote {FINAL} ({duration(FINAL):.1f}s, {FINAL.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "audio":
        build_audio()
    elif cmd == "video":
        build_video()
    else:
        sys.exit(__doc__)
