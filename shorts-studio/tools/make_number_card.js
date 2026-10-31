#!/usr/bin/env node
// 숫자 카드 렌더러 — 숫자·비교를 표 한 장으로 보여주는 전체 화면 이미지
//
//   node shorts-studio/tools/make_number_card.js <회차폴더>
//     → vrew.md의 ```vrew-numbers``` 블록(카드 배열)으로
//       vrew-pack/number-1.png, number-2.png ... (1080x1920, 해당 장면의 이미지 자리에 그대로 쓰기)
//   node shorts-studio/tools/make_number_card.js --showcase <출력.html>
//     → 스타일 견본 페이지
//
// 블록 형식과 규칙은 shorts-studio/brand/number-card-style.md 참고.
// 카드에 쓴 숫자가 factcheck.md에 없거나, 시기 표현(올해·연도·날짜 등)이 있으면 만들지 않는다.
var fs = require('fs');
var path = require('path');

// 분야별 배경색 (제목 그림 강조색과 같은 계열)
var THEMES = {
  건강: '#FFE14D',
  재테크: '#9CF2A6',
  '노후 준비': '#FFC56B',
  여행: '#9FE2FF',
  생활정보: '#FFA866',
  '최신 이슈': '#FF8C8C',
};
var THEME_ALIAS = { 돈: '재테크', 생활: '생활정보', 여가: '여행', 노후: '노후 준비', 이슈: '최신 이슈' };
function themeName(name) {
  return THEMES[name] ? name : THEME_ALIAS[name] || '건강';
}

// 영상이 오래 맞도록 카드에 쓰지 않는 표현 (channel-profile.md '오래 봐도 맞는 주제만')
var DATED = /지금|요즘|이번\s*(주|달)|올해|내년|오늘부터|새로\s*바뀐|(19|20)\d\d\s*년|\d{4}\s*[.\/-]\s*\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일/;

function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
  });
}

var CSS = [
  "@import url('https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@500;700;900&display=swap');",
  '.nc{position:relative;width:1080px;height:1920px;overflow:hidden;background:var(--bg);font-family:"Noto Sans KR",sans-serif;',
  '  display:flex;flex-direction:column;align-items:center;padding:150px 56px 0;box-sizing:border-box}',
  '.nc .t{font-family:"Black Han Sans","Noto Sans KR",sans-serif;color:#1B2A6B;text-align:center;line-height:1.18;letter-spacing:-2px;white-space:nowrap}',
  '.nc .t1{font-size:96px}',
  '.nc .t2{font-size:96px;background:#1B2A6B;color:#fff;padding:2px 28px 10px;margin-top:10px;border-radius:6px}',
  '.nc table{margin-top:56px;width:100%;border-collapse:collapse;background:#fff;border:4px solid #1d1d1f;',
  '  box-shadow:0 10px 0 rgba(0,0,0,.18)}',
  '.nc th,.nc td{border:2px solid #1d1d1f;text-align:center;padding:0 10px;color:#1d1d1f;white-space:nowrap}',
  '.nc th{background:#ECEEF3;font-weight:900;white-space:normal;word-break:keep-all;line-height:1.15}',
  '.nc td{font-weight:700;white-space:normal;word-break:keep-all;line-height:1.2}',
  '.nc td.k{background:#FFF1E6}',
  '.nc td.hl,.nc th.hl{background:#DCE6FF;color:#0B2FA8;font-weight:900}',
  '.nc tr.hl td{background:#FFF7B8;font-weight:900}',
  '.nc .n{margin-top:36px;width:100%;font-size:36px;font-weight:700;color:#1d1d1f;line-height:1.45}',
  '.nc .n::before{content:"✔ ";color:#1B2A6B}',
].join('\n');

// 표가 화면에 맞도록 글자 크기·행 높이를 정하고, 제목 줄이 넘치면 줄인다.
// 내용은 BOTTOM(px) 위에서 끝낸다: 그 아래는 Vrew 자막과 쇼츠 화면 버튼 자리.
var BOTTOM = 1480;
var FIT_JS =
  'document.querySelectorAll(".nc").forEach(function(c){' +
  'c.querySelectorAll(".t").forEach(function(el){var s=96;while(el.scrollWidth>968&&s>60){s-=4;el.style.fontSize=s+"px";}});' +
  'var tb=c.querySelector("table"),n=c.querySelector(".n"),rows=tb.rows.length;' +
  'var fs=64,h=Math.max(90,Math.min(170,Math.floor(1000/rows)));' +
  'function set(){tb.querySelectorAll("th,td").forEach(function(td){td.style.fontSize=(td.tagName=="TH"?Math.round(fs*.8):fs)+"px";td.style.height=h+"px";});}' +
  'set();while(tb.scrollWidth>968&&fs>34){fs-=2;set();}' +
  // 칸 글자가 두 줄로 꺾이면 46px까지는 글자를 줄여 한 줄에 넣는다
  'function wrapped(){return [].some.call(tb.querySelectorAll("td span"),function(s){return s.getClientRects().length>1;});}' +
  'while(wrapped()&&fs>46){fs-=2;set();}' +
  'function bottom(){var e=n||tb;return e.getBoundingClientRect().bottom-c.getBoundingClientRect().top;}' +
  'while(bottom()>' + BOTTOM + '&&h>64){h-=4;set();}' +
  'while(bottom()>' + BOTTOM + '&&fs>34){fs-=2;set();}' +
  '});';

function cardHtml(card, theme) {
  var cols = card['열'] || [];
  var hlCol = card['강조열'];
  var hlRows = card['강조행'] || [];
  var titles = String(card['제목'] || '').split('\n').filter(Boolean);
  var head = '<tr>' + cols.map(function (c, i) {
    return '<th' + (i === hlCol ? ' class="hl"' : '') + '>' + esc(c) + '</th>';
  }).join('') + '</tr>';
  var body = (card['행'] || []).map(function (r, ri) {
    return '<tr' + (hlRows.indexOf(ri + 1) >= 0 ? ' class="hl"' : '') + '>' + r.map(function (c, i) {
      var cls = i === hlCol ? 'hl' : i === 0 ? 'k' : '';
      return '<td' + (cls ? ' class="' + cls + '"' : '') + '><span>' + esc(c) + '</span></td>';
    }).join('') + '</tr>';
  }).join('');
  return (
    '<div class="nc" style="--bg:' + THEMES[themeName(theme)] + '">' +
    (titles[0] ? '<div class="t t1">' + esc(titles[0]) + '</div>' : '') +
    (titles[1] ? '<div class="t t2">' + esc(titles[1]) + '</div>' : '') +
    '<table>' + head + body + '</table>' +
    (card['주석'] ? '<div class="n">' + esc(card['주석']).replace(/\n/g, '<br>') + '</div>' : '') +
    '</div>'
  );
}

function pageHtml(body) {
  return (
    '<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>' + CSS +
    'html,body{margin:0;background:#111}</style></head><body>' + body +
    '<script>document.fonts.ready.then(function(){' + FIT_JS + 'document.body.dataset.ready=1;});</script></body></html>'
  );
}

function digits(s) {
  return String(s).replace(/[\s,]/g, '');
}

// 카드를 읽고 형식·시기 표현·숫자 근거를 검사한다
function readCards(folder) {
  var md = fs.readFileSync(path.join(folder, 'vrew.md'), 'utf8');
  var m = md.match(/```vrew-numbers\n([\s\S]*?)```/);
  if (!m) return null;
  var cards = JSON.parse(m[1]);
  if (!Array.isArray(cards) || !cards.length) throw new Error('vrew-numbers는 카드 1개 이상의 배열이어야 합니다.');
  var scenes = JSON.parse((md.match(/```vrew-scenes\n([\s\S]*?)```/) || [])[1] || '[]');
  var theme = (scenes[0] && scenes[0]['테마']) || '건강';
  var fact = digits(fs.readFileSync(path.join(folder, 'factcheck.md'), 'utf8'));
  cards.forEach(function (c, ci) {
    var name = (ci + 1) + '번 카드';
    var cols = c['열'] || [];
    if (!c['제목'] || !cols.length || !(c['행'] || []).length) throw new Error(name + ': 제목·열·행이 모두 있어야 합니다.');
    if (String(c['제목']).split('\n').filter(Boolean).length > 2) throw new Error(name + ': 제목은 2줄 이하입니다.');
    if (cols.length > 4) throw new Error(name + ': 열은 4개 이하입니다 (휴대폰에서 읽히게).');
    if (c['행'].length > 10) throw new Error(name + ': 행은 10개 이하입니다.');
    c['행'].forEach(function (r, ri) {
      if (r.length !== cols.length) throw new Error(name + ' ' + (ri + 1) + '행: 칸 수가 열 수와 다릅니다.');
    });
    var sc = [].concat(c['장면'] || []);
    if (!sc.length || sc.some(function (n) { return !scenes[n - 1]; })) throw new Error(name + ': 장면 번호가 vrew-scenes에 없습니다.');
    var all = [c['제목'], c['주석'] || ''].concat(cols, [].concat.apply([], c['행'])).join(' ');
    var dated = all.match(DATED);
    if (dated) throw new Error(name + ': 시기 표현 "' + dated[0] + '"은 쓰지 않습니다 (오래 봐도 맞는 주제만).');
    var nums = all.match(/\d[\d,.]*/g) || [];
    var missing = nums.filter(function (n) { return fact.indexOf(digits(n).replace(/\.$/, '')) < 0; });
    if (missing.length) throw new Error(name + ': factcheck.md에서 확인되지 않은 숫자 ' + missing.join(', ') + ' → 사실 검증에 넣고 다시 판정받으세요.');
  });
  return { cards: cards, theme: theme };
}

async function render(html, file) {
  var chromium = require('playwright').chromium;
  var browser = await chromium.launch();
  var page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.setContent(pageHtml(html));
  await page.waitForSelector('body[data-ready]');
  await page.screenshot({ path: file });
  await browser.close();
}

var SAMPLE = {
  '장면': [1],
  '제목': '숫자 카드 견본\n한눈에 비교',
  '열': ['구분', '조건 A', '조건 B'],
  '행': [['항목 1', '120', '150'], ['항목 2', '180', '210'], ['항목 3', '240', '270']],
  '강조열': 2,
  '주석': '출처: 공식 자료 이름\n개인 상황에 따라 다를 수 있음',
};

function showcase(out) {
  var cards = Object.keys(THEMES).map(function (t) {
    return '<figure><div class="scale">' + cardHtml(SAMPLE, t) + '</div><figcaption>' + esc(t) + '</figcaption></figure>';
  }).join('');
  var html =
    '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>숫자 카드 스타일</title><style>' + CSS +
    'body{margin:0;background:#0f1115;color:#e9ecf1;font:17px/1.6 "Noto Sans KR",sans-serif}main{max-width:1100px;margin:0 auto;padding:16px}' +
    'h1{font-size:24px;margin:8px 0}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:20px}' +
    'figure{margin:0}.scale{width:252px;height:448px;overflow:hidden;border-radius:14px}.scale .nc{transform:scale(.2333);transform-origin:0 0}' +
    'figcaption{margin-top:8px;color:#9aa3b2;font-size:15px}</style></head><body><main>' +
    '<h1>숫자 카드 스타일 — 분야별 배경색</h1><div class="grid">' + cards + '</div>' +
    '</main><script>document.fonts.ready.then(function(){' + FIT_JS + '});</script></body></html>';
  fs.writeFileSync(out, html);
  console.log('견본 페이지: ' + out);
}

async function main() {
  var args = process.argv.slice(2);
  if (args[0] === '--showcase' && args[1]) return showcase(args[1]);
  if (args.length !== 1) {
    console.log('사용법: node make_number_card.js <회차폴더> | --showcase <출력.html>');
    process.exitCode = 2;
    return;
  }
  var folder = args[0];
  var data = readCards(folder);
  if (!data) throw new Error('vrew.md에 vrew-numbers 블록이 없습니다. 숫자 카드를 1장 이상 설계하세요.');
  var out = path.join(folder, 'vrew-pack');
  fs.mkdirSync(out, { recursive: true });
  fs.readdirSync(out).filter(function (f) { return /^number-\d+\.png$/.test(f); }).forEach(function (f) {
    fs.unlinkSync(path.join(out, f));
  });
  for (var i = 0; i < data.cards.length; i++) {
    await render(cardHtml(data.cards[i], data.theme), path.join(out, 'number-' + (i + 1) + '.png'));
  }
  console.log('완료: ' + out + '/number-1.png' + (data.cards.length > 1 ? ' ~ number-' + data.cards.length + '.png' : ''));
}

main().catch(function (e) {
  console.error('숫자 카드를 만들지 않았습니다: ' + e.message);
  process.exitCode = 1;
});
