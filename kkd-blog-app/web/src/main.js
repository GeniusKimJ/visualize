import Anthropic from '@anthropic-ai/sdk';
import { buildCardDocument } from './card-template.js';
import {
  SYSTEM_PROMPT, CARD_SCHEMA, POST_SCHEMA, REVIEW_SCHEMA, REVISE_SCHEMA,
  cardRequest, postRequest, reviewRequest, reviseRequest,
} from './prompts.js';

var Native = window.Android || null;

// ---------- 저장소 (앱: SharedPreferences, 브라우저: localStorage) ----------
function getPref(k, d) {
  try {
    var v = Native ? Native.getPref(k) : localStorage.getItem(k);
    return v === null || v === undefined || v === '' ? d : v;
  } catch (e) { return d; }
}
function setPref(k, v) {
  try { if (Native) Native.setPref(k, String(v)); else localStorage.setItem(k, String(v)); } catch (e) { /* 무시 */ }
}

var DEFAULTS = { model: 'claude-opus-5-5', wmText: 'KKD', wmOpacity: '6', wmEnabled: 'true', postType: 'A', ratio: '5:5', length: '2000' };
var settings = {};
function loadSettings() {
  settings.apiKey = getPref('apiKey', '');
  Object.keys(DEFAULTS).forEach(function (k) { settings[k] = getPref(k, DEFAULTS[k]); });
  settings.wmEnabled = settings.wmEnabled !== 'false';
}

// 작업 상태: 마지막 결과를 보관해 앱을 다시 열어도 이어서 작업
var state = { images: [], memo: '', card: null, post: null, review: null, savedUri: null };
function persistState() {
  try {
    localStorage.setItem('kkd-state', JSON.stringify({ memo: state.memo, card: state.card, post: state.post, review: state.review }));
  } catch (e) { /* 용량 초과 등 무시 */ }
}
function restoreState() {
  try {
    var s = JSON.parse(localStorage.getItem('kkd-state') || 'null');
    if (s) { state.memo = s.memo || ''; state.card = s.card; state.post = s.post; state.review = s.review; }
  } catch (e) { /* 무시 */ }
}

// ---------- Claude 호출 ----------
var busy = false;

async function callClaude(opts) {
  if (!settings.apiKey) throw new Error('설정에서 Anthropic API 키를 먼저 입력해 주세요.');
  var client = new Anthropic({ apiKey: settings.apiKey, dangerouslyAllowBrowser: true, maxRetries: 2 });
  var params = {
    model: settings.model,
    max_tokens: 32000,
    system: [{ type: 'text', text: SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
    output_config: { effort: opts.effort, format: { type: 'json_schema', schema: opts.schema } },
    messages: [{ role: 'user', content: opts.content }],
    betas: ['server-side-fallback-2026-07-01'],
    fallbacks: 'default',
  };

  var msg;
  try {
    msg = await streamOnce(client, params, opts.onProgress);
  } catch (err) {
    // 거절 대비 fallbacks 옵션을 계정/모델이 받지 않으면 옵션 없이 한 번 더 시도
    if (err instanceof Anthropic.BadRequestError && /fallback/i.test(err.message || '')) {
      delete params.betas;
      delete params.fallbacks;
      msg = await streamOnce(client, params, opts.onProgress);
    } else {
      throw err;
    }
  }

  if (msg.stop_reason === 'refusal') throw new Error('Claude가 이 요청을 처리하지 않았습니다. 메모 내용을 바꿔 다시 시도해 주세요.');
  if (msg.stop_reason === 'max_tokens') throw new Error('응답이 너무 길어 중간에 끊겼습니다. 메모를 줄이거나 다시 시도해 주세요.');
  var text = msg.content.filter(function (b) { return b.type === 'text'; }).map(function (b) { return b.text; }).join('');
  return JSON.parse(text);
}

async function streamOnce(client, params, onProgress) {
  var chars = 0;
  var stream = client.beta.messages.stream(params);
  stream.on('text', function (t) { chars += t.length; if (onProgress) onProgress(chars); });
  return await stream.finalMessage();
}

function friendlyError(err) {
  if (err instanceof Anthropic.AuthenticationError) return 'API 키가 올바르지 않습니다. 설정에서 다시 확인해 주세요.';
  if (err instanceof Anthropic.PermissionDeniedError) return '이 API 키로는 선택한 모델을 쓸 수 없습니다. 모델을 바꾸거나 콘솔 권한을 확인해 주세요.';
  if (err instanceof Anthropic.RateLimitError) return '요청 한도를 넘었습니다. 잠시 후 다시 시도해 주세요.';
  if (err instanceof Anthropic.BadRequestError) return '요청 오류: ' + err.message;
  if (err instanceof Anthropic.APIConnectionError) return '네트워크에 연결할 수 없습니다. 인터넷 연결을 확인해 주세요.';
  if (err instanceof Anthropic.APIError) return 'API 오류 (' + err.status + '): ' + err.message;
  if (err instanceof SyntaxError) return '응답을 해석하지 못했습니다. 다시 시도해 주세요.';
  return err && err.message ? err.message : String(err);
}

// ---------- 이미지 입력 (긴 변 1568px로 축소해 토큰 절약) ----------
async function fileToImageBlock(file) {
  var bmp = await createImageBitmap(file);
  var scale = Math.min(1, 1568 / Math.max(bmp.width, bmp.height));
  var c = document.createElement('canvas');
  c.width = Math.round(bmp.width * scale);
  c.height = Math.round(bmp.height * scale);
  var g = c.getContext('2d');
  g.fillStyle = '#fff';
  g.fillRect(0, 0, c.width, c.height);
  g.drawImage(bmp, 0, 0, c.width, c.height);
  var dataUrl = c.toDataURL('image/jpeg', 0.9);
  return { thumb: dataUrl, block: { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: dataUrl.split(',')[1] } } };
}

// ---------- 단계별 작업 ----------
function postOpts() {
  return { postType: settings.postType, ratio: settings.ratio, length: settings.length };
}

async function stepCard() {
  var content = state.images.map(function (im) { return im.block; });
  content.push({ type: 'text', text: cardRequest(state.memo) });
  progress('① 지식카드 만드는 중');
  state.card = await callClaude({ content: content, schema: CARD_SCHEMA, effort: 'high', onProgress: tick });
  state.savedUri = null;
  persistState();
  renderAll();
}

async function stepPost() {
  if (!state.card) throw new Error('먼저 지식카드를 만들어 주세요.');
  progress('② 블로그 원고 쓰는 중');
  var r = await callClaude({ content: [{ type: 'text', text: postRequest(postOpts(), state.card, state.memo) }], schema: POST_SCHEMA, effort: 'medium', onProgress: tick });
  state.post = { titles: r.titles, title: r.titles[0] || '', keywords: r.keywords, body: r.body };
  persistState();
  renderAll();
}

async function stepReview() {
  if (!state.card || !state.post) throw new Error('카드와 원고가 있어야 검수할 수 있습니다.');
  syncPostFromEditor();
  progress('③ 발행 전 검수 중');
  state.review = await callClaude({ content: [{ type: 'text', text: reviewRequest(state.card, state.post) }], schema: REVIEW_SCHEMA, effort: 'high', onProgress: tick });
  state.review.applied = false;
  persistState();
  renderAll();
}

async function stepRevise() {
  if (!state.review || !state.review.items.length) throw new Error('반영할 검수 지적이 없습니다.');
  syncPostFromEditor();
  progress('④ 검수 지적 반영 중');
  var r = await callClaude({ content: [{ type: 'text', text: reviseRequest(state.card, state.post, state.review) }], schema: REVISE_SCHEMA, effort: 'high', onProgress: tick });
  state.card = { title: state.card.title, card_html: r.card_html, hashtags: r.hashtags, corrections: (state.card.corrections || []).concat(r.changes) };
  state.post.title = r.title;
  state.post.body = r.body;
  state.review.applied = true;
  state.review.changes = r.changes;
  state.savedUri = null;
  persistState();
  renderAll();
}

async function run(steps) {
  if (busy) return;
  busy = true;
  setBusyUi(true);
  try {
    for (var i = 0; i < steps.length; i++) await steps[i]();
    progress('완료', true);
  } catch (err) {
    showError(friendlyError(err));
  } finally {
    busy = false;
    setBusyUi(false);
  }
}

// ---------- 카드 이미지 저장 (네이티브 캡처 → 갤러리) ----------
var renderWaiters = {};
window.__kkdRendered = function (id, ok, uriOrError, name) {
  var w = renderWaiters[id];
  if (!w) return;
  delete renderWaiters[id];
  if (ok) w.resolve({ uri: uriOrError, name: name }); else w.reject(new Error(uriOrError));
};

function renderCardToGallery() {
  return new Promise(function (resolve, reject) {
    if (!Native) { reject(new Error('이미지 저장은 안드로이드 앱에서만 됩니다.')); return; }
    var id = 'r' + Date.now();
    renderWaiters[id] = { resolve: resolve, reject: reject };
    var safeTitle = (state.card.title || 'card').replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 40);
    Native.renderCard(buildCardDocument(state.card, settings, true), id, safeTitle);
  });
}

async function saveCard() {
  if (!state.card || busy) return;
  busy = true;
  setBusyUi(true);
  progress('카드 이미지 만드는 중');
  try {
    var r = await renderCardToGallery();
    state.savedUri = r.uri;
    progress('갤러리에 저장했습니다: Pictures/KKDBlog/' + r.name, true);
  } catch (err) {
    showError(friendlyError(err));
  } finally {
    busy = false;
    setBusyUi(false);
  }
}

function fullPostText() {
  syncPostFromEditor();
  return (state.post.title ? state.post.title + '\n\n' : '') + state.post.body;
}

function copyPost() {
  if (!state.post) return;
  var t = fullPostText();
  if (Native) Native.copyText(t);
  else navigator.clipboard.writeText(t);
  toast('원고를 복사했습니다. 네이버 블로그 에디터에 붙여 넣으세요.');
}

async function shareToBlog() {
  if (!state.card || !state.post) return;
  if (!state.savedUri) await saveCard();
  if (!state.savedUri) return;
  var t = fullPostText();
  if (Native) { Native.copyText(t); Native.share(t, state.savedUri); }
}

// ---------- 화면 ----------
var $ = function (id) { return document.getElementById(id); };

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
}

function toast(msg) {
  if (Native) { Native.toast(msg); return; }
  var t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(function () { t.classList.remove('show'); }, 2200);
}

var progressLabel = '';
function progress(label, done) {
  progressLabel = label;
  var p = $('progress');
  p.hidden = false;
  p.className = 'progress' + (done ? ' done' : '');
  p.textContent = done ? label : label + ' … (생각 중)';
}
function tick(chars) {
  $('progress').textContent = progressLabel + ' … ' + chars.toLocaleString() + '자 받는 중';
}
function showError(msg) {
  var p = $('progress');
  p.hidden = false;
  p.className = 'progress error';
  p.textContent = msg;
}
function setBusyUi(on) {
  document.querySelectorAll('button[data-act]').forEach(function (b) { b.disabled = on; });
}

function syncPostFromEditor() {
  if (!state.post) return;
  var ta = $('postBody');
  if (ta) state.post.body = ta.value;
  var ti = $('postTitle');
  if (ti) state.post.title = ti.value;
}

function renderImages() {
  $('thumbs').innerHTML = state.images.map(function (im, i) {
    return '<div class="thumb"><img src="' + im.thumb + '" alt=""><button class="x" data-rm="' + i + '" aria-label="삭제">×</button></div>';
  }).join('');
}

function renderCard() {
  var sec = $('cardSec');
  if (!state.card) { sec.hidden = true; return; }
  sec.hidden = false;
  var frame = $('cardFrame');
  frame.srcdoc = buildCardDocument(state.card, settings, false);
  frame.onload = function () {
    var doc = frame.contentDocument;
    var h = doc && doc.getElementById('card') ? doc.getElementById('card').getBoundingClientRect().height : 1200;
    var w = $('cardWrap').clientWidth;
    var s = w / 900;
    frame.style.height = h + 'px';
    frame.style.transform = 'scale(' + s + ')';
    $('cardWrap').style.height = Math.ceil(h * s) + 'px';
  };
  var c = state.card.corrections || [];
  $('corrections').innerHTML = c.length
    ? '<h4>원본에서 바로잡은 점</h4><ul>' + c.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul>'
    : '';
}

function renderPost() {
  var sec = $('postSec');
  if (!state.post) { sec.hidden = true; return; }
  sec.hidden = false;
  $('postTitle').value = state.post.title || '';
  $('titleChips').innerHTML = (state.post.titles || []).map(function (t) {
    return '<button class="chip" data-title="' + esc(t) + '">' + esc(t) + '</button>';
  }).join('');
  $('keywords').textContent = (state.post.keywords || []).length ? '키워드: ' + state.post.keywords.join(', ') : '';
  $('postBody').value = state.post.body || '';
  $('charCount').textContent = '공백 포함 ' + (state.post.body || '').length.toLocaleString() + '자';
}

function renderReview() {
  var sec = $('reviewSec');
  if (!state.review) { sec.hidden = true; return; }
  sec.hidden = false;
  var r = state.review;
  var groups = {};
  r.items.forEach(function (it) { (groups[it.category] = groups[it.category] || []).push(it); });
  var html = '<p class="summary">' + esc(r.summary) + '</p>';
  Object.keys(groups).forEach(function (cat) {
    html += '<h4>' + esc(cat) + ' <span class="cnt">' + groups[cat].length + '</span></h4>';
    groups[cat].forEach(function (it) {
      html += '<div class="item"><div class="loc">' + esc(it.location) + '</div>' +
        (it.quote ? '<blockquote>' + esc(it.quote) + '</blockquote>' : '') +
        '<p>' + esc(it.problem) + '</p><p class="sug">제안: ' + esc(it.suggestion) + '</p></div>';
    });
  });
  if (!r.items.length) html += '<p>지적할 사항이 없습니다.</p>';
  if (r.applied && r.changes) {
    html += '<h4>반영한 내용</h4><ul>' + r.changes.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul>';
  }
  $('reviewBody').innerHTML = html;
  $('btnRevise').hidden = r.applied || !r.items.length;
}

function renderAll() {
  renderImages();
  renderCard();
  renderPost();
  renderReview();
  $('memo').value = state.memo;
}

function fillSettingsForm() {
  $('apiKey').value = settings.apiKey;
  $('model').value = settings.model;
  $('wmText').value = settings.wmText;
  $('wmOpacity').value = settings.wmOpacity;
  $('wmEnabled').checked = settings.wmEnabled;
  $('postType').value = settings.postType;
  $('ratio').value = settings.ratio;
  $('length').value = settings.length;
  $('keyHint').hidden = !!settings.apiKey;
}

function saveSettingsForm() {
  settings.apiKey = $('apiKey').value.trim();
  settings.model = $('model').value;
  settings.wmText = $('wmText').value.trim() || 'KKD';
  settings.wmOpacity = $('wmOpacity').value || '6';
  settings.wmEnabled = $('wmEnabled').checked;
  ['apiKey', 'model', 'wmText', 'wmOpacity'].forEach(function (k) { setPref(k, settings[k]); });
  setPref('wmEnabled', settings.wmEnabled);
  $('keyHint').hidden = !!settings.apiKey;
  state.savedUri = null;
  renderCard();
  toast('설정을 저장했습니다.');
}

function saveOptions() {
  settings.postType = $('postType').value;
  settings.ratio = $('ratio').value;
  settings.length = $('length').value || '2000';
  ['postType', 'ratio', 'length'].forEach(function (k) { setPref(k, settings[k]); });
}

function bind() {
  $('pick').addEventListener('change', async function (e) {
    var files = Array.prototype.slice.call(e.target.files || []);
    for (var i = 0; i < files.length; i++) {
      try { state.images.push(await fileToImageBlock(files[i])); } catch (err) { showError('이미지를 읽지 못했습니다: ' + files[i].name); }
    }
    e.target.value = '';
    renderImages();
  });
  $('thumbs').addEventListener('click', function (e) {
    var i = e.target.getAttribute('data-rm');
    if (i !== null) { state.images.splice(Number(i), 1); renderImages(); }
  });
  $('memo').addEventListener('input', function () { state.memo = $('memo').value; persistState(); });
  ['postType', 'ratio', 'length'].forEach(function (id) { $(id).addEventListener('change', saveOptions); });
  $('saveSettings').addEventListener('click', saveSettingsForm);
  $('toggleKey').addEventListener('click', function () {
    var k = $('apiKey');
    k.type = k.type === 'password' ? 'text' : 'password';
  });
  $('titleChips').addEventListener('click', function (e) {
    var t = e.target.getAttribute('data-title');
    if (t) { $('postTitle').value = t; syncPostFromEditor(); persistState(); }
  });
  $('postBody').addEventListener('input', function () {
    syncPostFromEditor();
    $('charCount').textContent = '공백 포함 ' + state.post.body.length.toLocaleString() + '자';
    persistState();
  });
  $('postTitle').addEventListener('input', function () { syncPostFromEditor(); persistState(); });

  var actions = {
    all: function () {
      if (!state.images.length && !state.memo.trim()) { showError('이미지를 올리거나 메모를 입력해 주세요.'); return; }
      run([stepCard, stepPost, stepReview]);
    },
    card: function () {
      if (!state.images.length && !state.memo.trim()) { showError('이미지를 올리거나 메모를 입력해 주세요.'); return; }
      run([stepCard]);
    },
    post: function () { run([stepPost]); },
    review: function () { run([stepReview]); },
    revise: function () { run([stepRevise]); },
    save: saveCard,
    copy: copyPost,
    share: shareToBlog,
    reset: function () {
      if (busy) return;
      state = { images: [], memo: '', card: null, post: null, review: null, savedUri: null };
      persistState();
      $('progress').hidden = true;
      renderAll();
      window.scrollTo(0, 0);
    },
  };
  document.body.addEventListener('click', function (e) {
    var b = e.target.closest('button[data-act]');
    if (b && actions[b.getAttribute('data-act')]) actions[b.getAttribute('data-act')]();
  });
}

loadSettings();
restoreState();
fillSettingsForm();
bind();
renderAll();
if (!settings.apiKey) $('settings').open = true;
