import json
import tempfile
import unittest
from pathlib import Path

from server import create_app
from services.company_data.store import CompanyDataError, clear, create_policy, create_project, delete_policy, delete_project, project_document, read, reset, update_policy, update_project


ROOT = Path(__file__).resolve().parent
SEED = ROOT / "data" / "demo" / "nebula_company_seed.json"


class CompanyDataStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.runtime = Path(self.temporary.name) / "company-data.json"

    def test_initializes_once_and_clear_persists(self):
        first = read(self.runtime, SEED); self.assertEqual(5, len(first["projects"]))
        clear(self.runtime, SEED); second = read(self.runtime, SEED)
        self.assertEqual([], second["projects"]); self.assertEqual([], second["policies"])

    def test_reset_is_explicit_and_restores_rich_seed(self):
        clear(self.runtime, SEED); data = reset(self.runtime, SEED)
        self.assertEqual(5, len(data["projects"])); self.assertGreaterEqual(len(data["policies"]), 15)
        self.assertEqual(25, sum(len(item["tasks"]) for item in data["projects"]))

    def test_project_crud_and_scan_document(self):
        base = read(self.runtime, SEED)["projects"][0]; value = {**base, "project_id": "PRJ-NEW", "project_name": "新增项目"}
        create_project(self.runtime, SEED, value); value["stage"] = "验收"; update_project(self.runtime, SEED, "PRJ-NEW", value)
        document = project_document(read(self.runtime, SEED), "PRJ-NEW", "2026-09-07")
        self.assertEqual("验收", next(item for item in read(self.runtime, SEED)["projects"] if item["project_id"] == "PRJ-NEW")["stage"])
        self.assertEqual("editable_json", document["source"]["source_type"])
        delete_project(self.runtime, SEED, "PRJ-NEW")

    def test_duplicate_task_id_is_rejected(self):
        value = read(self.runtime, SEED)["projects"][0]; value["project_id"] = "PRJ-DUP"; value["tasks"][1]["task_id"] = value["tasks"][0]["task_id"]
        with self.assertRaises(CompanyDataError): create_project(self.runtime, SEED, value)

    def test_policy_crud_and_version_conflict(self):
        value={"document_id":"new-policy","title":"新制度","version":"1.0","effective_date":"2026-09-07","status":"effective","tags":["测试"],"content":"这是一条可编辑的模拟制度。"}
        create_policy(self.runtime, SEED, value)
        with self.assertRaises(CompanyDataError): create_policy(self.runtime, SEED, value)
        value["content"]="更新后的模拟制度。"; update_policy(self.runtime, SEED, "new-policy", "1.0", value); delete_policy(self.runtime, SEED, "new-policy", "1.0")


class CompanyDataApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        root=Path(self.temporary.name); app=create_app(output_dir=root/"generated",database_path=root/"actions.db",risk_decision_file=root/"risk.jsonl",company_data_file=root/"company.json",company_seed_file=SEED)
        app.config["TESTING"]=True; self.client=app.test_client(); self.root=root

    def test_company_api_clear_does_not_auto_restore(self):
        self.assertEqual(5,len(self.client.get("/api/company-data").get_json()["projects"]))
        self.assertEqual(400,self.client.post("/api/company-data/clear",json={}).status_code)
        self.client.post("/api/company-data/clear",json={"confirmed":True})
        self.assertEqual([],self.client.get("/api/company-data").get_json()["projects"])

    def test_selected_project_scan_uses_editable_store(self):
        response=self.client.post("/api/company-data/projects/PRJ-CRM-026/scan",json={"as_of":"2026-09-07"})
        self.assertEqual(200,response.status_code); data=response.get_json(); self.assertEqual("editable_company_project",data["source_mode"]); self.assertFalse(data["sample_mode"])

    def test_knowledge_answer_uses_runtime_policies(self):
        self.client.post("/api/company-data/clear",json={"confirmed":True})
        response=self.client.post("/api/knowledge/answer",json={"question":"高风险升级"})
        self.assertEqual(200,response.status_code); self.assertEqual("REFUSE",response.get_json()["decision"])

    def test_reports_use_runtime_records_and_actions_do_not_seed(self):
        actions=self.client.get("/api/actions").get_json(); self.assertEqual(0,actions["summary"]["total"])
        report=self.client.get("/api/reports/weekly").get_json(); self.assertEqual(0,report["metrics"]["risk_total"]); self.assertIn("当前本地记录",report["report_draft"])
        xlsx=self.client.get("/downloads/weekly-risk-report.xlsx"); self.assertEqual(200,xlsx.status_code); self.assertTrue(xlsx.data.startswith(b"PK"))

    def test_rejected_action_does_not_register_candidate(self):
        response=self.client.post("/api/actions",json={"candidate_id":"candidate-no-confirm","title":"不应保存","owner_role":"项目负责人","due_date":"2026-09-10","completion_signal":"完成","actor":"测试","human_confirmed":False})
        self.assertEqual(400,response.status_code)
        self.assertEqual(0,self.client.get("/api/actions").get_json()["summary"]["total"])


if __name__ == "__main__": unittest.main(verbosity=2)
