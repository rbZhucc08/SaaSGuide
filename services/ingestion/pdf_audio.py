from __future__ import annotations
import hashlib, io, wave
from pathlib import Path
from typing import Any
from pypdf import PdfReader

class MediaError(ValueError):
 def __init__(self,message,code,status=400): super().__init__(message); self.code=code; self.status=status

def parse_pdf(content:bytes,filename:str)->dict[str,Any]:
 if Path(filename).suffix.lower()!='.pdf': raise MediaError('仅支持 PDF','extension_not_allowed',415)
 if not content or len(content)>5*1024*1024: raise MediaError('PDF 必须非空且不超过 5 MB','pdf_size_invalid',413)
 try: reader=PdfReader(io.BytesIO(content)); pages=[(page.extract_text() or '').strip() for page in reader.pages]
 except Exception as error: raise MediaError('PDF 损坏或无法解析','pdf_invalid',422) from error
 chars=sum(len(p) for p in pages); status='TEXT_EXTRACTED' if chars>=20 else 'OCR_REQUIRED'
 return {'filename':Path(filename).name,'sha256':hashlib.sha256(content).hexdigest(),'page_count':len(pages),'text_char_count':chars,'status':status,'pages':[{'page':i+1,'text':text} for i,text in enumerate(pages)],'ocr_status':'not_run' if status=='OCR_REQUIRED' else 'not_needed'}

def inspect_wav(content:bytes,filename:str)->dict[str,Any]:
 if Path(filename).suffix.lower()!='.wav': raise MediaError('演示适配器仅接受 WAV','audio_extension_not_allowed',415)
 try:
  with wave.open(io.BytesIO(content),'rb') as wav: duration=wav.getnframes()/wav.getframerate(); channels=wav.getnchannels(); rate=wav.getframerate()
 except Exception as error: raise MediaError('WAV 文件损坏或格式不受支持','wav_invalid',422) from error
 return {'filename':Path(filename).name,'duration_seconds':round(duration,3),'channels':channels,'sample_rate':rate,'transcription_status':'not_run','reason':'未配置真实语音识别服务'}
