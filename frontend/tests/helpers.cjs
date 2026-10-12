const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Element {
  constructor(id = "") {
    this.id = id;
    this.value = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.listeners = {};
    this.classes = new Set();
    this.classList = {
      contains: (name) => this.classes.has(name),
      add: (name) => this.classes.add(name),
      remove: (name) => this.classes.delete(name),
      toggle: (name, active) => active ? this.classes.add(name) : this.classes.delete(name),
    };
  }
  set innerHTML(value) {
    this.html = value;
    if (this.id.endsWith("Select")) this.value = value.match(/<option value="([^"]*)"/)?.[1] || "";
  }
  get innerHTML() { return this.html || ""; }
  setAttribute() {}
  addEventListener(name, listener) { this.listeners[name] = listener; }
  querySelectorAll() { return []; }
  scrollIntoView() {}
  focus() { this.focused = true; }
  getContext() {
    return { clearRect() {}, fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, arc() {}, fill() {} };
  }
}

function harness(responder, options = {}) {
  const nodes = new Map();
  const node = (id) => {
    if (!nodes.has(id)) nodes.set(id, new Element(id));
    return nodes.get(id);
  };
  const tabs = ["dashboard", "ask", "quiz", "plan", "flashcards", "library", "review"].map((name) => {
    const tab = new Element();
    tab.dataset.tab = name;
    return tab;
  });
  const calls = [];
  const storage = () => ({ getItem: () => null, setItem() {}, removeItem() {} });
  const context = vm.createContext({
    document: {
      querySelector: (selector) => node(selector.slice(1)),
      querySelectorAll: (selector) => selector === ".tab-button" ? tabs
        : tabs.map((tab) => node(`${tab.dataset.tab}Tab`)),
    },
    localStorage: storage(), sessionStorage: storage(), FormData: class { append() {} },
    URLSearchParams,
    window: { location: { protocol: "https:", origin: "https://test.example", hash: "", pathname: "/", search: "" }, history: { replaceState() {} }, confirm: options.confirm || (() => false), listeners: {}, addEventListener(name, listener) { this.listeners[name] = listener; }, clearTimeout() {}, setTimeout() {} },
    fetch: async (url, requestOptions = {}) => {
      const pathname = new URL(url).pathname;
      calls.push({ pathname, method: requestOptions.method || "GET", body: typeof requestOptions.body === "string" ? JSON.parse(requestOptions.body) : null, url });
      if (pathname === "/auth/capabilities") return { ok: true, json: async () => options.capabilities || { account_email_enabled: false } };
      const result = await responder(pathname, requestOptions);
      return { ok: result?.error === undefined, status: result?.error || 200,
        statusText: "Unavailable", text: async () => JSON.stringify(result?.body ?? result) };
    },
  });
  vm.runInContext(readFileSync(path.join(__dirname, "../app.js"), "utf8"), context);
  const state = vm.runInContext("state", context);
  state.user = { id: "user-1" };
  state.token = "test-only-token";
  state.authApiBase = state.apiBase;
  state.courseId = "course-1";
  node("libraryType").value = "all";
  return { context, state, node, calls };
}

module.exports = { harness, Element };
