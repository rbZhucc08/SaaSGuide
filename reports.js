const $ = (selector) => document.querySelector(selector);
function cell(value) { const item = document.createElement("td"); item.textContent = value ?? "—"; return item; }
async function load() {
  try {
    const response = await fetch("/api/reports/weekly"); const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    $("#period").textContent = `${data.period} · 截至 ${data.as_of}`;
    const m=data.metrics; const values=[["候选风险",m.risk_total],["高风险",m.high_risk],["已确认",m.confirmed],["误报率",`${(m.false_positive_rate*100).toFixed(1)}%`],["逾期行动",m.overdue_actions],["平均处理小时",m.average_resolution_hours??"—"]];
    $("#metrics").innerHTML=values.map((item)=>`<div class="metric"><b>${item[1]}</b><span>${item[0]}</span></div>`).join("");
    const trend=$("#trend");trend.replaceChildren();
    if(data.trend.length)data.trend.forEach((item)=>{const bar=document.createElement("div");bar.className="bar";const number=document.createElement("b");number.textContent=item.new_risks;const column=document.createElement("i");column.style.setProperty("--v",item.new_risks);const label=document.createElement("span");label.textContent=item.date.slice(5);bar.append(number,column,label);trend.append(bar)});
    else{const empty=document.createElement("p");empty.className="report-empty";empty.textContent="尚无人工风险决策，因此不生成固定趋势。";trend.append(empty)}
    $("#draft").textContent=data.report_draft;const actions=$("#actions");actions.replaceChildren();
    if(data.actions.length)data.actions.forEach((item)=>{const row=document.createElement("tr");row.append(cell(item.title),cell(item.owner_role),cell(item.due_date),cell(item.status));actions.append(row)});
    else{const row=document.createElement("tr");const empty=cell("尚无人工确认的行动");empty.colSpan=4;empty.className="empty-cell";row.append(empty);actions.append(row)}
  }catch(error){$("#message").textContent=error.message;$("#message").className="message error"}
}
load();
