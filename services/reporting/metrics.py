from __future__ import annotations
import csv, io, json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from openpyxl import Workbook

def load_dataset(path: Path) -> dict[str, Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data.get('risks'),list) or not isinstance(data.get('actions'),list): raise ValueError('报告数据结构无效')
    return data

def calculate(data: dict[str,Any], as_of: str='2026-09-07')->dict[str,Any]:
    risks=data['risks']; actions=data['actions']; today=date.fromisoformat(as_of)
    closed=[r for r in risks if r['status'] in {'confirmed','dismissed'} and r.get('resolution_hours') is not None]
    levels=Counter(r['level'] for r in risks); statuses=Counter(r['status'] for r in risks)
    overdue=sum(a['status']!='completed' and date.fromisoformat(a['due_date'])<today for a in actions)
    false_positive=sum(bool(r.get('false_positive')) for r in risks)
    trend=[]
    for day in sorted({r['date'] for r in risks}): trend.append({'date':day,'new_risks':sum(r['date']==day for r in risks)})
    metrics={'risk_total':len(risks),'high_risk':levels['high'],'confirmed':statuses['confirmed'],'false_positive_count':false_positive,'false_positive_rate':false_positive/len(risks) if risks else 0,'overdue_actions':overdue,'average_resolution_hours':sum(r['resolution_hours'] for r in closed)/len(closed) if closed else None}
    prefix = "本周基于当前本地记录，" if data.get("scope") == "runtime_local_records" else "本周固定模拟数据"
    draft=f"{prefix}新增 {metrics['risk_total']} 条候选，其中高风险 {metrics['high_risk']} 条、已确认 {metrics['confirmed']} 条。当前逾期行动 {overdue} 条。误报率为 {metrics['false_positive_rate']:.1%}，只反映本地模拟或人工保存记录。"
    return {'period':data['period'],'as_of':as_of,'metrics':metrics,'level_distribution':dict(levels),'status_distribution':dict(statuses),'trend':trend,'actions':actions,'report_draft':draft,'generation':'python_deterministic_no_llm'}

def csv_bytes(result: dict[str,Any])->bytes:
    output=io.StringIO(newline=''); writer=csv.writer(output); writer.writerow(['指标','值'])
    labels={'risk_total':'候选风险数','high_risk':'高风险数','confirmed':'已确认数','false_positive_count':'误报数','false_positive_rate':'误报率','overdue_actions':'逾期行动数','average_resolution_hours':'平均处理小时'}
    for key,value in result['metrics'].items(): writer.writerow([labels[key],value])
    return ('\ufeff'+output.getvalue()).encode('utf-8')

def xlsx_bytes(result: dict[str,Any])->bytes:
    workbook=Workbook(); summary=workbook.active; summary.title='指标'
    summary.append(['指标','值'])
    labels={'risk_total':'候选风险数','high_risk':'高风险数','confirmed':'已确认数','false_positive_count':'误报数','false_positive_rate':'误报率','overdue_actions':'逾期行动数','average_resolution_hours':'平均处理小时'}
    for key,value in result['metrics'].items(): summary.append([labels[key],value])
    actions=workbook.create_sheet('行动'); actions.append(['行动','角色','截止日期','状态'])
    for item in result['actions']: actions.append([item['title'],item['owner_role'],item['due_date'],item['status']])
    output=io.BytesIO(); workbook.save(output); return output.getvalue()
