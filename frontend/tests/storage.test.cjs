const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const { harness, Element } = require('./helpers.cjs');

const usage = { documents: { used: 2, limit: 20, remaining: 18 },
  text_bytes: { used: 1024, limit: 2097152, remaining: 2096128 }, max_file_bytes: 2097152,
  max_pdf_pages: 100, max_text_chars: 200000, shared_capacity_available: true };

test('storage allowance shows shared note limits and can recover after a failed load', async () => {
  let failed = false;
  const h = harness(() => failed ? { error: 503 } : usage);
  await vm.runInContext('refreshStorage()', h.context);
  assert.match(h.node('storageStatus').textContent, /2 of 20/);
  assert.match(h.node('uploadLimits').textContent, /100 PDF pages/);
  failed = true;
  await vm.runInContext('refreshStorage()', h.context);
  assert.match(h.node('storageStatus').textContent, /could not be loaded/);
  assert.equal(h.state.storageUsage, null);
  failed = false;
  await vm.runInContext('refreshStorage()', h.context);
  assert.match(h.node('storageStatus').textContent, /space left/);
});

test('oversized files are rejected before upload and failed uploads remain retryable', async () => {
  let failed = true;
  const h = harness((path) => path === '/auth/storage-usage' ? usage
    : path.endsWith('/documents') ? [] : { error: failed ? 429 : undefined, body: {} });
  h.state.storageUsage = usage;
  h.node('documentFile').files = [{ name: 'notes.txt', size: 2097153, type: 'text/plain' }];
  const button = new Element();
  h.context.uploadEvent = { preventDefault() {}, submitter: button };
  await vm.runInContext('uploadDocument(uploadEvent)', h.context);
  assert.match(h.node('toast').textContent, /exceeds/);
  assert.equal(h.calls.filter(c => c.method === 'POST').length, 0);
  assert.equal(button.disabled, false);
  h.node('documentFile').files[0].size = 100;
  await vm.runInContext('uploadDocument(uploadEvent)', h.context);
  assert.equal(button.disabled, false);
  failed = false;
  await vm.runInContext('uploadDocument(uploadEvent)', h.context);
  assert.match(h.node('toast').textContent, /uploaded/);
});

test('delete requires confirmation, refreshes freed space, and escapes document names', async () => {
  let allowed = false, deleted = false;
  const h = harness((path, options) => {
    if (path === '/auth/storage-usage') return deleted
      ? { ...usage, documents: { used: 0, limit: 20, remaining: 20 } } : usage;
    if (options.method === 'DELETE') { deleted = true; return null; }
    return deleted ? [] : [{ id: 'doc-1', filename: '<notes>', status: 'completed',
      content_type: 'text/plain', chunk_count: 1, storage_bytes: 1024 }];
  }, { confirm: () => allowed });
  await vm.runInContext('refreshDocuments()', h.context);
  assert.match(h.node('documentList').innerHTML, /&lt;notes&gt;/);
  assert.match(h.node('documentList').innerHTML, /Delete document/);
  const button = new Element(); button.dataset.deleteDocument = 'doc-1';
  h.context.deleteEvent = { target: { closest: () => button } };
  await vm.runInContext('removeDocument(deleteEvent)', h.context);
  assert.equal(deleted, false);
  allowed = true;
  await vm.runInContext('removeDocument(deleteEvent)', h.context);
  assert.equal(deleted, true);
  assert.match(h.node('storageStatus').textContent, /0 of 20/);
  assert.equal(button.disabled, false);
});

test('logout and newer requests reject delayed storage responses', async () => {
  let resolve;
  const h = harness(() => new Promise(r => { resolve = r; }));
  const pending = vm.runInContext('refreshStorage()', h.context);
  vm.runInContext('clearAccount()', h.context);
  resolve(usage);
  await pending;
  assert.equal(h.node('storageStatus').textContent, '');
  assert.equal(h.state.storageUsage, null);
});

test('two clicks during an upload submit one file', async () => {
  let resolve;
  const h = harness((path) => path === '/auth/storage-usage' ? usage
    : path.endsWith('/documents') ? [] : new Promise(r => { resolve = r; }));
  h.node('documentFile').files = [{ name: 'notes.txt', size: 100, type: 'text/plain' }];
  const button = new Element();
  h.context.uploadEvent = { preventDefault() {}, submitter: button };
  const first = vm.runInContext('uploadDocument(uploadEvent)', h.context);
  await vm.runInContext('uploadDocument(uploadEvent)', h.context);
  assert.equal(h.calls.filter(c => c.method === 'POST').length, 1);
  resolve({});
  await first;
  assert.equal(button.disabled, false);
});
