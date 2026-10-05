const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
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
  const tabs = ["ask", "quiz", "plan", "flashcards", "library"].map((name) => {
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
      calls.push({ pathname, method: options.method || "GET" });
      const result = await responder(pathname);
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

const timestamp = "2026-10-05T10:00:00";
const question = { id: "question-1", text: "What is <binary> search?", answer_count: 1, created_at: timestamp };
const quiz = { id: "quiz-1", topic: "binary search", title: null, question_count: 4,
  difficulty: "medium", status: "generated", created_at: "2026-10-05T11:00:00" };
const flashcards = { id: "cards-1", topic: "trees", card_count: 5, difficulty: "easy",
  status: "generated", created_at: "2026-10-05T12:00:00" };

test("library loads stored work newest first, escapes titles, filters, and paginates", async () => {
  const h = harness((url) => url.endsWith("/questions") ? [question]
    : url.endsWith("/quizzes") ? [quiz] : [flashcards]);
  await h.context.refreshLibrary();
  const html = h.node("libraryList").innerHTML;
  assert.ok(html.indexOf("trees") < html.indexOf("binary search"));
  assert.match(html, /&lt;binary&gt;/);
  assert.doesNotMatch(html, /<binary>/);
  assert.match(h.node("libraryStatus").textContent, /3 saved items/);
  h.node("libraryType").value = "quiz";
  h.context.renderLibrary();
  assert.match(h.node("libraryList").innerHTML, /4 questions/);
  assert.doesNotMatch(h.node("libraryList").innerHTML, /trees/);
  h.node("librarySearch").value = "no match";
  h.context.renderLibrary();
  assert.match(h.node("libraryStatus").textContent, /matches these filters/);
  h.node("libraryType").value = "all";
  h.node("librarySearch").value = "";
  h.state.libraryItems = Array.from({ length: 21 }, (_, i) => ({ ...question,
    kind: "answer", label: "Answer", title: `Question ${i}`, description: "saved", id: `q-${i}` }));
  h.context.renderLibrary();
  assert.equal((h.node("libraryList").innerHTML.match(/<article/g) || []).length, 20);
  assert.equal(h.node("libraryPagination").hidden, false);
  h.state.libraryPage = 1;
  h.context.renderLibrary();
  assert.equal((h.node("libraryList").innerHTML.match(/<article/g) || []).length, 1);
  assert.equal(h.node("libraryNext").disabled, true);
  assert.ok(h.calls.every((call) => call.method === "GET"));
});

test("empty library and failed loads explain how to proceed", async () => {
  const h = harness(() => []);
  await h.context.refreshLibrary();
  assert.match(h.node("libraryStatus").textContent, /No saved work yet/);
  const failed = harness(() => ({ error: 503, body: { detail: "Database unavailable" } }));
  await failed.context.refreshLibrary();
  assert.match(failed.node("libraryStatus").textContent, /Refresh library to retry/);
  assert.equal(failed.node("refreshLibraryButton").disabled, false);
});

test("reopening answers, quizzes, scores, and cards uses GETs without regeneration", async () => {
  const h = harness((url) => ({
    "/questions/question-1": { ...question, answers: [{ id: "answer-1", status: "answered", created_at: timestamp }] },
    "/answers/answer-1": { answer: "Halve the sorted range.", status: "answered", provider: "groq",
      citations: [{ document_filename: "notes.txt", text: "Sorted data", chunk_index: 0, position: 1 }] },
    "/quizzes/quiz-1": { ...quiz, questions: [{ id: "q1", position: 1, question: "Sorted?", options: [{ id: "o1", text: "Yes" }] }] },
    "/quizzes/quiz-1/attempts": [{ id: "attempt-1", score_percent: 75, correct_count: 3, question_count: 4, created_at: timestamp }],
    "/quiz-attempts/attempt-1": { score_percent: 75, correct_count: 3, question_count: 4,
      answers: [{ question: "Sorted?", correct_option: "Yes", is_correct: true }] },
    "/flashcard-sets/cards-1": { ...flashcards, cards: [{ front: "Tree?", back: "A hierarchy", position: 1, citations: [] }] },
  })[url]);
  await h.context.openLibraryItem("answer", "question-1", new Element());
  assert.match(h.node("answerPanel").innerHTML, /Halve the sorted range/);
  assert.match(h.node("citationList").innerHTML, /notes.txt/);
  assert.equal(h.node("savedAnswerControls").hidden, false);
  await h.context.openLibraryItem("quiz", "quiz-1", new Element());
  assert.match(h.node("attemptForm").innerHTML, /Sorted\?/);
  assert.match(h.node("quizHistoryList").innerHTML, /75%/);
  await h.context.openSavedAttempt("attempt-1", new Element());
  assert.match(h.node("attemptPanel").innerHTML, /3\/4 correct/);
  await h.context.openLibraryItem("flashcards", "cards-1", new Element());
  assert.match(h.node("flashcardList").innerHTML, /A hierarchy/);
  assert.ok(h.calls.every((call) => call.method === "GET"));
  assert.equal(h.calls.filter((call) => call.pathname === "/auth/ai-usage").length, 0);
});

test("late library responses cannot paint after course change or sign out", async () => {
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  const h = harness(async () => { await pending; return [question]; });
  const load = h.context.refreshLibrary();
  h.state.courseId = "course-2";
  h.context.clearStudyViews();
  release();
  await load;
  assert.equal(h.state.libraryItems.length, 0);
  assert.equal(h.node("libraryList").innerHTML, "");
  assert.equal(h.node("refreshLibraryButton").disabled, false);
  h.node("questionInput").value = "Private saved question";
  h.node("quizTopic").value = "Private saved topic";
  h.node("librarySearch").value = "Private filter";
  h.context.clearAccount();
  assert.equal(h.node("questionInput").value, "What is binary search?");
  assert.equal(h.node("quizTopic").value, "binary search");
  assert.equal(h.node("librarySearch").value, "");
  h.context.renderLibrary();
  assert.match(h.node("libraryStatus").textContent, /Sign in/);
});

test("a newer open wins over a delayed saved answer", async () => {
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  const h = harness(async (url) => {
    if (url.startsWith("/questions/")) { await pending; return { ...question, answers: [] }; }
    return { ...flashcards, cards: [{ front: "Newer", back: "Visible", position: 1, citations: [] }] };
  });
  const old = h.context.openLibraryItem("answer", "question-1", new Element());
  await h.context.openLibraryItem("flashcards", "cards-1", new Element());
  release();
  await old;
  assert.equal(h.node("flashcardsTab").classList.contains("active"), true);
  assert.equal(h.node("askTab").classList.contains("active"), false);
  assert.equal(h.node("answerPanel").innerHTML, "");
});
