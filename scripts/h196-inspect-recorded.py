import json
from pathlib import Path
recorded = json.loads(Path('audit/visual/h196-workshop/recorded.json').read_text())
for key in ('library_empty', 'library_full', 'rpc'):
    value = recorded[key]
    print('##', key)
    print(json.dumps(value, indent=1)[:1200])
print('## install_response')
print(json.dumps(recorded['install_response'], indent=1))
