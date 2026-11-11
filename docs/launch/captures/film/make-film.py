#!/usr/bin/env python3
"""Compose the film from frames whose screen text was verified. Captions quote the screen."""
import subprocess, tempfile, pathlib
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (13, 14, 17)
FRAME = (21, 22, 26)
INK = (242, 243, 245)
MUTED = (154, 160, 170)
ACCENT = (196, 168, 120)

BASE = pathlib.Path('/home/deseretsaint/.hermes/cache/scratch/cbfreeze')
OUT = BASE / 'film-out'
OUT.mkdir(exist_ok=True)

BOLD = '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf'
REG = '/usr/share/fonts/TTF/DejaVuSans.ttf'
def font(p, s):
    try: return ImageFont.truetype(p, s)
    except Exception: return ImageFont.load_default()

beats = [
    ('loop/v4/s01.png', 'Home', 'Your field library',
     ['Choose a course or start a new expedition.', 'Four destinations: Home, Courses, Workshop, Parent Studio.']),
    ('loop/v4/s02.png', 'Courses', 'All courses · 14 on this profile',
     ['Review due is the first row.', 'Japanese affection and register — an L0 demonstration classroom.']),
    ('loop/v4/s03.png', 'Course', 'Tell everyday affection from a direct romantic declaration',
     ['Section 2 of 4 · Needs review · Source stale.', 'Progress is on the record: 0 of 4 with independent evidence.']),
    ('loop/v5/s04.png', 'Check', 'Which line from this pack fits, and why?',
     ['First try, no hints — recorded as evidence.', 'The field is off because the lesson chat has ended:',
      '"This lesson is no longer connected to its chat, so Submit is off."']),
]

def compose(src, kicker, headline, lines, dest):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    shot = Image.open(BASE / src).convert('RGB').crop((20, 28, 721, 1040))
    sh = 960
    sw = int(shot.width * sh / shot.height)
    shot = shot.resize((sw, sh), Image.LANCZOS)
    x = 300
    d.rectangle([x - 3, 37, x + sw + 3, 37 + sh + 3], fill=(58, 60, 66))
    im.paste(shot, (x, 40))

    tx = x + sw + 110
    y = 360
    d.text((tx, y), kicker.upper(), font=font(BOLD, 26), fill=ACCENT)
    y += 58
    for line in [headline] + lines:
        f = font(BOLD if line is headline else REG, 40 if line is headline else 27)
        col = INK if line is headline else MUTED
        words, cur = line.split(), ''
        for w in words:
            trial = (cur + ' ' + w).strip()
            if d.textlength(trial, font=f) > 760 and cur:
                d.text((tx, y), cur, font=f, fill=col); y += 54 if line is headline else 38; cur = w
            else:
                cur = trial
        if cur:
            d.text((tx, y), cur, font=f, fill=col); y += 54 if line is headline else 38
    im.save(dest)

def end_card(dest):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((300, 420), 'Hermes Coursebook', font=font(BOLD, 76), fill=INK)
    d.text((300, 520), 'release tree 172b61aa · desktop/plugin.js 98400108', font=font(REG, 30), fill=MUTED)
    for i, line in enumerate([
        'Every frame was captured from that module, sha-checked before each shot.',
        'The check\'s answer step is bound to a live lesson chat; it cannot be shown inline.',
        'docs/ACCEPTANCE-RUN.md records what was measured and what was not.',
    ]):
        d.text((300, 610 + i * 44), line, font=font(REG, 27), fill=MUTED)
    im.save(dest)

work = pathlib.Path(tempfile.mkdtemp())
entries = []
for i, (src, k, h, lines) in enumerate(beats, 1):
    p = work / f'f{i}.png'
    compose(src, k, h, lines, p)
    entries.append((p, 7))
e = work / 'end.png'; end_card(e); entries.append((e, 5))

lst = work / 'list.txt'
with lst.open('w') as fh:
    for p, dur in entries:
        fh.write(f"file '{p}'\nduration {dur}\n")
    fh.write(f"file '{entries[-1][0]}'\n")

out = OUT / 'coursebook-demo.mp4'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst),
                '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
                '-movflags', '+faststart', str(out)], check=True)
probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration,size',
                        '-of', 'default=nw=1', str(out)], capture_output=True, text=True)
print(probe.stdout.strip())
print('wrote', out)
