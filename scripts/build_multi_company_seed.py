"""Build the deterministic simulated multi-company seed. No real company data is used."""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"data"/"demo"/"nebula_company_seed.json"
COMPANIES=[
 ("nebula-digital","星云数科（模拟）","企业软件与数字化服务","200–499人","华东","B2B SaaS","成长期","稳健",["产品中心","研发中心","交付中心","客户成功部","数据与安全部"]),
 ("seaway-commerce","海路跨境（模拟）","跨境电商","50–199人","华南","多平台零售","成长期","平衡",["商品运营部","供应链部","广告增长部","客户服务部","财务合规部"]),
 ("forge-manufacturing","铸新制造（模拟）","智能制造","500–999人","华中","订单制造","成熟期","保守",["生产计划部","设备工程部","质量管理部","采购部","信息化部"]),
 ("swift-logistics","迅达物流（模拟）","物流与仓储","200–499人","华东","合同物流","扩张期","平衡",["运输运营部","仓储运营部","网络规划部","客户方案部","安全质量部"]),
 ("bright-marketing","明途营销（模拟）","营销服务","50–199人","华北","项目制服务","成长期","进取",["策略部","创意部","媒介部","客户部","数据分析部"]),
 ("care-healthtech","康桥科技（模拟）","医疗信息化","200–499人","西南","B2B 项目交付","成熟期","保守",["产品部","实施交付部","研发部","信息安全部","质量保证部"]),
]
PROJECTS=[
 ("核心系统升级","系统升级","方案设计"),("主数据治理","数据治理","数据清洗"),("供应商切换","供应商管理","切换演练"),("重点客户交付","客户交付","客户验收"),("运营流程优化","流程优化","试运行")]
TASKS=[("确认范围与验收口径","已完成",100,"高"),("冻结数据和接口清单","进行中",70,"高"),("完成跨部门评审","阻塞",45,"高"),("执行集成验证","未开始",0,"高"),("准备回滚与应急方案","未开始",0,"中"),("取得业务书面验收","未开始",0,"高")]
POLICIES=[
 ("risk-level","项目风险分级与升级标准",["风险","升级"],"高风险应在一个工作日内由项目负责人核对证据、影响和责任角色；中风险每三个工作日复核。"),
 ("change-control","需求变更控制办法",["变更","范围"],"变更进入执行前应记录提出方、业务理由、范围、验收条件、测试影响和排期影响。"),
 ("data-security","数据最小化处理规范",["数据","安全"],"导入资料前应移除无关个人信息与凭证；模拟数据不得冒充真实客户资料。"),
 ("release-approval","发布与切换审批清单",["发布","回滚"],"切换前必须核对测试结论、未关闭高优问题、监控指标、回滚方案和值班角色。"),
 ("supplier-management","关键供应商管理规范",["供应商","SLA"],"关键供应商交付前应取得容量证据、故障联系人、服务承诺和替代路径。"),
 ("customer-acceptance","客户验收证据要求",["客户","验收"],"验收应对应确认范围，保存测试记录、问题清单和书面结论；未确认不得标记完成。"),
 ("ai-usage","AI 助手使用边界",["AI","人工确认"],"AI 输出只作为草稿，不得自动改变负责人、期限、风险状态或创建正式行动。"),
 ("case-review","历史案例：依赖未闭环",["案例","依赖"],"模拟案例中上游评审阻塞导致验证推迟；团队核对缺口、拆分可并行任务并记录复核日期。"),
]

def build_project(company_index,project_index,department):
    title,ptype,stage=PROJECTS[project_index]; prefix=f"C{company_index+1}P{project_index+1}"; start=date(2026,7,1)+timedelta(days=project_index*7)
    tasks=[]
    for i,(name,status,progress,priority) in enumerate(TASKS):
        task_start=start+timedelta(days=i*6); task_id=f"{prefix}T{i+1}"
        tasks.append({"task_id":task_id,"task_name":name,"owner":f"模拟角色{company_index+1}-{i+1}","start_date":task_start.isoformat(),"due_date":(task_start+timedelta(days=5)).isoformat(),"status":status,"priority":priority,"dependency_ids":[] if i==0 else [f"{prefix}T{i}"],"progress_percent":progress,"effort_hours":16+i*4})
    return {"project_id":f"PRJ-{prefix}","project_name":title,"project_type":ptype,"department":department,"stage":stage,"start_date":start.isoformat(),"end_date":(start+timedelta(days=55)).isoformat(),"background":f"用于比较不同公司画像下的{ptype}风险信号，全部内容均为确定性生成的模拟数据。","outcome":"当前仍在执行；包含延期依赖、阻塞评审和待确认验收等可核查模拟状态。","tasks":tasks}

def main():
    companies=[]
    for ci,(cid,name,industry,size,region,model,lifecycle,appetite,departments) in enumerate(COMPANIES):
        projects=[build_project(ci,pi,departments[pi%len(departments)]) for pi in range(len(PROJECTS))]
        policies=[{"document_id":f"{cid}-{pid}","title":title,"version":"1.0","effective_date":"2026-06-01","status":"effective","tags":tags+[industry],"content":f"适用画像：{industry}、{size}、{model}。{content}"} for pid,title,tags,content in POLICIES]
        companies.append({"company_id":cid,"name":name,"industry":industry,"size_band":size,"region":region,"business_model":model,"lifecycle_stage":lifecycle,"risk_appetite":appetite,"description":"SaaSGuide 多公司对照使用的虚构画像，不对应任何真实企业、人员或经营结果。","simulated":True,"departments":departments,"projects":projects,"policies":policies})
    OUTPUT.write_text(json.dumps({"schema_version":"2.0-multi-company","active_company_id":companies[0]["company_id"],"companies":companies},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"companies":len(companies),"projects":sum(len(c["projects"]) for c in companies),"tasks":sum(len(p["tasks"]) for c in companies for p in c["projects"]),"policies":sum(len(c["policies"]) for c in companies)},ensure_ascii=False))
if __name__=="__main__": main()
