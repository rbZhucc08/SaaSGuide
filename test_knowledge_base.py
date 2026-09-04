import json
import unittest
from pathlib import Path

from services.retrieval.knowledge_base import answer, evaluate, load_documents

ROOT=Path(__file__).resolve().parent

class KnowledgeBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents=load_documents(ROOT/'knowledge/documents/policies.json')

    def test_effective_version_wins_and_is_cited(self):
        result=answer('高风险需要多久升级？',self.documents)
        self.assertEqual('ANSWER',result['decision'])
        self.assertEqual('2.0',result['citations'][0]['version'])
        self.assertIn('1.0',result['version_notice'])

    def test_unknown_business_fact_is_refused(self):
        result=answer('公司今年真实营收是多少？',self.documents)
        self.assertEqual('REFUSE',result['decision'])
        self.assertEqual([],result['citations'])

    def test_fixed_evaluation_passes(self):
        cases=json.loads((ROOT/'data/evaluation/phase4_questions.json').read_text(encoding='utf-8'))
        result=evaluate(self.documents,cases)
        self.assertTrue(result['passed'],result['results'])
        self.assertEqual(1.0,result['retrieval_hit_rate'])
        self.assertEqual(1.0,result['citation_accuracy'])
        self.assertEqual(1.0,result['refusal_accuracy'])

if __name__=='__main__': unittest.main(verbosity=2)
