const assert = require("node:assert/strict");
const { test } = require("node:test");
const { harness } = require("./helpers.cjs");

const card = { id: "card-1", title: "Algorithms", front: "What is binary search?",
  back: "Halve a sorted range.", version: 0, citations: [
    { document_filename: "<notes>.txt", text: "Sorted data", page_number: 2 },
  ] };
const queue = { total_count: 1, reviewed_count: 0, due_count: 1, next_due_at: null, cards: [card] };

test("review hides answers until reveal and saves the server version without AI calls", async () => {
  let saved = false;
  const h = harness((path, options) => {
    if (options.method === "POST") {
      saved = true;
      return { due_at: "2026-10-12T10:00:00Z" };
    }
    return saved ? { ...queue, cards: [], due_count: 0, reviewed_count: 1,
      next_due_at: "2026-10-12T10:00:00Z" } : queue;
  });
  await h.context.refreshReviewQueue();
  assert.equal(h.node("reviewAnswer").hidden, true);
  assert.equal(h.node("reviewBack").textContent, "");
  assert.equal(h.node("reviewRatings").hidden, true);
  await h.context.submitReview("good");
  assert.equal(h.calls.filter((c) => c.method === "POST").length, 0);
  h.context.revealReviewAnswer();
  assert.equal(h.node("reviewBack").textContent, card.back);
  assert.match(h.node("reviewCitations").innerHTML, /&lt;notes&gt;/);
  await h.context.submitReview("good");
  const post = h.calls.find((c) => c.method === "POST");
  assert.deepEqual(post.body, { rating: "good", version: 0 });
  assert.equal(post.pathname, "/flashcards/card-1/reviews");
  assert.match(h.node("reviewStatus").textContent, /caught up/);
  assert.match(h.node("reviewNotice").textContent, /Review saved/);
  assert.equal(h.node("reviewCard").hidden, true);
  assert.equal(h.calls.some((c) => /ai-usage|flashcard-sets/.test(c.pathname)), false);
});

test("double clicks submit once, and failed saves keep the revealed card retryable", async () => {
  let release;
  const wait = new Promise((resolve) => { release = resolve; });
  const h = harness(async (_, options) => {
    if (options.method === "POST") { await wait; throw new Error("Connection lost"); }
    return queue;
  });
  await h.context.refreshReviewQueue();
  h.context.revealReviewAnswer();
  const first = h.context.submitReview("again");
  await h.context.submitReview("easy");
  assert.equal(h.calls.filter((c) => c.method === "POST").length, 1);
  release();
  await first;
  assert.equal(h.state.reviewSaving, false);
  assert.equal(h.state.reviewRevealed, true);
  assert.equal(h.state.reviewQueue.cards[0].id, card.id);
  assert.match(h.node("reviewNotice").textContent, /Retry the rating/);
});

test("conflicting reviews refresh the queue instead of scheduling twice", async () => {
  let conflict = false;
  const h = harness((_, options) => {
    if (options.method === "POST") {
      conflict = true;
      return { error: 409, body: { detail: "Progress changed" } };
    }
    return conflict ? { ...queue, cards: [], due_count: 0, reviewed_count: 1 } : queue;
  });
  await h.context.refreshReviewQueue();
  h.context.revealReviewAnswer();
  await h.context.submitReview("good");
  assert.match(h.node("reviewNotice").textContent, /queue has been refreshed/);
  assert.equal(h.node("reviewCard").hidden, true);
});

test("course changes and logout clear progress and reject late queue responses", async () => {
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  const h = harness(async () => { await pending; return queue; });
  const load = h.context.refreshReviewQueue();
  h.state.courseId = "another-course";
  h.context.clearStudyViews();
  release();
  await load;
  assert.equal(h.state.reviewQueue, null);
  assert.equal(h.node("reviewCard").hidden, true);
  h.state.reviewQueue = queue;
  h.context.renderReviewCard();
  h.context.revealReviewAnswer();
  h.context.clearAccount();
  assert.equal(h.node("reviewFront").textContent, "");
  assert.equal(h.node("reviewBack").textContent, "");
  assert.equal(h.node("reviewCitations").innerHTML, "");
  assert.equal(h.state.reviewRevealed, false);
});

test("empty courses and queue errors give actionable messages", async () => {
  const empty = harness(() => ({ ...queue, total_count: 0, due_count: 0, cards: [] }));
  await empty.context.refreshReviewQueue();
  assert.match(empty.node("reviewStatus").textContent, /Generate a set/);
  const failed = harness(() => ({ error: 503, body: { detail: "Unavailable" } }));
  await failed.context.refreshReviewQueue();
  assert.match(failed.node("reviewStatus").textContent, /Refresh due cards to retry/);
  assert.equal(failed.node("refreshReviewButton").disabled, false);
});
