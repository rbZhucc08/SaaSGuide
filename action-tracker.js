const $ = (selector) => document.querySelector(selector);
let actionDrafts = [];
let activeDraft = null;

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function msg(text, error = false) {
  $("#message").textContent = text;
  $("#message").className = `message${text ? "" : " hidden"}${error ? " error" : ""}`;
}

function render(data) {
  const values = [["行动总数", data.summary.total], ["处理中", data.summary.open], ["已逾期", data.summary.overdue], ["已完成", data.summary.completed]];
  $("#summary").innerHTML = values.map((item) => `<div class="metric"><b>${item[1]}</b><span>${item[0]}</span></div>`).join("");
  const list = $("#actions");
  list.replaceChildren();
  if (!data.actions.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "尚无人工确认的行动。";
    list.append(empty);
    return;
  }
  data.actions.forEach((action) => {
    const card = document.createElement("article");
    card.className = "action";
    card.innerHTML = '<div><b></b><p></p><small></small></div><div><select><option value="">更新状态</option><option value="in_progress">进行中</option><option value="completed">完成</option><option value="open">重新打开</option><option value="cancelled">撤销</option></select></div>';
    card.querySelector("b").textContent = action.title;
    card.querySelector("p").textContent = `${action.owner_role} · 截止 ${action.due_date}${action.overdue ? " · 已逾期" : ""}`;
    card.querySelector("small").textContent = `状态：${action.status} · ${action.action_id} · 风险 ${action.candidate_id}`;
    card.querySelector("select").onchange = async (event) => {
      if (!event.target.value) return;
      try {
        await api(`/api/actions/${action.action_id}/transition`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: event.target.value, actor: $("#actor").value, note: "页面人工更新" }),
        });
        msg("行动状态和审计事件已更新");
        load();
      } catch (error) { msg(error.message, true); }
    };
    list.append(card);
  });
}

async function load() {
  try { render(await api("/api/actions")); }
  catch (error) { msg(error.message, true); }
}

function applyDraft(index) {
  activeDraft = actionDrafts[index] || null;
  if (!activeDraft) return;
  $("#candidate").value = activeDraft.candidate_id || "";
  $("#title").value = activeDraft.title || "";
  $("#owner").value = activeDraft.owner_role || "";
  $("#signal").value = activeDraft.completion_signal || "";
  $("#confirmed").checked = false;
}

function loadDrafts() {
  try { actionDrafts = JSON.parse(sessionStorage.getItem("saasguide.actionDrafts") || "[]"); }
  catch (_error) { actionDrafts = []; }
  if (!Array.isArray(actionDrafts) || !actionDrafts.length) return;
  const select = $("#draft-step");
  select.replaceChildren(...actionDrafts.map((draft, index) => {
    const option = document.createElement("option");
    option.value = index;
    option.textContent = `第 ${draft.plan_step || index + 1} 步 · ${draft.title}`;
    return option;
  }));
  select.onchange = () => applyDraft(Number(select.value));
  $("#draft-banner").classList.remove("hidden");
  applyDraft(0);
}

$("#refresh").onclick = load;
$("#create").onclick = async () => {
  const payload = {
    candidate_id: $("#candidate").value,
    title: $("#title").value,
    owner_role: $("#owner").value,
    due_date: $("#due").value,
    completion_signal: $("#signal").value,
    actor: $("#actor").value,
    human_confirmed: $("#confirmed").checked,
    project_id: activeDraft?.project_id,
    candidate_title: activeDraft?.candidate_title,
    risk_decision_id: activeDraft?.risk_decision_id,
    plan_run_id: activeDraft?.plan_run_id,
    plan_step: activeDraft?.plan_step,
  };
  try {
    await api("/api/actions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    msg("人工确认的行动已保存");
    if (activeDraft) {
      actionDrafts = actionDrafts.filter((item) => item !== activeDraft);
      sessionStorage.setItem("saasguide.actionDrafts", JSON.stringify(actionDrafts));
      if (actionDrafts.length) loadDrafts();
      else {
        $("#draft-banner").classList.add("hidden");
        activeDraft = null;
      }
    }
    load();
  } catch (error) { msg(error.message, true); }
};

loadDrafts();
load();
