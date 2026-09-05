let importPreview = null;

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
  previewSummary.textContent = `${data.source.source_name} · ${data.source.sheet_name} · ${summary.task_count} 条任务 · ${summary.dependency_count} 条依赖 · ${summary.error_count} 个错误${data.preview_truncated ? " · 仅显示前 20 行" : ""}`;
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
