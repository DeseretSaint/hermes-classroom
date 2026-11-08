import json
from pathlib import Path
evidence = json.loads(Path('audit/visual/h196-workshop/evidence.json').read_text())
for frame in evidence['frames']:
    print('##', frame['id'], frame['width'], 'x', frame['height'], frame['mode'], frame.get('font') or '')
    print('   tabs=', frame['tabs'], 'current=', frame['tab_current'])
    print('   covers=', frame['cover_kinds'], 'imgs=', [(i['loaded'], i['natural']) for i in frame['images']])
    print('   hero=', frame['hero_present'], frame['hero_title'])
    print('   hero_primary=', frame['hero_primary'])
    print('   badges=', frame['badges'][:3])
    print('   detail=', frame['detail_title'], 'primary=', frame['detail_primary'][:4], 'sections=', frame['detail_sections'])
    print('   facts=', frame['detail_fact_labels'])
    print('   notice=', frame['notice'])
    print('   library_rows=', frame['library_rows'], 'empty=', frame['library_empty'])
    print('   cards=', frame['card_count'], 'shelves=', frame['shelf_count'])
    print('   overflow=', frame['horizontal_overflow'], frame['scroll_width'], '/', frame['client_width'],
          'h1=', frame['h1_count'], 'unnamed=', frame['button_without_a_name'], 'primary=', frame['primary_count'])
    print('   text=', (frame['text_head'] or '')[:120].replace('\n', ' '))
