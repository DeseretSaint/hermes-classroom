import json, re, sys
from pathlib import Path
frames = json.loads(Path('audit/visual/h196-workshop/frames.json').read_text())['frames']
idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
frame = frames[idx]
html = frame['html']
text = re.sub(r'<[^>]+>', ' ', html)
print('ID', frame['id'], 'bytes', len(html))
print(re.sub(r'\s+', ' ', text)[:1200])
print('--- markers ---')
for marker in ('data-cb-workshop-cover', 'data-cb-workshop-hero', 'data-cb-workshop-card', 'data-cb-workshop-tab',
               'empty-state', 'loader', 'error-state', 'data-cb-pack-row'):
    print(marker, html.count(marker))
