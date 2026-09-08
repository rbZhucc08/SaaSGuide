import tempfile, unittest
from pathlib import Path
from database.store import StoreError, create_action, dashboard, migrate, schema_inventory, seed_demo, transition_action

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'demo.db'; seed_demo(self.db)
        self.payload={'candidate_id':'candidate-interface','risk_decision_id':'decision-risk-demo','title':'重新组织接口评审','owner_role':'技术负责人','due_date':'2026-09-08','completion_signal':'评审记录为通过','actor':'测试用户','human_confirmed':True}
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
        action=transition_action(self.db,action['action_id'],'open','测试用户','重新打开')
        action=transition_action(self.db,action['action_id'],'cancelled','测试用户','撤销')
        self.assertEqual('cancelled',action['status']); self.assertEqual(5,len(action['events']))
        with self.assertRaises(StoreError): transition_action(self.db,action['action_id'],'completed','测试用户')
    def test_dashboard_marks_overdue(self):
        create_action(self.db,self.payload)
        result=dashboard(self.db,'2026-09-09')
        self.assertEqual(1,result['summary']['overdue'])
    def test_v1_database_gets_backup_and_v2_columns(self):
        old=Path(self.tmp.name)/'old.db'
        import sqlite3
        connection=sqlite3.connect(old)
        connection.executescript('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL); INSERT INTO schema_migrations VALUES(1,"old"); CREATE TABLE risk_candidates(candidate_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL); CREATE TABLE action_items(action_id TEXT PRIMARY KEY,candidate_id TEXT NOT NULL,title TEXT NOT NULL,owner_role TEXT NOT NULL,due_date TEXT NOT NULL,completion_signal TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);')
        connection.close(); migrate(old)
        self.assertTrue(old.with_suffix('.db.pre-v2.bak').exists())
        connection=sqlite3.connect(old)
        self.assertIn('risk_decision_id',[row[1] for row in connection.execute('PRAGMA table_info(action_items)')])
        connection.close()

if __name__=='__main__': unittest.main(verbosity=2)
