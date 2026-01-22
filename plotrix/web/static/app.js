/* Plotrix Web UI (local-only)
 * Vanilla JS SPA with hash routing.
 * Theme + i18n (en/zh) persisted in localStorage.
 */

const STORAGE_THEME = "plotrix_theme"; // "dark" | "light" (absence => system)
const STORAGE_LANG = "plotrix_lang"; // "en" | "zh" (absence => auto)

const I18N = {
  en: {
    "app.name": "Plotrix",
    "app.local": "local",
    "app.local_hint": "Local-only Web UI",

    "nav.chat": "Chat",
    "nav.dice": "Dice",
    "nav.mcp": "MCP",
    "nav.config": "Config",
    "nav.history": "History",

    "page.chat": "Chat",
    "page.dice": "Dice",
    "page.mcp": "MCP",
    "page.config": "Config",
    "page.history": "History",

    "ui.theme": "Theme",
    "ui.theme.dark": "Dark",
    "ui.theme.light": "Light",
    "ui.lang": "Lang",
    "ui.lang.en": "EN",
    "ui.lang.zh": "ZH",

    "common.dismiss": "Dismiss",
    "common.close": "Close",
    "common.refresh": "Refresh",
    "common.reload": "Reload",
    "common.save": "Save",
    "common.tool_call_id": "tool_call_id: {id}",
    "common.updated": "Updated.",
    "common.loading": "Loading...",
    "common.not_found": "Not found.",

    "chat.sessions": "Sessions",
    "chat.session": "Session",
    "chat.new": "New",
    "chat.no_session": "No session loaded.",
    "chat.no_session_short": "no session",
    "chat.id": "id: {id}",
    "chat.message_placeholder": "Type a message...",
    "chat.send": "Send",
    "chat.stop": "Stop",
    "chat.reset": "Reset",
    "chat.roll": "Roll",
    "chat.provider_model": "Provider / Model",
    "chat.loading_config": "Loading config...",
    "chat.session_meta": "{count} msgs · {time}",
    "chat.assistant_stream": "assistant (stream)",

    "role.user": "user",
    "role.assistant": "assistant",
    "role.system": "system",
    "role.tool": "tool",
    "role.message": "message",

    "tool.arguments": "Arguments",
    "tool.result": "Result",
    "tool.none": "(none)",
    "tool.pending": "(pending)",
    "tool.call": "call {id}: {name}",
    "tool.status.queued": "QUEUED",
    "tool.status.running": "RUNNING",
    "tool.status.done": "DONE",
    "tool.status.failed": "FAILED",

    "dice.expression": "Expression",
    "dice.seed": "Seed (optional)",
    "dice.back": "Back to chat",
    "dice.total": "Total",
    "dice.result": "Result",
    "dice.copy": "Copy",
    "dice.send": "Send to chat",
    "dice.breakdown_hint": "Roll a dice expression to see the breakdown.",

    "mcp.title": "MCP Servers",
    "mcp.subtitle": "Local-only status + sync",
    "mcp.sync_all": "Sync all",
    "mcp.sync": "Sync",
    "mcp.tools": "Tools",
    "mcp.tools_title": "Tools ({server})",
    "mcp.pick_tools": "Select a server and click Tools.",
    "mcp.server": "Server",
    "mcp.enabled": "Enabled",
    "mcp.initialized": "Initialized",
    "mcp.tool_count": "Tools",
    "mcp.last_sync": "Last sync",
    "mcp.actions": "Actions",
    "mcp.on": "On",
    "mcp.off": "Off",
    "mcp.yes": "Yes",
    "mcp.no": "No",

    "config.title": "Config",
    "config.path": "Path: {path}",
    "config.env_override": "Note: env API key is present and may override config.",
    "config.provider": "Provider",
    "config.active": "Active",
    "config.base_url": "Base URL",
    "config.api_key": "API key",
    "config.saved_redacted": "Saved (redacted)",
    "config.model": "Model",
    "config.models": "Models (one per line)",
    "config.custom": "(custom)",
    "config.timeout": "Timeout (s)",
    "config.verify_tls": "Verify TLS",
    "config.extra_headers": "Extra headers (JSON)",
    "config.chat_defaults": "Chat defaults",
    "config.system_prompt": "System prompt",
    "config.temperature": "Temperature",
    "config.stream": "Stream",
    "config.enable_tool_roll": "Enable tool roll",
    "config.mcp_servers_raw": "MCP servers (raw)",

    "history.title": "Sessions (in-memory)",
    "history.updated": "Updated: {time}",
    "history.select": "Select a session.",

    "banner.session_reset": "Session reset.",
    "banner.cancelled": "Cancelled.",
    "banner.copied": "Copied.",
    "banner.copy_failed": "Copy failed.",
    "banner.config_saved": "Config saved.",
    "banner.reloaded": "Reloaded.",
    "banner.saved": "Saved.",
    "banner.mcp_synced": "MCP synced.",
    "banner.mcp_status_refreshed": "MCP status refreshed.",

    "error.request_failed": "Request failed: {msg}",
    "error.save_failed": "Save failed: {msg}",
    "error.mcp_sync_failed": "MCP sync failed: {msg}",
    "error.mcp_error": "MCP error: {msg}",
    "error.load_config": "Failed to load config: {msg}",
    "error.load_sessions": "Failed to load sessions: {msg}",
  },
  zh: {
    "app.name": "Plotrix",
    "app.local": "本机",
    "app.local_hint": "仅本机 Web UI",

    "nav.chat": "聊天",
    "nav.dice": "骰子",
    "nav.mcp": "MCP",
    "nav.config": "配置",
    "nav.history": "历史",

    "page.chat": "聊天",
    "page.dice": "骰子",
    "page.mcp": "MCP",
    "page.config": "配置",
    "page.history": "历史",

    "ui.theme": "主题",
    "ui.theme.dark": "深色",
    "ui.theme.light": "浅色",
    "ui.lang": "语言",
    "ui.lang.en": "英",
    "ui.lang.zh": "中",

    "common.dismiss": "关闭",
    "common.close": "关闭",
    "common.refresh": "刷新",
    "common.reload": "重载",
    "common.save": "保存",
    "common.tool_call_id": "tool_call_id: {id}",
    "common.updated": "已更新。",
    "common.loading": "加载中...",
    "common.not_found": "未找到。",

    "chat.sessions": "会话",
    "chat.session": "当前会话",
    "chat.new": "新建",
    "chat.no_session": "未加载会话。",
    "chat.no_session_short": "无会话",
    "chat.id": "ID: {id}",
    "chat.message_placeholder": "输入消息...",
    "chat.send": "发送",
    "chat.stop": "停止",
    "chat.reset": "重置",
    "chat.roll": "掷骰",
    "chat.provider_model": "Provider / Model",
    "chat.loading_config": "加载配置...",
    "chat.session_meta": "{count} 条 · {time}",
    "chat.assistant_stream": "助手 (流式)",

    "role.user": "你",
    "role.assistant": "助手",
    "role.system": "系统",
    "role.tool": "工具",
    "role.message": "消息",

    "tool.arguments": "参数",
    "tool.result": "结果",
    "tool.none": "(无)",
    "tool.pending": "(等待中)",
    "tool.call": "调用 {id}: {name}",
    "tool.status.queued": "排队",
    "tool.status.running": "运行中",
    "tool.status.done": "完成",
    "tool.status.failed": "失败",

    "dice.expression": "表达式",
    "dice.seed": "Seed (可选)",
    "dice.back": "返回聊天",
    "dice.total": "总计",
    "dice.result": "结果",
    "dice.copy": "复制",
    "dice.send": "发送到聊天",
    "dice.breakdown_hint": "掷骰后会显示拆解过程。",

    "mcp.title": "MCP 服务器",
    "mcp.subtitle": "仅本机状态与同步",
    "mcp.sync_all": "全部同步",
    "mcp.sync": "同步",
    "mcp.tools": "工具",
    "mcp.tools_title": "工具 ({server})",
    "mcp.pick_tools": "选择服务器后点击“工具”。",
    "mcp.server": "服务器",
    "mcp.enabled": "启用",
    "mcp.initialized": "初始化",
    "mcp.tool_count": "工具数",
    "mcp.last_sync": "上次同步",
    "mcp.actions": "操作",
    "mcp.on": "开",
    "mcp.off": "关",
    "mcp.yes": "是",
    "mcp.no": "否",

    "config.title": "配置",
    "config.path": "路径: {path}",
    "config.env_override": "提示: 检测到环境变量 API key，可能会覆盖配置文件。",
    "config.provider": "Provider",
    "config.active": "当前",
    "config.base_url": "Base URL",
    "config.api_key": "API key",
    "config.saved_redacted": "已保存 (脱敏)",
    "config.model": "模型",
    "config.models": "模型列表 (每行一个)",
    "config.custom": "(自定义)",
    "config.timeout": "超时 (秒)",
    "config.verify_tls": "验证 TLS",
    "config.extra_headers": "额外请求头 (JSON)",
    "config.chat_defaults": "聊天默认值",
    "config.system_prompt": "系统提示词",
    "config.temperature": "温度",
    "config.stream": "流式",
    "config.enable_tool_roll": "允许工具掷骰",
    "config.mcp_servers_raw": "MCP servers (raw)",

    "history.title": "会话 (仅内存)",
    "history.updated": "更新时间: {time}",
    "history.select": "选择一个会话查看详情。",

    "banner.session_reset": "会话已重置。",
    "banner.cancelled": "已取消。",
    "banner.copied": "已复制。",
    "banner.copy_failed": "复制失败。",
    "banner.config_saved": "配置已保存。",
    "banner.reloaded": "已重载。",
    "banner.saved": "已保存。",
    "banner.mcp_synced": "MCP 已同步。",
    "banner.mcp_status_refreshed": "MCP 状态已刷新。",

    "error.request_failed": "请求失败: {msg}",
    "error.save_failed": "保存失败: {msg}",
    "error.mcp_sync_failed": "MCP 同步失败: {msg}",
    "error.mcp_error": "MCP 错误: {msg}",
    "error.load_config": "加载配置失败: {msg}",
    "error.load_sessions": "加载会话失败: {msg}",
  },
};

function detectLang() {
  const lang = (navigator.language || "en").toLowerCase();
  return lang.startsWith("zh") ? "zh" : "en";
}

function getStoredLang() {
  const v = localStorage.getItem(STORAGE_LANG);
  return v === "zh" || v === "en" ? v : null;
}

function setStoredLang(lang) {
  localStorage.setItem(STORAGE_LANG, lang);
}

function detectTheme() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getStoredTheme() {
  const v = localStorage.getItem(STORAGE_THEME);
  return v === "dark" || v === "light" ? v : null;
}

function setStoredTheme(theme) {
  localStorage.setItem(STORAGE_THEME, theme);
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
}

function applyLang(lang) {
  document.documentElement.lang = lang;
}

function t(key, vars) {
  const lang = state.ui.lang;
  const dict = I18N[lang] || I18N.en;
  let s = dict[key] || I18N.en[key] || key;
  if (vars && typeof vars === "object") {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(new RegExp("\\{" + k + "\\}", "g"), String(v));
    }
  }
  return s;
}

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
  banner: null, // {kind, text}
  configMeta: null,
  config: null,
  redactedSentinel: "__REDACTED__",
  sessions: [],
  currentSessionId: null,
  currentSession: null,
  runId: null,
  es: null,
  assistantDraft: "",
  toolCards: {},
  toolOrder: [],
  composing: "",
  dice: { expression: "2d6+1", seed: "", last: null, error: null },
  mcp: { status: null, tools: null, toolsServer: null, error: null },
  configUi: { providerApiKeyTouched: {} },
  ui: {
    lang: "en",
    theme: "light",
    themeStored: false,
  },
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
  setBanner("ok", t("banner.session_reset"), 1400);
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
    setBanner("error", t("error.mcp_error", { msg: String(ev.error || "unknown") }));
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
      c.status = ev.error ? "failed" : "done";
      c.ended_at = nowTs();
      c.result = ev.content;
      c.error = ev.error ? String(ev.error) : null;
    }
    return;
  }
  if (ev.type === "assistant_final") {
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
      setBanner("warn", t("banner.cancelled"), 1200);
    } else if (payload.type === "error") {
      setBanner("error", t("error.request_failed", { msg: String(payload.error || "error") }));
    }
    scheduleRender();
  });

  es.addEventListener("hello", () => {});
  es.addEventListener("ping", () => {});

  es.onerror = async () => {
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
    setBanner("ok", t("banner.mcp_synced"), 1000);
  } catch (e) {
    setBanner("error", t("error.mcp_sync_failed", { msg: String(e.message || e) }));
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
      h("button", { class: "secondary", onclick: () => { state.banner = null; scheduleRender(); } }, [t("common.dismiss")]),
    ]),
  ]);
}

function toolStatusLabel(status) {
  if (status === "running") return t("tool.status.running");
  if (status === "done") return t("tool.status.done");
  if (status === "failed") return t("tool.status.failed");
  return t("tool.status.queued");
}

function toolStatusDot(status) {
  if (status === "running") return "dot warn";
  if (status === "done") return "dot ok";
  if (status === "failed") return "dot bad";
  return "dot";
}

function renderToolCard(card) {
  const call = card.call || {};
  const tn = toolNameFromCall(call) || t("role.tool");
  const args = argsFromCall(call);
  const argsParsed = typeof args === "string" ? safeJsonParse(args) : null;
  const argsPretty = argsParsed ? JSON.stringify(argsParsed, null, 2) : (typeof args === "string" ? args : JSON.stringify(args || {}, null, 2));
  const resultRaw = card.result;
  let resultPretty = "";
  if (typeof resultRaw === "string") {
    const parsed = safeJsonParse(resultRaw);
    resultPretty = parsed ? JSON.stringify(parsed, null, 2) : resultRaw;
  } else if (resultRaw !== null && resultRaw !== undefined) {
    resultPretty = JSON.stringify(resultRaw, null, 2);
  }

  const status = card.status || "queued";
  return h("div", { class: `toolcard ${status}` }, [
    h("div", { class: "th" }, [
      h("div", {}, [
        h("div", { class: "tn", text: tn }),
        h("div", { class: "mini", text: card.id }),
      ]),
      h("span", { class: "badge" }, [h("span", { class: toolStatusDot(status) }, []), toolStatusLabel(status)]),
    ]),
    h("div", { class: "tb" }, [
      h("details", { open: false }, [
        h("summary", { text: t("tool.arguments") }, []),
        h("pre", {}, [argsPretty || t("tool.none")]),
      ]),
      h("details", { open: false }, [
        h("summary", { text: t("tool.result") }, []),
        h("pre", {}, [resultPretty || t("tool.pending")]),
      ]),
      card.error ? h("div", { class: "banner", style: "margin-top:10px;" }, [String(card.error)]) : null,
    ]),
  ]);
}

function roleLabel(role) {
  if (role === "user") return t("role.user");
  if (role === "assistant") return t("role.assistant");
  if (role === "system") return t("role.system");
  if (role === "tool") return t("role.tool");
  return t("role.message");
}

function renderMessage(msg) {
  const role = String(msg.role || "");
  const content = msg.content !== undefined ? String(msg.content || "") : "";
  let bubbleClass = "bubble";
  if (role === "user") bubbleClass += " user";
  else if (role === "assistant") bubbleClass += " assistant";
  else if (role === "system") bubbleClass += " system";
  else if (role === "tool") bubbleClass += " system";

  const children = [
    h("div", { class: "meta" }, [
      h("span", { class: "badge" }, [h("span", { class: "dot" }, []), roleLabel(role)]),
      msg.tool_call_id ? h("span", { class: "muted", text: t("common.tool_call_id", { id: msg.tool_call_id }) }, []) : null,
    ]),
    h("div", { class: bubbleClass }, [
      role === "tool" ? h("pre", {}, [content]) : h("div", { class: "mono", text: content }, []),
    ]),
  ];

  if (role === "assistant" && Array.isArray(msg.tool_calls) && msg.tool_calls.length) {
    const list = msg.tool_calls.map((c) => {
      const name = toolNameFromCall(c) || t("role.tool");
      const id = String(c.id || "");
      return h("div", { class: "muted", style: "font-family:var(--font-mono);font-size:12px;" }, [t("tool.call", { id, name })]);
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
      h("div", { class: "small", text: t("chat.session_meta", { count: it.message_count || 0, time: fmtTime(it.updated_at) }) }),
    ]);
  }));

  const msgNodes = [];
  if (s && Array.isArray(s.messages)) {
    for (const m of s.messages) msgNodes.push(renderMessage(m));
  } else {
    msgNodes.push(h("div", { class: "muted", text: t("chat.no_session") }, []));
  }

  if (state.runId) {
    msgNodes.push(h("div", { class: "msg" }, [
      h("div", { class: "meta" }, [
        h("span", { class: "badge" }, [h("span", { class: "dot warn" }, []), t("chat.assistant_stream")]),
      ]),
      h("div", { class: "bubble assistant" }, [
        h("div", { class: "mono", text: state.assistantDraft || t("common.loading") }, []),
      ]),
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
        placeholder: t("chat.message_placeholder"),
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
        h("button", { class: "secondary", onclick: () => { location.hash = "#/dice"; } }, [t("chat.roll")]),
        h("button", { class: "secondary", onclick: () => resetSession(), disabled: !state.currentSessionId }, [t("chat.reset")]),
        h("button", { class: "secondary", onclick: () => stopRun(), disabled: !state.runId }, [t("chat.stop")]),
        h("button", { onclick: () => sendMessage(state.composing), disabled: state.runId }, [t("chat.send")]),
      ]),
    ]),
  ]);

  const inspector = h("div", { class: "panel" }, [
    h("div", { class: "ph" }, [
      h("div", { class: "title", text: t("chat.session") }, []),
      h("button", { class: "secondary", onclick: () => createSession() }, [t("chat.new")]),
    ]),
    h("div", { class: "pb" }, [
      h("div", { class: "muted", text: state.currentSessionId ? t("chat.id", { id: state.currentSessionId }) : t("chat.no_session_short") }, []),
      h("div", { style: "height:10px;" }, []),
      h("div", { class: "card" }, [
        h("div", { class: "muted", text: t("chat.provider_model") }, []),
        h("div", { style: "height:8px;" }, []),
        state.config ? renderProviderModelControls() : h("div", { class: "muted", text: t("chat.loading_config") }, []),
      ]),
      h("div", { style: "height:10px;" }, []),
      h("div", { class: "card" }, [
        h("div", { class: "muted", text: t("nav.mcp") }, []),
        h("div", { style: "height:8px;" }, []),
        h("button", {
          class: "secondary",
          onclick: async () => {
            await loadMcpStatus();
            setBanner("ok", t("banner.mcp_status_refreshed"), 900);
            scheduleRender();
          }
        }, [t("common.refresh")]),
        h("div", { style: "height:8px;" }, []),
        h("button", {
          onclick: async () => {
            await mcpSync(null);
            await loadMcpStatus();
            scheduleRender();
          }
        }, [t("mcp.sync_all")]),
      ]),
    ]),
  ]);

  return h("div", { class: "chat" }, [
    h("div", { class: "panel" }, [
      h("div", { class: "ph" }, [
        h("div", { class: "title", text: t("chat.sessions") }, []),
        h("button", { class: "secondary", onclick: () => createSession() }, [t("chat.new")]),
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
    h("option", { value: curModel, text: curModel || t("config.custom") }, []),
  ]);

  const saveBtn = h("button", {
    onclick: async () => {
      try {
        await api("/api/config", { method: "PUT", body: cfg });
        setBanner("ok", t("banner.config_saved"), 1100);
      } catch (e) {
        setBanner("error", t("error.save_failed", { msg: String(e.message || e) }));
      }
    },
  }, [t("common.save")]);

  return h("div", { style: "display:grid;gap:10px;" }, [
    h("div", { class: "kv" }, [h("label", { text: t("config.provider") }, []), providerSelect]),
    h("div", { class: "kv" }, [h("label", { text: t("config.model") }, []), modelSelect]),
    saveBtn,
  ]);
}

function renderDicePage() {
  const last = state.dice.last;
  return h("div", { style: "height:100%;display:grid;gap:12px;grid-template-rows:auto 1fr;" }, [
    h("div", { class: "card" }, [
      h("div", { class: "row" }, [
        h("div", {}, [
          h("div", { class: "muted", text: t("dice.expression") }, []),
          h("input", { value: state.dice.expression, oninput: (e) => { state.dice.expression = e.target.value; } }, []),
        ]),
        h("div", {}, [
          h("div", { class: "muted", text: t("dice.seed") }, []),
          h("input", { value: state.dice.seed, oninput: (e) => { state.dice.seed = e.target.value; } }, []),
        ]),
      ]),
      h("div", { style: "height:10px;" }, []),
      h("div", { style: "display:flex;gap:8px;justify-content:flex-end;" }, [
        h("button", { class: "secondary", onclick: () => { location.hash = "#/chat"; } }, [t("dice.back")]),
        h("button", { onclick: () => diceRoll() }, [t("chat.roll")]),
      ]),
      state.dice.error ? h("div", { class: "banner", style: "margin-top:10px;" }, [state.dice.error]) : null,
    ]),
    h("div", { class: "card", style: "overflow:auto;" }, [
      last
        ? h("div", { style: "display:grid;gap:12px;" }, [
            h("div", { style: "display:flex;align-items:baseline;justify-content:space-between;gap:10px;" }, [
              h("div", {}, [
                h("div", { class: "muted", text: t("dice.total") }, []),
                h("div", { style: "font-size:34px;font-weight:700;", text: String(last.total) }, []),
              ]),
              h("span", { class: "badge" }, [h("span", { class: "dot ok" }, []), String(last.expr || "")]),
            ]),
            h("div", { class: "muted", text: t("dice.result") }, []),
            h("pre", {}, [String(last.text || "")]),
            h("div", { style: "display:flex;gap:8px;justify-content:flex-end;" }, [
              h("button", {
                class: "secondary",
                onclick: async () => {
                  try {
                    await navigator.clipboard.writeText(String(last.text || ""));
                    setBanner("ok", t("banner.copied"), 800);
                  } catch {
                    setBanner("error", t("banner.copy_failed"));
                  }
                }
              }, [t("dice.copy")]),
              h("button", {
                onclick: async () => {
                  const text = String(last.text || "");
                  location.hash = "#/chat";
                  state.composing = text;
                  scheduleRender();
                }
              }, [t("dice.send")]),
            ]),
          ])
        : h("div", { class: "muted", text: t("dice.breakdown_hint") }, []),
    ]),
  ]);
}

function renderMcpPage() {
  const status = state.mcp.status || {};
  const rows = Object.entries(status);

  const table = h("table", { class: "table" }, [
    h("thead", {}, [
      h("tr", {}, [
        h("th", { text: t("mcp.server") }, []),
        h("th", { text: t("mcp.enabled") }, []),
        h("th", { text: t("mcp.initialized") }, []),
        h("th", { text: t("mcp.tool_count") }, []),
        h("th", { text: t("mcp.last_sync") }, []),
        h("th", { text: t("mcp.actions") }, []),
      ]),
    ]),
    h("tbody", {}, rows.map(([name, s]) => {
      const enabled = !!(s && s.enabled);
      const initialized = !!(s && s.initialized);
      const tools = s && s.tool_count !== undefined && s.tool_count !== null ? String(s.tool_count) : "-";
      const last = s && s.last_sync ? fmtTime(s.last_sync) : "-";
      const err = s && s.last_error ? String(s.last_error) : "";
      return h("tr", {}, [
        h("td", {}, [
          h("div", { style: "font-family:var(--font-mono);", text: name }, []),
          err ? h("div", { class: "muted", text: clampStr(err, 140) }, []) : null,
        ]),
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
                setBanner("ok", t("common.updated"), 900);
              } catch (e) {
                setBanner("error", t("error.save_failed", { msg: String(e.message || e) }));
              }
              scheduleRender();
            }
          }, [enabled ? t("mcp.on") : t("mcp.off")]),
        ]),
        h("td", {}, [
          h("span", { class: "badge" }, [
            h("span", { class: initialized ? "dot ok" : enabled ? "dot warn" : "dot" }, []),
            initialized ? t("mcp.yes") : t("mcp.no"),
          ]),
        ]),
        h("td", { text: tools }, []),
        h("td", { text: last }, []),
        h("td", {}, [
          h("button", { class: "secondary", onclick: async () => { await mcpSync(name); await loadMcpStatus(); scheduleRender(); } }, [t("mcp.sync")]),
          h("span", { style: "display:inline-block;width:8px;" }, []),
          h("button", { onclick: async () => { await mcpLoadTools(name); } }, [t("mcp.tools")]),
        ]),
      ]);
    })),
  ]);

  const toolsDrawer = state.mcp.tools
    ? h("div", { class: "card" }, [
        h("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:10px;" }, [
          h("div", { text: t("mcp.tools_title", { server: state.mcp.toolsServer || "all" }) }, []),
          h("button", { class: "secondary", onclick: () => { state.mcp.tools = null; scheduleRender(); } }, [t("common.close")]),
        ]),
        h("div", { style: "height:10px;" }, []),
        h("div", { style: "max-height:360px;overflow:auto;" }, [
          ...state.mcp.tools.map((tobj) => h("div", { class: "card", style: "margin-bottom:10px;padding:10px;" }, [
            h("div", { style: "font-family:var(--font-mono);font-size:12px;", text: tobj.public_name }, []),
            h("div", { class: "muted", text: tobj.description || "" }, []),
          ])),
        ]),
      ])
    : null;

  return h("div", { style: "height:100%;display:grid;gap:12px;grid-template-rows:auto 1fr;" }, [
    h("div", { class: "card" }, [
      h("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:10px;" }, [
        h("div", {}, [
          h("div", { class: "muted", text: t("mcp.title") }, []),
          h("div", { class: "muted", text: t("mcp.subtitle") }, []),
        ]),
        h("div", { style: "display:flex;gap:8px;" }, [
          h("button", { class: "secondary", onclick: async () => { await loadMcpStatus(); setBanner("ok", t("common.updated"), 800); scheduleRender(); } }, [t("common.refresh")]),
          h("button", { onclick: async () => { await mcpSync(null); await loadMcpStatus(); scheduleRender(); } }, [t("mcp.sync_all")]),
        ]),
      ]),
      state.mcp.error ? h("div", { class: "banner", style: "margin-top:10px;" }, [state.mcp.error]) : null,
    ]),
    h("div", { class: "grid-2" }, [
      h("div", { class: "card", style: "overflow:auto;" }, [table]),
      toolsDrawer || h("div", { class: "card" }, [h("div", { class: "muted", text: t("mcp.pick_tools") }, [])]),
    ]),
  ]);
}

function renderConfigPage() {
  const cfg = state.config;
  if (!cfg) {
    return h("div", { class: "card" }, [h("div", { class: "muted", text: t("common.loading") }, [])]);
  }

  const providers = cfg.providers || {};
  const names = Object.keys(providers);
  const active = cfg.active_provider || names[0] || "";
  const p = providers[active] || {};

  const touched = !!state.configUi.providerApiKeyTouched[active];
  const apiKeyValue = touched ? (p.api_key === state.redactedSentinel ? "" : (p.api_key || "")) : "";
  const apiKeyPlaceholder = p.api_key === state.redactedSentinel ? t("config.saved_redacted") : "";

  const providerEditor = h("div", { class: "card" }, [
    h("div", { class: "muted", text: t("config.provider") }, []),
    h("div", { style: "height:10px;" }, []),
    h("div", { class: "kv" }, [
      h("label", { text: t("config.active") }, []),
      h("select", {
        value: active,
        onchange: (e) => { cfg.active_provider = e.target.value; scheduleRender(); },
      }, names.map((n) => h("option", { value: n, text: n }, []))),
    ]),
    h("div", { style: "height:10px;" }, []),
    h("div", { class: "kv" }, [h("label", { text: t("config.base_url") }, []), h("input", { value: p.base_url || "", oninput: (e) => { p.base_url = e.target.value; } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: t("config.api_key") }, []), h("input", {
      type: "password",
      placeholder: apiKeyPlaceholder,
      value: apiKeyValue,
      oninput: (e) => {
        state.configUi.providerApiKeyTouched[active] = true;
        const v = e.target.value;
        p.api_key = v ? v : state.redactedSentinel;
      },
    }, [])]),
    h("div", { class: "kv" }, [h("label", { text: t("config.model") }, []), h("input", { value: p.model || "", oninput: (e) => { p.model = e.target.value; } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: t("config.models") }, []), h("textarea", { rows: 3, class: "mono", value: (Array.isArray(p.models) ? p.models.join("\n") : ""), oninput: (e) => { p.models = e.target.value.split(/\r?\n/).map((x) => x.trim()).filter(Boolean); } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: t("config.timeout") }, []), h("input", { value: String(p.timeout_s ?? ""), oninput: (e) => { const n = parseFloat(e.target.value); p.timeout_s = isFinite(n) ? n : p.timeout_s; } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: t("config.verify_tls") }, []), h("select", { value: String(!!p.verify_tls), onchange: (e) => { p.verify_tls = e.target.value === "true"; } }, [
      h("option", { value: "true", text: "true" }, []),
      h("option", { value: "false", text: "false" }, []),
    ])]),
    h("div", { class: "kv" }, [h("label", { text: t("config.extra_headers") }, []), h("textarea", {
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
    h("div", { class: "muted", text: t("config.chat_defaults") }, []),
    h("div", { style: "height:10px;" }, []),
    h("div", { class: "kv" }, [h("label", { text: t("config.system_prompt") }, []), h("textarea", { rows: 6, value: chat.system_prompt || "", oninput: (e) => { chat.system_prompt = e.target.value; } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: t("config.temperature") }, []), h("input", { value: String(chat.temperature ?? ""), oninput: (e) => { const n = parseFloat(e.target.value); chat.temperature = isFinite(n) ? n : chat.temperature; } }, [])]),
    h("div", { class: "kv" }, [h("label", { text: t("config.stream") }, []), h("select", { value: String(!!chat.stream), onchange: (e) => { chat.stream = e.target.value === "true"; } }, [
      h("option", { value: "true", text: "true" }, []),
      h("option", { value: "false", text: "false" }, []),
    ])]),
    h("div", { class: "kv" }, [h("label", { text: t("config.enable_tool_roll") }, []), h("select", { value: String(!!chat.enable_tool_roll), onchange: (e) => { chat.enable_tool_roll = e.target.value === "true"; } }, [
      h("option", { value: "true", text: "true" }, []),
      h("option", { value: "false", text: "false" }, []),
    ])]),
  ]);

  const mcpEditor = h("div", { class: "card" }, [
    h("div", { class: "muted", text: t("config.mcp_servers_raw") }, []),
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
          h("div", { class: "muted", text: t("config.title") }, []),
          h("div", { class: "muted", text: meta.config_path ? t("config.path", { path: meta.config_path }) : "" }, []),
          meta.env_api_key_present ? h("div", { class: "muted", text: t("config.env_override") }, []) : null,
        ]),
        h("div", { style: "display:flex;gap:8px;" }, [
          h("button", { class: "secondary", onclick: async () => { state.config = null; await ensureConfigLoaded(); setBanner("ok", t("banner.reloaded"), 800); scheduleRender(); } }, [t("common.reload")]),
          h("button", { onclick: async () => {
            try {
              await api("/api/config", { method: "PUT", body: cfg });
              setBanner("ok", t("banner.saved"), 1000);
            } catch (e) {
              setBanner("error", t("error.save_failed", { msg: String(e.message || e) }));
            }
          } }, [t("common.save")]),
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
        h("div", { class: "muted", text: t("history.title") }, []),
        h("button", { class: "secondary", onclick: async () => { await loadSessions(); scheduleRender(); } }, [t("common.refresh")]),
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
        h("div", { class: "small", text: t("chat.session_meta", { count: it.message_count || 0, time: fmtTime(it.updated_at) }) }, []),
      ])),
    ]),
    h("div", { class: "card", style: "overflow:auto;" }, [
      current
        ? h("div", {}, [
            h("div", { class: "muted", text: current.title || current.id }, []),
            h("div", { class: "muted", text: t("history.updated", { time: fmtTime(current.updated_at) }) }, []),
            h("div", { style: "height:10px;" }, []),
            ...(Array.isArray(current.messages) ? current.messages.map(renderMessage) : []),
          ])
        : h("div", { class: "muted", text: t("history.select") }, []),
    ]),
  ]);
}

function renderPage() {
  if (state.route === "chat") return renderChatPage();
  if (state.route === "dice") return renderDicePage();
  if (state.route === "mcp") return renderMcpPage();
  if (state.route === "config") return renderConfigPage();
  if (state.route === "history") return renderHistoryPage();
  return h("div", { class: "card" }, [h("div", { class: "muted", text: t("common.not_found") }, [])]);
}

function themeToggle() {
  const cur = document.documentElement.dataset.theme || "light";
  const next = cur === "dark" ? "light" : "dark";
  setStoredTheme(next);
  state.ui.themeStored = true;
  state.ui.theme = next;
  applyTheme(next);
  scheduleRender();
}

function langToggle() {
  const next = state.ui.lang === "zh" ? "en" : "zh";
  setStoredLang(next);
  state.ui.lang = next;
  applyLang(next);
  document.title = t("app.name") + " Web";
  scheduleRender();
}

function renderTopControls() {
  const theme = document.documentElement.dataset.theme || "light";
  const themeLabel = theme === "dark" ? t("ui.theme.dark") : t("ui.theme.light");
  const langLabel = state.ui.lang === "zh" ? t("ui.lang.zh") : t("ui.lang.en");

  const themeSeg = h("div", { class: "seg" }, [
    h("button", { class: theme === "light" ? "active" : "", onclick: () => { setStoredTheme("light"); state.ui.themeStored = true; state.ui.theme = "light"; applyTheme("light"); scheduleRender(); } }, [t("ui.theme.light")]),
    h("button", { class: theme === "dark" ? "active" : "", onclick: () => { setStoredTheme("dark"); state.ui.themeStored = true; state.ui.theme = "dark"; applyTheme("dark"); scheduleRender(); } }, [t("ui.theme.dark")]),
  ]);

  const langSeg = h("div", { class: "seg" }, [
    h("button", { class: state.ui.lang === "en" ? "active" : "", onclick: () => { setStoredLang("en"); state.ui.lang = "en"; applyLang("en"); scheduleRender(); } }, [t("ui.lang.en")]),
    h("button", { class: state.ui.lang === "zh" ? "active" : "", onclick: () => { setStoredLang("zh"); state.ui.lang = "zh"; applyLang("zh"); scheduleRender(); } }, [t("ui.lang.zh")]),
  ]);

  const providerBadge = (state.config && state.config.active_provider)
    ? h("span", { class: "badge" }, [h("span", { class: "dot" }, []), String(state.config.active_provider)])
    : null;

  return [providerBadge, themeSeg, langSeg].filter(Boolean);
}

function render() {
  state.route = routePath();
  const app = document.getElementById("app");

  const navItems = [
    [t("nav.chat"), "#/chat"],
    [t("nav.dice"), "#/dice"],
    [t("nav.mcp"), "#/mcp"],
    [t("nav.config"), "#/config"],
    [t("nav.history"), "#/history"],
  ];
  const cur = `#/${state.route}`;

  const oldMsgs = document.getElementById("chat-messages");
  let wasNearBottom = false;
  if (oldMsgs) {
    const remaining = oldMsgs.scrollHeight - oldMsgs.scrollTop - oldMsgs.clientHeight;
    wasNearBottom = remaining < 80;
  }

  app.innerHTML = "";

  const nav = h("div", { class: "nav" }, [
    h("div", { class: "brand" }, [
      h("div", { class: "mark", text: t("app.name") }, []),
      h("span", { class: "pill", text: t("app.local") }, []),
    ]),
    ...navItems.map(([label, href]) => navItem(label, href, cur)),
    h("div", { class: "foot", text: t("app.local_hint") }, []),
  ]);

  const pageTitleKey = `page.${state.route}`;
  const main = h("div", { class: "main" }, [
    h("div", { class: "topbar" }, [
      h("div", { class: "left" }, [
        h("div", { class: "title", text: t(pageTitleKey) }, []),
      ]),
      h("div", { class: "right" }, renderTopControls()),
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

function initUiPreferences() {
  const storedLang = getStoredLang();
  state.ui.lang = storedLang || detectLang();
  applyLang(state.ui.lang);

  const storedTheme = getStoredTheme();
  if (storedTheme) {
    state.ui.themeStored = true;
    state.ui.theme = storedTheme;
    applyTheme(storedTheme);
  } else {
    state.ui.themeStored = false;
    const sys = detectTheme();
    state.ui.theme = sys;
    applyTheme(sys);
    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      mq.addEventListener("change", () => {
        if (!getStoredTheme()) {
          const sys2 = detectTheme();
          state.ui.theme = sys2;
          applyTheme(sys2);
          scheduleRender();
        }
      });
    }
  }
}

async function boot() {
  initUiPreferences();
  document.title = t("app.name") + " Web";
  try {
    await ensureConfigLoaded();
  } catch (e) {
    setBanner("error", t("error.load_config", { msg: String(e.message || e) }));
  }
  try {
    await loadSessions();
    if (!state.currentSessionId) {
      await createSession();
    } else {
      await loadCurrentSession();
    }
  } catch (e) {
    setBanner("error", t("error.load_sessions", { msg: String(e.message || e) }));
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
