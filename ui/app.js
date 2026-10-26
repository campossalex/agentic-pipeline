// AAIF Agent Stack UI: talks to the agent's Open Responses endpoint (/v1/responses, SSE)
// and renders `aaif.trace` extension events in the trace panel.
const $ = (sel) => document.querySelector(sel);
const state = { previousResponseId: null, busy: false };

// ---------------------------------------------------------------- sidebar
async function loadInfo() {
  let info;
  try {
    info = await (await fetch("/api/info")).json();
  } catch (err) {
    $("#tools").innerHTML = `<p class="warn">Agent not reachable: ${escapeHtml(String(err))}</p>`;
    return;
  }
  const select = $("#model");
  select.innerHTML = info.models
    .map((m) => `<option ${m === info.default_model ? "selected" : ""}>${escapeHtml(m)}</option>`)
    .join("");

  $("#skills").innerHTML = info.skills
    .map((s) => `<li><strong>${escapeHtml(s.name)}</strong><span>${escapeHtml(s.description)}</span></li>`)
    .join("") || "<li><span>No skills installed</span></li>";

  const groups = {};
  for (const t of info.tools) {
    const server = t.name.split("_")[0];
    (groups[server] ||= []).push(t);
  }
  $("#tools").innerHTML =
    (info.mcp_error ? `<p class="warn">MCP gateway error: ${escapeHtml(info.mcp_error)}</p>` : "") +
    Object.entries(groups)
      .map(([server, tools]) => `<details class="tool-group"><summary>${escapeHtml(server)} (${tools.length})</summary>` +
        tools.map((t) => `<code title="${escapeHtml(t.description)}">${escapeHtml(t.name)}</code>`).join("") +
        "</details>")
      .join("");
}

// ---------------------------------------------------------------- chat
function addMessage(role, html, extraClass = "") {
  $("#empty")?.remove();
  const el = document.createElement("div");
  el.className = `msg ${role} ${extraClass}`;
  el.innerHTML = html;
  $("#messages").appendChild(el);
  el.scrollIntoView({ block: "end" });
  return el;
}

function addChip(text) {
  const el = document.createElement("div");
  el.className = "tool-chip";
  el.textContent = text;
  $("#messages").appendChild(el);
}

function addTrace(trace) {
  const li = document.createElement("li");
  li.className = `${trace.layer} ${trace.status === "error" ? "error" : ""}`;
  const detail = trace.detail == null ? "" :
    `<details><summary>details</summary><pre>${escapeHtml(
      typeof trace.detail === "string" ? trace.detail : JSON.stringify(trace.detail, null, 2))}</pre></details>`;
  li.innerHTML = `<span class="layer">${escapeHtml(trace.layer)}</span><span class="title">${escapeHtml(trace.title)}</span>${detail}`;
  $("#trace").appendChild(li);
  li.scrollIntoView({ block: "end" });
}

async function send(text) {
  if (state.busy || !text.trim()) return;
  state.busy = true;
  $("#send").disabled = true;
  addMessage("user", escapeHtml(text));
  const sep = document.createElement("li");
  sep.className = "turn-sep";
  sep.textContent = `— ${text.slice(0, 60)}${text.length > 60 ? "…" : ""}`;
  $("#trace").appendChild(sep);
  const thinking = addMessage("thinking", "Working…");

  try {
    const resp = await fetch("/v1/responses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: $("#model").value,
        input: text,
        previous_response_id: state.previousResponseId,
        stream: true,
      }),
    });
    if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
    await readSSE(resp.body, (type, data) => handleEvent(type, data, thinking));
  } catch (err) {
    addMessage("assistant", escapeHtml(String(err)), "error");
  } finally {
    thinking.remove();
    state.busy = false;
    $("#send").disabled = false;
  }
}

function handleEvent(type, data, thinking) {
  if (type === "aaif.trace") {
    addTrace(data.trace);
  } else if (type === "response.output_item.done") {
    const item = data.item;
    if (item.type === "message") {
      addMessage("assistant", renderMarkdown(item.content.map((c) => c.text || "").join("")));
    } else if (item.type === "function_call") {
      addChip(`→ ${item.name}`);
    }
    $("#messages").appendChild(thinking);
  } else if (type === "response.completed") {
    state.previousResponseId = data.response.id;
  } else if (type === "response.failed") {
    addMessage("assistant", escapeHtml(data.response.error?.message || "Agent failed"), "error");
  }
}

async function readSSE(body, onEvent) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let type = "message", data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) type = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data) onEvent(type, JSON.parse(data));
    }
  }
}

// ---------------------------------------------------------------- tiny markdown
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function inline(s) {
  return escapeHtml(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

function renderMarkdown(md) {
  const out = [];
  const lines = md.replace(/\r/g, "").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      const code = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      i++;
      out.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
    } else if (/^\s*\|.*\|\s*$/.test(line)) {
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
      const cells = (r) => r.trim().slice(1, -1).split("|").map((c) => c.trim());
      const body = rows.filter((r) => !/^\s*\|[\s:|-]+\|\s*$/.test(r));
      out.push("<table>" + body.map((r, n) =>
        "<tr>" + cells(r).map((c) => n === 0 ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`).join("") + "</tr>").join("") + "</table>");
    } else if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ""));
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>${items.map((it) => `<li>${inline(it)}</li>`).join("")}</${tag}>`);
    } else if (/^#{1,6}\s/.test(line)) {
      const level = Math.min(line.match(/^#+/)[0].length + 2, 6);
      out.push(`<h${level}>${inline(line.replace(/^#+\s*/, ""))}</h${level}>`);
      i++;
    } else if (line.trim() === "") {
      i++;
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() !== "" && !/^(```|#{1,6}\s|\s*([-*]|\d+\.)\s|\s*\|)/.test(lines[i])) para.push(lines[i++]);
      out.push(`<p>${inline(para.join(" "))}</p>`);
    }
  }
  return out.join("");
}

// ---------------------------------------------------------------- wiring
$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#prompt").value;
  $("#prompt").value = "";
  send(text);
});
$("#prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("#composer").requestSubmit();
  }
});
document.querySelectorAll(".suggestion").forEach((b) => b.addEventListener("click", () => send(b.textContent)));
$("#new-chat").addEventListener("click", () => {
  state.previousResponseId = null;
  $("#messages").innerHTML = "";
  $("#trace").innerHTML = "";
});
loadInfo();
