/* Plotrix Web UI (local-only)
 * Vanilla JS SPA with hash routing.
 */

function h(tag, attrs, children) {
  const n = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === undefined || v === null) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k === "html") n.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
      else if (k === "value") n.value = v;
      else if (k === "checked") n.checked = !!v;
      else n.setAttribute(k, String(v));
    }
  }
  for (const c of children || []) {
    if (c === null || c === undefined) continue;
    n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return n;
}

function routePath() {
  const r = (location.hash || "#/chat").trim();
  const m = r.match(/^#\/(\w+)/);
  return m ? m[1] : "chat";
}

function nowTs() {
  return Date.now() / 1000;
}

function fmtTime(ts) {
  if (!ts) return "";
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return "";
  }
}

function clampStr(s, n) {
  s = String(s || "");
  if (n <= 3) return s.slice(0, n);
  return s.length > n ? s.slice(0, n - 3) + "..." : s;
}

function safeJsonParse(s) {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

async function api(path, opt) {
  const res = await fetch(path, {
    method: (opt && opt.method) || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(opt && opt.headers ? opt.headers : {}),
    },
    body: opt && opt.body !== undefined ? JSON.stringify(opt.body) : undefined,
  });
  const ct = res.headers.get("content-type") || "";
  const isJson = ct.includes("application/json");
  const data = isJson ? await res.json().catch(() => null) : await res.text().catch(() => "");
  if (!res.ok) {
    const msg = typeof data === "string" ? data : (data && (data.detail || data.error)) || "request failed";
    throw new Error(String(msg));
  }
  return data;
}

const state = {
  route: "chat",
  banner: null, // {kind:'error'|'ok', text}
  configMeta: null,
  config: null,
  redactedSentinel: "__REDACTED__",
  sessions: [],
  currentSessionId: null,
  currentSession: null,
  runId: null,
  es: null,
  assistantDraft: "",
  toolCards: {}, // tool_call_id -> card
  toolOrder: [],
  composing: "",
  dice: { expression: "2d6+1", seed: "", last: null, error: null },
  mcp: { status: null, tools: null, toolsServer: null, error: null },
  configUi: { providerName: null, providerApiKeyTouched: {} },
};

let scheduled = false;

function setBanner(kind, text, ttlMs) {
  state.banner = { kind, text };
  scheduleRender();
  if (ttlMs) {
    setTimeout(() => {
      if (state.banner && state.banner.text === text) {
        state.banner = null;
        scheduleRender();
      }
    }, ttlMs);
  }
}

function scheduleRender() {
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => {
    scheduled = false;
    render();
  });
}

async function ensureConfigLoaded() {
  if (state.config) return;
  const data = await api("/api/config");
  state.configMeta = {
    config_path: data.config_path,
    env_api_key_present: !!data.env_api_key_present,
  };
  state.redactedSentinel = data.redacted_sentinel || "__REDACTED__";
  state.config = data.config;
  if (!state.configUi.providerName) {
    state.configUi.providerName = (state.config && state.config.active_provider) || null;
  }
}

async function loadSessions() {
  const data = await api("/api/sessions");
  state.sessions = (data && data.sessions) || [];
  if (!state.currentSessionId && state.sessions.length) {
    state.currentSessionId = state.sessions[0].id;
  }
}

async function createSession() {
  const data = await api("/api/sessions", { method: "POST", body: {} });
  state.currentSessionId = data.session_id;
  await loadSessions();
  await loadCurrentSession();
}

async function loadCurrentSession() {
  if (!state.currentSessionId) {
    state.currentSession = null;
    return;
  }
  const s = await api(`/api/sessions/${encodeURIComponent(state.currentSessionId)}`);
  state.currentSession = s;
}

function stopRun() {
  if (state.es) {
    try { state.es.close(); } catch {}
    state.es = null;
  }
  if (state.runId) {
    api(`/api/runs/${encodeURIComponent(state.runId)}/cancel`, { method: "POST", body: {} }).catch(() => {});
  }
  state.runId = null;
  state.assistantDraft = "";
  state.toolCards = {};
  state.toolOrder = [];
  scheduleRender();
}

async function resetSession() {
  if (!state.currentSessionId) return;
  stopRun();
  await api(`/api/sessions/${encodeURIComponent(state.currentSessionId)}/reset`, { method: "POST", body: {} });
  await loadCurrentSession();
  setBanner("ok", "Session reset.", 1400);
  scheduleRender();
}

function toolNameFromCall(call) {
  try {
    return String((call.function && call.function.name) || "");
  } catch {
    return "";
  }
}

function argsFromCall(call) {
  try {
    return call.function ? call.function.arguments : null;
  } catch {
    return null;
  }
}

function ensureToolCard(toolCallId, call) {
  const id = String(toolCallId || "");
  if (!id) return;
  if (!state.toolCards[id]) {
    state.toolCards[id] = {
      id,
      status: "queued",
      call: call || null,
      result: null,
      error: null,
      started_at: null,
      ended_at: null,
    };
    state.toolOrder.push(id);
  }
}

function handleStreamEvent(ev) {
  if (!ev || typeof ev !== "object") return;
  if (ev.type === "content_delta") {
    state.assistantDraft += String(ev.delta || "");
    return;
  }
  if (ev.type === "tool_calls" && Array.isArray(ev.tool_calls)) {
    for (const call of ev.tool_calls) {
      if (!call || typeof call !== "object") continue;
      const id = String(call.id || "");
      ensureToolCard(id, call);
    }
  }
}

function handleEventEvent(ev) {
  if (!ev || typeof ev !== "object") return;
  if (ev.type === "mcp_error") {
    setBanner("error", "MCP error: " + String(ev.error || "unknown"));
    return;
  }
  if (ev.type === "assistant_tool_calls" && Array.isArray(ev.tool_calls)) {
    for (const call of ev.tool_calls) {
      if (!call || typeof call !== "object") continue;
      ensureToolCard(String(call.id || ""), call);
    }
    return;
  }
  if (ev.type === "tool_start") {
    const id = String(ev.tool_call_id || "");
    ensureToolCard(id, ev.call);
    const c = state.toolCards[id];
    if (c) {
      c.status = "running";
      c.started_at = nowTs();
    }
    return;
  }
  if (ev.type === "tool_result") {
    const id = String(ev.tool_call_id || "");
    ensureToolCard(id, ev.call);
    const c = state.toolCards[id];
    if (c) {
      c.status = "done";
      c.ended_at = nowTs();
      c.result = ev.content;
    }
    return;
  }
  if (ev.type === "assistant_final") {
    // Some providers finalize without streaming deltas.
    state.assistantDraft = String(ev.content || "");
    return;
  }
}

async function sendMessage(text) {
  text = String(text || "").trim();
  if (!text) return;
  if (!state.currentSessionId) {
    await createSession();
  }
  stopRun();

  // Optimistic local append.
  if (state.currentSession && Array.isArray(state.currentSession.messages)) {
    state.currentSession.messages.push({ role: "user", content: text });
    state.currentSession.updated_at = nowTs();
  }

  state.composing = "";
  state.assistantDraft = "";
  scheduleRender();

  const data = await api(`/api/sessions/${encodeURIComponent(state.currentSessionId)}/message`, {
    method: "POST",
    body: { content: text },
  });
  state.runId = data.run_id;
  scheduleRender();

  const es = new EventSource(`/api/runs/${encodeURIComponent(state.runId)}/events`);
  state.es = es;

  es.addEventListener("event", (evt) => {
    let payload = null;
    try { payload = JSON.parse(evt.data); } catch { return; }
    if (!payload || typeof payload !== "object") return;

    if (payload.type === "stream") {
      handleStreamEvent(payload.event);
    } else if (payload.type === "event") {
      handleEventEvent(payload.event);
    } else if (payload.type === "cancelled") {
      setBanner("warn", "Cancelled.", 1200);
    } else if (payload.type === "error") {
      setBanner("error", String(payload.error || "error"));
    }
    scheduleRender();
  });

  es.addEventListener("hello", () => {});
  es.addEventListener("ping", () => {});

  es.onerror = async () => {
    // If server closed (or network blip), sync session.
    try { es.close(); } catch {}
    state.es = null;
    state.runId = null;
    try {
      await loadSessions();
      await loadCurrentSession();
    } catch {}
    state.assistantDraft = "";
    state.toolCards = {};
    state.toolOrder = [];
    scheduleRender();
  };
}

async function diceRoll() {
  const expr = String(state.dice.expression || "").trim();
  const seed = String(state.dice.seed || "").trim();
  state.dice.error = null;
  state.dice.last = null;
  scheduleRender();
  try {
    const body = { expression: expr };
    if (seed !== "") body.seed = seed;
    const data = await api("/api/dice/roll", { method: "POST", body });
    state.dice.last = data.result;
    scheduleRender();
  } catch (e) {
    state.dice.error = String(e.message || e);
    scheduleRender();
  }
}

async function loadMcpStatus() {
  try {
    const data = await api("/api/mcp/servers");
    state.mcp.status = data.status || {};
  } catch (e) {
    state.mcp.error = String(e.message || e);
  }
}

async function mcpSync(serverName) {
  try {
    const body = serverName ? { server: serverName } : {};
    const data = await api("/api/mcp/sync", { method: "POST", body });
    state.mcp.status = data.status || {};
    setBanner("ok", "MCP synced.", 1000);
  } catch (e) {
    setBanner("error", "MCP sync failed: " + String(e.message || e));
  }
}

async function mcpLoadTools(serverName) {
  state.mcp.tools = null;
  state.mcp.toolsServer = serverName;
  scheduleRender();
  const q = serverName ? `?server=${encodeURIComponent(serverName)}` : "";
  const data = await api(`/api/mcp/tools${q}`);
  state.mcp.tools = data.tools || [];
  scheduleRender();
}

function navItem(label, href, cur) {
  return h("a", { href, class: href === cur ? "active" : "" }, [label]);
}

function renderBanner() {
  if (!state.banner) return null;
  const kind = state.banner.kind;
  const cls = kind === "ok" ? "banner ok" : "banner";
  return h("div", { class: cls }, [
    h("div", { style: "display:flex;justify-content:space-between;gap:10px;" }, [
      h("div", { text: state.banner.text }),
      h("button", { class: "secondary", onclick: () => { state.banner = null; scheduleRender(); } }, ["Dismiss"]),
    ]),
  ]);
}

function renderToolCard(card) {
  const call = card.call || {};
  const tn = toolNameFromCall(call) || "tool";
  const args = argsFromCall(call);
  const argsPretty = typeof args === "string" ? (safeJsonParse(args) ? JSON.stringify(safeJsonParse(args), null, 2) : args) : JSON.stringify(args, null, 2);
  const resultRaw = card.result;
  let resultPretty = "";
  if (typeof resultRaw === "string") {
    const parsed = safeJsonParse(resultRaw);
    resultPretty = parsed ? JSON.stringify(parsed, null, 2) : resultRaw;
  } else if (resultRaw !== null && resultRaw !== undefined) {
    resultPretty = JSON.stringify(resultRaw, null, 2);
  }

  const status = card.status || "queued";
  const cls = `toolcard ${status}`;
  const badgeDot = status === "done" ? "dot ok" : status === "failed" ? "dot bad" : status === "running" ? "dot warn" : "dot";
  const badgeText = status.toUpperCase();

  return h("div", { class: cls }, [
    h("div", { class: "th" }, [
      h("div", {}, [
        h("div", { class: "tn", text: tn }),
        h("div", { class: "mini", text: card.id }),
      ]),
      h("span", { class: "badge" }, [h("span", { class: badgeDot }, []), badgeText]),
    ]),
    h("div", { class: "tb" }, [
      h("details", { open: false }, [
        h("summary", { text: "Arguments" }, []),
        h("pre", {}, [argsPretty || "(none)"])
      ]),
      h("details", { open: false }, [
        h("summary", { text: "Result" }, []),
        h("pre", {}, [resultPretty || "(pending)"])
      ]),
    ]),
  ]);
}

function renderMessage(msg) {
  const role = String(msg.role || "");
  const content = msg.content !== undefined ? String(msg.content || "") : "";
  const meta = role || "message";
  let bubbleClass = "bubble";
  if (role === "user") bubbleClass += " user";
  else if (role === "assistant") bubbleClass += " assistant";
  else if (role === "system") bubbleClass += " system";
  else if (role === "tool") bubbleClass += " system";
  else bubbleClass += "";

  const children = [
    h("div", { class: "meta" }, [
      h("span", { class: "badge" }, [h("span", { class: "dot" }, []), meta]),
      msg.tool_call_id ? h("span", { class: "muted", text: "tool_call_id: " + msg.tool_call_id }, []) : null,
    ]),
    h("div", { class: bubbleClass }, [
      role === "tool" ? h("pre", {}, [content]) : h("div", { class: "mono", text: content }, []),
    ]),
  ];

  // If assistant message has tool_calls (non-stream), render a compact list.
  if (role === "assistant" && Array.isArray(msg.tool_calls) && msg.tool_calls.length) {
    const list = msg.tool_calls.map((c) => {
      const name = toolNameFromCall(c) || "tool";
      const id = String(c.id || "");
      return h("div", { class: "muted", style: "font-family:var(--mono);font-size:12px;" }, [`call ${id}: ${name}`]);
    });
    children.push(h("div", { class: "card", style: "padding:10px;margin-top:6px;" }, list));
  }

  return h("div", { class: "msg" }, children);
}

function renderChatPage() {
  const s = state.currentSession;
  const sessions = state.sessions || [];

  const sessionsList = h("div", {}, sessions.map((it) => {
    const active = it.id === state.currentSessionId;
    return h("div", {
      class: "session-item" + (active ? " active" : ""),
      onclick: async () => {
        stopRun();
        state.currentSessionId = it.id;
        await loadCurrentSession();
        scheduleRender();
      },
    }, [
      h("div", { text: clampStr(it.title || it.id, 26) }),
      h("div", { class: "small", text: `${it.message_count || 0} msgs · ${fmtTime(it.updated_at)}` }),
    ]);
  }));

  const msgNodes = [];
  if (s && Array.isArray(s.messages)) {
    for (const m of s.messages) msgNodes.push(renderMessage(m));
  } else {
    msgNodes.push(h("div", { class: "muted", text: "No session loaded." }, []));
  }

  // Streaming draft
  if (state.runId) {
    msgNodes.push(h("div", { class: "msg" }, [
      h("div", { class: "meta" }, [h("span", { class: "badge" }, [h("span", { class: "dot warn" }, []), "assistant (stream)"])]),
      h("div", { class: "bubble assistant" }, [h("div", { class: "mono", text: state.assistantDraft || "..." }, [])]),
      state.toolOrder.length
        ? h("div", { style: "display:grid;gap:10px;margin-top:8px;" }, state.toolOrder.map((id) => renderToolCard(state.toolCards[id])))
        : null,
    ]));
  }

  const transcript = h("div", { class: "transcript" }, [
    h("div", { class: "messages", id: "chat-messages" }, msgNodes),
    h("div", { class: "composer" }, [
      h("textarea", {
        rows: 4,
        placeholder: "Type a message...",
        value: state.composing,
        oninput: (e) => { state.composing = e.target.value; },
        onkeydown: (e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            sendMessage(state.composing);
          }
        },
      }, []),
      h("div", { class: "actions" }, [
        h("button", { class: "secondary", onclick: () => { location.hash = "#/dice"; } }, ["Roll"]),
        h("button", { class: "secondary", onclick: () => resetSession(), disabled: !state.currentSessionId }, ["Reset"]),
        h("button", { class: "secondary", onclick: () => stopRun(), disabled: !state.runId }, ["Stop"]),
        h("button", { onclick: () => sendMessage(state.composing), disabled: state.runId }, ["Send"]),
      ]),
    ]),
  ]);

  const inspector = h("div", { class: "panel" }, [
    h("div", { class: "ph" }, [
      h("div", { class: "title", text: "Session" }, []),
      h("button", { class: "secondary", onclick: () => createSession() }, ["New"]),
    ]),
    h("div", { class: "pb" }, [
      h("div", { class: "muted", text: state.currentSessionId ? `id: ${state.currentSessionId}` : "no session" }, []),
      h("div", { style: "height:10px;" }, []),
      h("div", { class: "card" }, [
        h("div", { class: "muted", text: "Provider / Model" }, []),
        h("div", { style: "height:8px;" }, []),
        state.config ? renderProviderModelControls() : h("div", { class: "muted", text: "Loading config..." }, []),
      ]),
      h("div", { style: "height:10px;" }, []),
      h("div", { class: "card" }, [
        h("div", { class: "muted", text: "MCP" }, []),
        h("div", { style: "height:8px;" }, []),
        h("button", { class: "secondary", onclick: async () => { await loadMcpStatus(); setBanner("ok", "MCP status refreshed.", 900); scheduleRender(); } }, ["Refresh status"]),
        h("div", { style: "height:8px;" }, []),
        h("button", { onclick: async () => { await mcpSync(null); await loadMcpStatus(); scheduleRender(); } }, ["Sync tools"]),
      ]),
    ]),
  ]);

  return h("div", { class: "chat" }, [
    h("div", { class: "panel" }, [
      h("div", { class: "ph" }, [
        h("div", { class: "title", text: "Sessions" }, []),
        h("button", { class: "secondary", onclick: () => createSession() }, ["New"]),
      ]),
      h("div", { class: "pb" }, [sessionsList]),
    ]),
    transcript,
    inspector,
  ]);
}

function renderProviderModelControls() {
  const cfg = state.config || {};
  const providers = cfg.providers || {};
  const providerNames = Object.keys(providers);
  const active = cfg.active_provider || providerNames[0] || "";

  const providerSelect = h("select", {
    value: active,
    onchange: (e) => {
      cfg.active_provider = e.target.value;
      state.configUi.providerName = e.target.value;
      scheduleRender();
    },
  }, providerNames.map((p) => h("option", { value: p, text: p }, [])));

  const p = providers[active] || {};
  const models = Array.isArray(p.models) ? p.models : [];
  const curModel = p.model || (models.length ? models[0] : "");

  const modelSelect = h("select", {
    value: curModel,
    onchange: (e) => {
      p.model = e.target.value;
      scheduleRender();
    },
  }, [
    ...models.map((m) => h("option", { value: m, text: m }, [])),
    h("option", { value: curModel, text: curModel || "(custom)" }, []),
  ]);

  const saveBtn = h("button", {
    onclick: async () => {
      try {
        await api("/api/config", { method: "PUT", body: cfg });
        setBanner("ok", "Config saved.", 1100);
      } catch (e) {
        setBanner("error", "Save failed: " + String(e.message || e));
      }
    },
  }, ["Save config"]);

  return h("div", { style: "display:grid;gap:10px;" }, [
    h("div", { class: "kv" }, [h("label", { text: "Provider" }, []), providerSelect]),
    h("div", { class: "kv" }, [h("label", { text: "Model" }, []), modelSelect]),
    saveBtn,
  ]);
}

function renderDicePage() {
  const last = state.dice.last;
  return h("div", { style: "height:100%;display:grid;gap:12px;grid-template-rows:auto 1fr;" }, [
    h("div", { class: "card" }, [
      h("div", { class: "row" }, [
        h("div", {}, [
          h("div", { class: "muted", text: "Expression" }, []),
          h("input", { value: state.dice.expression, oninput: (e) => { state.dice.expression = e.target.value; } }, []),
        ]),
        h("div", {}, [
          h("div", { class: "muted", text: "Seed (optional)" }, []),
          h("input", { value: state.dice.seed, oninput: (e) => { state.dice.seed = e.target.value; } }, []),
        ]),
      ]),
      h("div", { style: "height:10px;" }, []),
      h("div", { style: "display:flex;gap:8px;justify-content:flex-end;" }, [
        h("button", { class: "secondary", onclick: () => { location.hash = "#/chat"; } }, ["Back to chat"]),
        h("button", { onclick: () => diceRoll() }, ["Roll"]),
      ]),
      state.dice.error ? h("div", { class: "banner", style: "margin-top:10px;" }, [state.dice.error]) : null,
    ]),
    h("div", { class: "card", style: "overflow:auto;" }, [
      last
        ? h("div", { style: "display:grid;gap:12px;" }, [
            h("div", { style: "display:flex;align-items:baseline;justify-content:space-between;gap:10px;" }, [
              h("div", {}, [
                h("div", { class: "muted", text: "Total" }, []),
                h("div", { style: "font-size:34px;font-weight:700;" , text: String(last.total) }, []),
              ]),
              h("span", { class: "badge" }, [h("span", { class: "dot ok" }, []), String(last.expr || "")]),
            ]),
            h("div", { class: "muted", text: "Result" }, []),
            h("pre", {}, [String(last.text || "")]),
            h("div", { style: "display:flex;gap:8px;justify-content:flex-end;" }, [
              h("button", { class: "secondary", onclick: async () => {
                try {
                  await navigator.clipboard.writeText(String(last.text || ""));
                  setBanner("ok", "Copied.", 800);
                } catch {
                  setBanner("error", "Copy failed.");
                }
              } }, ["Copy"]),
              h("button", { onclick: async () => {
                const t = String(last.text || "");
                location.hash = "#/chat";
                state.composing = t;
                scheduleRender();
              } }, ["Send to chat"]),
            ]),
          ])
        : h("div", { class: "muted", text: "Roll a dice expression to see the breakdown." }, []),
    ]),
  ]);
}

function renderMcpPage() {
  const status = state.mcp.status || {};
  const rows = Object.entries(status);

  const table = h("table", { class: "table" }, [
    h("thead", {}, [
      h("tr", {}, [
        h("th", { text: "Server" }, []),
        h("th", { text: "Enabled" }, []),
        h("th", { text: "Initialized" }, []),
        h("th", { text: "Tools" }, []),
        h("th", { text: "Last sync" }, []),
        h("th", { text: "Actions" }, []),
      ]),
    ]),
    h("tbody", {}, rows.map(([name, s]) => {
      const enabled = !!(s && s.enabled);
      const initialized = !!(s && s.initialized);
      const tools = s && s.tool_count !== undefined && s.tool_count !== null ? String(s.tool_count) : "-";
      const last = s && s.last_sync ? fmtTime(s.last_sync) : "-";
      const err = s && s.last_error ? String(s.last_error) : "";
      return h("tr", {}, [
        h("td", {}, [h("div", { style: "font-family:var(--mono);" , text: name }, []), err ? h("div", { class: "muted", text: clampStr(err, 120) }, []) : null]),
        h("td", {}, [
          h("button", {
            class: "secondary",
            onclick: async () => {
              await ensureConfigLoaded();
              const cfg = state.config;
              if (!cfg.mcp) cfg.mcp = { servers: {} };
              if (!cfg.mcp.servers) cfg.mcp.servers = {};
              if (!cfg.mcp.servers[name]) cfg.mcp.servers[name] = {};
              cfg.mcp.servers[name].enabled = !enabled;
              try {
                await api("/api/config", { method: "PUT", body: cfg });
                await loadMcpStatus();
                setBanner("ok", "Updated.", 900);
              } catch (e) {
                setBanner("error", "Save failed: " + String(e.message || e));
              }
              scheduleRender();
            }
          }, [enabled ? "On" : "Off"]),
        ]),
        h("td", {}, [h("span", { class: "badge" }, [h("span", { class: initialized ? "dot ok" : enabled ? "dot warn" : "dot" }, []), initialized ? "Yes" : "No"]) ]),
        h("td", { text: tools }, []),
        h("td", { text: last }, []),
        h("td", {}, [
          h("button", { class: "secondary", onclick: async () => { await mcpSync(name); await loadMcpStatus(); scheduleRender(); } }, ["Sync"]),
          h("span", { style: "display:inline-block;width:8px;" }, []),
          h("button", { onclick: async () => { await mcpLoadTools(name); } }, ["Tools"]),
        ]),
      ]);
    })),
  ]);

  const toolsDrawer = state.mcp.tools
    ? h("div", { class: "card" }, [
        h("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:10px;" }, [
          h("div", { text: `Tools (${state.mcp.toolsServer || "all"})` }, []),
          h("button", { class: "secondary", onclick: () => { state.mcp.tools = null; scheduleRender(); } }, ["Close"]),
        ]),
        h("div", { style: "height:10px;" }, []),
        h("div", { style: "max-height:360px;overflow:auto;" }, [
          ...state.mcp.tools.map((t) => h("div", { class: "card", style: "margin-bottom:10px;padding:10px;" }, [
            h("div", { style: "font-family:var(--mono);font-size:12px;" , text: t.public_name }, []),
            h("div", { class: "muted", text: t.description || "" }, []),
          ])),
        ]),
      ])
    : null;

  return h("div", { style: "height:100%;display:grid;gap:12px;grid-template-rows:auto 1fr;" }, [
    h("div", { class: "card" }, [
      h("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:10px;" }, [
        h("div", {}, [h("div", { class: "muted", text: "MCP Servers" }, []), h("div", { class: "muted", text: "Local-only status + sync" }, [])]),
        h("div", { style: "display:flex;gap:8px;" }, [
          h("button", { class: "secondary", onclick: async () => { await loadMcpStatus(); setBanner("ok", "Refreshed.", 800); scheduleRender(); } }, ["Refresh"]),
          h("button", { onclick: async () => { await mcpSync(null); await loadMcpStatus(); scheduleRender(); } }, ["Sync all"]),
        ]),
      ]),
      state.mcp.error ? h("div", { class: "banner", style: "margin-top:10px;" }, [state.mcp.error]) : null,
    ]),
    h("div", { class: "grid-2" }, [
      h("div", { class: "card", style: "overflow:auto;" }, [table]),
      toolsDrawer || h("div", { class: "card" }, [h("div", { class: "muted", text: "Select a server and click Tools." }, [])]),
    ]),
  ]);
}

function renderConfigPage() {
  const cfg = state.config;
  if (!cfg) {
    return h("div", { class: "card" }, [h("div", { class: "muted", text: "Loading config..." }, [])]);
  }

  const providers = cfg.providers || {};
  const names = Object.keys(providers);
  const active = cfg.active_provider || names[0] || "";
  const p = providers[active] || {};

  const touched = !!state.configUi.providerApiKeyTouched[active];
  const apiKeyValue = touched ? (p.api_key === state.redactedSentinel ? "" : (p.api_key || "")) : "";
  const apiKeyPlaceholder = p.api_key === state.redactedSentinel ? "Saved (redacted)" : "";

  const providerEditor = h("div", { class: "card" }, [
    h("div", { class: "muted", text: "Provider" }, []),
    h("div", { style: "height:10px;" }, []),
    h("div", { class: "kv" }, [
      h("label", { text: "Active" }, []),
      h("select", {
        value: active,
        onchange: (e) => { cfg.active_provider = e.target.value; scheduleRender(); },
      }, names.map((n) => h("option", { value: n, text: n }, []))),
    ]),
    h("div", { style: "height:10px;" }, []),
    h("div", { class: "kv" }, [h("label", { text: "Base URL" }, []), h("input", { value: p.base_url || "", oninput: (e) => { p.base_url = e.target.value; } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: "API key" }, []), h("input", {
      type: "password",
      placeholder: apiKeyPlaceholder,
      value: apiKeyValue,
      oninput: (e) => {
        state.configUi.providerApiKeyTouched[active] = true;
        const v = e.target.value;
        p.api_key = v ? v : state.redactedSentinel;
      },
    }, [])]),
    h("div", { class: "kv" }, [h("label", { text: "Model" }, []), h("input", { value: p.model || "", oninput: (e) => { p.model = e.target.value; } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: "Models (one per line)" }, []), h("textarea", { rows: 3, class: "mono", value: (Array.isArray(p.models) ? p.models.join("\n") : ""), oninput: (e) => { p.models = e.target.value.split(/\r?\n/).map((x) => x.trim()).filter(Boolean); } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: "Timeout (s)" }, []), h("input", { value: String(p.timeout_s ?? ""), oninput: (e) => { const n = parseFloat(e.target.value); p.timeout_s = isFinite(n) ? n : p.timeout_s; } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: "Verify TLS" }, []), h("select", { value: String(!!p.verify_tls), onchange: (e) => { p.verify_tls = e.target.value === "true"; } }, [
      h("option", { value: "true", text: "true" }, []),
      h("option", { value: "false", text: "false" }, []),
    ])]),
    h("div", { class: "kv" }, [h("label", { text: "Extra headers (JSON)" }, []), h("textarea", {
      rows: 4,
      class: "mono",
      value: JSON.stringify(p.extra_headers || {}, null, 2),
      oninput: (e) => {
        const parsed = safeJsonParse(e.target.value);
        if (parsed && typeof parsed === "object") p.extra_headers = parsed;
      },
    }, [])]),
  ]);

  const chat = cfg.chat || (cfg.chat = {});
  const chatEditor = h("div", { class: "card" }, [
    h("div", { class: "muted", text: "Chat defaults" }, []),
    h("div", { style: "height:10px;" }, []),
    h("div", { class: "kv" }, [h("label", { text: "System prompt" }, []), h("textarea", { rows: 6, value: chat.system_prompt || "", oninput: (e) => { chat.system_prompt = e.target.value; } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: "Temperature" }, []), h("input", { value: String(chat.temperature ?? ""), oninput: (e) => { const n = parseFloat(e.target.value); chat.temperature = isFinite(n) ? n : chat.temperature; } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: "Stream" }, []), h("select", { value: String(!!chat.stream), onchange: (e) => { chat.stream = e.target.value === "true"; } }, [
      h("option", { value: "true", text: "true" }, []),
      h("option", { value: "false", text: "false" }, []),
    ])]),
    h("div", { class: "kv" }, [h("label", { text: "Enable tool roll" }, []), h("select", { value: String(!!chat.enable_tool_roll), onchange: (e) => { chat.enable_tool_roll = e.target.value === "true"; } }, [
      h("option", { value: "true", text: "true" }, []),
      h("option", { value: "false", text: "false" }, []),
    ])]),
  ]);

  const mcpEditor = h("div", { class: "card" }, [
    h("div", { class: "muted", text: "MCP servers (raw)" }, []),
    h("div", { style: "height:10px;" }, []),
    h("textarea", {
      rows: 12,
      class: "mono",
      value: JSON.stringify((cfg.mcp && cfg.mcp.servers) || {}, null, 2),
      oninput: (e) => {
        const parsed = safeJsonParse(e.target.value);
        if (parsed && typeof parsed === "object") {
          if (!cfg.mcp) cfg.mcp = {};
          cfg.mcp.servers = parsed;
        }
      },
    }, []),
  ]);

  const meta = state.configMeta || {};
  return h("div", { style: "height:100%;display:grid;gap:12px;grid-template-rows:auto 1fr;" }, [
    h("div", { class: "card" }, [
      h("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:10px;" }, [
        h("div", {}, [
          h("div", { class: "muted", text: "Config" }, []),
          h("div", { class: "muted", text: meta.config_path ? `Path: ${meta.config_path}` : "" }, []),
          meta.env_api_key_present ? h("div", { class: "muted", text: "Note: env API key is present and may override config." }, []) : null,
        ]),
        h("div", { style: "display:flex;gap:8px;" }, [
          h("button", { class: "secondary", onclick: async () => { state.config = null; await ensureConfigLoaded(); setBanner("ok", "Reloaded.", 800); scheduleRender(); } }, ["Reload"]),
          h("button", { onclick: async () => {
            try {
              await api("/api/config", { method: "PUT", body: cfg });
              setBanner("ok", "Saved.", 1000);
            } catch (e) {
              setBanner("error", "Save failed: " + String(e.message || e));
            }
          } }, ["Save"]),
        ]),
      ]),
    ]),
    h("div", { class: "grid-2", style: "overflow:auto;" }, [
      h("div", { style: "display:grid;gap:12px;" }, [providerEditor, chatEditor]),
      h("div", { style: "display:grid;gap:12px;" }, [mcpEditor]),
    ]),
  ]);
}

function renderHistoryPage() {
  const items = state.sessions || [];
  const current = state.currentSession;
  return h("div", { class: "grid-2", style: "height:100%;" }, [
    h("div", { class: "card", style: "overflow:auto;" }, [
      h("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:10px;" }, [
        h("div", { class: "muted", text: "Sessions (in-memory)" }, []),
        h("button", { class: "secondary", onclick: async () => { await loadSessions(); scheduleRender(); } }, ["Refresh"]),
      ]),
      h("div", { style: "height:10px;" }, []),
      ...items.map((it) => h("div", {
        class: "session-item" + (it.id === state.currentSessionId ? " active" : ""),
        onclick: async () => {
          stopRun();
          state.currentSessionId = it.id;
          await loadCurrentSession();
          scheduleRender();
        },
      }, [
        h("div", { text: clampStr(it.title || it.id, 34) }, []),
        h("div", { class: "small", text: `${it.message_count || 0} msgs · ${fmtTime(it.updated_at)}` }, []),
      ])),
    ]),
    h("div", { class: "card", style: "overflow:auto;" }, [
      current
        ? h("div", {}, [
            h("div", { class: "muted", text: current.title || current.id }, []),
            h("div", { class: "muted", text: `Updated: ${fmtTime(current.updated_at)}` }, []),
            h("div", { style: "height:10px;" }, []),
            ...(Array.isArray(current.messages) ? current.messages.map(renderMessage) : []),
          ])
        : h("div", { class: "muted", text: "Select a session." }, []),
    ]),
  ]);
}

function renderPage() {
  if (state.route === "chat") return renderChatPage();
  if (state.route === "dice") return renderDicePage();
  if (state.route === "mcp") return renderMcpPage();
  if (state.route === "config") return renderConfigPage();
  if (state.route === "history") return renderHistoryPage();
  return h("div", { class: "card" }, [h("div", { class: "muted", text: "Not found." }, [])]);
}

function render() {
  state.route = routePath();
  const app = document.getElementById("app");

  const navItems = [
    ["Chat", "#/chat"],
    ["Dice", "#/dice"],
    ["MCP", "#/mcp"],
    ["Config", "#/config"],
    ["History", "#/history"],
  ];
  const cur = `#/${state.route}`;

  // Preserve transcript scroll if possible.
  const oldMsgs = document.getElementById("chat-messages");
  let wasNearBottom = false;
  if (oldMsgs) {
    const remaining = oldMsgs.scrollHeight - oldMsgs.scrollTop - oldMsgs.clientHeight;
    wasNearBottom = remaining < 80;
  }

  app.innerHTML = "";

  const nav = h("div", { class: "nav" }, [
    h("div", { class: "brand" }, [
      h("div", { class: "mark", text: "Plotrix" }, []),
      h("span", { class: "pill", text: "local" }, []),
    ]),
    ...navItems.map(([label, href]) => navItem(label, href, cur)),
    h("div", { class: "muted", style: "margin-top:12px;font-size:12px;" , text: "Local-only Web UI"}),
  ]);

  const topRight = [];
  if (state.config && state.config.active_provider) {
    topRight.push(h("span", { class: "badge" }, [h("span", { class: "dot" }, []), String(state.config.active_provider)]));
  }
  const main = h("div", { class: "main" }, [
    h("div", { class: "topbar" }, [
      h("div", { text: state.route.toUpperCase() }, []),
      h("div", { style: "display:flex;gap:8px;align-items:center;" }, topRight),
    ]),
    h("div", { class: "content" }, [
      renderBanner(),
      renderPage(),
    ]),
  ]);

  app.appendChild(h("div", { class: "shell" }, [nav, main]));

  const newMsgs = document.getElementById("chat-messages");
  if (newMsgs && wasNearBottom) {
    newMsgs.scrollTop = newMsgs.scrollHeight;
  }
}

async function boot() {
  try {
    await ensureConfigLoaded();
  } catch (e) {
    setBanner("error", "Failed to load config: " + String(e.message || e));
  }
  try {
    await loadSessions();
    if (!state.currentSessionId) {
      await createSession();
    } else {
      await loadCurrentSession();
    }
  } catch (e) {
    setBanner("error", "Failed to load sessions: " + String(e.message || e));
  }
  try {
    await loadMcpStatus();
  } catch {}
  render();
}

window.addEventListener("hashchange", () => {
  scheduleRender();
});

boot();
