# M4 media gate fixtures

These two files are the media bytes the M4 visual/media audit serves to the shipped Desktop
module. They are committed so `python3 scripts/m4v-audit.py` is reproducible on a clean checkout;
before H-136 the harness read them from `~/.hermes/cache/scratch/`, which the scratch janitor
prunes.

They are **labelled gate fixtures**. They are not the M0 host-probe artifacts recorded in
`docs/M0-MEDIA-PROBE.md`; that record is history, and these are the live bytes the gate measures.

| File | Bytes | SHA-256 | Provenance |
|---|---|---|---|
| `cb-media-image.png` | 49,776 | `e3be1eed6e3881ceb52bf76385ec542e9129728a65a3bf45477f54658f386669` | Deterministic flat illustration produced by `scripts/make-m4-fixtures.py` (PIL), 1024×576, `89 50 4e 47` |
| `cb-media-audio.mp3` | 27,936 | `85badba9b29393dfcae2189efed31a6e5f79fda0d400140cb5d9dc8ab6753e6a` | Real speech MP3 of `こんにちは。今日はいい天気ですね。` (ja-JP, 4.66 s), `ff f3` |

## Regenerating

Image (deterministic, offline):

```
python3 scripts/make-m4-fixtures.py          # rewrite cb-media-image.png
python3 scripts/make-m4-fixtures.py --check  # compare pixels against the generator
```

Speech (needs the free Microsoft Edge speech service, no key, no paid provider; run once and
commit the result — the gate itself never touches the network):

```
uvx --from edge-tts edge-tts --voice ja-JP-NanamiNeural --rate=-10% \
  --text "こんにちは。今日はいい天気ですね。" --write-media raw.mp3
ffmpeg -i raw.mp3 -codec:a libmp3lame -b:a 48k -ar 24000 -ac 1 \
  -write_id3v2 0 -write_xing 0 -id3v2_version 0 cb-media-audio.mp3
```

The `ffmpeg` step strips ID3/Xing so the file starts with the MPEG frame sync `ff f3`, which is the
magic the audit checks. Update the table above (and the review in
`docs/M4-VISUAL-MEDIA-AUDIT.md`) if either file is regenerated.
