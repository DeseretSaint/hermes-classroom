import glob
import json
import struct

d = json.load(open('audit/visual/h178-field-stop/measurements.json'))
print('plugin_sha256:', d.get('plugin_sha256'), 'theme key:', d.get('theme'), 'frames:', len(d.get('frames', [])))
for f in d.get('frames', []):
    s = f['state']
    print(f['name'], f['width'], f['text'], f['viewport'], f['rootFontSize'], f['scope'], s['chip'], 'ovf', s['horizontalOverflow'], '|', s['bar'])
print('--- png dims')
for p in sorted(glob.glob('audit/visual/h178-field-stop/*.png')):
    b = open(p, 'rb').read(33)
    w, h = struct.unpack('>II', b[16:24])
    print(p.split('/')[-1], w, h)
