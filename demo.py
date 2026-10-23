"""Reproducible synthetic-only demo. Run from this directory."""
import json,tempfile
from pathlib import Path
from runtime import Archive
root=Path(__file__).parent
with tempfile.TemporaryDirectory() as temp:
 archive=Archive(Path(temp)/'demo.sqlite','demo')
 try:
  imports=[]
  for fmt,ext in [('chatgpt','json'),('telegram','json'),('whatsapp','txt'),('eml','eml')]:
   imports.append(archive.import_file(root/'fixtures'/f'{fmt}.{ext}',fmt,'synthetic','sample','demo'))
  result=archive.search('demo','аренда');assert len(result['hits'])==4
  view=archive.view('demo',result['hits'][0]['record_id']);assert view['record']['text']==result['hits'][0]['text']
  repeat=archive.import_file(root/'fixtures/telegram.json','telegram','synthetic','sample','demo');assert repeat['inserted']==0
  report={'status':'PASS','synthetic_only':True,'imports':imports,'query_result':result,'source_view':view,'repeat_import':repeat,'network_calls':0,'models_connected':False}
  (root/'reports').mkdir(exist_ok=True);(root/'reports/demo-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  print('PASS: 4 formats imported; 4 exact-token hits; source viewer verified; repeat import inserted 0 records.')
  print('Mode: lexical_fts5. Coverage: partial. No live accounts or models.')
 finally:archive.close()
