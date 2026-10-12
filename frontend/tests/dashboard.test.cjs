const test = require('node:test');
const assert = require('node:assert/strict');
const { harness, Element } = require('./helpers.cjs');

const stamp = '2026-10-12T10:00:00Z';
const score = { id: 'score-1', quiz_id: 'quiz-1', title: 'Search <quiz>', topic: 'search',
  score_percent: 25, correct_count: 1, question_count: 4, created_at: stamp };
const saved = { id: 'quiz-1', kind: 'quiz', title: 'Search <quiz>', created_at: stamp };
const data = { course_id: 'course-1', course_title: 'Algorithms', document_count: 2,
  saved_count: 3, quiz_attempt_count: 1, review: { due_count: 2, total_count: 8, next_due_at: null },
  weak_topics: [{ topic: '<binary> search', accuracy_rate: 0.25, attempt_count: 1 }],
  recent_scores: [score], saved_work: [saved], next_action: { type: 'review',
    title: 'Review your due flashcards', reason: 'Two cards are ready', label: 'Start review' } };

function respond(path) {
  if (path.endsWith('/dashboard')) return data;
  if (path.endsWith('/flashcard-review')) return { cards: [], total_count: 8, due_count: 0,
    reviewed_count: 8, next_due_at: stamp };
  if (path === '/quizzes/quiz-1') return { id: 'quiz-1', topic: 'search', difficulty: 'easy',
    status: 'generated', questions: [] };
  if (path === '/quizzes/quiz-1/attempts') return [score];
  if (path === '/quiz-attempts/score-1') return { ...score, answers: [] };
  if (path === '/flashcard-sets/cards-1') return { cards: [{ front: 'New', back: 'Card',
    position: 1, citations: [] }] };
}

test('dashboard is the landing view and renders escaped course progress through GET', async () => {
  const h = harness(respond);
  assert.equal(h.node('dashboardTab').classList.contains('active'), true);
  await h.context.refreshDashboard();
  assert.equal(h.node('dashboardTitle').textContent, 'Algorithms');
  assert.match(h.node('dashboardSummary').innerHTML, /Cards due/);
  assert.match(h.node('dashboardTopics').innerHTML, /&lt;binary&gt;/);
  assert.match(h.node('dashboardScores').innerHTML, /25%/);
  assert.match(h.node('dashboardSaved').innerHTML, /&lt;quiz&gt;/);
  assert.equal(h.node('dashboardNextButton').textContent, 'Start review');
  assert.equal(h.node('dashboardContent').hidden, false);
  assert.ok(h.calls.every(c => c.method === 'GET'));
});

test('empty, signed-out, no-course, and verification states do not fabricate progress', async () => {
  const empty = { ...data, review: { due_count: 0, total_count: 0, next_due_at: null },
    recent_scores: [], weak_topics: [], saved_work: [], quiz_attempt_count: 0 };
  const h = harness(() => empty);
  await h.context.refreshDashboard();
  assert.match(h.node('dashboardScoresStatus').textContent, /No quiz results/);
  assert.match(h.node('dashboardTopicsStatus').textContent, /Complete a quiz/);
  assert.equal(h.node('dashboardReviewButton').disabled, true);
  h.state.courseId = '';
  await h.context.refreshDashboard();
  assert.match(h.node('dashboardStatus').textContent, /Create your first course/);
  h.state.verificationRequired = true;
  h.state.courseId = 'course-1';
  await h.context.refreshDashboard();
  assert.match(h.node('dashboardStatus').textContent, /Verify your email/);
  h.context.clearAccount();
  await h.context.refreshDashboard();
  assert.match(h.node('dashboardStatus').textContent, /Sign in/);
  assert.equal(h.node('dashboardContent').hidden, true);
  assert.equal(h.calls.filter(c => c.pathname.endsWith('/dashboard')).length, 1);
});

test('next action opens reviews or prepares a question without generating content', async () => {
  const h = harness(respond);
  await h.context.refreshDashboard();
  await h.context.runDashboardAction();
  assert.equal(h.node('reviewTab').classList.contains('active'), true);
  assert.ok(h.calls.some(c => c.pathname.endsWith('/flashcard-review')));
  h.state.dashboard.next_action = { type: 'ask', prompt: 'Explain search using my notes.' };
  await h.context.runDashboardAction();
  assert.equal(h.node('questionInput').value, 'Explain search using my notes.');
  assert.equal(h.node('questionInput').focused, true);
  assert.equal(h.node('askTab').classList.contains('active'), true);
  h.state.dashboard.next_action = { type: 'upload' };
  await h.context.runDashboardAction();
  assert.equal(h.node('documentFile').focused, true);
  assert.ok(h.calls.every(c => c.method === 'GET'));
});

test('saved quizzes and score details reopen through existing views using only GET', async () => {
  const h = harness(respond);
  await h.context.refreshDashboard();
  h.state.dashboard.next_action = { type: 'saved', kind: 'quiz', id: 'quiz-1' };
  await h.context.runDashboardAction();
  assert.equal(h.state.quiz.id, 'quiz-1');
  await h.context.openDashboardScore('score-1', new Element());
  assert.match(h.node('attemptPanel').innerHTML, /1\/4 correct/);
  assert.equal(h.node('quizTab').classList.contains('active'), true);
  assert.ok(h.calls.every(c => c.method === 'GET'));
  assert.ok(!h.calls.some(c => c.pathname === '/auth/ai-usage'));
});

test('failed dashboards clear private data and leave refresh retryable', async () => {
  let fail = false;
  const h = harness(() => fail ? { error: 503, body: { detail: 'Temporarily unavailable' } } : data);
  await h.context.refreshDashboard();
  fail = true;
  await h.context.refreshDashboard();
  assert.equal(h.state.dashboard, null);
  assert.equal(h.node('dashboardContent').hidden, true);
  assert.match(h.node('dashboardStatus').textContent, /Refresh dashboard to retry/);
  assert.equal(h.node('refreshDashboardButton').disabled, false);
  fail = false;
  await h.context.refreshDashboard();
  assert.equal(h.node('dashboardContent').hidden, false);
});

test('course changes and logout discard delayed dashboard data', async () => {
  let resolve;
  const h = harness(() => new Promise(r => { resolve = r; }));
  const pending = h.context.refreshDashboard();
  h.state.courseId = 'course-2';
  h.context.clearStudyViews();
  resolve(data);
  await pending;
  assert.equal(h.state.dashboard, null);
  assert.equal(h.node('dashboardContent').hidden, true);
  h.state.dashboard = data;
  h.context.clearAccount();
  assert.equal(h.node('dashboardScores').innerHTML, '');
  assert.equal(h.node('dashboardNextTitle').textContent, '');
});

test('a newer saved item prevents a delayed score open from stealing its view', async () => {
  let resolve;
  const h = harness(path => path === '/quizzes/quiz-1'
    ? new Promise(r => { resolve = r; }) : respond(path));
  h.state.dashboard = data;
  h.state.quiz = { id: 'quiz-1' };
  const pending = h.context.openDashboardScore('score-1', new Element());
  await h.context.openLibraryItem('flashcards', 'cards-1', new Element());
  resolve(respond('/quizzes/quiz-1'));
  await pending;
  assert.equal(h.node('flashcardsTab').classList.contains('active'), true);
  assert.ok(!h.calls.some(c => c.pathname === '/quiz-attempts/score-1'));
});
