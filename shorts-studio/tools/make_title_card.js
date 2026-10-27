#!/usr/bin/env node
// 채널 강조 제목 카드 렌더러 ("꽉찬 두 줄" 스타일)
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

var THEMES = {
  건강: { band1: '#0B1A44', band2: '#17306E', accent: '#FFD62E', chipText: '#0B1A44' },
  돈: { band1: '#06352A', band2: '#0E5541', accent: '#FFC93C', chipText: '#06352A' },
  생활: { band1: '#4A0B12', band2: '#7A1420', accent: '#FFE14D', chipText: '#4A0B12' },
  여가: { band1: '#2B1048', band2: '#4A1F7A', accent: '#FFD62E', chipText: '#2B1048' },
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
  '.tc .band{position:absolute;left:0;right:0;top:0;height:700px;padding:170px 60px 0;box-sizing:border-box;',
  '  background:linear-gradient(180deg,var(--band1),var(--band2));border-bottom:14px solid var(--accent);text-align:center}',
  '.tc .band:before{content:"";position:absolute;left:0;top:0;bottom:0;width:22px;background:var(--accent)}',
  '.tc .chip{display:inline-block;background:var(--accent);color:var(--chipText);font:900 52px/1 "Noto Sans KR",sans-serif;',
  '  padding:16px 30px 18px;border-radius:14px;letter-spacing:-1px;box-shadow:0 6px 0 rgba(0,0,0,.35);margin-bottom:34px}',
  '.tc .l{display:block;white-space:nowrap;line-height:1.08;letter-spacing:-3px;',
  '  text-shadow:0 8px 0 rgba(0,0,0,.45),0 0 2px rgba(0,0,0,.6)}',
  '.tc .l1{color:#fff}',
  '.tc .l2{color:var(--accent)}',
  '.tc .sig{position:absolute;right:46px;bottom:22px;font:700 34px/1 "Noto Sans KR",sans-serif;color:rgba(255,255,255,.75);letter-spacing:-.5px}',
].join('\n');

// 한 줄이 밴드 폭(960px)에 맞도록 글자 크기를 맞춘다 (최대 150px, 최소 96px)
var FIT_JS =
  'document.querySelectorAll(".tc .l").forEach(function(el){var s=150;el.style.fontSize=s+"px";' +
  'while(el.scrollWidth>960&&s>96){s-=4;el.style.fontSize=s+"px";}});';

function cardHtml(opt) {
  var t = THEMES[opt.theme] || THEMES['건강'];
  var vars = '--band1:' + t.band1 + ';--band2:' + t.band2 + ';--accent:' + t.accent + ';--chipText:' + t.chipText;
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
  { theme: '건강', tag: '2026년 대상', line1: '짝수년생 건강검진', line2: '12월 31일까지', note: '시범 회차 (검증 완료 문구)' },
  { theme: '돈', tag: '디자인 예시', line1: '은퇴 후 건보료', line2: '이것부터 확인', note: '돈 · 초록+금색' },
  { theme: '생활', tag: '디자인 예시', line1: '이런 문자 오면', line2: '절대 누르지 마세요', note: '생활·사기예방 · 버건디+노랑' },
  { theme: '여가', tag: '디자인 예시', line1: '가을 걷기 좋은 길', line2: '수도권 3곳', note: '여가 · 보라+노랑' },
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
    '<h1>강조 제목 스타일 — 꽉찬 두 줄</h1>' +
    '<p>위쪽 밴드에 태그 1개, 흰 줄 1개, 강조색 줄 1개. 주제 분야마다 밴드 색이 달라 채널 영상이 한눈에 구분됩니다. 아래 배경은 Vrew AI 이미지가 들어갈 자리입니다.</p>' +
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
