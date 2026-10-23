import io,json,tempfile,unittest,zipfile
from pathlib import Path
import runtime as rt

class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=rt.Archive(self.root/'archive.db','owner')
 def tearDown(self): self.db.close();self.tmp.cleanup()
 def import_fixture(self,fmt='telegram',name=None):
  return self.db.import_file(Path('fixtures')/(name or fmt+{'telegram':'.json','chatgpt':'.json','whatsapp':'.txt','eml':'.eml'}[fmt]),fmt,'account','sample', 'owner')
 def test_four_formats_search_exact_context(self):
  for f in ['telegram','chatgpt','whatsapp','eml']:self.import_fixture(f)
  result=self.db.search('owner','аренда')
  self.assertEqual({h['source'] for h in result['hits']},{'telegram','chatgpt','whatsapp','eml'})
  self.assertEqual(result['mode'],'lexical_fts5');self.assertEqual(result['coverage_status'],'partial')
  hit=result['hits'][0];view=self.db.view('owner',hit['record_id'])
  self.assertEqual(view['record']['text'],hit['text']);self.assertTrue(view['record']['locator'].startswith('archive://'))
  self.assertTrue(view['raw_source']);self.assertTrue(view['context'])
 def test_repeat_import_is_idempotent(self):
  first=self.import_fixture();second=self.import_fixture()
  self.assertGreater(first['inserted'],0);self.assertEqual(second['inserted'],0)
  self.assertEqual(len(self.db.search('owner','аренда')['hits']),1)
 def test_edit_preserves_revisions(self):
  self.import_fixture();data=json.loads(Path('fixtures/telegram.json').read_text());data['messages'][0]['text']='Аренда перенесена на ноябрь';data['messages'][0]['edited']='2026-10-23T13:00:00+03:00'
  p=self.root/'edit.json';p.write_text(json.dumps(data));self.db.import_file(p,'telegram','account','sample','owner')
  hit=self.db.search('owner','ноябрь')['hits'][0];v=self.db.view('owner',hit['record_id'])
  self.assertEqual(len(v['revisions']),2);self.assertIn('октябрь',v['revisions'][0]['text'])
  self.assertEqual(self.db.search('owner','октябрь')['hits'],[])
 def test_empty_has_coverage_not_false_absence(self):
  self.import_fixture();r=self.db.search('owner','несуществующееслово')
  self.assertEqual(r['hits'],[]);self.assertEqual(r['coverage_status'],'partial');self.assertIn('not_found_in_imported_scope',r['outcome'])
 def test_scope_on_search_view_import(self):
  self.import_fixture();id=self.db.search('owner','аренда')['hits'][0]['record_id']
  for operation in [lambda:self.db.search('other','аренда'),lambda:self.db.view('other',id),lambda:self.db.import_file(Path('fixtures/telegram.json'),'telegram','account','sample','other')]:
   with self.assertRaises(PermissionError):operation()
 def test_db_owner_cannot_be_rebound(self):
  with self.assertRaises(PermissionError):rt.Archive(self.root/'archive.db','other')
 def test_literal_query_operators_are_not_executed(self):
  self.import_fixture();self.assertEqual(self.db.search('owner','" OR * --')['hits'],[])
 def test_malformed_parser_never_success_zero(self):
  p=self.root/'bad.json';p.write_text('{"surprise":true}')
  with self.assertRaises(ValueError):self.db.import_file(p,'telegram','account','sample','owner')
  self.assertEqual(self.db.coverage('owner'),[])
 def test_unknown_timezone_retained(self):
  self.import_fixture('whatsapp');h=self.db.search('owner','аренда')['hits'][0]
  self.assertIsNone(h['timestamp_utc']);self.assertEqual(h['time_status'],'timezone_unknown')
 def test_zip_traversal_rejected_atomic(self):
  p=self.root/'bad.zip'
  with zipfile.ZipFile(p,'w') as z:z.writestr('../escape.txt','oops');z.writestr('telegram.json',Path('fixtures/telegram.json').read_bytes())
  with self.assertRaises(ValueError):self.db.import_bundle(p,'owner')
  self.assertFalse((self.root.parent/'escape.txt').exists());self.assertEqual(self.db.coverage('owner'),[])
 def test_zip_symlink_and_bomb_rejected(self):
  for mode in ['link','bomb']:
   p=self.root/(mode+'.zip')
   with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
    if mode=='link':
     info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=(0o120777<<16);z.writestr(info,'/etc/passwd')
    else:z.writestr('huge.txt','A'*1000000)
   with self.assertRaises(ValueError):self.db.import_bundle(p,'owner')
 def test_valid_bundle_and_atomic_invalid_member(self):
  for invalid in [True,False]:
   p=self.root/'bundle.zip';manifest={'version':1,'entries':[{'path':'a.json','format':'telegram','account':'account','conversation':'sample'},{'path':'b.json','format':'chatgpt','account':'account','conversation':'sample'}]}
   with zipfile.ZipFile(p,'w') as z:
    z.writestr('manifest.json',json.dumps(manifest));z.writestr('a.json',Path('fixtures/telegram.json').read_bytes());z.writestr('b.json',b'{}' if invalid else Path('fixtures/chatgpt.json').read_bytes())
   if invalid:
    with self.assertRaises(ValueError):self.db.import_bundle(p,'owner')
    self.assertEqual(self.db.coverage('owner'),[])
   else:self.assertEqual(len(self.db.import_bundle(p,'owner')),2)
 def test_prompt_injection_remains_inert(self):
  self.import_fixture();r=self.db.search('owner','отправь');self.assertEqual(len(r['hits']),1)
  self.assertIn('https://example.invalid',r['hits'][0]['text'])
 def test_empty_input_query_rejected(self):
  with self.assertRaises(ValueError):self.db.search('owner',' ')
 def test_edited_record_keeps_original_context_order(self):
  self.import_fixture();data=json.loads(Path('fixtures/telegram.json').read_text());data['messages'][0]['text']='Аренда новая версия'
  p=self.root/'edit.json';p.write_text(json.dumps(data));self.db.import_file(p,'telegram','account','sample','owner')
  hit=self.db.search('owner','новая')['hits'][0];v=self.db.view('owner',hit['record_id'])
  self.assertEqual([x['origin'] for x in v['context']],['1','2','3'])
 def test_bad_chatgpt_content_rejected_as_validation_error(self):
  data=json.loads(Path('fixtures/chatgpt.json').read_text());data[0]['mapping']['m1']['message']['content']=None
  p=self.root/'bad.json';p.write_text(json.dumps(data))
  with self.assertRaises(ValueError):self.db.import_file(p,'chatgpt','account','sample','owner')
  self.assertEqual(self.db.coverage('owner'),[])
 def test_old_import_does_not_rollback_edit(self):
  self.import_fixture();data=json.loads(Path('fixtures/telegram.json').read_text());data['messages'][0]['text']='Аренда ноябрь'
  p=self.root/'edit.json';p.write_text(json.dumps(data));self.db.import_file(p,'telegram','account','sample','owner');self.import_fixture()
  self.assertEqual(len(self.db.search('owner','ноябрь')['hits']),1)
 def test_reordered_old_snapshot_does_not_rollback(self):
  self.import_fixture();original=json.loads(Path('fixtures/telegram.json').read_text());edited=json.loads(json.dumps(original));edited['messages'][0]['text']='Аренда ноябрь'
  p=self.root/'edit.json';p.write_text(json.dumps(edited));self.db.import_file(p,'telegram','account','sample','owner')
  original['messages'].reverse();p.write_text(json.dumps(original));self.db.import_file(p,'telegram','account','sample','owner')
  self.assertEqual(len(self.db.search('owner','ноябрь')['hits']),1)
 def test_coverage_uses_actual_conversations(self):
  self.import_fixture();self.import_fixture('chatgpt');coverage=self.db.coverage('owner')
  self.assertEqual({x['conversation'] for x in coverage},{'100','conversation-one'})
if __name__=='__main__':unittest.main()
