import json,tempfile,unittest
from pathlib import Path
from runtime import Archive

class ConnectorEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.db=Archive(self.root/'index.sqlite','owner')
  self.payload={'schema_version':1,'connector':'saved-conversation-reader','conversation_id':'synthetic-conv','coverage':{'status':'partial','gaps':['Only selected messages read']},'messages':[{'message_id':'synthetic-message','role':'user','created_at':'2026-10-23T05:00:00Z','updated_at':'2026-10-23T05:00:00Z','text':'Синтетический вопрос про поиск','url':'https://example.invalid/conversation/message','content_omitted':False,'evidence_kind':'complete_message','start_offset':0,'end_offset':32}]}
 def tearDown(self):self.db.close();self.temp.cleanup()
 def ingest(self):
  p=self.root/'evidence.json';p.write_text(json.dumps(self.payload));return self.db.import_file(p,'connector_evidence','synthetic','ignored','owner')
 def test_preserves_message_provenance(self):
  self.ingest();r=self.db.search('owner','поиск')['hits'][0]
  self.assertEqual(r['origin'],'synthetic-message');self.assertEqual(r['source_url'],'https://example.invalid/conversation/message');self.assertEqual(r['author'],'user');self.assertEqual(r['timestamp_raw'],'2026-10-23T05:00:00Z');self.assertEqual(r['evidence_kind'],'complete_message');self.assertEqual(self.db.coverage('owner')[0]['status'],'partial')
 def test_omitted_text_never_indexed_as_complete(self):
  self.payload['messages'][0]['content_omitted']=True;self.payload['messages'][0]['text']='';r=self.ingest()
  self.assertEqual(r['parsed'],0);self.assertIn('Omitted message: synthetic-message',r['gaps'])
 def test_excerpt_stays_excerpt(self):
  self.payload['messages'][0]['evidence_kind']='search_excerpt';self.ingest()
  self.assertEqual(self.db.search('owner','поиск')['hits'][0]['evidence_kind'],'search_excerpt')
 def test_rejects_unsafe_source_url(self):
  self.payload['messages'][0]['url']='javascript:alert(1)'
  with self.assertRaises(ValueError):self.ingest()
  self.assertEqual(self.db.coverage('owner'),[])
 def test_rejects_missing_provenance(self):
  del self.payload['messages'][0]['message_id']
  with self.assertRaises(ValueError):self.ingest()
 def test_coverage_unknown_gap_cannot_be_promoted(self):
  self.payload['coverage']['status']='complete'
  with self.assertRaises(ValueError):self.ingest()
 def test_unknown_coverage_preserved(self):
  self.payload['coverage']['status']='unknown';r=self.ingest()
  self.assertEqual(r['coverage_status'],'unknown');self.assertEqual(self.db.coverage('owner')[0]['status'],'unknown');self.assertEqual(self.db.search('owner','поиск')['coverage_status'],'unknown')
 def test_connector_namespaces_do_not_collide(self):
  self.ingest();self.payload['connector']='second-reader';self.payload['messages'][0]['text']='Другая запись';self.ingest()
  self.assertEqual(len(self.db.search('owner','поиск')['hits']),1);self.assertEqual(len(self.db.coverage('owner')),2)
 def test_omitted_coverage_uses_source_conversation(self):
  self.payload['messages'][0]['content_omitted']=True;self.ingest()
  self.assertEqual(self.db.coverage('owner')[0]['conversation'],'synthetic-conv')
if __name__=='__main__':unittest.main()
