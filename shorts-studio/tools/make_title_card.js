#!/usr/bin/env node
// 채널 강조 제목 카드 렌더러 ("배경 없는 두 줄" 스타일)
//
//   node shorts-studio/tools/make_title_card.js <회차폴더>
//     → vrew.md의 vrew-scenes 1번 장면(큰글자 2줄, 태그, 테마)으로
//       vrew-pack/title-overlay.png (투명 배경, Vrew 첫 장면 위에 얹기)
//       vrew-pack/title-preview.png (배경 자리 표시, 미리보기용)
//   node shorts-studio/tools/make_title_card.js --showcase <출력.html>
//     → 스타일 견본 페이지
//
// 스타일 규칙은 shorts-studio/brand/title-style.md 참고.
var fs = require('fs');
var path = require('path');

var CHANNEL = '오늘의 5060'; // 채널 이름이 정해지면 여기만 바꾸세요

// 배경 띠 없이 글자만 얹는 스타일: 분야는 강조색(태그·2줄)으로만 구분
var THEMES = {
  건강: { accent: '#FFD62E' },
  돈: { accent: '#7CF08A' },
  생활: { accent: '#FF8A3D' },
  여가: { accent: '#7FD8FF' },
};

// 배경 사진 자리 표시 (실제 영상에서는 Vrew AI 이미지가 들어감)
var PREVIEW_BG = {
  건강: 'linear-gradient(180deg,#cfe3f3 0%,#9cc3e0 55%,#e9d9c4 100%)',
  돈: 'linear-gradient(180deg,#f3e6c4 0%,#d9b46a 60%,#7b5a2a 100%)',
  생활: 'linear-gradient(180deg,#e9e4dc 0%,#bfb2a2 60%,#5e5246 100%)',
  여가: 'linear-gradient(180deg,#ffb35c 0%,#e2603a 50%,#5a2a4a 100%)',
};

function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
  });
}

var CSS = [
  "@import url('https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@700;900&display=swap');",
  '.tc{position:relative;width:1080px;height:1920px;overflow:hidden;font-family:"Black Han Sans","Noto Sans KR",sans-serif}',
  '.tc .bg{position:absolute;inset:0}',
  '.tc .band{position:absolute;left:0;right:0;top:0;padding:200px 50px 0;box-sizing:border-box;text-align:center}',
  '.tc .chip{display:inline-block;background:var(--accent);color:#111;font:900 54px/1 "Noto Sans KR",sans-serif;',
  '  padding:16px 30px 18px;border-radius:14px;letter-spacing:-1px;box-shadow:0 6px 0 rgba(0,0,0,.45);margin-bottom:30px}',
  '.tc .l{display:block;white-space:nowrap;line-height:1.12;letter-spacing:-3px;',
  '  -webkit-text-stroke:18px #111;paint-order:stroke fill;text-shadow:0 12px 0 rgba(0,0,0,.55),0 0 30px rgba(0,0,0,.45)}',
  '.tc .l1{color:#fff}',
  '.tc .l2{color:var(--accent)}',
  '.tc .sig{display:inline-block;margin-top:22px;font:900 36px/1 "Noto Sans KR",sans-serif;color:#fff;letter-spacing:-.5px;',
  '  -webkit-text-stroke:8px #111;paint-order:stroke fill}',
].join('\n');

// 한 줄이 화면 폭(980px)에 맞도록 글자 크기를 맞춘다 (최대 150px, 최소 96px)
var FIT_JS =
  'document.querySelectorAll(".tc .l").forEach(function(el){var s=150;el.style.fontSize=s+"px";' +
  'while(el.scrollWidth>980&&s>96){s-=4;el.style.fontSize=s+"px";}});';

function cardHtml(opt) {
  var t = THEMES[opt.theme] || THEMES['건강'];
  var vars = '--accent:' + t.accent;
  var bg = opt.preview ? '<div class="bg" style="background:' + (PREVIEW_BG[opt.theme] || PREVIEW_BG['건강']) + '"></div>' : '';
  return (
    '<div class="tc" style="' + vars + '">' + bg +
    '<div class="band">' +
    (opt.tag ? '<span class="chip">' + esc(opt.tag) + '</span>' : '') +
    '<span class="l l1">' + esc(opt.line1) + '</span>' +
    '<span class="l l2">' + esc(opt.line2) + '</span>' +
    '<span class="sig">' + esc(CHANNEL) + '</span>' +
    '</div></div>'
  );
}

function pageHtml(body, transparent) {
  return (
    '<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>' + CSS +
    'html,body{margin:0;background:' + (transparent ? 'transparent' : '#111') + '}</style></head><body>' +
    body + '<script>document.fonts.ready.then(function(){' + FIT_JS + 'document.body.dataset.ready=1;});</script></body></html>'
  );
}

function readScene1(folder) {
  var md = fs.readFileSync(path.join(folder, 'vrew.md'), 'utf8');
  var m = md.match(/```vrew-scenes\n([\s\S]*?)```/);
  if (!m) throw new Error('vrew.md에 vrew-scenes 블록이 없습니다.');
  var s = JSON.parse(m[1])[0];
  var lines = String(s['큰글자'] || '').split('\n').filter(Boolean);
  if (lines.length !== 2) throw new Error('1번 장면 큰글자는 줄바꿈으로 나눈 2줄이어야 합니다.');
  return { line1: lines[0], line2: lines[1], tag: s['태그'] || '', theme: s['테마'] || '건강' };
}

async function render(opt, file, preview) {
  var chromium = require('playwright').chromium;
  var browser = await chromium.launch();
  var page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.setContent(pageHtml(cardHtml(Object.assign({}, opt, { preview: preview })), !preview));
  await page.waitForSelector('body[data-ready]');
  await page.screenshot({ path: file, omitBackground: !preview });
  await browser.close();
}

var SAMPLES = [
  { theme: '건강', tag: '2026년 대상', line1: '짝수년생 건강검진', line2: '12월 31일까지', note: '건강 · 노랑 강조 — 시범 회차 (검증 완료 문구)' },
  { theme: '돈', tag: '디자인 예시', line1: '은퇴 후 건보료', line2: '이것부터 확인', note: '돈 · 연두 강조' },
  { theme: '생활', tag: '디자인 예시', line1: '이런 문자 오면', line2: '절대 누르지 마세요', note: '생활·사기예방 · 주황 강조' },
  { theme: '여가', tag: '디자인 예시', line1: '가을 걷기 좋은 길', line2: '수도권 3곳', note: '여가 · 하늘 강조' },
];

function showcase(out) {
  var cards = SAMPLES.map(function (s) {
    return '<figure><div class="scale">' + cardHtml(Object.assign({ preview: true }, s)) + '</div><figcaption>' + esc(s.note) + '</figcaption></figure>';
  }).join('');
  var html =
    '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>강조 제목 스타일</title><style>' + CSS +
    'body{margin:0;background:#0f1115;color:#e9ecf1;font:17px/1.6 "Noto Sans KR",sans-serif}main{max-width:1100px;margin:0 auto;padding:16px}' +
    'h1{font-size:24px;margin:8px 0}p{color:#9aa3b2}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:20px}' +
    'figure{margin:0}.scale{width:252px;height:448px;overflow:hidden;border-radius:14px}.scale .tc{transform:scale(.2333);transform-origin:0 0}' +
    'figcaption{margin-top:8px;color:#9aa3b2;font-size:15px}ul{color:#c9d0db}</style></head><body><main>' +
    '<h1>강조 제목 스타일 — 배경 없는 두 줄</h1>' +
    '<p>배경 띠 없이 태그 1개, 흰 줄 1개, 강조색 줄 1개를 굵은 검은 테두리로 이미지 위에 바로 얹습니다. 분야는 강조색으로 구분합니다. 뒤 배경은 Vrew AI 이미지가 들어갈 자리입니다.</p>' +
    '<div class="grid">' + cards + '</div>' +
    '<h1 style="margin-top:28px">규칙</h1><ul>' +
    '<li>1줄: 누구 얘기인지 (흰색) · 2줄: 핵심 숫자나 행동 (강조색)</li>' +
    '<li>한 줄 9자 안팎 — 길면 글자가 자동으로 작아지지만 96px 아래로는 안 줄어듭니다</li>' +
    '<li>태그는 6자 이내, 시기·대상 (예: 2026년 대상, 11월부터)</li>' +
    '<li>제목에 쓰는 사실은 팩트체크 통과 문구만</li></ul>' +
    '</main><script>document.fonts.ready.then(function(){' + FIT_JS + '});</script></body></html>';
  fs.writeFileSync(out, html);
  console.log('견본 페이지: ' + out);
}

async function main() {
  var args = process.argv.slice(2);
  if (args[0] === '--showcase' && args[1]) return showcase(args[1]);
  if (args.length !== 1) {
    console.log('사용법: node make_title_card.js <회차폴더> | --showcase <출력.html>');
    process.exitCode = 2;
    return;
  }
  var folder = args[0];
  var opt = readScene1(folder);
  var out = path.join(folder, 'vrew-pack');
  fs.mkdirSync(out, { recursive: true });
  await render(opt, path.join(out, 'title-overlay.png'), false);
  await render(opt, path.join(out, 'title-preview.png'), true);
  console.log('완료: ' + out + '/title-overlay.png, title-preview.png');
}

main().catch(function (e) {
  console.error('제목 카드를 만들지 않았습니다: ' + e.message);
  process.exitCode = 1;
});
