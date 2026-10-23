import sys,socket,json,tempfile,time,resource
from pathlib import Path
import argparse
root=Path(__file__).resolve().parent

def smoke_exit_code(passed,total):
 return 0 if total>0 and passed==total else 1

def main():
 parser=argparse.ArgumentParser(description='Real local-model smoke test on synthetic messages only')
 parser.add_argument('--model',type=Path,required=True);args=parser.parse_args()
 def audit(event,args):
  if event in {'socket.connect','socket.getaddrinfo','socket.sendto'}:raise RuntimeError('Network forbidden during inference: '+event)
 sys.addaudithook(audit)
 from runtime import Archive
 from hybrid import LocalE5Encoder,HybridBackend
 cases=[
  ('В среду мастер заменит сломанный холодильник на кухне.','Когда придёт специалист починить технику для хранения продуктов?'),
  ('Билеты на поезд до Казани забронированы на пятницу, отправление в восемь утра.','В какой день мы едем в путешествие по железной дороге?'),
  ('Пароль от зашифрованного архива нужно хранить отдельно от файла.','Где безопаснее держать секрет для открытия защищённой копии?'),
  ('У статистики просмотров отсутствуют показатели пересылок, поэтому популярность по репостам неизвестна.','Можно ли по количеству зрителей понять, что люди чаще отправляли друзьям?'),
  ('Если два варианта ответа правдоподобны, следует задать уточняющий вопрос, а не выбрать случайно.','Как поступить, когда запрос допускает несколько толкований?')]
 start=time.time();encoder=LocalE5Encoder(args.model);loaded=time.time()
 with tempfile.TemporaryDirectory()as temp:
  a=Archive(Path(temp)/'a.sqlite','synthetic')
  p=Path(temp)/'messages.json';p.write_text(json.dumps({'id':10,'messages':[{'id':i+1,'type':'message','date':'2026-01-01','from':'Synthetic','text':t}for i,(t,q)in enumerate(cases)]}));a.import_file(p,'telegram','synthetic','sample','synthetic');h=HybridBackend(a,encoder)
  results=[]
  for i,(t,q)in enumerate(cases):
   res=h.search('synthetic',q,3);hit=res['hits'][0];assert hit['span']['text']==hit['text'][hit['span']['start']:hit['span']['end']]
   results.append({'query':q,'expected_origin':str(i+1),'top_origin':hit['origin'],'top1_pass':hit['origin']==str(i+1),'lexical_hits':len(a.search('synthetic',q)['hits']),'top_text':hit['span']['text'],'similarity':hit['semantic_similarity']})
  report={'model':encoder.identity,'load_seconds':loaded-start,'total_seconds':time.time()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'network_guard':'enabled; socket connect/DNS/sendto raise','results':results,'top1_passes':sum(x['top1_pass']for x in results),'coverage':'partial','quality_limit':'Five synthetic probes, not a general benchmark'}
  (root/'reports').mkdir(exist_ok=True)
  (root/'reports/synthetic-model-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2));a.close()
 return smoke_exit_code(report["top1_passes"],len(cases))

if __name__=="__main__":sys.exit(main())
