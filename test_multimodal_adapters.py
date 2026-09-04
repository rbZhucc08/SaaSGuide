import io,tempfile,unittest,wave
from pathlib import Path
from pypdf import PdfWriter
from services.ingestion.pdf_audio import MediaError,inspect_wav,parse_pdf
from services.adapters.contracts import AdapterError,validate_envelope
ROOT=Path(__file__).resolve().parent
class MultimodalTests(unittest.TestCase):
 def test_text_pdf_extracts_with_page(self):
  p=ROOT/'data/documents/phase7_meeting_notes.pdf'; r=parse_pdf(p.read_bytes(),p.name); self.assertEqual('TEXT_EXTRACTED',r['status']); self.assertEqual(1,r['page_count']); self.assertIn('接口评审未通过',r['pages'][0]['text'])
 def test_blank_pdf_requires_ocr_without_claiming_it_ran(self):
  stream=io.BytesIO(); w=PdfWriter(); w.add_blank_page(width=200,height=200); w.write(stream); r=parse_pdf(stream.getvalue(),'scan.pdf'); self.assertEqual('OCR_REQUIRED',r['status']); self.assertEqual('not_run',r['ocr_status'])
 def test_wav_metadata_does_not_claim_transcription(self):
  stream=io.BytesIO()
  with wave.open(stream,'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b'\0\0'*1600)
  r=inspect_wav(stream.getvalue(),'sample.wav'); self.assertEqual(0.1,r['duration_seconds']); self.assertEqual('not_run',r['transcription_status'])
 def test_adapter_rejects_live_mode_and_never_writes_back(self):
  with self.assertRaises(AdapterError): validate_envelope({'adapter':'mock-project-api','mode':'live','records':[]})
  r=validate_envelope({'adapter':'mock-project-api','mode':'simulation','records':[{}]}); self.assertFalse(r['writeback']); self.assertFalse(r['external_request_sent'])
if __name__=='__main__': unittest.main(verbosity=2)
