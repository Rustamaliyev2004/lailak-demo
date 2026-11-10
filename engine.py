"""Local document evidence extraction and deterministic review. No credit decisions."""
from pathlib import Path
from decimal import Decimal, InvalidOperation
import hashlib, json, re, subprocess, tempfile, time,sys,shutil,csv,io
import pymupdf as fitz
ROOT=Path(__file__).parent
ALIASES={
"project_id":["Project ID","Project reference","Loyiha ID","Loyiha kodi","Код проекта","Проект"],
"invoice_id":["Invoice ID","Invoice number","Invoice no","Hisob-faktura raqami","Faktura raqami","Номер счета","Счет-фактура","Счёт-фактура"],
"date":["Date","Issue date","Sana","Hujjat sanasi","Дата","Дата документа"],
"supplier":["Supplier","Vendor","Yetkazib beruvchi","Ta'minotchi","Поставщик","Продавец"],
"amount":["Invoice total","Total amount","Amount","Jami summa","Summa","Итого","Сумма","Всего"],
"requested_amount":["Requested amount","Funding requested","So'ralgan summa","Sorov summasi","Запрашиваемая сумма","Сумма заявки"],
"claimed_stage":["Reported stage","Claimed stage","Bosqich","Bajarilgan ish","Этап","Выполненные работы"],
"currency":["Currency","Valyuta","Валюта"],
}
def normalize_amount(value):
 s=str(value).strip().replace("\u00a0"," ").replace("\u202f"," ")
 s=re.sub(r"(UZS|USD|EUR|RUB|SO['‘’]?M|СУМ|СЎМ|РУБ)","",s,flags=re.I).strip()
 if not s or re.search(r"[A-Za-zА-Яа-я]",s):return None
 s=s.replace(" ","").replace("'","").replace("’","")
 if not re.fullmatch(r"[+-]?\d[\d.,]*",s):return None
 if "," in s and "." in s:
  if s.rfind(",")>s.rfind("."):s=s.replace(".","").replace(",",".")
  else:s=s.replace(",","")
 elif "," in s:
  # Repeated groups of 3 are thousands; trailing 1-2 digits are decimal.
  if re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+",s):s=s.replace(",","")
  elif s.count(",")==1 and len(s.split(",")[1]) in (1,2):s=s.replace(",",".")
  else:return None
 try:
  n=Decimal(s)
  return str(n.quantize(Decimal("0.01"))) if n.is_finite() else None
 except InvalidOperation:return None
def parse_text(text):
 text=re.sub("[\u00ad\u2010-\u2015\u2212]","-",text)
 lines=[x.strip().replace("’","'").replace("‘","'") for x in text.splitlines() if x.strip()]
 fields={}
 for key,aliases in ALIASES.items():
  found=[]
  for i,line in enumerate(lines):
   for alias in sorted(aliases,key=len,reverse=True):
    m=re.match(r"^"+re.escape(alias)+r"\s*(?::|=|#)\s*(.*)$",line,re.I)
    if m:
     value=m.group(1).strip()
     if not value and i+1<len(lines):value=lines[i+1]
     if value:found.append(value)
     break
  if found:fields[key]=found[0]
  if len(set(found))>1:fields[key+"_ambiguous"]=True
 for key in ("project_id","invoice_id"):
  if key in fields and re.search("[А-Яа-я]",str(fields[key])):fields[key+"_requires_review"]=True
 for key in ("amount","requested_amount"):
  if key in fields:
   fields[key+"_raw"]=fields[key];fields[key]=normalize_amount(fields[key])
 # ISO date only: other formats remain explicitly unnormalised.
 if "date" in fields:
  from datetime import date
  try:fields["date"]=date.fromisoformat(fields["date"]).isoformat()
  except ValueError:fields["date_unverified"]=True
 return fields
def ocr_image(path,provider="local"):
 if provider=="baidu":
  from baidu_backend import read_public_sample
  return read_public_sample(path)

 if sys.platform!='darwin' or not (ROOT/'vision_ocr').exists():
  binary=shutil.which('tesseract')
  if not binary:raise RuntimeError("Scan OCR is not installed on this server. Embedded-text PDFs can still be processed.")
  proc=subprocess.run([binary,str(path),'stdout','-l','eng+rus+uzb','--psm','6','tsv'],capture_output=True,text=True,timeout=45)
  if proc.returncode:raise RuntimeError("Server scan reader failed. Try a clearer page or an embedded-text PDF.")
  groups={}
  for row in csv.DictReader(io.StringIO(proc.stdout),delimiter='\t'):
   text=(row.get('text') or '').strip()
   if not text:continue
   key=(row.get('page_num'),row.get('block_num'),row.get('par_num'),row.get('line_num'))
   groups.setdefault(key,[]).append(row)
  result=[]
  for rows in groups.values():
   x=min(int(r['left']) for r in rows);y=min(int(r['top']) for r in rows)
   right=max(int(r['left'])+int(r['width']) for r in rows);bottom=max(int(r['top'])+int(r['height']) for r in rows)
   confs=[float(r['conf']) for r in rows if float(r['conf'])>=0]
   result.append({'text':' '.join(r['text'] for r in rows),'confidence':sum(confs)/len(confs)/100 if confs else None,'bbox':[x,y,right,bottom],'bbox_units':'pixels'})
  return result
 binary=ROOT/'vision_ocr'
 proc=subprocess.run([str(binary),str(path)],capture_output=True,text=True,timeout=45)
 if proc.returncode:raise RuntimeError("Local scan reader failed.")
 return json.loads(proc.stdout)

def extract(path,force_ocr=False,provider="local"):
 path=Path(path);start=time.perf_counter();pages=[]
 if path.suffix.lower()==".pdf":
  with fitz.open(path) as doc:
   if doc.needs_pass:raise ValueError("Encrypted PDF: supply an unlocked public or approved sample.")
   if len(doc)>5:raise ValueError("Public demo limit: 5 pages per PDF.")
   with tempfile.TemporaryDirectory() as tmp:
    for i,page in enumerate(doc):
     text=page.get_text(sort=True)
     if force_ocr or len(text.strip())<25:
      image=Path(tmp)/f"p{i}.png";page.get_pixmap(dpi=180).save(image)
      records=ocr_image(image,provider=provider)
      text="\n".join(r["text"] for r in records)
      method=("Apple Vision OCR" if sys.platform=="darwin" and (ROOT/"vision_ocr").exists() else "Tesseract server OCR") if provider=="local" else "Baidu Unlimited OCR 2 official demo"
     else:
      records=[{"text":b[4],"bbox":list(b[:4]),"confidence":None} for b in page.get_text("blocks") if len(b)>4]
      method="Embedded PDF text"
     fields=parse_text(text)
     pages.append({"page":i+1,"text":text,"fields":fields,"method":method,"regions":records})
 else:
  records=ocr_image(path,provider=provider);text="\n".join(r["text"] for r in records)
  pages=[{"page":1,"text":text,"fields":parse_text(text),"method":(("Apple Vision OCR" if sys.platform=="darwin" and (ROOT/"vision_ocr").exists() else "Tesseract server OCR") if provider=="local" else "Baidu Unlimited OCR 2 official demo"),"regions":records}]
 merged={}
 for page in pages:
  for k,v in page["fields"].items():
   if k not in merged:merged[k]=v
   elif merged[k]!=v:merged[k+"_ambiguous"]=True
 lower=" ".join(p["text"].lower() for p in pages)
 kind="request" if "requested_amount" in merged else "invoice" if "invoice_id" in merged else "work_report" if "claimed_stage" in merged else "unknown"
 refs={k:{"file":path.name,"page":next(p["page"] for p in pages if k in p["fields"])} for k in merged}
 return {"file":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"kind":kind,"fields":merged,"references":refs,"pages":pages,"seconds":round(time.perf_counter()-start,3)}
def review(documents):
 findings=[];invoices=[d for d in documents if d["kind"]=="invoice"];requests=[d for d in documents if d["kind"]=="request"]
 def add(code,msg,docs):
  findings.append({"code":code,"message":msg,"sources":[{"file":d["file"],"page":d["references"].get("invoice_id",d["references"].get("requested_amount",{"page":1}))["page"]} for d in docs]})
 seen={}
 for d in invoices:
  f=d["fields"];ident=str(f.get("invoice_id","")).upper().replace(" ","")
  # Duplicate key is supplier+invoice ID; date/project does not excuse repetition.
  supplier=re.sub(r"\s+"," ",str(f.get("supplier","")).strip().casefold())
  key=(supplier,ident)
  if ident and supplier:
   if key in seen:add("repeated_invoice","Same supplier and invoice ID appear more than once. Verify whether this is a duplicate or a documented split.",[seen[key],d])
   else:seen[key]=d
 for d in documents:
  required={"invoice":["project_id","invoice_id","date","supplier","amount","currency"],"request":["project_id","date","requested_amount","currency"],"work_report":["project_id","date","claimed_stage"]}.get(d["kind"],[])
  missing=[k for k in required if d["fields"].get(k) in (None,"") or d["fields"].get(k+"_ambiguous") or d["fields"].get(k+"_requires_review") or (k=="date" and d["fields"].get("date_unverified"))]
  if missing:add("missing_or_ambiguous","Verify extracted fields: "+", ".join(missing),[d])
  if d["kind"]=="unknown":add("unclassified_document","Document type was not recognised. Human classification is required.",[d])
 if not requests:add("missing_request","No funding request was recognised. Add the request before comparing totals.",documents[:1])
 if len(requests)>1:add("multiple_requests","Multiple funding requests were supplied; choose one request for this review.",requests)
 if not invoices:add("missing_invoices","No supporting invoice was recognised.",requests[:1])
 projects={d["fields"].get("project_id") for d in documents if d["fields"].get("project_id")}
 if len(projects)>1:add("project_mismatch","The documents name different projects: "+", ".join(sorted(projects)),documents)
 currencies={d["fields"].get("currency","").upper() for d in invoices+requests if d["fields"].get("currency")}
 eligible=(len(requests)==1 and invoices and len(currencies)==1 and all(d["fields"].get("currency") and d["fields"].get("amount") is not None and not d["fields"].get("amount_ambiguous") for d in invoices) and requests[0]["fields"].get("requested_amount") is not None and not requests[0]["fields"].get("requested_amount_ambiguous"))
 total=None;requested=None
 if len(currencies)>1:add("currency_mismatch","Mixed currencies: totals were not compared. Supply a documented conversion.",invoices+requests)
 if eligible:
  total=sum(Decimal(d["fields"]["amount"]) for d in invoices);requested=Decimal(requests[0]["fields"]["requested_amount"])
  if any(Decimal(d["fields"]["amount"])<=0 for d in invoices):add("nonpositive_amount","A listed amount is zero or negative. Confirm credit-note treatment.",invoices)
  if total!=requested:add("total_mismatch",f"Requested {requested:,.2f}; listed support {total:,.2f}; difference {total-requested:,.2f} {next(iter(currencies))}. Partial financing may explain the difference; confirm it.",invoices+requests)
 return {"findings":findings,"invoice_count":len(invoices),"requested_amount":str(requested) if requested is not None else None,"listed_total":str(total) if total is not None else None,"currency":next(iter(currencies)) if len(currencies)==1 else None,"method":"Label-based field extraction, local pretrained OCR when needed, exact Decimal arithmetic and explicit rules.","limits":["Synthetic test examples do not establish performance on bank records.","A discrepancy requires clarification; it is not proof of fraud.","Amounts must be checked against source pages before a funding decision.","No construction percentage, structural safety or payment approval is inferred."],"documents":documents}
