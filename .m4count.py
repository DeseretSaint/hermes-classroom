import json
a = json.load(open('audit/visual/m4-visual/audit.json'))
print(sorted(a.keys()))
fr = a.get('frames') or a.get('scenarios') or []
print('frames', len(fr))
if fr:
    print('frame keys', sorted(fr[0].keys()))
tot = 0
nonforced = 0
for f in fr:
    m = f.get('measurements') or f
    n = m.get('text_nodes') or m.get('textNodes') or 0
    tot += n
    v = f.get('variant') or f
    if not v.get('forced_colors') and not v.get('forcedColors'):
        nonforced += n
print('total', tot, 'nonforced', nonforced)
