const state = {
  apiBase: localStorage.getItem("studybot.apiBase") || "http://127.0.0.1:8000",
  userId: localStorage.getItem("studybot.userId") || "",
  courseId: localStorage.getItem("studybot.courseId") || "",
  quiz: null,
  selectedOptions: new Map(),
};

const els = {
  apiBase: document.querySelector("#apiBase"),
  saveApiButton: document.querySelector("#saveApiButton"),
  seedDemoButton: document.querySelector("#seedDemoButton"),
  workspaceForm: document.querySelector("#workspaceForm"),
  userEmail: document.querySelector("#userEmail"),
  displayName: document.querySelector("#displayName"),
  courseTitle: document.querySelector("#courseTitle"),
  userId: document.querySelector("#userId"),
  courseId: document.querySelector("#courseId"),
  uploadForm: document.querySelector("#uploadForm"),
  documentFile: document.querySelector("#documentFile"),
  refreshDocumentsButton: document.querySelector("#refreshDocumentsButton"),
  documentList: document.querySelector("#documentList"),
  refreshMetricsButton: document.querySelector("#refreshMetricsButton"),
  metricsGrid: document.querySelector("#metricsGrid"),
  askForm: document.querySelector("#askForm"),
  questionInput: document.querySelector("#questionInput"),
  answerPanel: document.querySelector("#answerPanel"),
  citationList: document.querySelector("#citationList"),
  quizForm: document.querySelector("#quizForm"),
  quizTopic: document.querySelector("#quizTopic"),
  quizDifficulty: document.querySelector("#quizDifficulty"),
  attemptForm: document.querySelector("#attemptForm"),
  attemptPanel: document.querySelector("#attemptPanel"),
  refreshPlanButton: document.querySelector("#refreshPlanButton"),
  weakTopicList: document.querySelector("#weakTopicList"),
  recommendationList: document.querySelector("#recommendationList"),
  flashcardForm: document.querySelector("#flashcardForm"),
  flashcardTopic: document.querySelector("#flashcardTopic"),
  flashcardDifficulty: document.querySelector("#flashcardDifficulty"),
  flashcardList: document.querySelector("#flashcardList"),
  toast: document.querySelector("#toast"),
};

const sampleNotes = `Binary search quickly finds values in a sorted array by repeatedly halving the search space.
Binary search requires sorted data and compares the target with the middle value.
Hash tables provide fast lookup by mapping keys to buckets.
Recursion solves a problem by calling the same process on smaller inputs.
Photosynthesis converts light energy into chemical energy in plants.`;

function saveState() {
  localStorage.setItem("studybot.apiBase", state.apiBase);
  localStorage.setItem("studybot.userId", state.userId);
  localStorage.setItem("studybot.courseId", state.courseId);
  els.apiBase.value = state.apiBase;
  els.userId.value = state.userId;
  els.courseId.value = state.courseId;
}

function setBusy(element, busy) {
  if (!element) return;
  element.disabled = busy;
  element.setAttribute("aria-busy", String(busy));
}

function showToast(message, type = "good") {
  els.toast.textContent = message;
  els.toast.dataset.type = type;
  els.toast.classList.add("visible");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    els.toast.classList.remove("visible");
  }, 3200);
}

async function request(path, options = {}) {
  const response = await fetch(`${state.apiBase}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers || {}),
    },
  });

  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = payload?.detail || response.statusText;
    throw new Error(Array.isArray(detail) ? detail[0]?.msg || response.statusText : detail);
  }
  return payload;
}

function requireCourseId() {
  syncIdsFromInputs();
  if (!state.courseId) {
    throw new Error("Course ID is required");
  }
  return state.courseId;
}

function syncIdsFromInputs() {
  state.apiBase = els.apiBase.value.trim().replace(/\/$/, "");
  state.userId = els.userId.value.trim();
  state.courseId = els.courseId.value.trim();
  saveState();
}

function formatPercent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function statusPill(value) {
  const className = value === "completed" || value === "generated" ? "good" : "warn";
  return `<span class="pill ${className}">${escapeHtml(value)}</span>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function createWorkspace(event) {
  event.preventDefault();
  setBusy(event.submitter, true);
  try {
    syncIdsFromInputs();
    const user = await request("/users", {
      method: "POST",
      body: JSON.stringify({
        email: els.userEmail.value,
        display_name: els.displayName.value,
      }),
    });
    const course = await request(`/users/${user.id}/courses`, {
      method: "POST",
      body: JSON.stringify({
        title: els.courseTitle.value,
        description: "Frontend demo workspace",
      }),
    });

    state.userId = user.id;
    state.courseId = course.id;
    saveState();
    showToast("Workspace created");
    await refreshDocuments();
    await refreshMetrics();
  } catch (error) {
    showToast(error.message, "bad");
  } finally {
    setBusy(event.submitter, false);
  }
}

async function seedDemo() {
  setBusy(els.seedDemoButton, true);
  try {
    const unique = Date.now();
    els.userEmail.value = `student.${unique}@example.com`;
    els.displayName.value = "StudyBot Demo";
    els.courseTitle.value = "Algorithms Demo";

    const user = await request("/users", {
      method: "POST",
      body: JSON.stringify({
        email: els.userEmail.value,
        display_name: els.displayName.value,
      }),
    });
    const course = await request(`/users/${user.id}/courses`, {
      method: "POST",
      body: JSON.stringify({
        title: els.courseTitle.value,
        description: "Seeded frontend demo",
      }),
    });

    state.userId = user.id;
    state.courseId = course.id;
    saveState();

    const data = new FormData();
    data.append(
      "file",
      new Blob([sampleNotes], { type: "text/plain" }),
      "studybot-demo-notes.txt",
    );
    await request(`/courses/${course.id}/documents/text`, {
      method: "POST",
      body: data,
    });

    showToast("Demo workspace ready");
    await refreshDocuments();
    await refreshMetrics();
    drawEvidenceCanvas();
  } catch (error) {
    showToast(error.message, "bad");
  } finally {
    setBusy(els.seedDemoButton, false);
  }
}

async function uploadDocument(event) {
  event.preventDefault();
  setBusy(event.submitter, true);
  try {
    const courseId = requireCourseId();
    const file = els.documentFile.files[0];
    if (!file) throw new Error("Select a file");

    const endpoint = file.type === "application/pdf" || file.name.endsWith(".pdf")
      ? "pdf"
      : "text";
    const data = new FormData();
    data.append("file", file);
    await request(`/courses/${courseId}/documents/${endpoint}`, {
      method: "POST",
      body: data,
    });

    els.documentFile.value = "";
    showToast("Document uploaded");
    await refreshDocuments();
    await refreshMetrics();
  } catch (error) {
    showToast(error.message, "bad");
  } finally {
    setBusy(event.submitter, false);
  }
}

async function refreshDocuments() {
  try {
    const courseId = requireCourseId();
    const documents = await request(`/courses/${courseId}/documents`);
    els.documentList.innerHTML = documents
      .map(
        (document) => `
          <article class="list-row">
            <h3>${escapeHtml(document.filename)}</h3>
            <div class="meta-row">
              ${statusPill(document.status)}
              <span class="pill">${document.chunk_count} chunks</span>
              <span class="pill">${escapeHtml(document.content_type)}</span>
            </div>
          </article>
        `,
      )
      .join("");
  } catch (error) {
    els.documentList.innerHTML = "";
    showToast(error.message, "bad");
  }
}

async function refreshMetrics() {
  try {
    const metrics = await request("/admin/metrics");
    const tiles = [
      ["Users", metrics.usage.users],
      ["Courses", metrics.usage.courses],
      ["Documents", metrics.usage.documents],
      ["Answers", metrics.usage.answers],
      ["Quizzes", metrics.usage.quizzes ?? 0],
      ["Feedback", metrics.usage.feedback_events],
    ];
    els.metricsGrid.innerHTML = tiles
      .map(
        ([label, value]) => `
          <div class="metric-tile">
            <strong>${escapeHtml(value)}</strong>
            <span>${escapeHtml(label)}</span>
          </div>
        `,
      )
      .join("");
  } catch (error) {
    showToast(error.message, "bad");
  }
}

async function askQuestion(event) {
  event.preventDefault();
  setBusy(event.submitter, true);
  try {
    const courseId = requireCourseId();
    const answer = await request(`/courses/${courseId}/questions`, {
      method: "POST",
      body: JSON.stringify({
        question: els.questionInput.value,
        limit: 5,
      }),
    });

    els.answerPanel.innerHTML = `
      <h3>${escapeHtml(answer.status)}</h3>
      <p>${escapeHtml(answer.answer || "No grounded answer was generated.")}</p>
      <div class="meta-row">
        <span class="pill">${escapeHtml(answer.provider)}</span>
        <span class="pill">${answer.citations.length} citations</span>
        <span class="pill">${answer.retrieved_chunks.length} chunks</span>
      </div>
    `;
    els.citationList.innerHTML = answer.citations
      .map(
        (citation) => `
          <article class="list-row">
            <h3>${escapeHtml(citation.document_filename)}</h3>
            <p>${escapeHtml(citation.text)}</p>
            <div class="meta-row">
              <span class="pill">chunk ${citation.chunk_index}</span>
              <span class="pill">citation ${citation.position}</span>
            </div>
          </article>
        `,
      )
      .join("");
    showToast("Answer ready");
    await refreshMetrics();
  } catch (error) {
    showToast(error.message, "bad");
  } finally {
    setBusy(event.submitter, false);
  }
}

async function generateQuiz(event) {
  event.preventDefault();
  setBusy(event.submitter, true);
  try {
    const courseId = requireCourseId();
    const quiz = await request(`/courses/${courseId}/quizzes`, {
      method: "POST",
      body: JSON.stringify({
        topic: els.quizTopic.value,
        difficulty: els.quizDifficulty.value,
        question_count: 4,
        limit: 5,
      }),
    });
    state.quiz = quiz;
    state.selectedOptions = new Map();
    renderQuiz(quiz);
    els.attemptPanel.innerHTML = "";
    showToast("Quiz generated");
  } catch (error) {
    showToast(error.message, "bad");
  } finally {
    setBusy(event.submitter, false);
  }
}

function renderQuiz(quiz) {
  if (!quiz.questions.length) {
    els.attemptForm.innerHTML = `
      <div class="result-surface">
        <h3>${escapeHtml(quiz.status)}</h3>
        <p>No quiz questions were generated.</p>
      </div>
    `;
    return;
  }

  els.attemptForm.innerHTML = `
    ${quiz.questions
      .map(
        (question) => `
          <article class="question-row">
            <h3>${question.position}. ${escapeHtml(question.question)}</h3>
            <div class="question-options">
              ${question.options
                .map(
                  (option) => `
                    <label class="option-label">
                      <input
                        type="radio"
                        name="question-${question.id}"
                        value="${option.id}"
                        data-question-id="${question.id}"
                      />
                      ${escapeHtml(option.text)}
                    </label>
                  `,
                )
                .join("")}
            </div>
          </article>
        `,
      )
      .join("")}
    <button type="submit">Submit Attempt</button>
  `;
}

async function submitAttempt(event) {
  event.preventDefault();
  if (!state.quiz?.id) return;
  const button = event.submitter;
  setBusy(button, true);
  try {
    const answers = state.quiz.questions.map((question) => {
      const selected = els.attemptForm.querySelector(
        `input[name="question-${question.id}"]:checked`,
      );
      if (!selected) {
        throw new Error("Select one option for each question");
      }
      return {
        question_id: question.id,
        selected_option_id: selected.value,
      };
    });
    const attempt = await request(`/quizzes/${state.quiz.id}/attempts`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    });

    els.attemptPanel.innerHTML = `
      <h3>${attempt.correct_count}/${attempt.question_count} correct</h3>
      <p>Score: ${Math.round(attempt.score_percent)}%</p>
      <div class="compact-list">
        ${attempt.answers
          .map(
            (answer) => `
              <div class="list-row">
                <h3>${escapeHtml(answer.question)}</h3>
                <div class="meta-row">
                  <span class="pill ${answer.is_correct ? "good" : "bad"}">
                    ${answer.is_correct ? "correct" : "missed"}
                  </span>
                  <span class="pill">${escapeHtml(answer.correct_option)}</span>
                </div>
              </div>
            `,
          )
          .join("")}
      </div>
    `;
    showToast("Attempt graded");
    await refreshPlan();
    await refreshMetrics();
  } catch (error) {
    showToast(error.message, "bad");
  } finally {
    setBusy(button, false);
  }
}

async function refreshPlan() {
  try {
    const courseId = requireCourseId();
    const [weakTopics, recommendations] = await Promise.all([
      request(`/courses/${courseId}/weak-topics`),
      request(`/courses/${courseId}/study-recommendations`),
    ]);

    els.weakTopicList.innerHTML = weakTopics.weak_topics
      .map(
        (topic) => `
          <article class="list-row">
            <h3>${escapeHtml(topic.topic)}</h3>
            <div class="meta-row">
              <span class="pill warn">${formatPercent(topic.weakness_score)} weakness</span>
              <span class="pill">${formatPercent(topic.accuracy_rate)} accuracy</span>
              <span class="pill">${topic.attempt_count} attempts</span>
            </div>
          </article>
        `,
      )
      .join("");

    els.recommendationList.innerHTML = recommendations.recommendations
      .map(
        (recommendation) => `
          <article class="recommendation-item">
            <h3>${escapeHtml(recommendation.topic)}</h3>
            <p>${escapeHtml(recommendation.reason)}</p>
            <div class="meta-row">
              <span class="pill ${recommendation.priority === "high" ? "bad" : "warn"}">
                ${escapeHtml(recommendation.priority)}
              </span>
              ${recommendation.recommended_actions
                .map((action) => `<span class="pill">${escapeHtml(action.label)}</span>`)
                .join("")}
            </div>
          </article>
        `,
      )
      .join("");
    showToast("Plan refreshed");
  } catch (error) {
    showToast(error.message, "bad");
  }
}

async function generateFlashcards(event) {
  event.preventDefault();
  setBusy(event.submitter, true);
  try {
    const courseId = requireCourseId();
    const set = await request(`/courses/${courseId}/flashcard-sets`, {
      method: "POST",
      body: JSON.stringify({
        topic: els.flashcardTopic.value,
        difficulty: els.flashcardDifficulty.value,
        card_count: 5,
        limit: 5,
      }),
    });

    els.flashcardList.innerHTML = set.cards
      .map(
        (card) => `
          <article class="flashcard-item">
            <h3>${escapeHtml(card.front)}</h3>
            <p class="back">${escapeHtml(card.back)}</p>
            <div class="meta-row">
              <span class="pill">${card.citations.length} citations</span>
              <span class="pill">card ${card.position}</span>
            </div>
          </article>
        `,
      )
      .join("");
    if (!set.cards.length) {
      els.flashcardList.innerHTML = `
        <div class="result-surface">
          <h3>${escapeHtml(set.status)}</h3>
          <p>No flashcards were generated.</p>
        </div>
      `;
    }
    showToast("Flashcards ready");
  } catch (error) {
    showToast(error.message, "bad");
  } finally {
    setBusy(event.submitter, false);
  }
}

function setupTabs() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-button").forEach((tab) => {
        tab.classList.toggle("active", tab === button);
      });
      document.querySelectorAll(".tab-pane").forEach((pane) => {
        pane.classList.toggle("active", pane.id === `${button.dataset.tab}Tab`);
      });
    });
  });
}

function drawEvidenceCanvas() {
  const canvas = document.querySelector("#evidenceCanvas");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const nodes = [
    [13, 36, "#16756f"],
    [31, 14, "#b06a20"],
    [53, 32, "#17211c"],
    [74, 17, "#a0443f"],
  ];
  ctx.strokeStyle = "#cbd5cf";
  ctx.lineWidth = 2;
  for (let index = 0; index < nodes.length - 1; index += 1) {
    ctx.beginPath();
    ctx.moveTo(nodes[index][0], nodes[index][1]);
    ctx.lineTo(nodes[index + 1][0], nodes[index + 1][1]);
    ctx.stroke();
  }
  nodes.forEach(([x, y, color]) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fill();
  });
}

function bindEvents() {
  els.apiBase.value = state.apiBase;
  els.userId.value = state.userId;
  els.courseId.value = state.courseId;
  els.saveApiButton.addEventListener("click", () => {
    syncIdsFromInputs();
    showToast("API saved");
  });
  els.workspaceForm.addEventListener("submit", createWorkspace);
  els.seedDemoButton.addEventListener("click", seedDemo);
  els.uploadForm.addEventListener("submit", uploadDocument);
  els.refreshDocumentsButton.addEventListener("click", refreshDocuments);
  els.refreshMetricsButton.addEventListener("click", refreshMetrics);
  els.askForm.addEventListener("submit", askQuestion);
  els.quizForm.addEventListener("submit", generateQuiz);
  els.attemptForm.addEventListener("submit", submitAttempt);
  els.refreshPlanButton.addEventListener("click", refreshPlan);
  els.flashcardForm.addEventListener("submit", generateFlashcards);
}

setupTabs();
bindEvents();
drawEvidenceCanvas();
saveState();
