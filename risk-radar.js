let currentScan = null;
let agentConfigured = false;

const pageMessage = document.querySelector("#page-message");
const summarySection = document.querySelector("#summary-section");
const candidateSection = document.querySelector("#candidate-section");
const summaryGrid = document.querySelector("#summary-grid");
const candidateList = document.querySelector("#candidate-list");
const evaluationPanel = document.querySelector("#evaluation-panel");

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

function appendTextList(parent, title, items, ordered = false) {
  if (!Array.isArray(items) || !items.length) return;
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
  parent.append(heading, list);
}

function renderAgentResult(container, result) {
  container.replaceChildren();
  const meta = document.createElement("div");
  meta.className = "ai-meta";
  [result.decision, result.model || "本地预检查", result.run_id].filter(Boolean).forEach((value) => {
    const chip = document.createElement("span");
    chip.textContent = value;
    meta.append(chip);
  });
  container.append(meta);
  const summary = document.createElement("p");
  summary.textContent = result.decision === "PLAN" ? result.summary : result.reason;
  container.append(summary);
  if (result.decision === "PLAN") {
    const recommendation = document.createElement("p");
    recommendation.textContent = `建议：${result.suggestedLevel} · ${result.priority}。这是草稿，仍需人工确认。`;
    container.append(recommendation);
    appendTextList(container, "判断依据", result.rationale);
    appendTextList(container, "行动草稿", result.actions, true);
    appendTextList(container, "注意事项", result.cautions);
    appendTextList(container, "引用", (result.citations || []).filter((item) => result.citationIds.includes(item.citation_id)).map((item) => `${item.title} v${item.version}：${item.quote}`));
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
    if (!response.ok) throw new Error(data.error || `AI 研判失败（HTTP ${response.status}）`);
    renderAgentResult(container, data);
  } catch (error) {
    container.textContent = error.message || "AI 研判失败；确定性扫描结果仍可使用。";
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
  meta.textContent = `${candidate.task_id} · ${candidate.task_name} · 负责人 ${candidate.owner || "未填写"} · ${candidate.risk_type}`;
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
  document.querySelector("#source-badge").textContent = data.sample_mode ? "固定模拟评测" : "最近本地导入";
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
        decision,
        note,
      }),
    });
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || `保存失败（HTTP ${response.status}）`);
    const labels = { confirm: "已确认", watch: "已设为观察", reject: "已驳回", false_positive: "已标记误报" };
    status.textContent = `${labels[decision]}；只写入审计记录，没有修改任务或 V1 风险。`;
  } catch (error) {
    status.textContent = error.message || "人工选择保存失败。";
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

document.querySelector("#scan-sample").addEventListener("click", (event) => runScan("/api/risk-scans/sample", event.currentTarget));
document.querySelector("#scan-latest").addEventListener("click", (event) => {
  const asOf = document.querySelector("#scan-date").value;
  runScan("/api/risk-scans/latest", event.currentTarget, asOf ? { as_of: asOf } : {});
});

async function loadAgentCapabilities() {
  const status = document.querySelector("#agent-status");
  try {
    const response = await fetch("/api/agent/capabilities");
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "AI 状态不可用");
    agentConfigured = data.provider_configured === true;
    status.textContent = agentConfigured ? `DeepSeek 已配置 · ${data.skills.length} Skills` : "DeepSeek 未配置";
    status.classList.toggle("is-ready", agentConfigured);
    status.classList.toggle("is-offline", !agentConfigured);
  } catch (_error) {
    agentConfigured = false;
    status.textContent = "AI 状态不可用";
    status.classList.add("is-offline");
  }
}

loadAgentCapabilities();
