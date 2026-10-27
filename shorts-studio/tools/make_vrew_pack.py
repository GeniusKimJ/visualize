#!/usr/bin/env python3
"""회차 폴더의 결과물로 Vrew 복사용 패키지(vrew-pack/)를 만든다.

사용법: python3 shorts-studio/tools/make_vrew_pack.py shorts-studio/episodes/<회차폴더>

- factcheck.md 최신(맨 위) 최종판정과 qa.md 마지막 QA 판정이 '통과'일 때만 만든다.
- script.md 첫 번째 'Vrew 붙여넣기용 순수 원고' 블록과 vrew.md의 ```vrew-scenes``` JSON 블록,
  upload.md의 추천 제목·설명란·고정댓글·업로드 직전 확인 항목을 읽는다.
"""
import html
import json
import re
import sys
from pathlib import Path

IMAGE_STYLE_KO = "따뜻한 자연광, 사실적인 사진 스타일, 세로 9:16 구도, 화면에 글자 없음"
IMAGE_STYLE_EN = "warm natural light, realistic photo, vertical 9:16, no text in image"

# 영상·업로드 후에만 확인할 수 있어 회차와 상관없이 항상 넣는 항목
ALWAYS_CHECK = [
    "AI 목소리가 숫자·영문(연도, 전화번호, 앱 이름)을 제대로 읽는지 들어 보기",
    "휴대폰으로 끝까지 재생: 자막이 얼굴·쇼츠 버튼을 가리지 않는지, 길이 30~60초인지",
    "배경음악 곡명·라이선스를 설명란 [음원] 칸에 채우기",
    "업로드 후 YouTube Studio에서 '저작권 주장' 없는지 확인",
]


class PackError(Exception):
    pass


def read(folder, name):
    path = folder / name
    if not path.exists():
        raise PackError(f"{name} 파일이 없습니다.")
    return path.read_text(encoding="utf-8")


def check_gates(folder):
    fact = re.search(r"^최종판정\s*=\s*(\S+)", read(folder, "factcheck.md"), re.M)
    if not fact or not fact.group(1).startswith("통과"):
        raise PackError("factcheck.md 최신 최종판정이 '통과'가 아닙니다. 사실 검증을 먼저 통과하세요.")
    qa = re.findall(r"^QA\s*=\s*(\S+)", read(folder, "qa.md"), re.M)
    if not qa or not qa[-1].startswith("통과"):
        raise PackError("qa.md 마지막 QA 판정이 '통과'가 아닙니다. 업로드 전 점검을 먼저 통과하세요.")


def code_block_after(text, heading_pattern, lang=""):
    m = re.search(heading_pattern, text, re.M)
    if not m:
        return None
    block = re.search(r"```" + lang + r"\n(.*?)```", text[m.end():], re.S)
    return block.group(1).strip("\n") if block else None


def parse_script(folder):
    script = code_block_after(read(folder, "script.md"), r"^## Vrew 붙여넣기용 순수 원고")
    if not script:
        raise PackError("script.md에서 'Vrew 붙여넣기용 순수 원고' 블록을 찾지 못했습니다.")
    return script


def parse_scenes(folder, script):
    raw = code_block_after(read(folder, "vrew.md"), r"^", "vrew-scenes")
    if not raw:
        raise PackError("vrew.md에 ```vrew-scenes``` 블록이 없습니다. shorts-vrew-director로 다시 만드세요.")
    try:
        scenes = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PackError(f"vrew-scenes JSON 형식 오류: {e}")
    lines = [l for l in script.split("\n") if l.strip()]
    narr = [s.get("나레이션", "") for s in scenes]
    if narr != lines:
        raise PackError("vrew-scenes의 나레이션이 script.md 최종 원고와 줄 단위로 다릅니다. 장면표를 최신 원고로 맞추세요.")
    return scenes


def parse_upload(folder):
    text = read(folder, "upload.md")
    title = re.search(r'^### 추천:\s*\d+안\s*"(.+?)"', text, re.M)
    desc = code_block_after(text, r"^## \d+\. 설명란")
    pinned = code_block_after(text, r"^## \d+\. 고정댓글")
    if not (title and desc and pinned):
        raise PackError("upload.md에서 추천 제목·설명란·고정댓글 중 하나를 찾지 못했습니다.")
    when = re.search(r"^## \d+\. 업로드 추천 시간\n+\*\*(.+?)\*\*", text, re.M)
    pre = re.search(r"^## 업로드 직전 확인.*?\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    checks = re.findall(r"^- \[ \] (.+)$", pre.group(1), re.M) if pre else []
    return {
        "title": title.group(1),
        "desc": desc,
        "pinned": pinned,
        "when": when.group(1) if when else "",
        "checks": checks,
    }


def build_texts(script, scenes, up):
    prompts, bigtext = [], []
    for i, s in enumerate(scenes, 1):
        prompts.append(
            f"[장면 {i}] {s['나레이션']}\n"
            f"  한글: {s['이미지프롬프트_ko']}, {IMAGE_STYLE_KO}\n"
            f"  영문: {s['이미지프롬프트_en']}, {IMAGE_STYLE_EN}"
        )
        if s.get("큰글자"):
            bigtext.append(f"[장면 {i}] {s['큰글자']}")
    upload = (
        f"[제목]\n{up['title']}\n\n[설명란]\n{up['desc']}\n\n[고정댓글]\n{up['pinned']}\n"
        + (f"\n[업로드 추천 시간]\n{up['when']}\n" if up["when"] else "")
    )
    return {
        "01_원고_붙여넣기.txt": script + "\n",
        "02_AI이미지_프롬프트.txt": "\n\n".join(prompts) + "\n",
        "03_화면_큰글자.txt": ("\n".join(bigtext) or "(큰 글자 장면 없음)") + "\n",
        "04_업로드_정보.txt": upload,
    }


def card(title, body, copy_text=None, note=""):
    btn = ""
    if copy_text is not None:
        btn = f'<button class="copy" data-copy="{html.escape(copy_text, quote=True)}">복사</button>'
    note_html = f'<p class="note">{note}</p>' if note else ""
    return (
        f'<section class="card"><div class="card-head"><h3>{html.escape(title)}</h3>{btn}</div>'
        f"{note_html}<pre>{html.escape(body)}</pre></section>"
    )


def build_html(episode, script, scenes, up, has_title=False):
    scene_cards = []
    for i, s in enumerate(scenes, 1):
        ko = f"{s['이미지프롬프트_ko']}, {IMAGE_STYLE_KO}"
        big = s.get("큰글자") or ""
        rows = [
            f'<div class="row"><span class="label">나레이션</span><span>{html.escape(s["나레이션"])}</span></div>',
            f'<div class="row"><span class="label">AI 이미지</span><span>{html.escape(ko)}</span>'
            f'<button class="copy small" data-copy="{html.escape(ko, quote=True)}">복사</button></div>',
        ]
        if big:
            rows.append(
                f'<div class="row"><span class="label">큰 글자</span><strong>{html.escape(big)}</strong>'
                f'<button class="copy small" data-copy="{html.escape(big, quote=True)}">복사</button></div>'
            )
        scene_cards.append(f'<section class="scene"><h4>장면 {i}</h4>{"".join(rows)}</section>')

    checks = up["checks"] + ALWAYS_CHECK
    check_items = "".join(
        f'<label class="check"><input type="checkbox" data-key="{i}"><span>{html.escape(c)}</span></label>'
        for i, c in enumerate(checks)
    )
    return HTML_TEMPLATE.format(
        episode=html.escape(episode),
        script_card=card("1. 대본 붙여넣기", script, script,
                         "Vrew → 새로 만들기 → 텍스트로 비디오 만들기 → 쇼츠 9:16 → 대본 칸에 붙여넣기"),
        scenes="".join(scene_cards),
        title_card=card("제목", up["title"], up["title"]),
        desc_card=card("설명란", up["desc"], up["desc"], "[음원] 칸은 고른 배경음악으로 채운 뒤 올리세요."),
        pinned_card=card("고정댓글", up["pinned"], up["pinned"]),
        when=html.escape(up["when"]) or "—",
        title_section=TITLE_SECTION if has_title else "",
        checks=check_items,
    )


TITLE_SECTION = """<h2>0단계 · 첫 장면 강조 제목</h2>
<section class="card"><img src="title-preview.png" alt="강조 제목 미리보기" style="width:100%;max-width:320px;border-radius:12px;display:block">
<p class="note">Vrew 1번 장면 → 삽입 → 이미지 → 같은 폴더의 <strong>title-overlay.png</strong>(투명 배경) → 화면 전체 크기로 맨 위에 얹기.
1번 장면의 '큰 글자'는 이 이미지가 대신하므로 따로 넣지 않습니다. 아래 배경은 AI 이미지 자리 표시입니다.</p></section>
"""

HTML_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vrew 작업 카드 — {episode}</title>
<style>
:root{{--bg:#0f1115;--card:#181b22;--line:#2a2f3a;--text:#e9ecf1;--muted:#9aa3b2;--accent:#f5c518;--btn:#2d6cdf;--btn-text:#fff}}
.theme-light{{--bg:#f6f7f9;--card:#fff;--line:#dde1e7;--text:#16191f;--muted:#5b6474;--accent:#b8860b;--btn:#1f5fd1;--btn-text:#fff}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:18px/1.6 -apple-system,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif}}
main{{max-width:760px;margin:0 auto;padding:16px}}
header{{display:flex;justify-content:space-between;align-items:center;gap:12px}}
h1{{font-size:22px;margin:8px 0}} h2{{font-size:20px;margin:28px 0 8px;border-bottom:2px solid var(--accent);padding-bottom:4px}}
h3{{font-size:18px;margin:0}} h4{{margin:0 0 6px;color:var(--accent)}}
.card,.scene{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:12px 0}}
.card-head{{display:flex;justify-content:space-between;align-items:center;gap:8px}}
pre{{white-space:pre-wrap;word-break:break-word;margin:10px 0 0;font:inherit}}
.note{{color:var(--muted);font-size:16px;margin:6px 0 0}}
.row{{display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap;margin:6px 0}}
.row>span:nth-child(2),.row>strong{{flex:1 1 220px}}
.label{{color:var(--muted);font-size:15px;min-width:72px}}
button{{font:inherit;cursor:pointer;border:0;border-radius:8px}}
.copy{{background:var(--btn);color:var(--btn-text);padding:10px 18px;min-height:44px}}
.copy.small{{padding:6px 14px;min-height:36px;font-size:16px}}
.copy.done{{background:#2e9e5b}}
#theme{{background:var(--card);color:var(--text);border:1px solid var(--line);padding:8px 12px}}
.check{{display:flex;gap:10px;align-items:flex-start;padding:10px 0;border-bottom:1px solid var(--line)}}
.check input{{width:22px;height:22px;margin-top:3px;flex:none}}
.check span,pre,.row span{{min-width:0;overflow-wrap:anywhere}}
.steps li{{margin:4px 0}}
</style></head>
<body><main>
<header><h1>Vrew 작업 카드</h1><button id="theme" type="button">밝게/어둡게</button></header>
<p class="note">{episode} · 사실 검증과 업로드 전 점검을 통과한 회차입니다. 위에서부터 차례로 복사해 붙여넣으세요.</p>
<ol class="steps">
<li>대본 붙여넣기 → AI 목소리(차분한 중년, 0.9~1.0배)</li>
<li>장면마다 AI 이미지 문구 복사 → 이미지 바꾸기</li>
<li>큰 글자가 있는 장면에 텍스트 추가</li>
<li>배경음악(오디오 보관함·Vrew 음원) → 내보내기 mp4</li>
<li>제목·설명란·고정댓글 복사해 업로드</li>
</ol>
{title_section}<h2>1단계 · 대본</h2>
{script_card}
<h2>2~3단계 · 장면별 이미지와 큰 글자</h2>
{scenes}
<h2>5단계 · 업로드 정보</h2>
{title_card}
{desc_card}
{pinned_card}
<p class="note">업로드 추천 시간: {when}</p>
<h2>업로드 전 직접 확인</h2>
<section class="card">{checks}</section>
</main>
<script>
var root = document.documentElement;
var stored = null;
try {{ stored = localStorage.getItem("vrew-pack-theme"); }} catch (e) {{}}
var light = stored ? stored === "light" : (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches);
if (light) root.classList.add("theme-light");
document.getElementById("theme").addEventListener("click", function () {{
  var on = root.classList.toggle("theme-light");
  try {{ localStorage.setItem("vrew-pack-theme", on ? "light" : "dark"); }} catch (e) {{}}
}});
function fallbackCopy(text) {{
  var ta = document.createElement("textarea");
  ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
  document.body.appendChild(ta); ta.select();
  try {{ document.execCommand("copy"); }} catch (e) {{}}
  document.body.removeChild(ta);
}}
document.querySelectorAll(".copy").forEach(function (btn) {{
  btn.addEventListener("click", function () {{
    var text = btn.getAttribute("data-copy");
    var done = function () {{
      var old = btn.textContent; btn.textContent = "복사됨"; btn.classList.add("done");
      setTimeout(function () {{ btn.textContent = old; btn.classList.remove("done"); }}, 1500);
    }};
    if (navigator.clipboard && window.isSecureContext) {{
      navigator.clipboard.writeText(text).then(done, function () {{ fallbackCopy(text); done(); }});
    }} else {{ fallbackCopy(text); done(); }}
  }});
}});
var KEY = "vrew-pack-checks:" + document.title;
var saved = {{}};
try {{ saved = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{}}
document.querySelectorAll(".check input").forEach(function (box) {{
  box.checked = !!saved[box.dataset.key];
  box.addEventListener("change", function () {{
    saved[box.dataset.key] = box.checked;
    try {{ localStorage.setItem(KEY, JSON.stringify(saved)); }} catch (e) {{}}
  }});
}});
</script>
</body></html>
"""


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    folder = Path(sys.argv[1])
    try:
        check_gates(folder)
        script = parse_script(folder)
        scenes = parse_scenes(folder, script)
        up = parse_upload(folder)
    except PackError as e:
        print(f"패키지를 만들지 않았습니다: {e}")
        return 1
    out = folder / "vrew-pack"
    out.mkdir(exist_ok=True)
    for name, text in build_texts(script, scenes, up).items():
        (out / name).write_text(text, encoding="utf-8")
    has_title = (out / "title-overlay.png").exists()
    (out / "index.html").write_text(build_html(folder.name, script, scenes, up, has_title), encoding="utf-8")
    print(f"완료: {out} (장면 {len(scenes)}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
