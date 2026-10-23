import json,tempfile,unittest
from pathlib import Path
from runtime import Archive
try:
 from hybrid import HybridBackend, character_spans
except ImportError:
 HybridBackend = None
 character_spans = None

class ContractEncoder:
 """Synthetic deterministic vectors test plumbing, not semantic quality."""
 identity='synthetic-test-encoder'
 calls=0
 def spans(self,text):return character_spans(text,80,10)
 def encode(self,texts,kind):
  self.calls+=1
  return [[1.0,0.0] if 'пароль' in t else [0.0,1.0] for t in texts]

class HybridTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.a=Archive(self.root/'a.sqlite','owner')
 def tearDown(self):self.a.close();self.tmp.cleanup()
 def add(self,text='Здесь обсуждался пароль от архива.'):
  p=self.root/'t.json';p.write_text(json.dumps({'id':1,'messages':[{'id':1,'type':'message','date':'2026-01-01','from':'Synthetic','text':text}]}));self.a.import_file(p,'telegram','synthetic','c','owner')
 def backend(self):
  self.assertIsNotNone(HybridBackend,'Optional hybrid adapter not implemented');return HybridBackend(self.a,ContractEncoder())
 def test_source_span_is_exact(self):
  self.add();h=self.backend();r=h.search('owner','пароль');hit=r['hits'][0]
  self.assertEqual(hit['span']['text'],hit['text'][hit['span']['start']:hit['span']['end']]);self.assertEqual(r['coverage_status'],'partial');self.assertEqual(h.view('owner',hit['record_id'])['record']['text'],hit['text'])
 def test_scope_rejected_before_embedding(self):
  self.add();h=self.backend();before=h.encoder.calls
  with self.assertRaises(PermissionError):h.search('other','пароль')
  self.assertEqual(h.encoder.calls,before)
 def test_empty_archive_is_not_fake_hit(self):
  h=self.backend();r=h.search('owner','пароль');self.assertEqual(r['hits'],[]);self.assertEqual(r['coverage_status'],'unknown')
 def test_revision_invalidates_index(self):
  self.add();h=self.backend();h.search('owner','пароль');self.add('Совершенно новая версия.')
  with self.assertRaisesRegex(ValueError,'stale'):h.search('owner','пароль')
 def test_chunks_cover_unicode_without_changing_text(self):
  self.assertIsNotNone(character_spans,'chunking missing');text='А🙂я '+('строка\n'*30);spans=character_spans(text,40,8)
  self.assertEqual(spans[0][0],0);self.assertEqual(spans[-1][1],len(text));self.assertTrue(all(a<b and b-a<=40 for a,b in spans));self.assertTrue(all(spans[i][1]>=spans[i+1][0]for i in range(len(spans)-1)))
 def test_lexical_default_remains_lexical(self):
  self.add();self.assertEqual(self.a.search('owner','пароль')['mode'],'lexical_fts5')
 def test_invalid_query_rejected(self):
  h=self.backend()
  for q in ['', 'x'*8193]:
   with self.assertRaises(ValueError):h.search('owner',q)
 def test_similarity_not_answer_confidence(self):
  self.add();h=self.backend();r=h.search('owner','неизвестный запрос');self.assertEqual(r['outcome'],'candidates_not_verified_answers');self.assertIn('not calibrated',r['limitations'][0])

class MultiSpanTests(unittest.TestCase):
 setUp=HybridTests.setUp
 tearDown=HybridTests.tearDown
 add=HybridTests.add
 def test_distracting_best_span_does_not_hide_separate_caveat(self):
  text='Список популярных товаров и больших чисел.\nНельзя сравнивать спрос без числа реальных заказов.\nОстальные сведения не относятся к вопросу.'
  self.add(text)
  class ParagraphEncoder:
   identity='synthetic-paragraph-encoder'
   def spans(self,text):
    out=[];start=0
    for line in text.splitlines(True):out.append((start,start+len(line)));start+=len(line)
    return out
   def encode(self,texts,kind):
    if kind=='query':return [[1.0,0.0]for _ in texts]
    return [[1.0,0.0]if t.startswith('Список') else [0.8,0.2]if t.startswith('Нельзя') else [0.0,1.0]for t in texts]
  self.assertIsNotNone(HybridBackend)
  h=HybridBackend(self.a,ParagraphEncoder());hit=h.search('owner','Что можно установить по этим сведениям?')['hits'][0]
  spans=hit.get('spans',[])
  self.assertGreaterEqual(len(spans),2,'One best distractor must not hide separate evidence')
  self.assertTrue(any('Нельзя сравнивать' in x['text']for x in spans))
  for i,x in enumerate(spans):
   self.assertEqual(x['text'],text[x['start']:x['end']])
   self.assertEqual(x['context']['text'],text[x['context']['start']:x['context']['end']])
   for y in spans[i+1:]:self.assertFalse(x['start']<y['end']and y['start']<x['end'])
