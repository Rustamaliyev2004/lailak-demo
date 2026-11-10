
"""Official Baidu demo adapter, exposed only for synthetic examples in the UI."""
import json,re,time
from pathlib import Path
import requests
BASE='https://baidu-unlimited-ocr-2.hf.space'
def read_public_sample(path):
 start=time.perf_counter()
 with Path(path).open('rb') as f:
  upload=requests.post(BASE+'/gradio_api/upload',files={'files':(Path(path).name,f,'image/png')},timeout=30)
 upload.raise_for_status();remote=upload.json()[0]
 response=requests.post(BASE+'/gradio_api/call/parse_page',json={'data':[{'path':remote,'meta':{'_type':'gradio.FileData'}},'','auto',2048]},timeout=30)
 response.raise_for_status();event=response.json()['event_id'];text='';completed=False;message=''
 with requests.get(BASE+'/gradio_api/call/parse_page/'+event,stream=True,timeout=(15,100)) as stream:
  stream.raise_for_status()
  for raw in stream.iter_lines():
   if raw.startswith(b'event: complete'):completed=True
   if raw.startswith(b'data: '):
    data=json.loads(raw[6:])
    if isinstance(data,list) and data and isinstance(data[0],dict):
     text=data[0].get('text',text)
    elif data:message=str(data)
   if time.perf_counter()-start>140:raise RuntimeError('Official model timed out; use local OCR or inspect the saved trial.')
 if not completed or not text:raise RuntimeError('Official demo returned no complete OCR output. '+message)
 clean=re.sub(r'<[^>]+>|(?:header|text|title|footer|table)\[[^\]]*\]','',text)
 return [{'text':line,'confidence':None,'bbox':None,'method':'Baidu Unlimited OCR 2'} for line in clean.splitlines() if line.strip()]
