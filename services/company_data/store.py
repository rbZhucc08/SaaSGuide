"""Migration-safe local store for editable simulated multi-company data."""
from __future__ import annotations
import json, re, threading
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

class CompanyDataError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message); self.code=code; self.status=status

_LOCK=threading.Lock(); _ID=re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
def _now(): return datetime.now().astimezone().isoformat(timespec="seconds")
def _text(v,label,maximum,required=True):
    if not isinstance(v,str): raise CompanyDataError("invalid_field",f"{label}必须是文字")
    v=v.strip()
    if required and not v: raise CompanyDataError("missing_field",f"{label}不能为空")
    if len(v)>maximum: raise CompanyDataError("field_too_long",f"{label}不能超过 {maximum} 字")
    return v
def _identifier(v,label):
    v=_text(v,label,80)
    if not _ID.fullmatch(v): raise CompanyDataError("invalid_identifier",f"{label}只能包含字母、数字、点、下划线或连字符")
    return v
def _date(v,label):
    v=_text(v,label,10)
    try: date.fromisoformat(v)
    except ValueError as e: raise CompanyDataError("invalid_date",f"{label}必须是 YYYY-MM-DD") from e
    return v

def validate_task(v:Any,index:int):
    if not isinstance(v,dict): raise CompanyDataError("invalid_task",f"第 {index} 条任务必须是对象")
    progress=v.get("progress_percent"); deps=v.get("dependency_ids",[])
    if isinstance(progress,bool) or not isinstance(progress,(int,float)) or not 0<=progress<=100: raise CompanyDataError("invalid_progress",f"第 {index} 条任务完成度必须是 0 到 100")
    if not isinstance(deps,list) or any(not isinstance(x,str) for x in deps): raise CompanyDataError("invalid_dependencies",f"第 {index} 条任务的前置任务必须是编号列表")
    r={"task_id":_identifier(v.get("task_id"),f"第 {index} 条任务编号"),"task_name":_text(v.get("task_name"),f"第 {index} 条任务名称",120),"owner":_text(v.get("owner"),f"第 {index} 条任务负责人",60),"start_date":_date(v.get("start_date"),f"第 {index} 条任务开始日期"),"due_date":_date(v.get("due_date"),f"第 {index} 条任务截止日期"),"status":_text(v.get("status"),f"第 {index} 条任务状态",30),"priority":_text(v.get("priority"),f"第 {index} 条任务优先级",20),"dependency_ids":[_identifier(x,f"第 {index} 条任务前置编号") for x in deps],"progress_percent":int(progress),"effort_hours":int(v.get("effort_hours",0) or 0)}
    if r["start_date"]>r["due_date"]: raise CompanyDataError("invalid_date_order",f"第 {index} 条任务截止日期不能早于开始日期")
    if not 0<=r["effort_hours"]<=10000: raise CompanyDataError("invalid_effort",f"第 {index} 条任务工时无效")
    return r

def validate_project(v:Any):
    if not isinstance(v,dict): raise CompanyDataError("invalid_project","项目必须是对象")
    r={"project_id":_identifier(v.get("project_id"),"项目编号"),"project_name":_text(v.get("project_name"),"项目名称",120),"project_type":_text(v.get("project_type","其他"),"项目类型",50),"department":_text(v.get("department"),"所属部门",60),"stage":_text(v.get("stage"),"项目阶段",40),"start_date":_date(v.get("start_date"),"项目开始日期"),"end_date":_date(v.get("end_date"),"项目结束日期"),"background":_text(v.get("background",""),"项目背景",1000,False),"outcome":_text(v.get("outcome",""),"项目经历或结果",1000,False)}
    if r["start_date"]>r["end_date"]: raise CompanyDataError("invalid_project_dates","项目结束日期不能早于开始日期")
    tasks=v.get("tasks")
    if not isinstance(tasks,list) or len(tasks)>500: raise CompanyDataError("invalid_tasks","项目任务必须是最多 500 条的列表")
    r["tasks"]=[validate_task(x,i) for i,x in enumerate(tasks,1)]; ids=[x["task_id"] for x in r["tasks"]]
    if len(ids)!=len(set(ids)): raise CompanyDataError("duplicate_task_id","同一项目内任务编号不能重复")
    known=set(ids)
    if any(x["task_id"] in x["dependency_ids"] or any(d not in known for d in x["dependency_ids"]) for x in r["tasks"]): raise CompanyDataError("invalid_dependency_reference","任务包含无效前置任务")
    return r

def validate_policy(v:Any):
    if not isinstance(v,dict): raise CompanyDataError("invalid_policy","制度必须是对象")
    status=_text(v.get("status"),"制度状态",20); tags=v.get("tags",[])
    if status not in {"effective","superseded","draft","retired"}: raise CompanyDataError("invalid_policy_status","制度状态无效")
    if not isinstance(tags,list) or len(tags)>12: raise CompanyDataError("invalid_policy_tags","制度标签必须是最多 12 项的列表")
    return {"document_id":_identifier(v.get("document_id"),"制度编号"),"title":_text(v.get("title"),"制度名称",120),"version":_identifier(v.get("version"),"制度版本"),"effective_date":_date(v.get("effective_date"),"生效日期"),"status":status,"tags":[_text(x,"制度标签",30) for x in tags],"content":_text(v.get("content"),"制度正文",5000)}

_PROFILE=("company_id","name","industry","size_band","region","business_model","lifecycle_stage","risk_appetite","description","simulated")
def validate_company(v:Any):
    if not isinstance(v,dict): raise CompanyDataError("invalid_company","公司资料必须是对象")
    ds=v.get("departments",[]); ps=v.get("projects",[]); ks=v.get("policies",[])
    if not isinstance(ds,list) or len(ds)>100: raise CompanyDataError("invalid_departments","部门必须是最多 100 项的列表")
    if not isinstance(ps,list) or len(ps)>200: raise CompanyDataError("invalid_projects","单家公司项目必须是最多 200 项的列表")
    if not isinstance(ks,list) or len(ks)>500: raise CompanyDataError("invalid_policies","单家公司制度必须是最多 500 项的列表")
    r={"company_id":_identifier(v.get("company_id"),"公司编号"),"name":_text(v.get("name"),"公司名称",120),"industry":_text(v.get("industry","其他"),"公司行业",120),"size_band":_text(v.get("size_band","未标注"),"公司规模",40),"region":_text(v.get("region","未标注"),"所在区域",80),"business_model":_text(v.get("business_model","未标注"),"业务模式",80),"lifecycle_stage":_text(v.get("lifecycle_stage","未标注"),"发展阶段",40),"risk_appetite":_text(v.get("risk_appetite","稳健"),"风险偏好",40),"description":_text(v.get("description",""),"公司说明",500,False),"simulated":True,"departments":[_text(x,"部门名称",60) for x in ds],"projects":[validate_project(x) for x in ps],"policies":[validate_policy(x) for x in ks]}
    pids=[x["project_id"] for x in r["projects"]]; kids=[(x["document_id"],x["version"]) for x in r["policies"]]
    if len(pids)!=len(set(pids)): raise CompanyDataError("duplicate_project_id","同一公司内项目编号不能重复")
    if len(kids)!=len(set(kids)): raise CompanyDataError("duplicate_policy_version","同一公司内制度版本不能重复")
    return r

def validate_data(v:Any):
    if not isinstance(v,dict): raise CompanyDataError("invalid_company_data","公司数据必须是对象")
    if "companies" in v: raw=v.get("companies"); active=str(v.get("active_company_id",""))
    else:
        old=v.get("company") or {}; raw=[{**old,"departments":v.get("departments",[]),"projects":v.get("projects",[]),"policies":v.get("policies",[])}]; active=str(old.get("company_id","nebula-digital"))
    if not isinstance(raw,list) or not raw or len(raw)>100: raise CompanyDataError("invalid_companies","公司列表必须包含 1 到 100 家公司")
    companies=[validate_company(x) for x in raw]; ids=[x["company_id"] for x in companies]
    if len(ids)!=len(set(ids)): raise CompanyDataError("duplicate_company_id","公司编号不能重复")
    return {"schema_version":"2.0-multi-company","initialized_at":str(v.get("initialized_at") or _now()),"updated_at":str(v.get("updated_at") or _now()),"active_company_id":active if active in ids else ids[0],"companies":companies}

def _summary(d):
    projects=[p for c in d["companies"] for p in c["projects"]]
    return {"companies":len(d["companies"]),"industries":len({c["industry"] for c in d["companies"]}),"business_models":len({c["business_model"] for c in d["companies"]}),"projects":len(projects),"tasks":sum(len(p["tasks"]) for p in projects),"policy_versions":sum(len(c["policies"]) for c in d["companies"])}
def _view(d):
    active=next(c for c in d["companies"] if c["company_id"]==d["active_company_id"]); profiles=[]
    for c in d["companies"]:
        x={k:c[k] for k in _PROFILE}; x.update(projects=len(c["projects"]),tasks=sum(len(p["tasks"]) for p in c["projects"]),policy_versions=len(c["policies"])); profiles.append(x)
    return {"schema_version":d["schema_version"],"initialized_at":d["initialized_at"],"updated_at":d["updated_at"],"active_company_id":d["active_company_id"],"companies":profiles,"dataset_summary":_summary(d),"company":{k:active[k] for k in _PROFILE},"departments":deepcopy(active["departments"]),"projects":deepcopy(active["projects"]),"policies":deepcopy(active["policies"])}
def _write(path,d):
    path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_suffix(path.suffix+".tmp"); temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); temp.replace(path)
def _load(runtime,seed):
    source=runtime if runtime.exists() else seed; raw=json.loads(source.read_text(encoding="utf-8")); d=validate_data(raw)
    changed=False
    # On first V1 -> V2 migration keep the user's existing company and append
    # only missing simulated comparison companies from the new seed.
    if source==runtime and "companies" not in raw:
        seed_data=validate_data(json.loads(seed.read_text(encoding="utf-8"))); known={c["company_id"] for c in d["companies"]}
        d["companies"].extend(deepcopy(c) for c in seed_data["companies"] if c["company_id"] not in known)
        changed=True
    # Enrich only fields introduced by V2; never replace user projects/policies.
    if source==runtime:
        seed_data=validate_data(json.loads(seed.read_text(encoding="utf-8"))); seed_by_id={c["company_id"]:c for c in seed_data["companies"]}
        for company in d["companies"]:
            template=seed_by_id.get(company["company_id"],{})
            for key in ("size_band","region","business_model","lifecycle_stage"):
                if company.get(key)=="未标注" and template.get(key) not in {None,"未标注"}: company[key]=template[key]; changed=True
    if source==seed or raw.get("schema_version")!=d["schema_version"] or changed: _write(runtime,d)
    return d
def read(runtime,seed):
    with _LOCK: return _view(_load(runtime,seed))
initialize=read
def reset(runtime,seed):
    with _LOCK:
        d=validate_data(json.loads(seed.read_text(encoding="utf-8"))); d["initialized_at"]=d["updated_at"]=_now(); _write(runtime,d); return _view(d)
def _active(d,company_id=None):
    c=next((x for x in d["companies"] if x["company_id"]==(company_id or d["active_company_id"])),None)
    if c is None: raise CompanyDataError("company_not_found","所选公司不存在",404)
    return c
def clear(runtime,seed):
    with _LOCK:
        d=_load(runtime,seed); c=_active(d); c["projects"]=[]; c["policies"]=[]; d["updated_at"]=_now(); _write(runtime,d); return _view(d)
def create_company(runtime,seed,v):
    c=validate_company(v)
    with _LOCK:
        d=_load(runtime,seed)
        if any(x["company_id"]==c["company_id"] for x in d["companies"]): raise CompanyDataError("record_conflict","相同公司编号已存在",409)
        d["companies"].append(c); d["active_company_id"]=c["company_id"]; d["updated_at"]=_now(); _write(runtime,d)
    return deepcopy(c)
def update_company(runtime,seed,company_id,v):
    c=validate_company(v)
    if c["company_id"]!=company_id: raise CompanyDataError("immutable_identifier","公司编号不能在编辑时改变")
    with _LOCK:
        d=_load(runtime,seed); old=_active(d,company_id); d["companies"][d["companies"].index(old)]=c; d["updated_at"]=_now(); _write(runtime,d)
    return deepcopy(c)
def delete_company(runtime,seed,company_id):
    with _LOCK:
        d=_load(runtime,seed); c=_active(d,company_id)
        if len(d["companies"])==1: raise CompanyDataError("last_company","至少保留一家公司",409)
        d["companies"].remove(c)
        if d["active_company_id"]==company_id: d["active_company_id"]=d["companies"][0]["company_id"]
        d["updated_at"]=_now(); _write(runtime,d)
    return {"deleted":True}
def set_active_company(runtime,seed,company_id):
    with _LOCK:
        d=_load(runtime,seed); _active(d,company_id); d["active_company_id"]=company_id; d["updated_at"]=_now(); _write(runtime,d); return _view(d)
def _mutate(runtime,seed,collection,v,identity,operation):
    with _LOCK:
        d=_load(runtime,seed); items=_active(d)[collection]; keys=tuple(str(v.get(k,"")) for k in identity); i=next((i for i,x in enumerate(items) if tuple(str(x.get(k,"")) for k in identity)==keys),None)
        if operation=="create":
            if i is not None: raise CompanyDataError("record_conflict","相同编号或版本的数据已存在",409)
            items.append(v)
        elif i is None: raise CompanyDataError("record_not_found","要修改的数据不存在",404)
        elif operation=="update": items[i]=v
        else: items.pop(i)
        validate_data(d); d["updated_at"]=_now(); _write(runtime,d)
    return deepcopy(v) if operation!="delete" else {"deleted":True}
def create_project(runtime,seed,v): return _mutate(runtime,seed,"projects",validate_project(v),("project_id",),"create")
def update_project(runtime,seed,project_id,v):
    p=validate_project(v)
    if p["project_id"]!=project_id: raise CompanyDataError("immutable_identifier","项目编号不能在编辑时改变")
    return _mutate(runtime,seed,"projects",p,("project_id",),"update")
def delete_project(runtime,seed,project_id): return _mutate(runtime,seed,"projects",{"project_id":project_id},("project_id",),"delete")
def create_policy(runtime,seed,v): return _mutate(runtime,seed,"policies",validate_policy(v),("document_id","version"),"create")
def update_policy(runtime,seed,document_id,version,v):
    p=validate_policy(v)
    if (p["document_id"],p["version"])!=(document_id,version): raise CompanyDataError("immutable_identifier","制度编号和版本不能在编辑时改变")
    return _mutate(runtime,seed,"policies",p,("document_id","version"),"update")
def delete_policy(runtime,seed,document_id,version): return _mutate(runtime,seed,"policies",{"document_id":document_id,"version":version},("document_id","version"),"delete")
def project_document(data,project_id,as_of=None):
    p=next((x for x in data["projects"] if x["project_id"]==project_id),None)
    if p is None: raise CompanyDataError("project_not_found","所选项目不存在",404)
    stamp=data.get("updated_at") or data.get("initialized_at"); tasks=[{**x,"source_row":i+2} for i,x in enumerate(p["tasks"])]; cid=data["company"]["company_id"]
    return {"schema_version":"2.1-company-project","as_of":as_of or date.today().isoformat(),"source":{"source_id":f"company-{cid}-{project_id}","source_type":"editable_json","source_name":f"{data['company']['name']} · 当前项目档案","source_version":str(stamp),"sha256":"local-editable-data","imported_at":stamp},"company":deepcopy(data["company"]),"project":{"project_id":p["project_id"],"project_name":p["project_name"],"project_type":p["project_type"]},"tasks":tasks,"dependencies":[],"updates":[],"summary":{"task_count":len(tasks),"dependency_count":sum(len(x["dependency_ids"]) for x in tasks),"update_count":0,"error_count":0}}
def new_id(prefix): return f"{prefix}-{uuid4().hex[:10]}"
