const PAGE_ELEMENTS = {
  riskTotal: "risk-total",
  highRiskFilter: "high-risk-filter",
  riskDetail: "risk-detail",
  resolveRisk: "resolve-risk",
};

const samples = {
  complete: {
    featureName: "项目风险看板引导",
    featureBrief: "帮助项目经理发现、查看并处理当前项目风险。",
    targetUsers: "首次使用风险看板的项目经理",
    entryPoint: "项目详情页的风险看板入口",
    operationSteps: ["查看风险总数", "筛选高风险", "查看风险详情", "标记为已处理"],
    successState: "选中的风险显示为已处理并完成引导",
  },
  ambiguous: {
    featureName: "风险相关功能",
    featureBrief: "做一个大致的风险操作引导。",
    targetUsers: "还不确定",
    entryPoint: "页面里的某个位置",
    operationSteps: ["先看看", "再操作一下"],
    successState: "看起来差不多完成",
  },
};

const fields = {
  featureName: document.querySelector("#feature-name"),
  featureBrief: document.querySelector("#feature-brief"),
  targetUsers: document.querySelector("#target-users"),
  entryPoint: document.querySelector("#entry-point"),
  operationSteps: document.querySelector("#operation-steps"),
  successState: document.querySelector("#success-state"),
};

const form = document.querySelector("#brief-form");
const submitButton = document.querySelector("#submit-brief");
const resultStatus = document.querySelector("#result-status");
const resultEmpty = document.querySelector("#result-empty");
const resultContent = document.querySelector("#result-content");

function loadSample(sample) {
  Object.entries(fields).forEach(([name, field]) => {
    const value = sample[name] ?? "";
    field.value = Array.isArray(value) ? value.join("\n") : value;
  });
}

function collectBrief() {
  return {
    featureName: fields.featureName.value.trim(),
    featureBrief: fields.featureBrief.value.trim(),
    targetUsers: fields.targetUsers.value.trim(),
    entryPoint: fields.entryPoint.value.trim(),
    operationSteps: fields.operationSteps.value
      .split("\n")
      .map((step) => step.trim())
      .filter(Boolean),
    successState: fields.successState.value.trim(),
    pageElements: PAGE_ELEMENTS,
  };
}

function resetResult() {
  resultStatus.textContent = "等待提交";
  resultStatus.className = "result-status";
  resultEmpty.classList.remove("is-hidden");
  resultContent.classList.add("is-hidden");
  resultContent.replaceChildren();
}

function addParagraph(text) {
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  resultContent.append(paragraph);
}

function renderAsk(data) {
  resultStatus.textContent = "ASK · 需要补充";
  resultStatus.className = "result-status is-ask";
  addParagraph(data.reason);

  const list = document.createElement("ol");
  list.className = "question-list";
  data.questions.forEach((item) => {
    const row = document.createElement("li");
    const field = document.createElement("strong");
    field.textContent = item.field;
    row.append(field, document.createTextNode(item.question));
    list.append(row);
  });
  resultContent.append(list);
}

function renderBuild(data) {
  resultStatus.textContent = "BUILD · 已通过校验";
  resultStatus.className = "result-status is-build";
  addParagraph(data.reason);

  const list = document.createElement("div");
  list.className = "step-list";
  data.guide.guideSteps.forEach((step) => {
    const item = document.createElement("article");
    item.className = "step-item";
    const label = document.createElement("span");
    label.textContent = `步骤 ${step.step} · ${step.target}`;
    const title = document.createElement("h3");
    title.textContent = step.title;
    const description = document.createElement("p");
    description.textContent = step.description;
    item.append(label, title, description);
    list.append(item);
  });
  resultContent.append(list);

  if (data.artifacts) {
    const links = document.createElement("div");
    links.className = "artifact-links";
    const preview = document.createElement("a");
    preview.href = data.artifacts.previewUrl;
    preview.target = "_blank";
    preview.rel = "noreferrer";
    preview.textContent = "打开 HTML 预览";
    const jsonLink = document.createElement("a");
    jsonLink.href = data.artifacts.guideUrl;
    jsonLink.target = "_blank";
    jsonLink.rel = "noreferrer";
    jsonLink.textContent = "查看生成 JSON";
    links.append(preview, jsonLink);
    resultContent.append(links);
  }
}

function renderMeta(data) {
  const meta = document.createElement("div");
  meta.className = "meta";
  const usage = data.usage?.total_tokens ? ` · ${data.usage.total_tokens} tokens` : "";
  meta.textContent = `来源：${data.source ?? "未记录"} · 模型：${data.model ?? "未调用"}${usage}`;
  resultContent.append(meta);
}

function renderError(message) {
  resultStatus.textContent = "处理失败";
  resultStatus.className = "result-status is-error";
  addParagraph(message);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.textContent = "正在判断，请稍候…";
  resultEmpty.classList.add("is-hidden");
  resultContent.classList.remove("is-hidden");
  resultContent.replaceChildren();
  resultStatus.textContent = "处理中";
  resultStatus.className = "result-status";

  try {
    const response = await fetch("/api/guides/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectBrief()),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `请求失败：${response.status}`);

    if (data.decision === "ASK") renderAsk(data);
    else if (data.decision === "BUILD") renderBuild(data);
    else throw new Error("服务返回了未知结果");
    renderMeta(data);
  } catch (error) {
    renderError(error.message || "无法连接本地服务");
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "让 DeepSeek 判断";
  }
});

document.querySelector("#load-complete").addEventListener("click", () => loadSample(samples.complete));
document.querySelector("#load-ambiguous").addEventListener("click", () => loadSample(samples.ambiguous));
document.querySelector("#clear-form").addEventListener("click", () => {
  form.reset();
  resetResult();
});

loadSample(samples.complete);
