let guideSteps = [];

const guideActions = {
  "filter-high": () => applyFilter("high"),
};

let initialRiskData = [];
let riskData = [];

let currentStep = 0;
let selectedRiskId = "api-delay";
let resolved = false;
let latestAiPlan = null;
let latestAiRiskId = null;
let latestNewRiskAnalysis = null;
let latestNewRiskFingerprint = null;

const guideCard = document.querySelector("#guide-card");
const guideResult = document.querySelector("#guide-result");
const stepLabel = document.querySelector("#step-label");
const guideTitle = document.querySelector("#guide-title");
const guideDescription = document.querySelector("#guide-description");
const previousButton = document.querySelector("#previous-step");
const nextButton = document.querySelector("#next-step");
const finishButton = document.querySelector("#finish-guide");
const progressDots = [...document.querySelectorAll(".progress-dots i")];

async function loadGuideData() {
  const response = await fetch("guide-data.json");
  if (!response.ok) throw new Error(`引导数据读取失败：${response.status}`);

  const data = await response.json();
  if (!data.pageElements || !Array.isArray(data.guideSteps)) {
    throw new Error("引导数据缺少页面元素或步骤列表");
  }

  guideSteps = data.guideSteps.map((step) => ({
    targetId: data.pageElements[step.target],
    title: step.title,
    description: step.description,
    onEnter: guideActions[step.action],
  }));
}

function cloneRisks(risks) {
  return risks.map((risk) => ({
    ...risk,
    plan: Array.isArray(risk.plan) ? [...risk.plan] : [],
  }));
}

async function loadRiskData() {
  const response = await fetch("risk-data.json");
  if (!response.ok) throw new Error(`风险数据读取失败：${response.status}`);

  const data = await response.json();
  if (!Array.isArray(data.risks) || data.risks.length === 0) {
    throw new Error("风险数据缺少非空的 risks 列表");
  }

  initialRiskData = cloneRisks(data.risks);
  riskData = cloneRisks(initialRiskData);
  selectedRiskId = riskData[0].id;
}

function escapeHtml(value) {
  const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
  return String(value ?? "").replace(/[&<>"']/g, (character) => entities[character]);
}

function statusClass(status) {
  if (status === "待处理") return "status--open";
  if (status === "已处理") return "status--resolved";
  return "status--progress";
}

function displayDate(date) {
  const [, month, day] = String(date).split("-");
  return month && day ? `${month} 月 ${day} 日` : date;
}

function bindRiskRowEvents() {
  document.querySelectorAll(".risk-row").forEach((row) => {
    const selectRow = () => showRiskDetail(row.dataset.riskId);
    row.addEventListener("click", selectRow);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectRow();
      }
    });
  });
}

function renderRiskRows() {
  const tableBody = document.querySelector("#risk-table-body");
  tableBody.innerHTML = riskData.map((risk) => `
    <tr class="risk-row${risk.id === selectedRiskId ? " is-selected" : ""}"
        data-risk="${escapeHtml(risk.type)}"
        data-risk-id="${escapeHtml(risk.id)}"
        tabindex="0">
      <td>
        <strong>${escapeHtml(risk.title)}</strong>
        <small>${escapeHtml(risk.summary)}</small>
      </td>
      <td><span class="risk-level risk-level--${escapeHtml(risk.type)}">${escapeHtml(risk.level)}</span></td>
      <td><span class="person"><i class="${escapeHtml(risk.avatarClass)}">${escapeHtml(risk.owner?.slice(0, 1))}</i>${escapeHtml(risk.owner)}</span></td>
      <td><span class="due-date${risk.overdue ? " due-date--late" : ""}">${escapeHtml(displayDate(risk.due))}</span></td>
      <td><span class="status ${statusClass(risk.status)}">${escapeHtml(risk.status)}</span></td>
    </tr>
  `).join("");

  bindRiskRowEvents();
}

function showGuideLoadError(error) {
  console.error(error);
  guideCard.classList.remove("is-hidden");
  guideResult.classList.add("is-hidden");
  stepLabel.textContent = "引导无法加载";
  guideTitle.textContent = "请通过本地预览地址打开页面";
  guideDescription.textContent = "独立 JSON 文件需要通过本地预览服务读取，不能再直接双击 HTML 文件运行。";
  previousButton.classList.add("is-hidden");
  nextButton.classList.add("is-hidden");
  finishButton.classList.add("is-hidden");
}

function updateRiskCounts() {
  const counts = { all: 0, high: 0, medium: 0, low: 0 };
  const statusCounts = { pending: 0, resolved: 0 };

  riskData.forEach((risk) => {
    counts.all += 1;
    if (risk.type in counts) counts[risk.type] += 1;

    if (risk.status === "待处理") statusCounts.pending += 1;
    if (risk.status === "已处理") statusCounts.resolved += 1;
  });

  document.querySelectorAll("[data-risk-count]").forEach((element) => {
    element.textContent = counts[element.dataset.riskCount] ?? 0;
  });

  document.querySelectorAll("[data-status-count]").forEach((element) => {
    element.textContent = statusCounts[element.dataset.statusCount] ?? 0;
  });

  const highRiskShare = counts.all === 0 ? 0 : Math.round((counts.high / counts.all) * 100);
  document.querySelector("#high-risk-share").textContent = `占比 ${highRiskShare}%`;
}

function updateGuide() {
  document.querySelectorAll(".guide-target.is-highlighted").forEach((element) => {
    element.classList.remove("is-highlighted");
  });

  const step = guideSteps[currentStep];
  const target = document.getElementById(step.targetId);

  stepLabel.textContent = `步骤 ${currentStep + 1} / ${guideSteps.length}`;
  guideTitle.textContent = step.title;
  guideDescription.textContent = step.description;
  previousButton.disabled = currentStep === 0;
  previousButton.style.visibility = currentStep === 0 ? "hidden" : "visible";
  nextButton.classList.toggle("is-hidden", currentStep === guideSteps.length - 1);
  finishButton.classList.toggle("is-hidden", currentStep !== guideSteps.length - 1);
  finishButton.disabled = currentStep === guideSteps.length - 1 && !resolved;
  guideCard.classList.toggle("is-final-step", currentStep === guideSteps.length - 1);

  progressDots.forEach((dot, index) => {
    dot.classList.toggle("is-complete", index < currentStep);
    dot.classList.toggle("is-current", index === currentStep);
  });

  if (typeof step.onEnter === "function") step.onEnter();
  target.classList.add("is-highlighted");
  target.scrollIntoView({ behavior: "smooth", block: "center" });
}

function applyFilter(filter) {
  const rows = [...document.querySelectorAll(".risk-row")];
  const filterButtons = [...document.querySelectorAll(".filter-button")];
  let visibleCount = 0;

  rows.forEach((row) => {
    const isVisible = filter === "all" || row.dataset.risk === filter;
    row.classList.toggle("is-hidden", !isVisible);
    if (isVisible) visibleCount += 1;
  });

  filterButtons.forEach((button) => {
    const isSelected = button.dataset.filter === filter;
    button.classList.toggle("is-selected", isSelected);
    if (button.id === "high-risk-filter") {
      button.setAttribute("aria-pressed", String(isSelected));
    }
  });

  const filterNames = { all: "全部", high: "高风险", medium: "中风险", low: "低风险" };
  const filterName = filterNames[filter] || "全部";
  document.querySelector("#result-summary").textContent = `显示${filterName} ${visibleCount} 条模拟风险`;
}

function showRiskDetail(riskId) {
  const detail = riskData.find((risk) => risk.id === riskId);
  if (!detail) return;

  document.querySelector("#risk-detail").classList.remove("is-hidden");
  document.querySelector(".workspace-grid").classList.remove("is-detail-closed");
  selectedRiskId = riskId;
  resetAiAssistant();
  const detailLevel = document.querySelector("#detail-level");
  detailLevel.textContent = detail.level;
  detailLevel.className = `risk-level risk-level--${detail.type}`;
  document.querySelector("#detail-title").textContent = detail.title;
  document.querySelector("#detail-description").textContent = detail.description;
  document.querySelector("#detail-owner").textContent = detail.owner;
  document.querySelector("#detail-due").textContent = detail.due;
  document.querySelector("#detail-impact").textContent = detail.impact;
  document.querySelector("#detail-status").textContent = detail.status;
  document.querySelector("#detail-plan").innerHTML = detail.plan
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  document.querySelectorAll(".risk-row").forEach((row) => {
    row.classList.toggle("is-selected", row.dataset.riskId === riskId);
  });

  const resolveButton = document.querySelector("#resolve-risk");
  const feedback = document.querySelector("#resolve-feedback");
  resolved = detail.status === "已处理";
  resolveButton.disabled = resolved;
  resolveButton.innerHTML = resolved
    ? '<span aria-hidden="true">✓</span> 已处理'
    : '<span aria-hidden="true">✓</span> 标记为已处理';
  feedback.textContent = resolved ? "该风险已在本次演示中处理" : "";
  if (currentStep === guideSteps.length - 1) finishButton.disabled = !resolved;
}

function resetAiAssistant() {
  latestAiPlan = null;
  latestAiRiskId = null;
  const result = document.querySelector("#ai-risk-result");
  result.replaceChildren();
  result.classList.add("is-hidden");
  document.querySelector("#ai-context").value = "";
  const analyzeButton = document.querySelector("#analyze-risk");
  analyzeButton.disabled = false;
  analyzeButton.textContent = "AI 分析当前风险";
}

function createTextElement(tag, text, className = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  if (className) element.className = className;
  return element;
}

function renderAiAsk(data) {
  const container = document.querySelector("#ai-risk-result");
  container.replaceChildren(
    createTextElement("p", "ASK · 还需要补充信息", "ai-result-label"),
    createTextElement("h4", data.reason)
  );
  const list = document.createElement("ul");
  data.questions.forEach((question) => {
    list.append(createTextElement("li", question.question));
  });
  container.append(list);
  container.classList.remove("is-hidden");
}

function renderAiPlan(data) {
  const container = document.querySelector("#ai-risk-result");
  container.replaceChildren(
    createTextElement("p", "PLAN · AI 建议", "ai-result-label"),
    createTextElement("h4", data.summary)
  );

  const meta = document.createElement("div");
  meta.className = "ai-result-meta";
  meta.append(
    createTextElement("span", `建议等级：${data.suggestedLevel}`),
    createTextElement("span", `优先级：${data.priority}`)
  );
  container.append(meta);

  const rationaleTitle = createTextElement("strong", "判断依据");
  const rationaleList = document.createElement("ul");
  data.rationale.forEach((item) => rationaleList.append(createTextElement("li", item)));
  container.append(rationaleTitle, rationaleList, createTextElement("strong", "建议行动"));

  const actionList = document.createElement("ol");
  data.actions.forEach((item) => {
    const row = document.createElement("li");
    row.append(
      document.createTextNode(item.action),
      createTextElement("small", `完成信号：${item.successSignal}`, "ai-success-signal")
    );
    actionList.append(row);
  });
  container.append(actionList);

  const note = createTextElement("p", `注意：${data.cautions.join(" ")}`, "ai-result-note");
  const applyButton = createTextElement("button", "采纳为当前应对计划", "ai-apply-button");
  applyButton.type = "button";
  applyButton.id = "apply-ai-plan";
  applyButton.addEventListener("click", applyAiPlan);
  container.append(note, applyButton);
  container.classList.remove("is-hidden");

  latestAiPlan = data.actions.map((item) => item.action);
  latestAiRiskId = selectedRiskId;
}

function renderAiError(message) {
  const container = document.querySelector("#ai-risk-result");
  container.replaceChildren(
    createTextElement("p", "分析失败", "ai-result-label"),
    createTextElement("p", message)
  );
  container.classList.remove("is-hidden");
}

async function analyzeSelectedRisk() {
  const selectedRisk = riskData.find((risk) => risk.id === selectedRiskId);
  if (!selectedRisk) return;

  const analyzeButton = document.querySelector("#analyze-risk");
  analyzeButton.disabled = true;
  analyzeButton.textContent = "正在分析，请稍候…";
  const container = document.querySelector("#ai-risk-result");
  container.replaceChildren(createTextElement("p", "正在整理风险信息并请求 DeepSeek…"));
  container.classList.remove("is-hidden");

  try {
    const response = await fetch("/api/risks/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        risk: selectedRisk,
        contextNote: document.querySelector("#ai-context").value.trim(),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `分析失败：${response.status}`);
    if (data.decision === "ASK") renderAiAsk(data);
    else if (data.decision === "PLAN") renderAiPlan(data);
    else throw new Error("服务返回了未知结果");
  } catch (error) {
    renderAiError(error.message || "无法连接本地分析服务");
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.textContent = "重新分析当前风险";
  }
}

function applyAiPlan(event) {
  if (!latestAiPlan || latestAiRiskId !== selectedRiskId) return;
  const selectedRisk = riskData.find((risk) => risk.id === selectedRiskId);
  if (!selectedRisk) return;

  selectedRisk.plan = [...latestAiPlan];
  document.querySelector("#detail-plan").innerHTML = selectedRisk.plan
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  event.currentTarget.disabled = true;
  event.currentTarget.textContent = "已采纳（仅本次演示）";
  document.querySelector("#resolve-feedback").textContent = "AI 建议已更新为当前应对计划，风险等级和状态未自动修改";
}

function readNewRiskDraft() {
  const formData = new FormData(document.querySelector("#new-risk-form"));
  return {
    title: String(formData.get("title") || "").trim(),
    description: String(formData.get("description") || "").trim(),
    impact: String(formData.get("impact") || "").trim(),
    owner: String(formData.get("owner") || "").trim(),
    due: String(formData.get("due") || "").trim(),
  };
}

function newRiskFingerprint(draft) {
  const contextNote = document.querySelector("#new-risk-form [name='contextNote']").value.trim();
  return JSON.stringify({ draft, contextNote });
}

function openNewRiskModal() {
  const modal = document.querySelector("#new-risk-modal");
  modal.classList.remove("is-hidden");
  document.body.classList.add("has-modal");
  document.querySelector("#new-risk-title-input").focus();
}

function closeNewRiskModal() {
  const form = document.querySelector("#new-risk-form");
  form.reset();
  latestNewRiskAnalysis = null;
  latestNewRiskFingerprint = null;
  document.querySelector("#new-risk-result").replaceChildren();
  document.querySelector("#new-risk-result").classList.add("is-hidden");
  document.querySelector("#confirm-new-risk").classList.add("is-hidden");
  document.querySelector("#new-risk-modal").classList.add("is-hidden");
  document.body.classList.remove("has-modal");
  document.querySelector("#open-new-risk").focus();
}

function renderNewRiskAsk(data) {
  const container = document.querySelector("#new-risk-result");
  container.replaceChildren(
    createTextElement("p", "ASK · 还需要补充信息", "ai-result-label"),
    createTextElement("h3", data.reason)
  );
  const list = document.createElement("ul");
  data.questions.forEach((question) => list.append(createTextElement("li", question.question)));
  container.append(list);
  container.classList.remove("is-hidden");
  document.querySelector("#confirm-new-risk").classList.add("is-hidden");
}

function renderNewRiskPlan(data) {
  const container = document.querySelector("#new-risk-result");
  container.replaceChildren(
    createTextElement("p", "PLAN · 等待你的确认", "ai-result-label"),
    createTextElement("h3", data.summary)
  );
  const meta = document.createElement("div");
  meta.className = "ai-result-meta";
  meta.append(
    createTextElement("span", `建议等级：${data.suggestedLevel}`),
    createTextElement("span", `优先级：${data.priority}`)
  );
  const actionList = document.createElement("ol");
  data.actions.forEach((item) => {
    const row = document.createElement("li");
    row.append(
      document.createTextNode(item.action),
      createTextElement("small", `完成信号：${item.successSignal}`, "ai-success-signal")
    );
    actionList.append(row);
  });
  container.append(meta, createTextElement("strong", "建议行动"), actionList);
  container.classList.remove("is-hidden");
  document.querySelector("#confirm-new-risk").classList.remove("is-hidden");
}

function renderNewRiskError(message) {
  const container = document.querySelector("#new-risk-result");
  container.replaceChildren(
    createTextElement("p", "操作未完成", "ai-result-label"),
    createTextElement("p", message)
  );
  container.classList.remove("is-hidden");
  document.querySelector("#confirm-new-risk").classList.add("is-hidden");
}

async function analyzeNewRisk(event) {
  event.preventDefault();
  const draft = readNewRiskDraft();
  const fingerprint = newRiskFingerprint(draft);
  const analyzeButton = document.querySelector("#analyze-new-risk");
  const result = document.querySelector("#new-risk-result");
  analyzeButton.disabled = true;
  analyzeButton.textContent = "正在分析，请稍候…";
  document.querySelector("#confirm-new-risk").classList.add("is-hidden");
  result.replaceChildren(createTextElement("p", "正在把你填写的事实交给 DeepSeek 分析…"));
  result.classList.remove("is-hidden");

  const risk = {
    id: "draft-risk",
    title: draft.title,
    description: draft.description,
    level: "待评估",
    impact: draft.impact,
    status: "待处理",
    owner: draft.owner,
    due: draft.due,
    plan: [],
  };

  try {
    const response = await fetch("/api/risks/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        risk,
        contextNote: document.querySelector("#new-risk-form [name='contextNote']").value.trim(),
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `分析失败：${response.status}`);
    latestNewRiskAnalysis = data.decision === "PLAN" ? data : null;
    latestNewRiskFingerprint = data.decision === "PLAN" ? fingerprint : null;
    if (data.decision === "ASK") renderNewRiskAsk(data);
    else if (data.decision === "PLAN") renderNewRiskPlan(data);
    else throw new Error("服务返回了未知结果");
  } catch (error) {
    latestNewRiskAnalysis = null;
    latestNewRiskFingerprint = null;
    renderNewRiskError(error.message || "无法连接本地分析服务");
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.textContent = "重新分析新风险";
  }
}

async function confirmNewRisk() {
  const draft = readNewRiskDraft();
  if (!latestNewRiskAnalysis || latestNewRiskFingerprint !== newRiskFingerprint(draft)) {
    renderNewRiskError("填写内容已经变化，请重新进行 AI 分析后再确认。 ");
    return;
  }

  const confirmButton = document.querySelector("#confirm-new-risk");
  confirmButton.disabled = true;
  confirmButton.textContent = "正在保存…";
  try {
    const response = await fetch("/api/risks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft, analysis: latestNewRiskAnalysis }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `保存失败：${response.status}`);

    riskData.push(data.risk);
    initialRiskData.push(cloneRisks([data.risk])[0]);
    selectedRiskId = data.risk.id;
    renderRiskRows();
    updateRiskCounts();
    applyFilter("all");
    closeNewRiskModal();
    showRiskDetail(data.risk.id);
    document.querySelector("#resolve-feedback").textContent = "新风险已写入本地风险列表（模拟数据）";
  } catch (error) {
    renderNewRiskError(error.message || "新风险无法保存");
  } finally {
    confirmButton.disabled = false;
    confirmButton.textContent = "确认加入风险列表";
  }
}

function resetDemoState() {
  riskData = cloneRisks(initialRiskData);
  selectedRiskId = riskData[0].id;
  resolved = false;
  renderRiskRows();
  updateRiskCounts();
}

function csvCell(value) {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

function exportRiskReport() {
  const headers = ["风险编号", "风险事项", "等级", "责任人", "截止日期", "状态", "影响范围", "应对计划"];
  const rows = riskData.map((risk) => [
    risk.id,
    risk.title,
    risk.level,
    risk.owner,
    risk.due,
    risk.status,
    risk.impact,
    risk.plan.join("；"),
  ]);
  const csv = [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n");
  const blob = new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `SaaSGuide-风险报告-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);

  const button = document.querySelector("#export-report");
  button.textContent = `已导出 ${riskData.length} 条`;
  window.setTimeout(() => { button.textContent = "导出报告"; }, 1800);
}

function closeRiskDetail() {
  document.querySelector("#risk-detail").classList.add("is-hidden");
  document.querySelector(".workspace-grid").classList.add("is-detail-closed");
  document.querySelectorAll(".risk-row").forEach((row) => row.classList.remove("is-selected"));
}

document.querySelectorAll(".filter-button").forEach((button) => {
  button.addEventListener("click", () => applyFilter(button.dataset.filter));
});

nextButton.addEventListener("click", () => {
  if (currentStep < guideSteps.length - 1) {
    currentStep += 1;
    updateGuide();
  }
});

previousButton.addEventListener("click", () => {
  if (currentStep > 0) {
    currentStep -= 1;
    updateGuide();
  }
});

document.querySelector("#resolve-risk").addEventListener("click", (event) => {
  if (resolved) return;
  const selectedRisk = riskData.find((risk) => risk.id === selectedRiskId);
  if (!selectedRisk) return;

  resolved = true;
  selectedRisk.status = "已处理";
  event.currentTarget.disabled = true;
  event.currentTarget.innerHTML = '<span aria-hidden="true">✓</span> 已处理';
  document.querySelector("#resolve-feedback").textContent = "状态已更新（仅在本次演示页面中生效）";
  document.querySelector("#detail-status").textContent = "已处理";
  finishButton.disabled = false;

  const selectedRow = document.querySelector(`[data-risk-id="${selectedRiskId}"]`);
  const status = selectedRow?.querySelector(".status");
  if (status) {
    status.textContent = "已处理";
    status.className = "status status--resolved";
  }
  updateRiskCounts();
});

document.querySelector("#analyze-risk").addEventListener("click", analyzeSelectedRisk);
document.querySelector("#export-report").addEventListener("click", exportRiskReport);
document.querySelector("#close-risk-detail").addEventListener("click", closeRiskDetail);
document.querySelector("#open-new-risk").addEventListener("click", openNewRiskModal);
document.querySelector("#close-new-risk").addEventListener("click", closeNewRiskModal);
document.querySelector("#cancel-new-risk").addEventListener("click", closeNewRiskModal);
document.querySelector("#new-risk-form").addEventListener("submit", analyzeNewRisk);
document.querySelector("#confirm-new-risk").addEventListener("click", confirmNewRisk);
document.querySelector("#new-risk-form").addEventListener("input", () => {
  if (!latestNewRiskAnalysis) return;
  latestNewRiskAnalysis = null;
  latestNewRiskFingerprint = null;
  document.querySelector("#confirm-new-risk").classList.add("is-hidden");
  renderNewRiskError("填写内容已经变化，请重新进行 AI 分析。 ");
});
document.querySelector("#new-risk-modal").addEventListener("click", (event) => {
  if (event.target.id === "new-risk-modal") closeNewRiskModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !document.querySelector("#new-risk-modal").classList.contains("is-hidden")) {
    closeNewRiskModal();
  }
});

finishButton.addEventListener("click", () => {
  document.querySelectorAll(".guide-target.is-highlighted").forEach((element) => {
    element.classList.remove("is-highlighted");
  });
  guideCard.classList.add("is-hidden");
  guideResult.classList.remove("is-hidden");
});

document.querySelector("#exit-guide").addEventListener("click", () => {
  document.querySelectorAll(".guide-target.is-highlighted").forEach((element) => {
    element.classList.remove("is-highlighted");
  });
  guideCard.classList.add("is-hidden");
  guideResult.classList.remove("is-hidden");
  guideResult.querySelector("strong").textContent = "引导已退出";
  guideResult.querySelector("small").textContent = "你可以随时重新开始四步导览";
  guideResult.querySelector("span").textContent = "↩";
});

document.querySelector("#restart-guide").addEventListener("click", () => {
  currentStep = 0;
  guideResult.classList.add("is-hidden");
  guideCard.classList.remove("is-hidden");
  guideResult.querySelector("strong").textContent = "引导已完成";
  guideResult.querySelector("small").textContent = "你已经了解风险处理的完整路径";
  guideResult.querySelector("span").textContent = "✓";
  resetDemoState();
  applyFilter("all");
  showRiskDetail(selectedRiskId);
  updateGuide();
});

async function initializeApp() {
  try {
    await Promise.all([loadGuideData(), loadRiskData()]);
    renderRiskRows();
    applyFilter("all");
    showRiskDetail(selectedRiskId);
    updateRiskCounts();
  } catch (error) {
    showGuideLoadError(error);
  }
}

initializeApp();
