// 지식카드 HTML 문서 조립: Claude가 만든 본문 + 고정 디자인 CSS + 해시태그 + 사선 워터마크

export var CARD_CSS = `
  :root { --ink:#1E2A3A; --blue:#2563EB; --sub:#6B7686; --line:#DCE2EA; --tint:#F3F6FA; }
  * { box-sizing:border-box; margin:0; padding:0; }
  html, body { background:#fff; }
  body { font-family:'Noto Sans KR','Noto Sans CJK KR',sans-serif; color:var(--ink); width:900px; }
  .card { position:relative; width:900px; padding:56px 56px 44px; background:#fff; overflow:hidden; }
  h1 { font-size:46px; font-weight:900; letter-spacing:-1.5px; margin:0 0 10px; line-height:1.25; }
  h1 em { font-style:normal; color:var(--blue); }
  .lead { font-size:20px; color:var(--sub); line-height:1.6; }
  .lead b { color:var(--ink); }
  .rows { margin-top:34px; border-top:2px solid var(--ink); }
  .row { display:grid; grid-template-columns:220px 1fr; gap:32px; padding:30px 0; border-bottom:1px solid var(--line); align-items:center; }
  .fig { background:var(--tint); border-radius:14px; height:190px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; }
  .fig span { font-size:14px; color:var(--sub); }
  .num { font-size:15px; font-weight:700; color:var(--blue); letter-spacing:1px; }
  h2 { font-size:30px; font-weight:900; letter-spacing:-.8px; margin:2px 0 4px; }
  h2 small { font-size:18px; font-weight:500; color:var(--sub); letter-spacing:0; margin-left:6px; }
  h3 { font-size:22px; font-weight:700; margin:0 0 10px; }
  .key { font-size:19px; font-weight:700; margin-bottom:12px; }
  .key mark { background:none; color:var(--blue); }
  ul { list-style:none; display:grid; grid-template-columns:1fr 1fr; gap:6px 18px; font-size:17px; line-height:1.5; }
  ul.one { grid-template-columns:1fr; }
  li::before { content:''; display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--blue); margin:0 9px 3px 0; }
  .ex { margin-top:12px; display:flex; flex-wrap:wrap; gap:8px; }
  .ex span { font-size:15px; padding:4px 12px; border:1px solid var(--line); border-radius:8px; color:var(--sub); }
  .ex span b { color:var(--ink); font-weight:500; }
  .note { font-size:14px; color:var(--sub); margin-top:8px; }
  .sum { margin-top:30px; display:grid; grid-template-columns:repeat(3,1fr); border:1px solid var(--line); border-radius:14px; overflow:hidden; }
  .sum.two { grid-template-columns:repeat(2,1fr); }
  .sum.four { grid-template-columns:repeat(4,1fr); }
  .sum div { padding:18px 20px; font-size:16px; line-height:1.55; border-right:1px solid var(--line); }
  .sum div:last-child { border-right:none; }
  .sum b { display:block; font-size:15px; color:var(--blue); margin-bottom:4px; }
  .bms { margin-top:18px; background:var(--ink); color:#fff; border-radius:14px; padding:20px 24px; font-size:18px; line-height:1.6; }
  .bms b { color:#8FB4FF; }
  .diagram { margin-top:30px; background:var(--tint); border-radius:14px; padding:26px; display:flex; flex-direction:column; align-items:center; gap:10px; }
  .diagram svg { max-width:736px; height:auto; }
  .diagram .cap { font-size:14px; color:var(--sub); }
  .steps { margin-top:30px; display:grid; gap:12px; counter-reset:step; }
  .steps > div { display:grid; grid-template-columns:44px 1fr; gap:16px; align-items:start; padding:16px 18px; border:1px solid var(--line); border-radius:12px; font-size:17px; line-height:1.55; }
  .steps > div::before { counter-increment:step; content:counter(step); width:44px; height:44px; border-radius:50%; background:var(--blue); color:#fff; font-weight:700; font-size:18px; display:flex; align-items:center; justify-content:center; }
  .steps b { display:block; font-size:18px; margin-bottom:2px; }
  .grid2 { margin-top:30px; display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  .grid2 > div { border:1px solid var(--line); border-radius:14px; padding:20px 22px; font-size:17px; line-height:1.55; }
  table.cmp { margin-top:30px; width:100%; border-collapse:collapse; font-size:16px; }
  table.cmp th, table.cmp td { border-bottom:1px solid var(--line); padding:12px 10px; text-align:left; vertical-align:top; }
  table.cmp th { font-size:15px; color:var(--blue); border-bottom:2px solid var(--ink); }
  code { font-family:'JetBrains Mono',Consolas,monospace; font-size:.92em; background:var(--tint); padding:1px 6px; border-radius:5px; }
  .foot { margin-top:22px; display:flex; justify-content:flex-end; font-size:14px; color:var(--sub); }
  .wm { position:absolute; inset:0; pointer-events:none; z-index:10; mix-blend-mode:difference; background-repeat:repeat; }
`;

function escXml(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
  });
}

// 사선 워터마크 타일 (흰색 글자 + difference 블렌드 → 밝은/어두운 배경 모두 보임)
export function watermarkStyle(text, opacityPct) {
  var t = escXml(text || 'KKD');
  var svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='160' height='130'>" +
    "<g font-family='Noto Sans KR,sans-serif' font-weight='900' font-size='20' fill='#FFFFFF'>" +
    "<text x='20' y='40' transform='rotate(-30 40 34)'>" + t + '</text>' +
    "<text x='100' y='105' transform='rotate(-30 120 99)'>" + t + '</text>' +
    '</g></svg>';
  var op = Math.max(0, Math.min(100, Number(opacityPct) || 0)) / 100;
  return 'opacity:' + op + ";background-image:url(\"data:image/svg+xml," + encodeURIComponent(svg) + '");';
}

// forRender=true 이면 네이티브 캡처용 신호 스크립트 포함
export function buildCardDocument(card, settings, forRender) {
  var tags = (card.hashtags || [])
    .map(function (h) { return '#' + String(h).replace(/^#/, '').replace(/\s+/g, ''); })
    .join(' ');
  var wm = settings.wmEnabled === false ? '' : '<div class="wm" style="' + watermarkStyle(settings.wmText, settings.wmOpacity).replace(/"/g, '&quot;') + '"></div>';
  var signal = forRender
    ? '<script>(function(){function go(){var h=document.getElementById("card").getBoundingClientRect().height;' +
      'if(window.KKDRender){KKDRender.ready(h);}}' +
      'var done=false;function once(){if(!done){done=true;setTimeout(go,400);}}' +
      '(document.fonts&&document.fonts.ready?document.fonts.ready:Promise.resolve()).then(once);setTimeout(once,4000);})();</script>'
    : '';
  return (
    '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">' +
    '<meta name="viewport" content="width=900">' +
    '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' +
    '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel="stylesheet">' +
    '<style>' + CARD_CSS + '</style></head><body>' +
    '<div class="card" id="card">' + sanitizeCardHtml(card.card_html || '') +
    (tags ? '<div class="foot"><span>' + escXml(tags) + '</span></div>' : '') +
    wm + '</div>' + signal + '</body></html>'
  );
}

// 모델 출력에서 스크립트·외부 리소스·이벤트 핸들러 제거 (카드는 정적 HTML + 인라인 SVG만 허용)
export function sanitizeCardHtml(html) {
  var doc = new DOMParser().parseFromString('<div id="r">' + html + '</div>', 'text/html');
  var root = doc.getElementById('r');
  root.querySelectorAll('script,iframe,object,embed,link,meta,style,img,video,audio,form,input,button').forEach(function (n) { n.remove(); });
  root.querySelectorAll('*').forEach(function (el) {
    Array.prototype.slice.call(el.attributes).forEach(function (a) {
      var n = a.name.toLowerCase();
      var v = String(a.value || '').trim().toLowerCase();
      if (n.indexOf('on') === 0) el.removeAttribute(a.name);
      else if ((n === 'href' || n === 'src' || n === 'xlink:href') && !v.startsWith('#')) el.removeAttribute(a.name);
      else if (n === 'style' && v.indexOf('url(') !== -1) el.removeAttribute(a.name);
    });
  });
  return root.innerHTML;
}
