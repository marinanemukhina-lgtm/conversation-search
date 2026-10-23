"""Offline, single-owner correspondence archive. No network or model calls."""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, stat, sys, zipfile
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path, PurePosixPath
from typing import Protocol
from urllib.parse import urlsplit

MAX_FILE=8*1024*1024
MAX_BUNDLE=24*1024*1024
FORMATS={'telegram','chatgpt','whatsapp','eml','connector_evidence'}

def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def canonical(value)->str:return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def require_string(value,name):
 if not isinstance(value,str) or not value.strip() or len(value)>512:raise ValueError('Invalid '+name)
 return value

def timestamp(value):
 if value is None:return None,'unknown'
 try:
  dt=datetime.fromtimestamp(value,timezone.utc) if isinstance(value,(int,float)) else datetime.fromisoformat(str(value).replace('Z','+00:00'))
  if dt.tzinfo is None:return None,'timezone_unknown'
  return dt.astimezone(timezone.utc).isoformat(),'known'
 except (ValueError,OverflowError,TypeError,OSError):return None,'unparsed'

def parse(raw:bytes,fmt:str,conversation:str):
 """Parse supported export profiles; reject unexpected structures, never guess."""
 if len(raw)>MAX_FILE:raise ValueError('Input exceeds 8 MiB pilot limit')
 if fmt not in FORMATS:raise ValueError('Unsupported format')
 out=[];gaps=['Export only; completeness of the original service is not established.'];metadata={'source':fmt,'conversation':conversation,'coverage_status':'partial'}
 def add(origin,conv,author,time,text,locator,reply=None):
  if not isinstance(text,str):raise ValueError('Text must be a string')
  if len(text)>100000:raise ValueError('Message too large for pilot')
  utc,status=timestamp(time)
  out.append(dict(origin=str(origin),conversation=str(conv),author=str(author) if author is not None else None,timestamp_raw=time,timestamp_utc=utc,time_status=status,text=text,locator=locator,reply_to=str(reply) if reply is not None else None))
 if fmt=='connector_evidence':
  obj=json.loads(raw)
  if not isinstance(obj,dict) or obj.get('schema_version')!=1:raise ValueError('Unsupported evidence schema')
  require_string(obj.get('connector'),'connector');conv=require_string(obj.get('conversation_id'),'conversation_id')
  coverage=obj.get('coverage')
  if not isinstance(coverage,dict) or coverage.get('status') not in {'partial','unknown'} or not isinstance(coverage.get('gaps'),list) or any(not isinstance(g,str) for g in coverage['gaps']):raise ValueError('Connector coverage must remain partial or unknown')
  metadata={'source':fmt+':'+obj['connector'],'conversation':conv,'coverage_status':coverage['status']}
  gaps=['Selected connector messages only; not the whole account or conversation.']+coverage['gaps']
  if not isinstance(obj.get('messages'),list):raise ValueError('Missing evidence messages')
  for i,m in enumerate(obj['messages']):
   if not isinstance(m,dict):raise ValueError('Invalid evidence message')
   mid=require_string(m.get('message_id'),'message_id')
   if m.get('role') not in {'user','assistant','system','tool','unknown'}:raise ValueError('Invalid author role')
   if not isinstance(m.get('content_omitted'),bool):raise ValueError('Missing omission state')
   if m['content_omitted']:
    gaps.append('Omitted message: '+mid);continue
   if m.get('evidence_kind') not in {'complete_message','search_excerpt','partial_message'}:raise ValueError('Missing reading extent')
   url=m.get('url')
   if not isinstance(url,str) or len(url)>8192:raise ValueError('Invalid source URL')
   parsed=urlsplit(url)
   if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:raise ValueError('Source URL must be HTTPS without credentials')
   for field in ['created_at','updated_at']:
    if field not in m or m[field] is not None and not isinstance(m[field],str):raise ValueError('Missing or invalid source timestamp')
   start=m.get('start_offset');end=m.get('end_offset')
   if not isinstance(start,int) or not isinstance(end,int) or start<0 or end<start:raise ValueError('Invalid text offsets')
   add(mid,conv,m['role'],m['created_at'],m.get('text'),f'/messages/{i}')
   out[-1].update(source_url=url,updated_at=m['updated_at'],evidence_kind=m['evidence_kind'],start_offset=start,end_offset=end,connector=obj['connector'])
   if m['evidence_kind']!='complete_message':gaps.append('Partial text or search excerpt: '+mid)
 elif fmt=='telegram':
  obj=json.loads(raw)
  if not isinstance(obj,dict) or not isinstance(obj.get('messages'),list) or 'id' not in obj:raise ValueError('Unsupported Telegram export schema')
  conv=str(obj['id'])
  for i,m in enumerate(obj['messages']):
   if not isinstance(m,dict) or 'id' not in m:raise ValueError('Invalid Telegram message')
   if m.get('type')!='message':gaps.append('Service event skipped');continue
   text=m.get('text')
   if isinstance(text,list):
    if any(not isinstance(v,(str,dict)) or isinstance(v,dict) and not isinstance(v.get('text'),str) for v in text):raise ValueError('Unsupported Telegram text segment')
    text=''.join(v if isinstance(v,str) else v['text'] for v in text)
   if not isinstance(text,str):raise ValueError('Missing Telegram text')
   if any(k in m for k in ['photo','file','media_type']):gaps.append('Attachment content not extracted')
   add(m['id'],conv,m.get('from_id') or m.get('from'),m.get('date'),text,f'/messages/{i}',m.get('reply_to_message_id'))
 elif fmt=='chatgpt':
  obj=json.loads(raw)
  if not isinstance(obj,list):raise ValueError('Expected ChatGPT conversation array')
  for ci,c in enumerate(obj):
   if not isinstance(c,dict) or not isinstance(c.get('mapping'),dict) or not c.get('id'):raise ValueError('Unsupported ChatGPT export schema')
   for node_id,node in c['mapping'].items():
    if not isinstance(node,dict):raise ValueError('Invalid ChatGPT node')
    m=node.get('message')
    if m is None:continue
    if not isinstance(m,dict) or not m.get('id'):raise ValueError('Invalid ChatGPT message')
    content=m.get('content',{})
    if not isinstance(content,dict) or not isinstance(m.get('author',{}),dict):raise ValueError('Invalid ChatGPT content or author')
    if content.get('content_type')!='text':gaps.append('Non-text ChatGPT message skipped');continue
    parts=content.get('parts')
    if not isinstance(parts,list) or any(not isinstance(s,str) for s in parts):raise ValueError('Unsupported ChatGPT text parts')
    node_key=str(node_id).replace('~','~0').replace('/','~1')
    add(m['id'],c['id'],m.get('author',{}).get('role'),m.get('create_time'),'\n'.join(parts),f'/{ci}/mapping/{node_key}/message',node.get('parent'))
  gaps.append('All exported mapping nodes are retained; branch selection is not inferred.')
 elif fmt=='whatsapp':
  lines=raw.decode('utf-8-sig').splitlines(); pattern=re.compile(r'^(\d{2}/\d{2}/\d{4}), (\d{2}:\d{2}) - ([^:]+): (.*)$');entries=[]
  for line_no,line in enumerate(lines,1):
   m=pattern.match(line)
   if m:
    d,t,author,text=m.groups();dt=datetime.strptime(d+' '+t,'%d/%m/%Y %H:%M').isoformat();entries.append([line_no,dt,author,text])
   elif entries:entries[-1][3]+='\n'+line
   elif line.strip():raise ValueError('Unsupported WhatsApp profile: expected DD/MM/YYYY, HH:MM - Author: text')
  if not entries and raw.strip():raise ValueError('No supported WhatsApp messages')
  seen={}
  for line_no,dt,author,text in entries:
   key=dt+'|'+author;seen[key]=seen.get(key,0)+1
   add(key+'|'+str(seen[key]),conversation,author,dt,text,f'line:{line_no}')
  gaps += ['WhatsApp profile: DD/MM/YYYY 24-hour; timezone unknown.', 'No stable provider IDs: timestamp/author/occurrence keys are local heuristics; collisions/reordering need review.', 'Media and system-event interpretation are not implemented.']
 elif fmt=='eml':
  msg=BytesParser(policy=policy.default).parsebytes(raw)
  if msg.defects:raise ValueError('Malformed EML')
  body=msg.get_body(preferencelist=('plain',))
  if body is None:raise ValueError('EML requires text/plain; HTML-only is not supported')
  try: text=body.get_content()
  except (LookupError,UnicodeError):raise ValueError('Unsupported EML encoding') from None
  date=msg.get('Date');dt=None
  if date:
   try:dt=parsedate_to_datetime(date).isoformat()
   except (ValueError,TypeError):dt=str(date)
  origin=str(msg.get('Message-ID') or ('content:'+digest(raw)))
  add(origin,conversation,str(msg.get('From') or 'unknown'),dt,text,'mime:text/plain',msg.get('In-Reply-To'))
  if list(msg.iter_attachments()):gaps.append('Attachments not extracted')
  if not msg.get('Message-ID'):gaps.append('Missing Message-ID: content-hash identity; edits cannot be linked automatically.')
 if len(out)>10000:raise ValueError('Pilot limit is 10000 records per file')
 origins=[(m['conversation'],m['origin']) for m in out]
 if len(set(origins))!=len(origins):raise ValueError('Duplicate source IDs inside export')
 return out,sorted(set(gaps)),metadata

class KnowledgeBackend(Protocol):
 """A future backend must preserve owner isolation, exact evidence and coverage."""
 def search(self,owner:str,query:str,limit:int=20)->dict:...
 def view(self,owner:str,record_id:str)->dict:...
 def coverage(self,owner:str)->list[dict]:...

class Archive:
 def __init__(self,path:Path,owner:str):
  require_string(owner,'owner');self.owner=owner;self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row
  self.db.execute('PRAGMA foreign_keys=ON')
  self.db.executescript('''
   CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS blobs(hash TEXT PRIMARY KEY,content BLOB NOT NULL);
   CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,source TEXT NOT NULL,account TEXT NOT NULL,conversation TEXT NOT NULL,origin TEXT NOT NULL,current_revision INTEGER);
   CREATE TABLE IF NOT EXISTS revisions(seq INTEGER PRIMARY KEY,record_id TEXT NOT NULL REFERENCES records(id),hash TEXT NOT NULL,payload TEXT NOT NULL,blob_hash TEXT NOT NULL REFERENCES blobs(hash),observed_at TEXT NOT NULL,UNIQUE(record_id,hash));
   CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY,source TEXT NOT NULL,account TEXT NOT NULL,conversation TEXT NOT NULL,blob_hash TEXT NOT NULL,count INTEGER NOT NULL,gaps TEXT NOT NULL,observed_at TEXT NOT NULL);
   CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(record_id UNINDEXED,text,tokenize='unicode61');
  ''')
  row=self.db.execute("SELECT value FROM meta WHERE key='owner'").fetchone()
  if row and row[0]!=owner:self.db.close();raise PermissionError('Archive owner mismatch')
  if 'coverage_status' not in {r[1] for r in self.db.execute('PRAGMA table_info(imports)')}:self.db.execute("ALTER TABLE imports ADD COLUMN coverage_status TEXT NOT NULL DEFAULT 'partial'")
  self.db.execute("INSERT OR IGNORE INTO meta VALUES('owner',?)",(owner,));self.db.commit()
 def close(self):self.db.close()
 def _authorize(self,owner):
  if owner!=self.owner:raise PermissionError('Archive owner mismatch')
 def _commit_import(self,raw,fmt,account,conversation,records,gaps,metadata):
  fmt=metadata['source'];conversation=metadata['conversation'];coverage_status=metadata['coverage_status']
  blob=digest(raw);now=datetime.now(timezone.utc).isoformat();inserted=0
  self.db.execute('INSERT OR IGNORE INTO blobs VALUES(?,?)',(blob,raw))
  for record in records:
   rid=digest(canonical([fmt,account,record['conversation'],record['origin']]).encode());rh=digest(canonical({k:v for k,v in record.items() if k!='locator'}).encode())
   self.db.execute('INSERT OR IGNORE INTO records(id,source,account,conversation,origin) VALUES(?,?,?,?,?)',(rid,fmt,account,record['conversation'],record['origin']))
   prior=self.db.execute('SELECT seq FROM revisions WHERE record_id=? AND hash=?',(rid,rh)).fetchone()
   if prior:continue  # Reimporting an old observation never rolls back current revision.
   cursor=self.db.execute('INSERT INTO revisions(record_id,hash,payload,blob_hash,observed_at) VALUES(?,?,?,?,?)',(rid,rh,canonical(record),blob,now));seq=cursor.lastrowid
   self.db.execute('UPDATE records SET current_revision=? WHERE id=?',(seq,rid));self.db.execute('DELETE FROM search_index WHERE record_id=?',(rid,));self.db.execute('INSERT INTO search_index VALUES(?,?)',(rid,record['text']));inserted+=1
  conversations=sorted({r['conversation'] for r in records}) or [conversation]
  for conv in conversations:
   count=sum(r['conversation']==conv for r in records)
   self.db.execute('INSERT INTO imports(source,account,conversation,blob_hash,count,gaps,observed_at,coverage_status) VALUES(?,?,?,?,?,?,?,?)',(fmt,account,conv,blob,count,canonical(gaps),now,coverage_status))
  return {'source':fmt,'parsed':len(records),'inserted':inserted,'coverage_status':coverage_status,'gaps':gaps,'blob_hash':blob}
 def import_file(self,path,fmt,account,conversation,owner):
  self._authorize(owner);require_string(account,'account');require_string(conversation,'conversation')
  path=Path(path)
  if path.is_symlink() or not path.is_file():raise ValueError('Input must be a regular non-symlink file')
  with path.open('rb') as f:raw=f.read(MAX_FILE+1)
  records,gaps,metadata=parse(raw,fmt,conversation)
  with self.db:return self._commit_import(raw,fmt,account,conversation,records,gaps,metadata)
 def import_bundle(self,path,owner):
  self._authorize(owner);path=Path(path)
  if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_BUNDLE:raise ValueError('Invalid bundle')
  with zipfile.ZipFile(path) as z:
   infos=z.infolist();names=set();total=0
   if len(infos)>100:raise ValueError('Too many ZIP members')
   for info in infos:
    name=info.filename;p=PurePosixPath(name);mode=(info.external_attr>>16)&0xffff
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or name in names or info.is_dir() or stat.S_ISLNK(mode):raise ValueError('Unsafe ZIP member')
    if info.flag_bits&1 or info.file_size>MAX_FILE or info.file_size/max(info.compress_size,1)>100:raise ValueError('Encrypted or oversized ZIP member')
    if Path(name).suffix.lower() in {'.zip','.tar','.gz','.7z'}:raise ValueError('Nested archives rejected')
    total+=info.file_size;names.add(name)
   if total>MAX_BUNDLE or 'manifest.json' not in names:raise ValueError('Invalid bundle size or missing manifest')
   def read(name):
    with z.open(name) as f:data=f.read(MAX_FILE+1)
    if len(data)>MAX_FILE:raise ValueError('Expanded member too large')
    return data
   manifest=json.loads(read('manifest.json'))
   if not isinstance(manifest,dict) or manifest.get('version')!=1 or not isinstance(manifest.get('entries'),list):raise ValueError('Invalid manifest')
   pending=[];used={'manifest.json'}
   for e in manifest['entries']:
    if not isinstance(e,dict) or set(e)!={'path','format','account','conversation'}:raise ValueError('Invalid manifest entry')
    name=e['path']
    if name in used or name not in names:raise ValueError('Invalid manifest path')
    used.add(name);require_string(e['account'],'account');require_string(e['conversation'],'conversation');raw=read(name);records,gaps,metadata=parse(raw,e['format'],e['conversation']);pending.append((raw,e['format'],e['account'],e['conversation'],records,gaps,metadata))
   if used!=names:raise ValueError('Unlisted ZIP member')
  with self.db:return [self._commit_import(*args) for args in pending]
 def coverage(self,owner):
  self._authorize(owner)
  return [{**dict(r),'gaps':json.loads(r['gaps']),'status':r['coverage_status']} for r in self.db.execute('SELECT source,account,conversation,count,gaps,observed_at,coverage_status FROM imports WHERE id IN (SELECT MAX(id) FROM imports GROUP BY source,account,conversation) ORDER BY source,account,conversation')]
 def _record(self,row):
  p=json.loads(row['payload']);return {**p,'source_pointer':p['locator'],'locator':f"archive://{row['id']}/revision/{row['seq']}",'record_id':row['id'],'source':row['source'],'account':row['account'],'revision':row['seq'],'observed_at':row['observed_at'],'content_hash':row['hash'],'raw_blob_hash':row['blob_hash'],'revision_semantics':'observed_import_order_not_attested_source_version'}
 def search(self,owner,query,limit=20):
  self._authorize(owner)
  if not isinstance(query,str) or not query.strip() or len(query)>8192 or not isinstance(limit,int) or not 1<=limit<=100:raise ValueError('Invalid query or limit')
  tokens=re.findall(r'\w+',query,flags=re.UNICODE)[:64]
  match=' AND '.join('"'+t.replace('"','""')+'"' for t in tokens)
  hits=[]
  if match:
   rows=self.db.execute('''SELECT r.*,v.* FROM search_index f JOIN records r ON r.id=f.record_id JOIN revisions v ON v.seq=r.current_revision WHERE search_index MATCH ? ORDER BY bm25(search_index),r.id LIMIT ?''',(match,limit))
   hits=[self._record(r) for r in rows]
  return {'mode':'lexical_fts5','query':query,'hits':hits,'coverage':self.coverage(owner),'coverage_status':'partial' if self.coverage(owner) and all(x['status']=='partial' for x in self.coverage(owner)) else 'unknown','outcome':'found' if hits else 'not_found_in_imported_scope','limitations':['Exact token AND match; no stemming, embeddings, semantic inference or live sync.']}
 def view(self,owner,record_id):
  self._authorize(owner)
  row=self.db.execute('SELECT r.*,v.* FROM records r JOIN revisions v ON v.seq=r.current_revision WHERE r.id=?',(record_id,)).fetchone()
  if row is None:raise KeyError('Record not found')
  record=self._record(row)
  revisions=[{**json.loads(r['payload']),'revision':r['seq'],'observed_at':r['observed_at'],'raw_blob_hash':r['blob_hash']} for r in self.db.execute('SELECT * FROM revisions WHERE record_id=? ORDER BY seq',(record_id,))]
  rows=list(self.db.execute('SELECT r.*,v.* FROM records r JOIN revisions v ON v.seq=r.current_revision WHERE r.source=? AND r.account=? AND r.conversation=? ORDER BY (SELECT MIN(first.seq) FROM revisions first WHERE first.record_id=r.id)',(row['source'],row['account'],row['conversation'])))
  index=next(i for i,r in enumerate(rows) if r['id']==record_id);context=[self._record(r) for r in rows[max(0,index-2):index+3]]
  raw=self.db.execute('SELECT content FROM blobs WHERE hash=?',(row['blob_hash'],)).fetchone()[0]
  return {'record':record,'revisions':revisions,'context':context,'context_order':'observed import order (not inferred chronology)','raw_source':raw.decode('utf-8',errors='replace'),'raw_source_display':'UTF-8 preview; original bytes stored unchanged in SQLite','scope':'single local archive owner'}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--db',required=True,type=Path);parser.add_argument('--owner',required=True);sub=parser.add_subparsers(dest='cmd',required=True)
 imp=sub.add_parser('import');imp.add_argument('file',type=Path);imp.add_argument('--format',choices=sorted(FORMATS),required=True);imp.add_argument('--account',required=True);imp.add_argument('--conversation',required=True)
 bundle=sub.add_parser('bundle');bundle.add_argument('file',type=Path)
 search=sub.add_parser('search');search.add_argument('query');search.add_argument('--limit',type=int,default=20)
 view=sub.add_parser('view');view.add_argument('record_id');sub.add_parser('coverage')
 args=parser.parse_args();archive=None
 try:
  archive=Archive(args.db,args.owner)
  if args.cmd=='import':result=archive.import_file(args.file,args.format,args.account,args.conversation,args.owner)
  elif args.cmd=='bundle':result=archive.import_bundle(args.file,args.owner)
  elif args.cmd=='search':result=archive.search(args.owner,args.query,args.limit)
  elif args.cmd=='view':result=archive.view(args.owner,args.record_id)
  else:result=archive.coverage(args.owner)
  print(json.dumps(result,ensure_ascii=False,indent=2));return 0
 except (ValueError,PermissionError,KeyError,sqlite3.Error,OSError,zipfile.BadZipFile) as exc:
  print(json.dumps({'error':type(exc).__name__,'message':str(exc)},ensure_ascii=False),file=sys.stderr);return 2
 finally:
  if archive:archive.close()
if __name__=='__main__':sys.exit(main())
