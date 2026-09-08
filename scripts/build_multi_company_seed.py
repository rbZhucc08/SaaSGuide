"""Build a deterministic, domain-differentiated simulated company dataset."""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; OUTPUT=ROOT/"data"/"demo"/"nebula_company_seed.json"; BENCHMARK=ROOT/"data"/"evaluation"/"company_scenario_expected.json"

COMPANIES=[
 {"id":"nebula-digital","name":"星云数科（模拟）","industry":"企业软件与数字化服务","size":"200–499人","region":"华东","model":"订阅制 B2B SaaS","stage":"成长期","appetite":"稳健","departments":["产品中心","平台研发部","客户成功部","交付中心","数据安全部"],"traits":["续费收入敏感","多租户架构","季度版本发布","大客户定制需求"],"standard":(3,5,24,"每周两次","交付平台主管",["客户影响范围","错误率曲线","回滚验证"]),"background":"提供订阅制项目协作软件，收入同时受产品稳定性、续费和大客户实施进度影响。"},
 {"id":"seaway-commerce","name":"海路跨境（模拟）","industry":"跨境电商","size":"50–199人","region":"华南","model":"Amazon/Ozon 多平台零售","stage":"快速扩张期","appetite":"平衡","departments":["商品运营部","供应链部","广告增长部","平台合规部","客户服务部"],"traits":["旺季波动明显","跨境补货周期长","平台规则变化","多币种毛利"],"standard":(2,10,12,"旺季每日", "运营负责人",["可售库存","在途节点","平台通知","贡献毛利"]),"background":"经营家居和户外品类，多平台库存、广告、合规和跨境履约相互影响。"},
 {"id":"forge-manufacturing","name":"铸新制造（模拟）","industry":"智能制造","size":"500–999人","region":"华中","model":"按订单生产 MTO","stage":"数字化转型期","appetite":"保守","departments":["生产计划部","设备工程部","质量管理部","采购部","信息化部"],"traits":["关键设备单点依赖","批次质量追溯","原料交期波动","停线成本高"],"standard":(1,7,4,"每日班前会","生产总监",["设备报警记录","批次检验报告","产能缺口","替代物料批准"]),"background":"按客户订单组织生产，设备、原料、质量和排产异常会直接影响交期。"},
 {"id":"swift-logistics","name":"迅达物流（模拟）","industry":"物流与仓储","size":"200–499人","region":"华东","model":"合同物流与区域配送","stage":"网络扩张期","appetite":"平衡","departments":["运输运营部","仓储运营部","网络规划部","客户方案部","安全质量部"],"traits":["时效 SLA","仓容峰谷","承运商协同","天气与线路扰动"],"standard":(1,3,6,"每日早晚两次","区域运营经理",["轨迹节点","仓容利用率","承运商回执","客户SLA"]),"background":"为零售客户提供仓配服务，核心约束是仓容、干线、末端时效和货物安全。"},
 {"id":"bright-marketing","name":"明途营销（模拟）","industry":"营销服务","size":"50–199人","region":"华北","model":"项目制整合营销","stage":"成长期","appetite":"进取","departments":["策略部","创意部","媒介部","客户部","数据分析部"],"traits":["客户审批链长","热点窗口短","媒体预算波动","归因口径争议"],"standard":(4,5,48,"每周三次","客户合伙人",["客户书面确认","媒介排期","预算消耗","归因口径"]),"background":"同时管理品牌和效果项目，范围变更、素材审批、投放窗口和数据归因是主要风险源。"},
 {"id":"care-healthtech","name":"康桥科技（模拟）","industry":"医疗信息化","size":"200–499人","region":"西南","model":"医院项目交付与运维","stage":"成熟期","appetite":"保守","departments":["产品部","实施交付部","研发部","信息安全部","质量保证部"],"traits":["敏感数据","院内多系统接口","严格变更窗口","验收材料密集"],"standard":(1,7,2,"每日", "质量与安全负责人",["脱敏证明","接口测试报告","变更审批单","应急回退记录"]),"background":"交付院内业务系统，隐私、安全、接口兼容和上线审批优先于交付速度。"},
]

SCENARIOS={
"nebula-digital":[
 ("企业客户单点登录上线","客户实施","联调","交付中心","blocked","确认身份源与租户边界|完成 SAML 元数据交换|配置测试租户|执行权限回归|组织客户安全评审|取得上线窗口确认"),
 ("季度版本灰度发布","版本发布","灰度","平台研发部","due","冻结版本范围|关闭阻断缺陷|完成容量压测|验证数据库回滚|执行百分之十灰度|复核核心错误率"),
 ("续费流失预警看板","数据产品","试运行","客户成功部","healthy","统一续费口径|清理合同主数据|设计流失特征|校验历史样本|发布客户分层看板|完成使用培训"),
 ("开放 API 限流升级","平台治理","方案评审","平台研发部","mixed","统计租户调用峰值|确定分级限流策略|完成 SDK 兼容评估|通知重点集成客户|部署灰度网关|监控拒绝率与延迟"),
 ("客户数据删除能力","隐私合规","验收","数据安全部","ambiguous","盘点个人数据位置|确认删除与保留规则|开发异步删除任务|验证备份处理边界|完成审计日志检查|准备客户操作说明"),
],
"seaway-commerce":[
 ("旺季海外仓补货","库存运营","在途补货","供应链部","mixed","汇总渠道销量预测|计算安全库存与覆盖天数|确认供应商可交数量|锁定海运舱位|提交清关资料|跟踪海外仓预约入库"),
 ("Ozon 商品卡合规整改","平台合规","批量复核","平台合规部","blocked","导出违规商品清单|核对标题与属性规则|复查图片和认证材料|完成俄文信息修订|提交平台复审|监控下架与恢复状态"),
 ("Amazon 广告预算重分配","广告优化","观察期","广告增长部","healthy","统一广告归因窗口|分解品牌与非品牌词|识别高花费低转化组|调整活动预算上限|保留实验对照组|复核 ACOS 与贡献毛利"),
 ("高退货 SKU 治理","商品运营","原因核查","商品运营部","due","按原因拆解退货记录|抽检尺码与包装问题|比对详情页承诺|联系供应商确认批次|更新客服问题标签|验证两周退货趋势"),
 ("多平台库存同步","系统集成","联调","供应链部","ambiguous","梳理平台库存口径|定义预占与释放时点|建立 SKU 映射|模拟超卖并发请求|验证失败补偿队列|完成手工兜底预案"),
],
"forge-manufacturing":[
 ("关键机床预测性维护","设备维护","试运行","设备工程部","blocked","采集主轴振动基线|校准温度传感器|设定异常阈值|安排低峰停机检查|更换高风险轴承|验证复机首件质量"),
 ("原料短缺替代认证","供应保障","材料验证","采购部","mixed","确认缺料订单范围|获取替代材料样本|完成成分与强度检测|评估工艺参数变化|取得客户偏差许可|更新采购与排产计划"),
 ("批次质量追溯整改","质量治理","闭环验证","质量管理部","due","隔离疑似批次|复核首检与巡检记录|追溯设备和操作班组|完成根因试验|实施纠正预防措施|验证连续三批结果"),
 ("MES 工单接口改造","系统升级","联调","信息化部","healthy","冻结工单字段字典|核对 ERP 下发规则|开发异常重传机制|执行班组终端测试|完成历史工单迁移|组织生产切换演练"),
 ("旺季产能平衡","生产计划","滚动排产","生产计划部","ambiguous","汇总确认订单需求|计算瓶颈工序负荷|核对人员班次限制|评估外协可用产能|发布周滚动计划|监控计划达成率"),
],
"swift-logistics":[
 ("华东暴雨线路改道","运输应急","应急执行","运输运营部","blocked","识别受影响干线车辆|核对高速与港区封闭信息|规划替代中转节点|通知承运商调整班次|向客户更新预计到达|复盘额外成本与晚点"),
 ("双十一仓容扩展","仓储能力","容量准备","仓储运营部","mixed","预测每日入出库峰值|盘点可用库位和设备|规划临时外租仓|招聘并培训临时人员|执行峰值压力演练|监控仓容与积压小时"),
 ("冷链承运商准入","供应商准入","资质核验","安全质量部","due","核验运输与保险资质|抽查温控设备校准证书|评估历史断链记录|执行模拟线路测试|确认异常赔付条款|完成准入评审签字"),
 ("重点客户 SLA 看板","客户运营","上线","客户方案部","healthy","确认客户时效定义|接入揽收与签收轨迹|处理异常节点去重|建立超时预警规则|与客户核对样本|发布周度服务报告"),
 ("区域分拨中心选址","网络规划","方案比选","网络规划部","ambiguous","收集订单热力分布|估算干支线运输成本|比较租金与改造投入|评估劳动力供给|模拟旺季网络韧性|提交投资决策材料"),
],
"bright-marketing":[
 ("新品整合传播战役","品牌营销","创意制作","客户部","blocked","确认传播目标与受众|锁定创意主概念|完成主视觉与脚本|取得客户法务审批|排定达人和媒体档期|准备上线舆情预案"),
 ("效果广告归因校准","数据分析","口径验证","数据分析部","ambiguous","盘点各渠道转化事件|统一点击与曝光窗口|检查埋点缺失比例|对齐平台与内部订单|重算历史归因结果|取得客户口径确认"),
 ("直播发布会执行","活动运营","上线准备","创意部","due","冻结直播流程与嘉宾|完成场地网络压测|交付视频与包装素材|执行全流程彩排|配置评论应急机制|汇总直播效果数据"),
 ("年度媒介框架采购","媒介采购","商务谈判","媒介部","healthy","汇总客户投放需求|分析历史媒体效率|发出供应商询价|比较返点与资源包|完成合规比价审批|签署年度框架协议"),
 ("客户临时范围变更","项目管理","影响评估","策略部","mixed","记录新增交付要求|拆分人力与外采成本|识别原排期冲突|提出范围取舍方案|取得费用与日期确认|更新交付基线"),
],
"care-healthtech":[
 ("医院核心接口升级","系统集成","院内联调","实施交付部","blocked","确认 HIS 接口变更清单|搭建脱敏联调环境|执行患者主索引测试|核验医嘱状态映射|完成接口性能测试|取得信息科上线批准"),
 ("患者数据脱敏整改","数据安全","安全验证","信息安全部","mixed","盘点测试环境敏感字段|定义不可逆脱敏规则|替换历史测试数据|检查日志与导出文件|执行再识别风险评估|形成安全验收报告"),
 ("门诊系统版本上线","版本发布","变更窗口","研发部","due","冻结上线功能范围|关闭安全与阻断缺陷|备份配置和数据库|执行院内全流程演练|完成夜间窗口切换|验证挂号收费与退费"),
 ("临床规则库复核","知识治理","专家复核","产品部","ambiguous","汇总规则变更来源|标记冲突与过期规则|邀请临床专家复核|记录适用科室边界|执行历史病例回放|发布审批后规则版本"),
 ("等保整改证据归档","合规审计","材料归档","质量保证部","healthy","整理资产与网络边界|核对账号权限复查|汇总漏洞修复证据|更新应急演练记录|完成第三方测评核对|归档问题闭环清单"),
]}

POLICIES={
"nebula-digital":[("availability","SaaS 可用性事故升级","核心接口五分钟错误率超过 5% 或单租户故障扩散时，由交付平台主管立即升级并保留监控曲线。"),("tenant-data","租户数据隔离标准","跨租户访问迹象按最高风险处理，上线证据必须包含权限回归和审计日志。"),("release","季度版本灰度规范","灰度前关闭阻断缺陷并验证数据库回滚；错误率超过基线两倍立即停止。"),("renewal","续费风险复核规则","续费风险只能结合合同、使用趋势和客户确认，不得仅凭单一活跃度指标。"),("api","开放 API 变更标准","破坏性变更至少提前三十日通知，并提供兼容期和调用方清单。"),("privacy","客户数据删除规范","删除请求应覆盖主库、缓存、导出和备份边界，并保留不可篡改审计记录。")],
"seaway-commerce":[("stock","跨境库存预警标准","旺季覆盖天数低于补货周期加安全缓冲时升级；必须同时核对可售、锁定和在途库存。"),("listing","平台商品合规复核","商品卡整改必须保存平台通知、版本差异、认证材料和复审结果，不得把恢复上架视为永久合规。"),("ads","广告预算异常规则","广告调整同时核对 ACOS、转化率和贡献毛利；单日波动不足以直接停投。"),("logistics","跨境在途升级标准","关键入仓节点超过承诺两日未更新时升级，并核对承运商回执和清关状态。"),("returns","高退货治理要求","退货率判断应按 SKU、批次、国家和原因拆分，样本过少时只能观察。"),("currency","多币种毛利口径","毛利报告应记录汇率日期、平台佣金、物流、广告和退货成本口径。")],
"forge-manufacturing":[("downtime","关键设备停机升级","瓶颈设备预计停机超过四小时按高风险升级，必须记录报警、备件和产能缺口。"),("quality","批次质量隔离标准","关键尺寸或安全指标异常应立即隔离批次，在连续三批验证前不得关闭。"),("material","替代材料批准要求","替代材料需完成检验、工艺评估和客户偏差许可，不得由采购单方放行。"),("capacity","产能冲突复核","排产应核对设备、模具、人员和外协四类约束，不能只比较总工时。"),("mes","MES 切换标准","切换前完成工单重传、终端离线和历史追溯演练，并保留纸质兜底流程。"),("supplier","来料供应风险标准","关键原料交期变化超过一天即复核，缺少替代来源时升级生产总监。")],
"swift-logistics":[("sla","运输时效升级标准","预计晚于客户 SLA 三小时即预警，超过六小时由区域运营经理升级。"),("weather","极端天气应急规则","天气预警需结合实际封路、车辆位置和替代线路，不得只凭天气等级停运。"),("capacity","仓容峰值控制","库位利用率持续超过 90% 或积压超过八小时应启动外溢方案。"),("carrier","承运商准入规范","准入必须核验资质、保险、设备、历史事故和异常赔付条款。"),("cold-chain","冷链断链处理","温度超限应隔离货物、保存连续温控记录并等待质量结论。"),("damage","货损证据标准","货损处理应关联交接照片、包装状态、轨迹节点和责任方回执。")],
"bright-marketing":[("scope","客户范围变更规则","新增交付必须记录费用、排期和原范围取舍；口头要求不得直接进入制作。"),("approval","素材审批标准","涉及品牌、法务或代言人内容必须取得书面批准，未批准不得投放。"),("budget","媒介预算控制","累计消耗偏离计划 10% 时复核，调整需保留客户确认和版本记录。"),("attribution","营销归因口径","归因结论应标明窗口、去重和跨设备限制，不得把相关性表述为因果。"),("event","直播活动应急规范","上线前完成网络、内容、舆情和备用信号演练，明确现场决策人。"),("vendor","内容供应商采购规范","外采内容需确认版权范围、交付格式、修改轮次和使用期限。")],
"care-healthtech":[("privacy","医疗数据最小化规范","测试和日志不得保留可直接识别患者的信息，脱敏证明是上线必备证据。"),("interface","医院接口变更标准","HIS、LIS 等核心接口变更需完成脱敏环境回归、性能验证和院方批准。"),("release","院内变更窗口规范","上线前应完成备份、回退、全流程演练和值守安排，阻断缺陷不得豁免。"),("clinical","临床规则审批规范","规则变更必须记录来源、适用科室、专家复核和生效版本，AI 不得自动发布。"),("security","安全问题升级标准","高危漏洞或越权迹象在两小时内升级质量与安全负责人。"),("evidence","项目验收证据要求","验收材料应包含需求基线、测试报告、安全结论、培训和院方书面确认。")],
}

PATTERNS={
 "healthy":[("已完成",100), ("已完成",100), ("已完成",100), ("进行中",75), ("进行中",60), ("未开始",0)],
 "blocked":[("已完成",100), ("已完成",100), ("阻塞",35), ("未开始",0), ("未开始",0), ("未开始",0)],
 "due":[("已完成",100), ("已完成",100), ("进行中",45), ("进行中",25), ("未开始",0), ("未开始",0)],
 "ambiguous":[("已完成",100), ("进行中",80), ("进行中",60), ("进行中",50), ("未开始",0), ("未开始",0)],
 "mixed":[("已完成",100), ("阻塞",55), ("进行中",40), ("未开始",0), ("进行中",20), ("未开始",0)],
}

def build_project(ci,pi,row):
    name,ptype,stage,department,pattern,step_text=row; steps=step_text.split("|"); start=date(2026,8,1)+timedelta(days=pi*5); states=PATTERNS[pattern]; tasks=[]; prefix=f"C{ci+1}P{pi+1}"
    for i,(step,(status,progress)) in enumerate(zip(steps,states)):
        task_start=start+timedelta(days=i*6); due=task_start+timedelta(days=5)
        deps=[] if i==0 else ([f"{prefix}T{i}"] if i<4 else [f"{prefix}T{i-1}",f"{prefix}T{i}"])
        effort_hours=12+i*5
        # 四个行业的第 5 个项目都保留一条“小工时、临期、低进度”边界任务。
        # 当前确定性规则会提示进度压力，而场景标准答案认为剩余工作量可控，
        # 因而它们是有业务解释的已知负例，可用于观察规则误报。
        if pi==4 and i==3 and ci in {0,1,4,5}:
            progress=40
            effort_hours=18
        tasks.append({"task_id":f"{prefix}T{i+1}","task_name":step,"owner":f"模拟岗位{ci+1}-{i+1}","start_date":task_start.isoformat(),"due_date":due.isoformat(),"status":status,"priority":"高" if i in {1,2,3} else "中","dependency_ids":deps,"progress_percent":progress,"effort_hours":effort_hours})
    return {"project_id":f"PRJ-{prefix}","project_name":name,"project_type":ptype,"department":department,"stage":stage,"start_date":start.isoformat(),"end_date":(start+timedelta(days=65)).isoformat(),"background":f"{name}是该模拟公司特有的{ptype}场景，用于验证行业背景和标准如何影响风险判断。","outcome":"模拟执行中；状态分布用于覆盖健康、阻塞、延期、临期和信息不足场景，不代表真实业务结果。","tasks":tasks}

def main():
    companies=[]
    for ci,spec in enumerate(COMPANIES):
        projects=[build_project(ci,pi,row) for pi,row in enumerate(SCENARIOS[spec["id"]])]
        policies=[{"document_id":f"{spec['id']}-{pid}","title":title,"version":"1.0","effective_date":"2026-06-01","status":"effective","tags":[spec["industry"],pid],"content":content} for pid,title,content in POLICIES[spec["id"]]]
        policies += [{"document_id":f"{spec['id']}-ai-boundary","title":"AI 助手使用边界","version":"1.0","effective_date":"2026-08-25","status":"effective","tags":["AI","人工确认"],"content":"AI 输出仅作草稿；引用必须来自当前公司知识版本，不得自动改变负责人、日期、风险状态或正式行动。"},{"document_id":f"{spec['id']}-record-evidence","title":"事实与证据记录规范","version":"1.0","effective_date":"2026-05-01","status":"effective","tags":["证据","审计"],"content":"记录必须区分事实、推测和待验证事项，保留来源、时间、责任角色和下一次检查日期。"}]
        high,due,blocked,cadence,role,evidence=spec["standard"]
        companies.append({"company_id":spec["id"],"name":spec["name"],"industry":spec["industry"],"size_band":spec["size"],"region":spec["region"],"business_model":spec["model"],"lifecycle_stage":spec["stage"],"risk_appetite":spec["appetite"],"operating_characteristics":spec["traits"],"risk_standard":{"high_overdue_days":high,"due_soon_days":due,"blocked_hours_high":blocked,"review_cadence":cadence,"escalation_role":role,"mandatory_evidence":evidence},"description":spec["background"]+" 全部数据均为虚构。","simulated":True,"departments":spec["departments"],"projects":projects,"policies":policies})
    data={"schema_version":"2.0-multi-company","dataset_revision":"2026-09-08-differentiated-v1","active_company_id":companies[0]["company_id"],"companies":companies}
    OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    as_of=date(2026,9,8); cases=[]
    for company,spec in zip(companies,COMPANIES):
        high=company["risk_standard"]["high_overdue_days"]; due_soon=company["risk_standard"]["due_soon_days"]
        for project,scenario in zip(company["projects"],SCENARIOS[company["company_id"]]):
            pattern=scenario[4]; positives=[]; negatives=[]; severities={}; task_by_id={t["task_id"]:t for t in project["tasks"]}
            for task in project["tasks"]:
                if task["status"] in {"已完成","已取消","完成","取消","done","completed","cancelled","canceled"}: continue
                days=(date.fromisoformat(task["due_date"])-as_of).days; base=f"{project['project_id']}:{task['task_id']}"
                if days<0:
                    key=f"{base}:schedule_delay"; positives.append(key); severities[key]="high" if abs(days)>=high else "medium"
                if task["status"]=="阻塞":
                    key=f"{base}:delivery_blocked"; positives.append(key); severities[key]="high"
                if 0<=days<=due_soon and task["progress_percent"]<50:
                    key=f"{base}:schedule_pressure"
                    if task["effort_hours"]<=20: negatives.append(key)
                    else: positives.append(key); severities[key]="medium"
                blocked_direct=[d for d in task["dependency_ids"] if task_by_id[d]["status"]=="阻塞"]
                if blocked_direct:
                    key=f"{base}:dependency_risk"; positives.append(key); severities[key]="high"
                blocked_indirect=[]
                for dependency in task["dependency_ids"]:
                    blocked_indirect.extend(d for d in task_by_id[dependency]["dependency_ids"] if task_by_id[d]["status"]=="阻塞")
                if blocked_indirect:
                    key=f"{base}:dependency_risk"
                    if key not in positives: positives.append(key); severities[key]="medium"
            cases.append({"company_id":company["company_id"],"company_name":company["name"],"industry":company["industry"],"project_id":project["project_id"],"project_name":project["project_name"],"project_type":project["project_type"],"scenario_pattern":pattern,"expected_ai_decision":"ASK" if pattern=="ambiguous" else "PLAN","positive_candidate_keys":positives,"negative_candidate_keys":negatives,"expected_severity_by_key":severities,"scope_note":"由模拟场景作者依据任务状态、公司阈值和直接/间接依赖编写；不是企业专家标注。"})
    BENCHMARK.write_text(json.dumps({"schema_version":"company-benchmark-v1","as_of":as_of.isoformat(),"dataset_revision":data["dataset_revision"],"cases":cases,"boundaries":{"schedule_pressure_small_effort":"临期但剩余工时不超过20小时标为边界误报","indirect_dependency":"间接依赖阻塞也应提示，但当前规则只检查直接依赖","ambiguous_scenario":"预期 DeepSeek 返回 ASK，规则候选仍单独评测"}},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"companies":len(companies),"projects":sum(len(c["projects"]) for c in companies),"tasks":sum(len(p["tasks"]) for c in companies for p in c["projects"]),"policies":sum(len(c["policies"]) for c in companies),"unique_project_names":len({p["project_name"] for c in companies for p in c["projects"]}),"unique_task_names":len({t["task_name"] for c in companies for p in c["projects"] for t in p["tasks"]})},ensure_ascii=False))
if __name__=="__main__": main()
