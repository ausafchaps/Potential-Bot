const assert = require("node:assert/strict");
const { test } = require("node:test");
const { harness, Element } = require("./helpers.cjs");

test("reset links strip fragments and use their own origin instead of a saved API", async () => {
  const h = harness(() => ({ message: "Password reset. Sign in again." }));
  const token = "t".repeat(43);
  let scrubbed = false;
  h.context.window.location.hash = `#reset=${token}`;
  h.context.window.history.replaceState = () => { scrubbed = true; };
  h.state.apiBase = "https://another-api.example";
  h.context.detectAccountLink();
  assert.equal(scrubbed, true);
  assert.equal(h.state.apiBase, "https://test.example");
  assert.equal(h.node("resetPasswordForm").hidden, false);
  assert.equal(h.node("verifyEmailButton").hidden, true);
  assert.equal(h.calls.some((call) => call.method === "POST"), false);
  h.node("newPassword").value = "new-password-long-enough";
  h.node("confirmPassword").value = "different-password";
  await h.context.submitAccountLink({ preventDefault() {}, submitter: new Element() });
  assert.match(h.node("recoveryStatus").textContent, /do not match/);
  assert.equal(h.calls.some((call) => call.method === "POST"), false);
  h.node("newPassword").value = h.node("confirmPassword").value = "new-password-long-enough";
  await h.context.submitAccountLink({ preventDefault() {}, submitter: new Element() });
  const request = h.calls.find((call) => call.method === "POST");
  assert.equal(request.url, "https://test.example/auth/reset-password");
  assert.equal(request.body.token, token);
  assert.equal(h.state.accountLink, null);
  assert.equal(h.node("newPassword").value, "");
  assert.match(h.node("recoveryStatus").textContent, /Password reset/);
});

test("verification requires an explicit click and failures keep a readable link error", async () => {
  const h = harness(() => ({ error: 400, body: { detail: "Link expired. Request a new one." } }));
  h.context.window.location.hash = `#verify=${"v".repeat(43)}`;
  h.context.detectAccountLink();
  assert.equal(h.node("verifyEmailButton").hidden, false);
  assert.equal(h.calls.some((call) => call.method === "POST"), false);
  await h.context.submitAccountLink();
  assert.equal(h.calls.find((call) => call.method === "POST").pathname, "/auth/verify-email");
  assert.match(h.node("recoveryStatus").textContent, /expired/);
});

test("an email link opened in the same tab replaces the previous recovery form", () => {
  const h = harness(() => null);
  h.node("forgotPasswordForm").hidden = false;
  h.context.window.location.hash = `#reset=${"r".repeat(43)}`;
  h.context.window.listeners.hashchange();
  assert.equal(h.node("forgotPasswordForm").hidden, true);
  assert.equal(h.node("resetPasswordForm").hidden, false);
  assert.equal(h.state.accountLink.purpose, "reset");
});

test("disabled delivery does not pretend to send email", async () => {
  const h = harness(() => null);
  await h.context.showForgotPassword();
  assert.equal(h.node("forgotPasswordForm").hidden, true);
  assert.match(h.node("recoveryStatus").textContent, /not available yet/);
});

test("forgot password sends only email and displays generic server status", async () => {
  const h = harness(() => ({ message: "If an eligible account exists, a link will be emailed." }),
    { capabilities: { account_email_enabled: true } });
  await h.context.showForgotPassword();
  assert.equal(h.node("forgotPasswordForm").hidden, false);
  h.node("recoveryEmail").value = "student@example.com";
  await h.context.submitForgotPassword({ preventDefault() {}, submitter: new Element() });
  assert.deepEqual(h.calls.find((c) => c.method === "POST").body, { email: "student@example.com" });
  assert.match(h.node("recoveryStatus").textContent, /eligible account/);
});
