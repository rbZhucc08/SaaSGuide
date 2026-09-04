import unittest
from pathlib import Path
from services.reporting.metrics import calculate,csv_bytes,load_dataset
ROOT=Path(__file__).resolve().parent
class ReportingTests(unittest.TestCase):
 def setUp(self): self.result=calculate(load_dataset(ROOT/'data/evaluation/phase6_reporting_data.json'))
 def test_fixed_metrics(self):
  m=self.result['metrics']; self.assertEqual(6,m['risk_total']); self.assertEqual(3,m['high_risk']); self.assertEqual(3,m['confirmed']); self.assertEqual(2,m['overdue_actions']); self.assertAlmostEqual(1/3,m['false_positive_rate']); self.assertEqual(23.8,m['average_resolution_hours'])
 def test_draft_uses_calculated_numbers(self): self.assertIn('新增 6 条',self.result['report_draft']); self.assertEqual('python_deterministic_no_llm',self.result['generation'])
 def test_csv_has_bom_and_header(self):
  data=csv_bytes(self.result); self.assertTrue(data.startswith(b'\xef\xbb\xbf')); self.assertIn('误报率',data.decode('utf-8-sig'))
if __name__=='__main__': unittest.main(verbosity=2)
