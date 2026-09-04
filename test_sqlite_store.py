import tempfile, unittest
from pathlib import Path
from database.store import StoreError, create_action, dashboard, schema_inventory, seed_demo, transition_action

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'demo.db'; seed_demo(self.db)
        self.payload={'candidate_id':'candidate-interface','title':'重新组织接口评审','owner_role':'技术负责人','due_date':'2026-09-08','completion_signal':'评审记录为通过','actor':'测试用户','human_confirmed':True}
    def test_schema_contains_audit_entities(self):
        names=schema_inventory(self.db)
        for name in ('projects','documents','risk_candidates','risk_evidence','human_decisions','action_items','action_events','ai_runs','error_logs'):
            self.assertIn(name,names)
    def test_action_requires_human_confirmation(self):
        with self.assertRaises(StoreError): create_action(self.db,{**self.payload,'human_confirmed':False})
    def test_action_lifecycle_keeps_events(self):
        action=create_action(self.db,self.payload)
        self.assertEqual('open',action['status'])
        action=transition_action(self.db,action['action_id'],'in_progress','测试用户','开始处理')
        action=transition_action(self.db,action['action_id'],'completed','测试用户','评审通过')
        self.assertEqual('completed',action['status']); self.assertEqual(3,len(action['events']))
    def test_dashboard_marks_overdue(self):
        create_action(self.db,self.payload)
        result=dashboard(self.db,'2026-09-09')
        self.assertEqual(1,result['summary']['overdue'])

if __name__=='__main__': unittest.main(verbosity=2)
