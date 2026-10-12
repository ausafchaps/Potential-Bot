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
  getContext() {
    return { clearRect() {}, fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, arc() {}, fill() {} };
  }
}

function harness(responder) {
  const nodes = new Map();
  const node = (id) => {
    if (!nodes.has(id)) nodes.set(id, new Element(id));
    return nodes.get(id);
  };
  const tabs = ["ask", "quiz", "plan", "flashcards", "library", "review"].map((name) => {
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
    localStorage: storage(), sessionStorage: storage(), FormData: class {},
    window: { location: { protocol: "https:", origin: "https://test.example" }, clearTimeout() {}, setTimeout() {} },
    fetch: async (url, options) => {
      const pathname = new URL(url).pathname;
      calls.push({ pathname, method: options.method || "GET", body: options.body ? JSON.parse(options.body) : null });
      const result = await responder(pathname, options);
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
