let currentScan = null;
let agentConfigured = false;

const pageMessage = document.querySelector("#page-message");
const summarySection = document.querySelector("#summary-section");
const candidateSection = document.querySelector("#candidate-section");
const summaryGrid = document.querySelector("#summary-grid");
const candidateList = document.querySelector("#candidate-list");
const evaluationPanel = document.querySelector("#evaluation-panel");
const companyBenchmarkPanel = document.querySelector("#company-benchmark-panel");
const independentEvaluationPanel = document.querySelector("#independent-evaluation-panel");

function setMessage(text = "", type = "error") {
  pageMessage.textContent = text;
  pageMessage.classList.toggle("is-hidden", !text);
  pageMessage.classList.toggle("is-info", type === "info");
}

async function readJson(response) {
  try { return await response.json(); }
  catch (_error) { return { error: `服务返回了无法读取的结果（HTTP ${response.status}）` }; }
}

function metric(label, value) {
  const item = document.createElement("div");
  item.className = "metric";
  const name = document.createElement("span");
  const number = document.createElement("strong");
  name.textContent = label;
  number.textContent = value;
  item.append(name, number);
  return item;
}

function renderEvaluation(evaluation) {
  evaluationPanel.replaceChildren();
  evaluationPanel.classList.toggle("is-hidden", !evaluation);
  if (!evaluation) return;
  const grid = document.createElement("div");
  grid.className = "evaluation-grid";
  grid.append(
    metric("Precision 查准率", `${evaluation.precision_percent}%`),
    metric("Recall 查全率", `${evaluation.recall_percent}%`),
    metric("TP / FP / FN", `${evaluation.true_positive} / ${evaluation.false_positive} / ${evaluation.false_negative}`)
  );
  const note = document.createElement("small");
  note.textContent = evaluation.scope_note;
  evaluationPanel.append(grid, note);
}

function appendBenchmarkTable(parent, rows) {
  const wrapper = document.createElement("div");
  wrapper.className = "benchmark-table-wrap";
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["公司", "TP", "FP", "FN", "Precision", "Recall", "严重度一致率"].forEach((label) => {
    const cell = document.createElement("th"); cell.scope = "col"; cell.textContent = label; headRow.append(cell);
  });
  head.append(headRow); table.append(head);
  const body = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    [row.company_name, row.true_positive, row.false_positive, row.false_negative, `${row.precision_percent}%`, `${row.recall_percent}%`, `${row.severity_match_percent}%`].forEach((value) => {
      const cell = document.createElement("td"); cell.textContent = value; tr.append(cell);
    });
    body.append(tr);
  });
  table.append(body); wrapper.append(table); parent.append(wrapper);
}

function renderCompanyBenchmark(data) {
  companyBenchmarkPanel.replaceChildren();
  const heading = document.createElement("div"); heading.className = "section-heading";
  const titleWrap = document.createElement("div");
  const eyebrow = document.createElement("p"); eyebrow.className = "eyebrow"; eyebrow.textContent = "FIXED BENCHMARK";
  const title = document.createElement("h2"); title.id = "benchmark-title"; title.textContent = "跨公司规则基准";
  const subtitle = document.createElement("p"); subtitle.textContent = `${data.case_count} 个差异化项目 · 固定扫描日 ${data.as_of}`;
  titleWrap.append(eyebrow, title, subtitle);
  const status = document.createElement("span"); status.className = "source-badge"; status.textContent = "DeepSeek 未运行";
  heading.append(titleWrap, status);

  const metrics = document.createElement("div"); metrics.className = "summary-grid benchmark-summary";
  metrics.append(
    metric("TP / FP / FN", `${data.overall.true_positive} / ${data.overall.false_positive} / ${data.overall.false_negative}`),
    metric("Precision", `${data.overall.precision_percent}%`),
    metric("Recall", `${data.overall.recall_percent}%`),
    metric("严重度一致率", `${data.overall.severity_match_percent}%`),
    metric("预期 ASK / PLAN", `${data.expected_ask_cases} / ${data.expected_plan_cases}`),
    metric("DeepSeek 实际运行", data.deepseek_runs)
  );
  const note = document.createElement("p"); note.className = "benchmark-note"; note.textContent = data.scope_note;
  companyBenchmarkPanel.append(heading, metrics, note);
  appendBenchmarkTable(companyBenchmarkPanel, data.by_company);

  const gaps = document.createElement("div"); gaps.className = "benchmark-gaps";
  const gapTitle = document.createElement("h3"); gapTitle.textContent = "已暴露的规则缺口";
  const gapText = document.createElement("p");
  gapText.textContent = `边界误报 ${data.false_positive_cases.length} 条；间接依赖等漏报 ${data.false_negative_cases.length} 条；严重度不一致 ${data.severity_mismatches.length} 条。`;
  gaps.append(gapTitle, gapText); companyBenchmarkPanel.append(gaps);
  companyBenchmarkPanel.classList.remove("is-hidden");
}

async function runCompanyBenchmark(button) {
  const normalText = button.textContent; button.disabled = true; button.textContent = "评测中…";
  setMessage("正在运行固定合成场景规则基准；不会调用 DeepSeek。", "info");
  try {
    const response = await fetch("/api/evaluation/company-benchmark");
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || `评测失败（HTTP ${response.status}）`);
    renderCompanyBenchmark(data);
    setMessage(`跨公司规则基准完成：${data.case_count} 个项目，DeepSeek 实际运行 ${data.deepseek_runs} 次。`, "info");
  } catch (error) {
    setMessage(error.message || "跨公司规则基准失败。");
  } finally {
    button.disabled = false; button.textContent = normalText;
  }
}

function renderIndependentEvaluation(data) {
  independentEvaluationPanel.replaceChildren();
  independentEvaluationPanel.classList.remove("is-hidden");
  const heading = document.createElement("div"); heading.className = "section-heading";
  const copy = document.createElement("div");
  const title = document.createElement("h2"); title.id = "independent-evaluation-title"; title.textContent = "独立评测框架";
  const status = document.createElement("p"); status.className = "evaluation-status"; status.textContent = data.status;
  copy.append(title, status);
  const badge = document.createElement("span"); badge.className = "source-badge"; badge.textContent = `标注者 ${data.annotator_count}/${data.required_annotators}`;
  heading.append(copy, badge);
  const grid = document.createElement("div"); grid.className = "summary-grid benchmark-summary";
  grid.append(
    metric("开发集", `${data.development_cases} 个案例`),
    metric("留出集", `${data.holdout_cases} 个案例`),
    metric("系统预测字段", data.prediction_fields_removed ? "已移除" : "检查失败")
  );
  const metrics = document.createElement("p"); metrics.className = "benchmark-note"; metrics.textContent = `分开计算：${data.metrics.join("、")}。`;
  const note = document.createElement("p"); note.className = "framework-scope-note"; note.textContent = data.scope_note;
  independentEvaluationPanel.append(heading, grid, metrics, note);
}

async function checkEvaluationFramework(button) {
  const normalText = button.textContent; button.disabled = true; button.textContent = "检查中…";
  try {
    const response = await fetch("/api/evaluation/framework");
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "独立评测框架无法读取");
    renderIndependentEvaluation(data);
    setMessage("已检查独立评测框架；外部人工标注状态单独显示。", "success");
  } catch (error) {
    setMessage(error.message || "独立评测框架无法读取。", "error");
  } finally {
    button.disabled = false; button.textContent = normalText;
  }
}

function appendTextList(parent, title, items, ordered = false) {
  if (!Array.isArray(items) || !items.length) return;
  const block = document.createElement("section");
  block.className = "ai-block";
  const heading = document.createElement("h4");
  heading.textContent = title;
  const list = document.createElement(ordered ? "ol" : "ul");
  items.forEach((item) => {
    const row = document.createElement("li");
    row.textContent = typeof item === "string" ? item : item.action
      ? `${item.action}（角色：${item.ownerRole}；完成信号：${item.successSignal}）`
      : item.question || String(item);
    list.append(row);
  });
  block.append(heading, list);
  parent.append(block);
}

function renderAgentResult(container, result, candidate, card) {
  container.replaceChildren();
  container.dataset.decision = result.decision;
  const meta = document.createElement("div");
  meta.className = "ai-meta";
  [result.decision, result.model || "本地预检查", result.run_id].filter(Boolean).forEach((value) => {
    const chip = document.createElement("span");
    chip.textContent = value;
    meta.append(chip);
  });
  container.append(meta);
  const overview = document.createElement("section");
  overview.className = "ai-block";
  const summary = document.createElement("p");
  summary.textContent = result.decision === "PLAN" ? result.summary : result.reason;
  overview.append(summary);
  container.append(overview);
  if (result.decision === "PLAN") {
    const recommendation = document.createElement("p");
    recommendation.textContent = `建议：${result.suggestedLevel} · ${result.priority}。这是草稿，仍需人工确认。`;
    overview.append(recommendation);
    appendTextList(container, "判断依据", result.rationale);
    appendTextList(container, "行动草稿", result.actions, true);
    appendTextList(container, "注意事项", result.cautions);
    appendTextList(container, "引用", (result.citations || []).filter((item) => result.citationIds.includes(item.citation_id)).map((item) => `${item.title} v${item.version}：${item.quote}`));
    card.dataset.citations = JSON.stringify(
      (result.citations || []).filter((item) => result.citationIds.includes(item.citation_id))
    );
    const prefill = document.createElement("button");
    prefill.type = "button";
    prefill.className = "secondary-button prefill-action";
    prefill.textContent = "预填行动表单";
    prefill.disabled = !card.dataset.riskDecisionId;
    prefill.title = prefill.disabled ? "请先完成风险人工确认" : "只预填，不会自动保存";
    prefill.addEventListener("click", () => {
      // 行动的制度依据直接取自本次 AI 研判引用的当前生效制度，保证写回飞书时引用可核查。
      const citations = JSON.parse(card.dataset.citations || "[]");
      const policyReference = citations.length
        ? citations.map((item) => `${item.title} v${item.version}`).join("；")
        : "";
      const drafts = result.actions.map((item) => ({
        candidate_id: candidate.candidate_id,
        candidate_title: candidate.title,
        project_id: currentScan.project.project_id,
        risk_decision_id: card.dataset.riskDecisionId,
        plan_run_id: result.run_id,
        plan_step: item.step,
        title: item.action,
        owner_role: item.ownerRole,
        completion_signal: item.successSignal,
        task_id: candidate.task_id,
        policy_reference: policyReference,
      }));
      sessionStorage.setItem("saasguide.actionDrafts", JSON.stringify(drafts));
      location.href = "/action-tracker?draft=1";
    });
    container.append(prefill);
  } else {
    appendTextList(container, "需要补充", result.questions);
  }
  const details = document.createElement("details");
  const label = document.createElement("summary");
  label.textContent = "查看 Skill 运行轨迹";
  const trace = document.createElement("ul");
  (result.trace || []).forEach((item) => {
    const row = document.createElement("li");
    row.textContent = `${item.skill} · ${item.status} · ${item.detail}`;
    trace.append(row);
  });
  details.append(label, trace);
  container.append(details);
}

async function runAgent(button, container, candidate, contextNote) {
  const normalText = button.textContent;
  button.disabled = true;
  button.textContent = "AI 研判中…";
  container.textContent = "协调智能体正在运行证据检索和行动规划 Skill。";
  try {
    const response = await fetch("/api/agent/risk-assessment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate, project: currentScan.project, source: currentScan.source, context_note: contextNote }),
    });
    const data = await readJson(response);
    if (!response.ok) {
      const failure = new Error(data.error || `AI 研判失败（HTTP ${response.status}）`);
      failure.details = data;
      throw failure;
    }
    renderAgentResult(container, data, candidate, button.closest(".candidate-card"));
  } catch (error) {
    container.replaceChildren();
    const reason = document.createElement("p");
    reason.textContent = error.message || "AI 研判失败。";
    const fallback = document.createElement("p");
    fallback.className = "ai-fallback";
    fallback.textContent = error.details?.fallback || "确定性扫描结果和人工处理仍可使用。";
    container.append(reason, fallback);
    if (error.details?.telemetry?.run_id) {
      const details = document.createElement("details");
      const summary = document.createElement("summary"); summary.textContent = "查看失败运行信息";
      const telemetry = error.details.telemetry;
      const line = document.createElement("p");
      line.textContent = `${telemetry.run_id} · ${error.details.error_category} · ${telemetry.latency_ms} ms · 重试 ${telemetry.retry_count} 次`;
      details.append(summary, line); container.append(details);
    }
  } finally {
    button.disabled = !agentConfigured;
    button.textContent = normalText;
  }
}

function candidateCard(candidate) {
  const card = document.createElement("article");
  card.className = "candidate-card";
  card.dataset.severity = candidate.severity;
  card.dataset.candidateId = candidate.candidate_id;

  const top = document.createElement("div");
  top.className = "candidate-top";
  const heading = document.createElement("div");
  const title = document.createElement("h3");
  const meta = document.createElement("p");
  title.textContent = candidate.title;
  meta.className = "candidate-meta";
  meta.textContent = `${candidate.task_id} · ${candidate.task_name} · 负责人 ${candidate.owner || "未填写"} · ${candidate.risk_type} · ${candidate.candidate_id}`;
  heading.append(title, meta);
  const severity = document.createElement("span");
  severity.className = `severity ${candidate.severity}`;
  severity.textContent = candidate.severity === "high" ? "高" : "中";
  top.append(heading, severity);

  const rules = document.createElement("p");
  rules.className = "rule-list";
  rules.textContent = `触发规则：${candidate.trigger_rules.join("、")} · 依据：确定性规则命中，不是概率判断`;

  const evidence = document.createElement("ul");
  evidence.className = "evidence-list";
  candidate.evidence.forEach((item) => {
    const row = document.createElement("li");
    const label = document.createElement("strong");
    label.textContent = `${item.label} · 原表第 ${item.source_row ?? "—"} 行`;
    const value = Array.isArray(item.value) ? item.value.join(", ") : String(item.value ?? "—");
    row.append(label, document.createTextNode(value));
    evidence.append(row);
  });

  const aiArea = document.createElement("section");
  aiArea.className = "ai-area";
  const aiTop = document.createElement("div");
  aiTop.className = "ai-area__top";
  const aiTitle = document.createElement("strong");
  aiTitle.textContent = "AI 综合研判";
  const aiButton = document.createElement("button");
  aiButton.type = "button";
  aiButton.className = "ai-button";
  aiButton.textContent = "调用 DeepSeek";
  aiButton.disabled = !agentConfigured;
  const aiResult = document.createElement("div");
  aiResult.className = "ai-result";
  aiTop.append(aiTitle, aiButton);
  aiArea.append(aiTop, aiResult);

  const decisionArea = document.createElement("div");
  decisionArea.className = "decision-area";
  const note = document.createElement("input");
  note.maxLength = 500;
  note.placeholder = "可选：记录判断依据（最多 500 字）";
  const actions = [["confirm", "确认"], ["watch", "观察"], ["reject", "驳回"], ["false_positive", "标记误报"]];
  decisionArea.append(note);
  actions.forEach(([decision, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "decision-button";
    button.dataset.decision = decision;
    button.textContent = label;
    button.addEventListener("click", () => saveDecision(card, candidate, decision, note.value));
    decisionArea.append(button);
  });
  const status = document.createElement("p");
  status.className = "decision-status";
  status.setAttribute("aria-live", "polite");
  decisionArea.append(status);
  aiButton.addEventListener("click", () => runAgent(aiButton, aiResult, candidate, note.value));
  card.append(top, rules, evidence, aiArea, decisionArea);
  return card;
}

function renderScan(data) {
  currentScan = data;
  document.querySelector("#scan-meta").textContent = `${data.project.project_name}（${data.project.project_id}）· 扫描日 ${data.as_of} · 来源 ${data.source.source_name}`;
  document.querySelector("#source-badge").textContent = data.sample_mode ? "隔离评测夹具" : data.source_mode === "editable_company_project" ? "可编辑公司项目" : "最近本地导入";
  summaryGrid.replaceChildren(
    metric("候选风险", data.summary.candidate_count),
    metric("高风险信号", data.summary.high_count),
    metric("中风险信号", data.summary.medium_count),
    metric("规则命中", data.summary.rule_hit_count)
  );
  renderEvaluation(data.evaluation);
  candidateList.replaceChildren();
  data.candidates.forEach((candidate) => candidateList.append(candidateCard(candidate)));
  if (!data.candidates.length) {
    const empty = document.createElement("p");
    empty.textContent = "当前规则没有发现候选风险；这不等于项目一定没有风险。";
    candidateList.append(empty);
  }
  summarySection.classList.remove("is-hidden");
  candidateSection.classList.remove("is-hidden");
}

async function runScan(endpoint, button, body) {
  const normalText = button.textContent;
  button.disabled = true;
  button.textContent = "扫描中…";
  setMessage("正在运行确定性规则；完成后可在候选卡中按需调用 DeepSeek。", "info");
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || `扫描失败（HTTP ${response.status}）`);
    renderScan(data);
    setMessage(`扫描完成：生成 ${data.summary.candidate_count} 条待人工判断的候选风险。`, "info");
  } catch (error) {
    setMessage(error.message || "风险扫描失败。");
  } finally {
    button.disabled = false;
    button.textContent = normalText;
  }
}

async function saveDecision(card, candidate, decision, note) {
  const status = card.querySelector(".decision-status");
  const buttons = [...card.querySelectorAll(".decision-button")];
  buttons.forEach((button) => { button.disabled = true; });
  status.textContent = "正在记录人工选择…";
  try {
    const response = await fetch("/api/risk-scans/decisions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_id: candidate.candidate_id,
        candidate_key: candidate.candidate_key,
        source_id: currentScan.source.source_id,
        company_id: currentScan.company?.company_id || "",
        decision,
        note,
        project_id: currentScan.project.project_id,
        project_name: currentScan.project.project_name,
        title: candidate.title,
        severity: candidate.severity,
        risk_type: candidate.risk_type,
        task_id: candidate.task_id,
        scan_id: currentScan.scan_id,
        evidence: candidate.evidence,
        citations: JSON.parse(card.dataset.citations || "[]"),
        actor: "本地演示用户",
      }),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || `保存失败（HTTP ${response.status}）`);
    const labels = { confirm: "已确认", watch: "已设为观察", reject: "已驳回", false_positive: "已标记误报" };
    status.textContent = `${labels[decision]}；只写入审计记录，没有修改任务或 V1 风险。`;
    if (decision === "confirm") card.dataset.riskDecisionId = data.record.decision_id;
    else delete card.dataset.riskDecisionId;
    const prefill = card.querySelector(".prefill-action");
    if (prefill) {
      prefill.disabled = decision !== "confirm";
      prefill.title = prefill.disabled ? "请先完成风险人工确认" : "只预填，不会自动保存";
    }
  } catch (error) {
    status.textContent = error.message || "人工选择保存失败。";
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

document.querySelector("#scan-sample").addEventListener("click", (event) => runScan("/api/risk-scans/sample", event.currentTarget));
document.querySelector("#run-company-benchmark").addEventListener("click", (event) => runCompanyBenchmark(event.currentTarget));
document.querySelector("#check-evaluation-framework").addEventListener("click", (event) => checkEvaluationFramework(event.currentTarget));
document.querySelector("#scan-company").addEventListener("click", (event) => {
  const projectId = document.querySelector("#company-project").value;
  if (!projectId) { setMessage("当前没有可扫描项目，请先在数据源页面新增或恢复模拟公司数据。"); return; }
  const asOf = document.querySelector("#scan-date").value;
  runScan(`/api/company-data/projects/${encodeURIComponent(projectId)}/scan`, event.currentTarget, asOf ? { as_of: asOf } : {});
});
document.querySelector("#scan-latest").addEventListener("click", (event) => {
  const asOf = document.querySelector("#scan-date").value;
  runScan("/api/risk-scans/latest", event.currentTarget, asOf ? { as_of: asOf } : {});
});

async function loadAgentCapabilities() {
  const status = document.querySelector("#agent-status");
  const note = document.querySelector("#model-runtime-note");
  try {
    const response = await fetch("/api/agent/capabilities");
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "AI 状态不可用");
    agentConfigured = data.provider_configured === true;
    status.textContent = agentConfigured ? `DeepSeek 已配置 · ${data.skills.length} Skills` : "DeepSeek 未配置";
    note.textContent = `${data.model_status_reason}；超时 ${data.timeout_seconds} 秒，最多重试 ${data.max_retries} 次，单次上限 ${data.budget.max_total_tokens} Token。`;
    status.classList.toggle("is-ready", agentConfigured);
    status.classList.toggle("is-offline", !agentConfigured);
  } catch (_error) {
    agentConfigured = false;
    status.textContent = "AI 状态不可用";
    note.textContent = "模型状态读取失败；规则扫描和人工处理仍可使用。";
    status.classList.add("is-offline");
  }
}

loadAgentCapabilities();

async function loadCompanyProjects() {
  const select = document.querySelector("#company-project");
  try {
    const response = await fetch("/api/company-data"); const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "项目列表不可用");
    select.replaceChildren(...data.projects.map((project) => { const option = document.createElement("option"); option.value = project.project_id; option.textContent = `${project.project_name} · ${project.department}`; return option; }));
    const requested = new URLSearchParams(location.search).get("project");
    if (requested && [...select.options].some((item) => item.value === requested)) select.value = requested;
    document.querySelector("#scan-company").disabled = data.projects.length === 0;
  } catch (error) { setMessage(error.message || "无法读取项目列表。"); }
}
loadCompanyProjects();
