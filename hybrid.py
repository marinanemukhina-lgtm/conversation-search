"""Optional in-process hybrid retrieval. No downloader, service or generation."""
import hashlib,json,math
from pathlib import Path

MODEL_REVISION='614241f622f53c4eeff9890bdc4f31cfecc418b3'

def character_spans(text,size=700,overlap=100):
 if not 0<=overlap<size:raise ValueError('Invalid chunk bounds')
 return [(start,min(start+size,len(text))) for start in range(0,len(text),size-overlap)]


def verify_model_directory(directory):
 """Anchor to the code-reviewed manifest beside this module, never caller hashes."""
 directory=Path(directory)
 trusted=json.loads(Path(__file__).with_name('model-manifest.json').read_text())
 supplied=json.loads((directory/'manifest.json').read_text())
 if trusted.get('revision')!=MODEL_REVISION or supplied!=trusted:
  raise ValueError('Local manifest conflicts with trusted pinned manifest')
 allowed={entry['path'] for entry in trusted['files']} | {'manifest.json'}
 if {p.name for p in directory.iterdir()} != allowed:
  raise ValueError('Unexpected or missing files in model directory')
 for entry in trusted['files']:
  path=directory/entry['path']
  if path.is_symlink() or not path.is_file() or path.stat().st_size!=entry['bytes']:
   raise ValueError('Model file type or size mismatch')
  digest=hashlib.sha256()
  with path.open('rb') as stream:
   for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
  actual=digest.hexdigest()
  if actual!=entry['sha256']:raise ValueError('Model file checksum mismatch')
 return directory

class LocalE5Encoder:
 identity='intfloat/multilingual-e5-small@'+MODEL_REVISION
 def __init__(self,model_directory):
  # Validate before ML imports; no pickle weights or repository executable code.
  directory=verify_model_directory(model_directory)
  import os
  os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',TOKENIZERS_PARALLELISM='false')
  from transformers import AutoTokenizer,AutoModel
  import torch
  self.torch=torch;torch.set_num_threads(2)
  self.tokenizer=AutoTokenizer.from_pretrained(str(directory),local_files_only=True,trust_remote_code=False,use_fast=True)
  self.model=AutoModel.from_pretrained(str(directory),local_files_only=True,trust_remote_code=False,use_safetensors=True).eval().to('cpu')
 def spans(self,text):
  offsets=self.tokenizer(text,add_special_tokens=False,return_offsets_mapping=True,truncation=False,verbose=False)['offset_mapping']
  spans=[]
  for i in range(0,len(offsets),160):
   part=offsets[i:i+192]
   if part:spans.append((part[0][0],part[-1][1]))
   if i+192>=len(offsets):break
  return spans
 def encode(self,texts,kind):
  if kind not in {'query','passage'}:raise ValueError('Invalid embedding kind')
  result=[]
  for i in range(0,len(texts),2):
   batch=self.tokenizer([kind+': '+s for s in texts[i:i+2]],padding=True,truncation=False,return_tensors='pt')
   if batch['input_ids'].shape[1]>512:raise ValueError('Input exceeds model token budget; no silent truncation')
   with self.torch.inference_mode():
    out=self.model(**batch).last_hidden_state
    mask=batch['attention_mask'].unsqueeze(-1).bool();out=out.masked_fill(~mask,0)
    pooled=out.sum(dim=1)/batch['attention_mask'].sum(dim=1).unsqueeze(-1)
    normalized=self.torch.nn.functional.normalize(pooled,p=2,dim=1)
   result.extend(normalized.tolist())
  return result

class HybridBackend:
 """KnowledgeBackend-compatible wrapper. Small bounded in-memory derived index."""
 def __init__(self,archive,encoder):
  self.archive=archive;self.encoder=encoder;self.snapshot=None;self.chunks=[];self.vectors=[]
 def _rows(self):
  count,total=self.archive.db.execute('SELECT COUNT(*), COALESCE(SUM(length(CAST(v.payload AS BLOB))),0) FROM records r JOIN revisions v ON v.seq=r.current_revision').fetchone()
  if count>1000 or total>2*1024*1024:raise ValueError('Pilot archive record/payload cap exceeded')
  return list(self.archive.db.execute('SELECT r.*,v.* FROM records r JOIN revisions v ON v.seq=r.current_revision ORDER BY r.id'))
 def _fingerprint(self,rows):return [(r['id'],r['seq'],r['hash'])for r in rows]
 def _index(self,owner):
  self.archive._authorize(owner);rows=self._rows();fingerprint=self._fingerprint(rows)
  if self.snapshot is not None:
   if self.snapshot!=fingerprint:raise ValueError('Semantic index stale after archive change; create a fresh backend')
   return
  chunks=[]
  for row in rows:
   record=self.archive._record(row)
   for start,end in self.encoder.spans(record['text']):
    if not 0<=start<end<=len(record['text']):raise ValueError('Invalid source span')
    chunks.append({'record':record,'start':start,'end':end})
    if len(chunks)>2000:raise ValueError('Pilot cap: 2000 chunks')
  vectors=self.encoder.encode([c['record']['text'][c['start']:c['end']]for c in chunks],'passage') if chunks else []
  if len(vectors)!=len(chunks):raise ValueError('Embedding count mismatch')
  self.chunks=chunks;self.vectors=vectors;self.snapshot=fingerprint
 def coverage(self,owner):return self.archive.coverage(owner)
 def view(self,owner,record_id):return self.archive.view(owner,record_id)
 def search(self,owner,query,limit=20):
  self.archive._authorize(owner)
  if not isinstance(query,str) or not query.strip() or len(query)>8192 or not isinstance(limit,int) or not 1<=limit<=100:raise ValueError('Invalid query or limit')
  self._index(owner);lexical=self.archive.search(owner,query,100)
  hits=[]
  if self.chunks:
   q=self.encoder.encode([query],'query')[0]
   scores=[]
   for i,v in enumerate(self.vectors):
    if len(v)!=len(q) or not all(math.isfinite(x)for x in v+q):raise ValueError('Invalid embedding dimensions or values')
    denom=math.sqrt(sum(x*x for x in v)*sum(x*x for x in q))
    score=sum(a*b for a,b in zip(v,q))/denom if denom else 0
    scores.append((score,i))
   # One best exact chunk per record; reciprocal-rank fusion with unchanged lexical baseline.
   best={};span_candidates={}
   for score,i in sorted(scores,reverse=True):
    rid=self.chunks[i]['record']['record_id']
    if rid not in best:best[rid]=(score,i)
    span_candidates.setdefault(rid,[]).append((score,i))
   sranks={rid:rank for rank,rid in enumerate(best,1)}
   lranks={h['record_id']:rank for rank,h in enumerate(lexical['hits'],1)}
   for rid,(similarity,i)in best.items():
    c=self.chunks[i];record=c['record'];rrf=1/(60+sranks[rid])+(1/(60+lranks[rid]) if rid in lranks else 0)
    spans=[]
    for span_score,j in span_candidates[rid]:
     candidate=self.chunks[j];start,end=candidate['start'],candidate['end']
     if any(start<x['end'] and x['start']<end for x in spans):continue
     cs,ce=max(0,start-200),min(len(record['text']),end+200)
     spans.append({'start':start,'end':end,'text':record['text'][start:end],'semantic_similarity':span_score,'context':{'start':cs,'end':ce,'text':record['text'][cs:ce]}})
     if len(spans)==3:break
    hits.append({**record,'span':spans[0],'spans':spans,'span_offsets':'Unicode character offsets relative to the returned record text','semantic_similarity':similarity,'rrf_score':rrf,'lexical_rank':lranks.get(rid),'semantic_rank':sranks[rid]})
   hits=sorted(hits,key=lambda h:(-h['rrf_score'],h['record_id']))[:limit]
  return {'mode':'local_hybrid_rrf','model':self.encoder.identity,'query':query,'hits':hits,'coverage':lexical['coverage'],'coverage_status':lexical['coverage_status'],'outcome':'candidates_not_verified_answers' if hits else 'not_found_in_imported_scope','limitations':['Similarity is not calibrated answer confidence; nearest candidates can be irrelevant.','Partial imported scope; no generated answer, live sync or completeness claim.'],'chunk_count':len(self.chunks)}
