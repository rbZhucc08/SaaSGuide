let importPreview = null;
let companyData = null;
let editingProjectId = null;
let editingCompanyId = null;

async function companyApi(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `请求失败（HTTP ${response.status}）`);
  return data;
}

function projectInput(id) { return document.querySelector(`#${id}`); }

function createTaskRow(task = {}) {
  const row = document.createElement("div");
  row.className = "task-row";
  const fields = [
    ["task_id", "编号", "text"], ["task_name", "任务名称", "text"], ["owner", "负责人", "text"],
    ["start_date", "开始", "date"], ["due_date", "截止", "date"], ["status", "状态", "text"],
    ["priority", "优先级", "text"], ["progress_percent", "完成度", "number"], ["dependency_ids", "前置任务", "text"],
  ];
  fields.forEach(([key, labelText, type]) => {
    const label = document.createElement("label");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.type = type;
    input.dataset.taskField = key;
    if (type === "number") { input.min = "0"; input.max = "100"; }
    const value = key === "dependency_ids" ? (task[key] || []).join(",") : task[key];
    input.value = value ?? (key === "progress_percent" ? 0 : "");
    input.required = !["dependency_ids"].includes(key);
    label.append(input); row.append(label);
  });
  const remove = document.createElement("button");
  remove.type = "button"; remove.className = "icon-danger"; remove.textContent = "删除任务";
  remove.addEventListener("click", () => row.remove()); row.append(remove);
  return row;
}

function readTaskRows() {
  return [...document.querySelectorAll("#task-rows .task-row")].map((row) => {
    const values = Object.fromEntries([...row.querySelectorAll("[data-task-field]")].map((input) => [input.dataset.taskField, input.value.trim()]));
    values.progress_percent = Number(values.progress_percent);
    values.effort_hours = 0;
    values.dependency_ids = values.dependency_ids ? values.dependency_ids.split(",").map((item) => item.trim()).filter(Boolean) : [];
    return values;
  });
}

function openProjectEditor(project = null) {
  editingProjectId = project?.project_id || null;
  document.querySelector("#project-editor-title").textContent = project ? "编辑项目" : "新增项目";
  const values = project || {};
  [["project-id","project_id"],["project-name","project_name"],["project-type","project_type"],["project-department","department"],["project-stage","stage"],["project-start","start_date"],["project-end","end_date"],["project-background","background"],["project-outcome","outcome"]].forEach(([id,key]) => { projectInput(id).value = values[key] || (key === "project_type" ? "其他" : ""); });
  projectInput("project-id").readOnly = Boolean(project);
  const rows = document.querySelector("#task-rows"); rows.replaceChildren(...(values.tasks || []).map(createTaskRow));
  if (!values.tasks?.length) rows.append(createTaskRow());
  document.querySelector("#project-editor").classList.remove("is-hidden");
  document.querySelector("#project-editor").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCompany(data) {
  companyData = data;
  document.querySelector("#company-summary").textContent = `${data.company.name} · ${data.company.industry} · ${data.company.size_band} · ${data.company.business_model}`;
  const standard=data.company.risk_standard||{}; document.querySelector("#company-profile").textContent=`经营特征：${(data.company.operating_characteristics||[]).join("、")||"未记录"}　｜　高风险逾期阈值：${standard.high_overdue_days??"—"} 天　｜　临期窗口：${standard.due_soon_days??"—"} 天　｜　复核：${standard.review_cadence||"—"}　｜　升级角色：${standard.escalation_role||"—"}`;
  const select = document.querySelector("#company-select");
  select.replaceChildren(...data.companies.map((company) => { const option=document.createElement("option"); option.value=company.company_id; option.textContent=`${company.name} · ${company.projects} 项目`; option.selected=company.company_id===data.active_company_id; return option; }));
  const coverage=document.querySelector("#dataset-coverage"); coverage.replaceChildren();
  [["公司",data.dataset_summary.companies],["行业",data.dataset_summary.industries],["业务模式",data.dataset_summary.business_models],["项目",data.dataset_summary.projects],["任务",data.dataset_summary.tasks],["制度版本",data.dataset_summary.policy_versions]].forEach(([label,value])=>{const item=document.createElement("div");const strong=document.createElement("strong");strong.textContent=value;const small=document.createElement("small");small.textContent=label;item.append(strong,small);coverage.append(item)});
  const list = document.querySelector("#project-list"); list.replaceChildren();
  if (!data.projects.length) {
    const empty = document.createElement("div"); empty.className = "record-empty"; empty.textContent = "当前没有项目。可新增项目，或显式恢复模拟公司数据。"; list.append(empty); return;
  }
  data.projects.forEach((project) => {
    const card = document.createElement("article"); card.className = "record-card";
    const copy = document.createElement("div"); const title = document.createElement("h3"); title.textContent = project.project_name;
    const meta = document.createElement("p"); meta.textContent = `${project.project_id} · ${project.department} · ${project.stage} · ${project.tasks.length} 条任务`;
    const outcome = document.createElement("small"); outcome.textContent = project.outcome || "尚未记录项目经历或结果"; copy.append(title, meta, outcome);
    const actions = document.createElement("div");
    const edit = document.createElement("button"); edit.className = "secondary-button"; edit.type = "button"; edit.textContent = "编辑"; edit.addEventListener("click", () => openProjectEditor(project));
    const scan = document.createElement("a"); scan.className = "secondary-button"; scan.href = `/risk-radar?project=${encodeURIComponent(project.project_id)}`; scan.textContent = "扫描";
    const remove = document.createElement("button"); remove.className = "danger-button"; remove.type = "button"; remove.textContent = "删除"; remove.addEventListener("click", async () => { if (!confirm(`删除模拟项目“${project.project_name}”？`)) return; try { await companyApi(`/api/company-data/projects/${encodeURIComponent(project.project_id)}`, {method:"DELETE"}); await loadCompany(); setMessage("项目已删除。", "info"); } catch (error) { setMessage(error.message); } });
    actions.append(edit, scan, remove); card.append(copy, actions); list.append(card);
  });
}

async function loadCompany() { try { renderCompany(await companyApi("/api/company-data")); } catch (error) { setMessage(error.message); } }

function openCompanyEditor(company = null) {
  editingCompanyId=company?.company_id||null; const value=company||{};
  document.querySelector("#company-editor-title").textContent=company?"编辑公司画像与风险标准":"新增公司画像与风险标准";
  [["company-id","company_id"],["company-name","name"],["company-industry","industry"],["company-size","size_band"],["company-region","region"],["company-model","business_model"],["company-lifecycle","lifecycle_stage"],["company-appetite","risk_appetite"],["company-description","description"]].forEach(([id,key])=>{document.querySelector(`#${id}`).value=value[key]||""});
  const standard=value.risk_standard||{}; document.querySelector("#company-high-overdue").value=standard.high_overdue_days??3; document.querySelector("#company-due-soon").value=standard.due_soon_days??3; document.querySelector("#company-blocked-hours").value=standard.blocked_hours_high??24; document.querySelector("#company-cadence").value=standard.review_cadence||"每周"; document.querySelector("#company-escalation").value=standard.escalation_role||"项目负责人"; document.querySelector("#company-evidence").value=(standard.mandatory_evidence||[]).join(","); document.querySelector("#company-characteristics").value=(value.operating_characteristics||[]).join(",");
  document.querySelector("#company-departments").value=(companyData?.departments||[]).join(","); document.querySelector("#company-id").readOnly=Boolean(company);
  document.querySelector("#company-editor").classList.remove("is-hidden"); document.querySelector("#company-editor").scrollIntoView({behavior:"smooth",block:"start"});
}

const uploadForm = document.querySelector("#upload-form");
const fileInput = document.querySelector("#xlsx-file");
const fileName = document.querySelector("#file-name");
const previewButton = document.querySelector("#preview-button");
const message = document.querySelector("#page-message");
const mappingSection = document.querySelector("#mapping-section");
const mappingGrid = document.querySelector("#mapping-grid");
const previewSection = document.querySelector("#preview-section");
const previewSummary = document.querySelector("#preview-summary");
const previewBody = document.querySelector("#preview-body");
const validationBadge = document.querySelector("#validation-badge");
const errorPanel = document.querySelector("#error-panel");
const errorList = document.querySelector("#error-list");
const confirmSection = document.querySelector("#confirm-section");
const confirmButton = document.querySelector("#confirm-button");
const successSection = document.querySelector("#success-section");
const successDetails = document.querySelector("#success-details");

async function loadSecurityReadiness() {
  const summary = document.querySelector("#security-readiness-summary");
  const badge = document.querySelector("#security-readiness-badge");
  const grid = document.querySelector("#security-control-grid");
  try {
    const response = await fetch("/api/security/readiness");
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "安全状态不可用");
    summary.textContent = "当前仅允许模拟或已去标识化测试数据；认证、权限、租户隔离和加密尚未完成。";
    badge.textContent = "真实数据已阻断";
    badge.className = "validation-badge is-invalid";
    grid.replaceChildren();
    data.controls.forEach((control) => {
      const item = document.createElement("div");
      item.className = `security-control ${control.implemented ? "is-ready" : "is-blocked"}`;
      const label = document.createElement("strong");
      label.textContent = control.control;
      const state = document.createElement("span");
      state.textContent = control.implemented ? "已实现" : "未实现";
      const evidence = document.createElement("small");
      evidence.textContent = control.evidence;
      item.append(label, state, evidence);
      grid.append(item);
    });
  } catch (error) {
    summary.textContent = error.message || "无法读取安全准备状态。";
    badge.textContent = "状态不可用";
    badge.className = "validation-badge is-invalid";
  }
}

async function loadFeishuConnector() {
  const summary = document.querySelector("#feishu-connector-summary");
  const badge = document.querySelector("#feishu-connector-badge");
  const button = document.querySelector("#feishu-sync-button");
  try {
    const response = await fetch("/api/connectors/feishu/status");
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "飞书连接器状态不可用");
    if (data.configured) {
      summary.textContent = "本机已提供连接参数；同步仍只读取飞书多维表格。";
      badge.textContent = "已配置，待真实同步";
      badge.className = "validation-badge is-valid";
      button.disabled = false;
    } else {
      summary.textContent = "连接器底座可用；本机尚未设置飞书应用凭据和表格标识。";
      badge.textContent = "真实授权待完成";
      badge.className = "validation-badge is-invalid";
      button.disabled = true;
    }
  } catch (error) {
    summary.textContent = error.message || "无法读取飞书连接器状态。";
    badge.textContent = "状态不可用";
    badge.className = "validation-badge is-invalid";
  }
}

document.querySelector("#feishu-sync-button").addEventListener("click", async () => {
  const button = document.querySelector("#feishu-sync-button");
  const result = document.querySelector("#feishu-sync-result");
  setBusy(button, true, "正在只读同步…", "运行只读同步");
  try {
    const response = await fetch("/api/connectors/feishu/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "飞书同步失败");
    result.textContent = `同步完成：读取 ${data.fetched_count} 条，增量应用 ${data.applied_count} 条，本地保存 ${data.stored_count} 条；没有向飞书写回。`;
  } catch (error) {
    result.textContent = error.message || "飞书同步失败。";
  } finally {
    setBusy(button, false, "正在只读同步…", "运行只读同步");
  }
});

function setMessage(text = "", type = "error") {
  message.textContent = text;
  message.classList.toggle("is-hidden", !text);
  message.classList.toggle("is-info", type === "info");
}

function setBusy(button, busy, busyText, normalText) {
  button.disabled = busy;
  button.textContent = busy ? busyText : normalText;
}

function readMapping() {
  return Object.fromEntries(
    [...mappingGrid.querySelectorAll("input[data-field]")].map((input) => [
      input.dataset.field,
      input.value.trim(),
    ])
  );
}

function renderMapping(data) {
  mappingGrid.replaceChildren();
  const datalistId = `source-headers-${data.preview_id || "current"}`;
  const datalist = document.createElement("datalist");
  datalist.id = datalistId;
  data.headers.forEach((header) => {
    const option = document.createElement("option");
    option.value = header;
    datalist.append(option);
  });
  mappingGrid.append(datalist);
  data.field_definitions.forEach((field) => {
    const row = document.createElement("div");
    row.className = "mapping-field";
    const label = document.createElement("label");
    label.htmlFor = `mapping-${field.key}`;
    label.textContent = field.label;
    if (field.required) {
      const required = document.createElement("span");
      required.textContent = " *";
      label.append(required);
    }

    const input = document.createElement("input");
    input.type = "text";
    input.id = `mapping-${field.key}`;
    input.dataset.field = field.key;
    input.setAttribute("list", datalistId);
    input.value = data.mapping[field.key] || "";
    input.placeholder = field.required ? "输入原始列名（必填）" : "输入原始列名；留空表示不映射";
    input.autocomplete = "off";
    row.append(label, input);
    mappingGrid.append(row);
  });
  mappingSection.classList.remove("is-hidden");
}

function tableCell(text) {
  const cell = document.createElement("td");
  cell.textContent = text ?? "—";
  return cell;
}

function renderPreview(data) {
  importPreview = data;
  previewBody.replaceChildren();
  data.tasks.forEach((task) => {
    const row = document.createElement("tr");
    row.append(
      tableCell(task.source_row),
      tableCell(task.task_id),
      tableCell(task.task_name),
      tableCell(task.owner),
      tableCell(task.start_date),
      tableCell(task.due_date),
      tableCell(task.status),
      tableCell(task.dependency_ids.join(", ")),
      tableCell(task.progress_percent)
    );
    previewBody.append(row);
  });

  const summary = data.summary;
  const sensitiveNotice = data.security?.sensitive_data_detected ? " · 检出敏感样式，请先去标识化" : "";
  previewSummary.textContent = `${data.source.source_name} · ${data.source.sheet_name} · ${summary.task_count} 条任务 · ${summary.dependency_count} 条依赖 · ${summary.error_count} 个错误${data.preview_truncated ? " · 仅显示前 20 行" : ""}${sensitiveNotice}`;
  validationBadge.textContent = data.valid ? "校验通过" : `发现 ${summary.error_count} 个错误`;
  validationBadge.className = `validation-badge ${data.valid ? "is-valid" : "is-invalid"}`;

  errorList.replaceChildren();
  data.errors.forEach((error) => {
    const item = document.createElement("li");
    item.textContent = `${error.message}（${error.code}）`;
    errorList.append(item);
  });
  errorPanel.classList.toggle("is-hidden", data.errors.length === 0);
  previewSection.classList.remove("is-hidden");
  confirmSection.classList.remove("is-hidden");
  confirmButton.disabled = !data.valid;
  successSection.classList.add("is-hidden");
}

async function readJson(response) {
  try {
    return await response.json();
  } catch (_error) {
    return { error: `服务返回了无法读取的结果（HTTP ${response.status}）` };
  }
}

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files[0]?.name || "尚未选择文件";
  setMessage();
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) {
    setMessage("请选择一个 XLSX 文件。");
    return;
  }
  setMessage("正在读取工作簿并检查表头…", "info");
  setBusy(previewButton, true, "正在读取…", "读取并生成预览");
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetch("/api/imports/preview", { method: "POST", body: form });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || `预览失败（HTTP ${response.status}）`);
    renderMapping(data);
    renderPreview(data);
    setMessage(data.valid ? "自动列映射已生成，当前文件通过校验。请核对后再确认。" : "自动列映射已生成，但文件仍有错误。请按行号修正源文件或映射。", "info");
  } catch (error) {
    importPreview = null;
    mappingSection.classList.add("is-hidden");
    previewSection.classList.add("is-hidden");
    confirmSection.classList.add("is-hidden");
    successSection.classList.add("is-hidden");
    setMessage(error.message || "无法读取 XLSX 文件。");
  } finally {
    setBusy(previewButton, false, "正在读取…", "读取并生成预览");
  }
});

document.querySelector("#load-sample-button").addEventListener("click", async () => {
  const sampleButton = document.querySelector("#load-sample-button");
  const selectedSample = document.querySelector("#sample-select").value;
  setMessage("正在读取内置模拟 XLSX；这条路径不等于浏览器文件上传。", "info");
  setBusy(sampleButton, true, "正在加载…", "加载样本");
  try {
    const response = await fetch(`/api/imports/sample/${encodeURIComponent(selectedSample)}`, {
      method: "POST",
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || `样本读取失败（HTTP ${response.status}）`);
    renderMapping(data);
    renderPreview(data);
    setMessage(
      data.valid
        ? "内置有效样本通过校验。请核对映射后再人工确认。"
        : "内置错误样本已被拦截；请查看原表行号和错误代码。",
      "info"
    );
  } catch (error) {
    setMessage(error.message || "无法读取内置模拟样本。");
  } finally {
    setBusy(sampleButton, false, "正在加载…", "加载样本");
  }
});

document.querySelector("#validate-button").addEventListener("click", async () => {
  if (!importPreview?.preview_id) return;
  const validateButton = document.querySelector("#validate-button");
  setMessage("正在按当前列映射重新校验…", "info");
  setBusy(validateButton, true, "正在校验…", "按当前映射重新校验");
  try {
    const response = await fetch("/api/imports/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preview_id: importPreview.preview_id, mapping: readMapping() }),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || `校验失败（HTTP ${response.status}）`);
    renderPreview(data);
    setMessage(data.valid ? "当前映射和数据通过校验，可以进入人工确认。" : "当前数据仍有错误，不能确认导入。", "info");
  } catch (error) {
    confirmButton.disabled = true;
    setMessage(error.message || "无法重新校验映射。");
  } finally {
    setBusy(validateButton, false, "正在校验…", "按当前映射重新校验");
  }
});

confirmButton.addEventListener("click", async () => {
  if (!importPreview?.preview_id || !importPreview.valid) return;
  setMessage("服务器正在重新校验并保存原始文件与统一 JSON…", "info");
  setBusy(confirmButton, true, "正在保存…", "确认导入");
  try {
    const response = await fetch("/api/imports/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preview_id: importPreview.preview_id, mapping: readMapping() }),
    });
    const data = await readJson(response);
    if (!response.ok) {
      if (Array.isArray(data.errors)) renderPreview(data);
      throw new Error(data.error || `保存失败（HTTP ${response.status}）`);
    }
    successDetails.replaceChildren();
    const details = [
      ["项目", `${data.project.project_name}（${data.project.project_id}）`],
      ["任务与依赖", `${data.summary.task_count} 条任务，${data.summary.dependency_count} 条依赖`],
      ["来源哈希", data.source.sha256],
      ["统一 JSON", data.saved.normalized],
    ];
    details.forEach(([term, description]) => {
      const wrapper = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = term;
      dd.textContent = description;
      wrapper.append(dt, dd);
      successDetails.append(wrapper);
    });
    successSection.classList.remove("is-hidden");
    confirmButton.disabled = true;
    setMessage("导入完成。页面显示的是本地模拟数据结果，不代表真实企业系统接入。", "info");
    successSection.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    setMessage(error.message || "确认导入失败。");
    confirmButton.disabled = !importPreview?.valid;
  } finally {
    if (!successSection.classList.contains("is-hidden")) {
      confirmButton.textContent = "已确认导入";
    } else {
      setBusy(confirmButton, false, "正在保存…", "确认导入");
    }
  }
});

document.querySelector("#new-project").addEventListener("click", () => openProjectEditor());
document.querySelector("#cancel-project").addEventListener("click", () => document.querySelector("#project-editor").classList.add("is-hidden"));
document.querySelector("#add-task").addEventListener("click", () => document.querySelector("#task-rows").append(createTaskRow()));
document.querySelector("#project-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {project_id:projectInput("project-id").value.trim(),project_name:projectInput("project-name").value.trim(),project_type:projectInput("project-type").value.trim(),department:projectInput("project-department").value.trim(),stage:projectInput("project-stage").value.trim(),start_date:projectInput("project-start").value,end_date:projectInput("project-end").value,background:projectInput("project-background").value.trim(),outcome:projectInput("project-outcome").value.trim(),tasks:readTaskRows()};
  const endpoint = editingProjectId ? `/api/company-data/projects/${encodeURIComponent(editingProjectId)}` : "/api/company-data/projects";
  try { await companyApi(endpoint,{method:editingProjectId?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}); document.querySelector("#project-editor").classList.add("is-hidden"); await loadCompany(); setMessage("项目档案已保存，风险雷达将读取最新内容。", "info"); } catch(error) { setMessage(error.message); }
});
document.querySelector("#company-select").addEventListener("change",async(event)=>{try{renderCompany(await companyApi("/api/company-data/active-company",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({company_id:event.target.value})}));setMessage("已切换公司；风险扫描和知识检索将使用该公司的数据。","info")}catch(error){setMessage(error.message)}});
document.querySelector("#new-company").addEventListener("click",()=>openCompanyEditor());
document.querySelector("#edit-company").addEventListener("click",()=>openCompanyEditor(companyData.company));
document.querySelector("#cancel-company").addEventListener("click",()=>document.querySelector("#company-editor").classList.add("is-hidden"));
document.querySelector("#company-form").addEventListener("submit",async(event)=>{event.preventDefault();const list=(id)=>document.querySelector(id).value.split(",").map(x=>x.trim()).filter(Boolean);const payload={company_id:document.querySelector("#company-id").value.trim(),name:document.querySelector("#company-name").value.trim(),industry:document.querySelector("#company-industry").value.trim(),size_band:document.querySelector("#company-size").value.trim(),region:document.querySelector("#company-region").value.trim(),business_model:document.querySelector("#company-model").value.trim(),lifecycle_stage:document.querySelector("#company-lifecycle").value.trim(),risk_appetite:document.querySelector("#company-appetite").value.trim(),operating_characteristics:list("#company-characteristics"),risk_standard:{high_overdue_days:Number(document.querySelector("#company-high-overdue").value),due_soon_days:Number(document.querySelector("#company-due-soon").value),blocked_hours_high:Number(document.querySelector("#company-blocked-hours").value),review_cadence:document.querySelector("#company-cadence").value.trim(),escalation_role:document.querySelector("#company-escalation").value.trim(),mandatory_evidence:list("#company-evidence")},description:document.querySelector("#company-description").value.trim(),departments:list("#company-departments"),projects:editingCompanyId?companyData.projects:[],policies:editingCompanyId?companyData.policies:[]};try{await companyApi(editingCompanyId?`/api/company-data/companies/${encodeURIComponent(editingCompanyId)}`:"/api/company-data/companies",{method:editingCompanyId?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});document.querySelector("#company-editor").classList.add("is-hidden");await loadCompany();setMessage("公司画像与风险标准已保存。","info")}catch(error){setMessage(error.message)}});
document.querySelector("#delete-company").addEventListener("click",async()=>{if(!confirm(`删除“${companyData.company.name}”及其项目和制度？`))return;try{await companyApi(`/api/company-data/companies/${encodeURIComponent(companyData.active_company_id)}`,{method:"DELETE"});await loadCompany();setMessage("公司数据已删除。","info")}catch(error){setMessage(error.message)}});
document.querySelector("#reset-company").addEventListener("click", async () => { if (!confirm("恢复会覆盖整个多公司数据集，确定继续？")) return; try { renderCompany(await companyApi("/api/company-data/reset",{method:"POST"})); setMessage("已恢复多公司模拟数据集。", "info"); } catch(error) { setMessage(error.message); } });
document.querySelector("#clear-company").addEventListener("click", async () => { if (!confirm("清空当前公司的项目和制度？其他公司不受影响。")) return; try { renderCompany(await companyApi("/api/company-data/clear",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmed:true})})); setMessage("当前公司项目和制度已清空；其他公司数据仍保留。", "info"); } catch(error) { setMessage(error.message); } });
loadCompany();
loadSecurityReadiness();
loadFeishuConnector();
