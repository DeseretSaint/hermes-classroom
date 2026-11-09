import hashlib
import json
import struct
import sys

d = json.load(open('audit/visual/h178-field-stop/measurements.json'))
print('plugin_sha256:', d['plugin_sha256'])
print('frames:', len(d['frames']))
ok = True
for f in d['frames']:
    s = f['state']
    p = 'audit/visual/h178-field-stop/' + f['name']
    raw = open(p, 'rb').read()
    sha = hashlib.sha256(raw).hexdigest()
    w, h = struct.unpack('>II', raw[16:24])
    good = (
        sha == f['sha256']
        and w == f['pixels']['width'] and h == f['pixels']['height']
        and s['chip'] == 'cold' and s['chipPending'] == 'true'
        and s['stopHeaderPresent'] and s['horizontalOverflow'] == 0
        and f['viewport']['innerWidth'] == f['width']
    )
    ok = ok and good
    print(('OK ' if good else 'BAD'), f['name'], 'inner', f['viewport']['innerWidth'],
          'root', f['rootFontSize'], 'scope', f['scope'], 'png', w, h, 'chip', s['chip'],
          'ovf', s['horizontalOverflow'], 'header', s['stopHeaderPresent'])
print('ALL OK' if ok else 'FAILURES', '| dark frames:', sum(1 for f in d['frames'] if f['scope'] == 'dark'))
sys.exit(0 if ok else 1)
