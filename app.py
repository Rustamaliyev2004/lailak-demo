
from pathlib import Path
from io import BytesIO
import copy,html,json,re,tempfile,hashlib,sys,zipfile
import streamlit as st
import pandas as pd
import pymupdf as fitz
from engine import extract,review,parse_text
ROOT=Path(__file__).parent
st.set_page_config(page_title='Lailak | Construction finance review',page_icon='🕊',layout='wide')
st.markdown("""<style>
.block-container{padding-top:1.8rem;max-width:1450px}
h1,h2,h3{letter-spacing:-.7px}h1{font-size:2.55rem!important}
[data-testid="stSidebar"]{background:#102c34}
[data-testid="stSidebar"] *{color:#edf5f0}
[data-testid="stMetric"]{background:#f0f6f2;border:1px solid #deebe1;border-radius:12px;padding:17px}
.stButton>button[kind="primary"]{background:#126b57;border:none}
</style>""",unsafe_allow_html=True)
with st.sidebar:
 st.image(str(ROOT/'assets/logo_dark.png'),width=175)
 st.caption('CONSTRUCTION FINANCE / REVIEW DESK')
 section=st.radio('Workspace',['Document review','Evidence & benchmark','Satellite histories','Pilot plan'],label_visibility='collapsed')
 st.divider();st.caption('Public prototype · 10 Nov 2026')
 st.caption('Example records are synthetic. Public satellite histories are exploratory.')
st.caption('LAILAK / EVIDENCE BEFORE THE NEXT FUNDING DECISION')
st.caption('Public demonstration. Use sample or redacted documents. Uploaded files are processed on this app server for the review; do not upload confidential bank or customer records.')
if section=='Document review':
 st.title('Check the request. Trace every finding.')
 st.write('Compare a funding request with its supporting invoices and work report. Inspect the original pages and export a review pack.')
 source=st.segmented_control('Choose input',['Synthetic example','Upload documents'],default='Synthetic example')
 inputs=[]
 if source=='Synthetic example':
  packet=st.selectbox('Example packet',['Clean request','Request with repeated support'])
  folder=ROOT/'examples'/('clean' if packet=='Clean request' else 'issues')
  inputs=[{'name':p.name,'data':p.read_bytes()} for p in sorted(folder.iterdir()) if p.suffix in ('.pdf','.png')]
  st.info('Invented demonstration records. The clean packet should have no consistency flags. The second packet repeats an invoice and lists more support than the requested amount.')
  with st.expander('Download these documents and check them yourself'):
   buffer=BytesIO()
   with zipfile.ZipFile(buffer,'w') as z:
    for f in inputs:z.writestr(f['name'],f['data'])
   st.download_button('Download sample packet',buffer.getvalue(),'lailak_synthetic_packet.zip')
 else:
  uploaded=st.file_uploader('Public or redacted PDFs and scans · up to 5 pages per PDF',type=['pdf','png','jpg','jpeg'],accept_multiple_files=True)
  if len(uploaded)>5:st.error('Please review at most five documents at a time.');st.stop()
  inputs=[{'name':f'{i+1:02d}_'+Path(f.name).name,'data':f.getvalue()} for i,f in enumerate(uploaded)]
 cloud_state_path=ROOT/'benchmark/baidu_adapter_check.json'
 cloud_blocked=cloud_state_path.exists() and json.loads(cloud_state_path.read_text()).get('live_adapter_status')=='blocked_by_anonymous_gpu_quota'
 provider="local"
 if source=="Synthetic example":
  choice=st.selectbox('OCR engine for synthetic scans',['Server scan reader','Baidu Unlimited OCR 2 — official cloud demo'])
  provider="baidu" if choice.startswith("Baidu") else "local"
  if provider=="baidu":
   if cloud_blocked:st.warning('Baidu’s public demo quota is currently exhausted. Use Server scan reader to run this packet; the completed Baidu trials and raw outputs are on the benchmark screen.')
   else:st.info('Only generated sample scans will be sent to Baidu’s official Hugging Face demo. Shared GPU availability and queue times can vary.')
 signature=hashlib.sha256(b''.join(f['name'].encode()+f['data']+provider.encode() for f in inputs)).hexdigest()
 if st.button('Extract and review',type='primary',disabled=not inputs or (provider=='baidu' and cloud_blocked)):
  documents=[]
  with st.status('Reading source documents...',expanded=True) as status:
   for i,f in enumerate(inputs):
    st.write(f['name'])
    if len(f['data'])>5_000_000:st.error('File exceeds 5 MB demo limit.');st.stop()
    with tempfile.TemporaryDirectory() as tmp:
     path=Path(tmp)/f['name'];path.write_bytes(f['data'])
     try:documents.append(extract(path,provider=provider))
     except Exception as e:st.error(str(e));st.stop()
   result=review(documents)
   st.session_state['review']={'signature':signature,'result':result}
   status.update(label='Review ready',state='complete',expanded=False)
 active=st.session_state.get('review')
 if active and active['signature']==signature:
  result=active['result'];docs=result['documents']
  a,b,c,d=st.columns(4)
  a.metric('Source documents',len(docs));b.metric('Items to clarify',len(result['findings']))
  c.metric('Requested '+(result['currency'] or ''),f"{float(result['requested_amount']):,.2f}" if result['requested_amount'] else 'Unverified')
  d.metric('Listed support',f"{float(result['listed_total']):,.2f}" if result['listed_total'] else 'Unverified')
  st.subheader('What needs attention')
  if not result['findings']:st.success('No inconsistency found by the current rules. Authenticity and completed work still need confirmation.')
  for finding in result['findings']:
   with st.container(border=True):
    st.markdown('**'+finding['code'].replace('_',' ').capitalize()+'**')
    st.write(finding['message'])
    st.caption('Sources: '+' · '.join(x['file']+' / page '+str(x['page']) for x in finding['sources']))
  st.subheader('Check the extracted fields against the page')
  selected=st.selectbox('Source document',[d['file'] for d in docs])
  doc=next(d for d in docs if d['file']==selected);f=next(f for f in inputs if f['name']==selected)
  left,right=st.columns([1.25,1])
  with left:
   if selected.lower().endswith('.pdf'):
    pdf=fitz.open(stream=f['data'],filetype='pdf');pn=st.number_input('Page',min_value=1,max_value=len(pdf),step=1)
    st.image(pdf[pn-1].get_pixmap(dpi=110).tobytes('png'),caption=f"{selected} · page {pn}");pdf.close()
   else:st.image(f['data'],caption=selected)
  with right:
   table=[{'Field':k,'Extracted value':str(v),'Source page':doc['references'].get(k,{}).get('page')} for k,v in doc['fields'].items() if not k.endswith('_raw')]
   st.dataframe(pd.DataFrame(table),hide_index=True,width='stretch')
   if any(k.endswith('_requires_review') and v for k,v in doc['fields'].items()):st.warning('Identifier contains Cyrillic characters. Compare it carefully with the source before matching records.')
   st.caption('Extraction: '+', '.join(sorted(set(p['method'] for p in doc['pages'])))+f" · {doc['seconds']:.2f}s")
   with st.expander('Original extracted text and regions'):
    for page in doc['pages']:
     st.markdown(f"**Page {page['page']}**");st.code(page['text'],language=None)
   st.download_button('Download original source',f['data'],selected,key='source_dl')
  st.subheader('Record the reviewer’s next action')
  action=st.selectbox('Action',['Request clarification','Order site inspection','Refer to credit team','Record review; await next update'])
  note=st.text_area('Review notes',placeholder='Which discrepancy needs an explanation? Which document or inspection would settle it?')
  confirmed=st.checkbox('I checked the extracted amounts and identifiers against the source pages.')
  exported=copy.deepcopy(result);exported['human_review']={'action':action,'notes':note,'fields_checked':confirmed}
  st.download_button('Download review record (JSON)',json.dumps(exported,ensure_ascii=False,indent=2),'lailak_review.json','application/json')
  summary='<html><meta charset="utf-8"><title>Lailak review</title><body style="font:16px/1.5 sans-serif;max-width:900px;margin:40px auto"><h1>Lailak / funding review</h1><p>Prototype consistency review. Human verification required.</p>'
  for finding in result['findings']:
   summary+='<h2>'+html.escape(finding['code'])+'</h2><p>'+html.escape(finding['message'])+'</p><p>Sources: '+html.escape(', '.join(x['file']+' p'+str(x['page']) for x in finding['sources']))+'</p>'
  summary+='<h2>Reviewer action</h2><p>'+html.escape(action)+'</p><p>'+html.escape(note)+'</p><h2>Limitations</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in result['limits'])+'</ul></body></html>'
  st.download_button('Download printable review (HTML)',summary,'lailak_review.html','text/html')
 st.caption('Reads embedded PDF text directly; scans use the selected pretrained OCR engine. Uploaded documents use the server scan reader. Cloud OCR is available only for generated samples. Fields use label matching; findings use arithmetic and matching rules. Funding decisions remain with the bank.')
elif section=='Evidence & benchmark':
 st.title('Results you can inspect.')
 st.write('The published test set contains generated invoices with known answers. The 69/72 and 36/36 scores below were measured using the Mac Apple Vision workflow. This hosted edition uses a different scan reader, Tesseract. Those historical scores are not its measured accuracy.')
 p=ROOT/'benchmark/results.json'
 if p.exists():
  r=json.loads(p.read_text());a,b,c=st.columns(3)
  a.metric('Exact fields on this set',f"{r['fields_correct']} / {r['fields_total']}")
  b.metric('Complete documents',f"{r['complete_documents']} / {r['documents']}")
  c.metric('Median extraction',f"{r['median_seconds']:.2f}s")
  rows=[]
  for d in r['results']:
   wrong=[k for k,v in d['checks'].items() if not v['correct']]
   rows.append({'Document':d['file'],'Language':d['language'],'Format':d['quality'],'Correct fields':sum(v['correct'] for v in d['checks'].values()),'Fields':len(d['checks']),'Errors':', '.join(wrong) or 'None','Seconds':d['seconds']})
  st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
  st.warning('The templates share label families with the parser, and defects discovered in the first run were used to improve it. This is a transparent regression benchmark, not a blind real-world accuracy estimate.')
  st.download_button('Download benchmark with every answer',p.read_bytes(),'benchmark_results.json')
  with st.expander('Packet checks and reproducibility'):
   st.json(r['packets']);st.code(r['parser_sha256'])
  buffer=BytesIO()
  with zipfile.ZipFile(buffer,'w') as z:
   for f in sorted((ROOT/'benchmark/test').iterdir()):z.writestr(f.name,f.read_bytes())
   z.writestr('manifest.json',(ROOT/'benchmark/manifest.json').read_bytes())
  st.download_button('Download test documents and answer key',buffer.getvalue(),'lailak_test_documents.zip')
 st.subheader('Fresh layout challenge / parser frozen')
 challenge=ROOT/'benchmark/frozen_holdout/results.json'
 if challenge.exists():
  h=json.loads(challenge.read_text())
  st.metric('Exact fields on new synthetic layouts',str(h['fields_correct'])+' / '+str(h['fields_total']))
  st.caption('Six generated row-table documents, three languages, native PDFs and scans. The parser hash was fixed before testing and was not changed after seeing this result. These are still synthetic documents, not an external bank holdout.')
  st.download_button('Download frozen challenge results',challenge.read_bytes(),'frozen_challenge_results.json')
 st.subheader('Baidu Unlimited OCR 2 / official-model trial')
 probe=ROOT/'benchmark/baidu_probe_result.json'
 if probe.exists():
  data=json.loads(probe.read_text());events=[json.loads(e[6:]) for e in data.get('events',[]) if e.startswith('data: ')]
  raw=events[-1][0].get('text','') if events and isinstance(events[-1],list) else ''
  clean=re.sub(r'<[^>]+>|(?:header|text|title|footer|table)\[[^\]]*\]','',raw)
  fields=parse_text(clean)
  if fields:
   st.success('The official model returned the synthetic invoice. Its six expected fields can be checked below.')
   st.json(fields);st.caption(f"Observed wall time: {data['seconds']} seconds including remote queue and network. One synthetic page; no broad accuracy or production latency claim.")
   st.image(str(ROOT/'benchmark/baidu_probe.png'),width=550)
   with st.expander('Original model output'):st.code(raw,language=None)
  else:st.write(data.get('status'));st.json(data)
 language_results=ROOT/'benchmark/baidu_language_results.json'
 if language_results.exists():
  lr=json.loads(language_results.read_text())
  st.markdown('**Additional official-model language trials**')
  st.dataframe(pd.DataFrame([{'Language':x['language'],'Exact fields':str(x.get('correct',0))+' / '+str(x.get('total',6)),'Observed seconds':x['seconds'],'Status':x['status']} for x in lr]),hide_index=True,width='stretch')
  st.caption('English, Russian and Uzbek Latin: 18 of 18 fields across three generated pages. This small test is not a general accuracy estimate or a fair model comparison with the larger local test.')
 st.caption('The working upload workflow uses the server scan reader. The Baidu trial is a separate recorded experiment on synthetic data. A production Baidu deployment is not connected.')
elif section=='Satellite histories':
 st.title('Site evidence with a corrected method.')
 summary=ROOT/'satellite/summary.json'
 if summary.exists():
  st.dataframe(pd.DataFrame(json.loads(summary.read_text())),hide_index=True,width='stretch')
  options=list((ROOT/'satellite').glob('*_monthly.csv'))
  if options:
   f=st.selectbox('Example',options,format_func=lambda p:p.stem.replace('_monthly','').replace('_',' ').title())
   df=pd.read_csv(f,index_col='month');df.index=pd.to_datetime(df.index)
   if 'vv_db' in df:
    st.subheader('One radar track and pass');st.line_chart(df[['vv_db']])
   if 'ndvi' in df:
    st.subheader('Pixel-masked vegetation index');st.line_chart(df[['ndvi']])
   st.download_button('Download corrected observations',f.read_bytes(),f.name)
   st.caption('Fixed Sentinel-1A track 173 ascending / IW. Optical data uses a common 20m grid, cloud/shadow/snow rejection and processing-baseline offsets. Missing values remain missing.')
 else:st.info('The corrected satellite rerun is still processing.')
 st.warning('These are public examples with no independently verified construction labels or crop records. The rerun repairs extraction; it does not establish stage accuracy. Native boundaries remain to be verified.')
else:
 st.title('The next evidence must come from a lender.')
 st.write('First pilot: one construction funding-review workflow. Obtain an approved historical request, the documents the officer used, and the actual review outcome.')
 st.markdown('1. Compare preparation and review time with and without Lailak.\n2. Count extraction corrections, false flags and missed discrepancies.\n3. Test whether adding satellite evidence changes a useful action.\n4. Agree the success criteria with the budget owner before evaluating cases.')
 st.info('Proposed target: reduce total preparation and review time by 30%, including corrections. This is a target, not an achieved saving.')
 st.write('Our current examples and document tests use synthetic or public data. No banker assessment, customer traction or paid pilot has been claimed.')
 st.caption('Buyer escrow is held until commissioning; a bank’s construction loan can have separate tranche conditions. Confirm those conditions for each lending product.')
