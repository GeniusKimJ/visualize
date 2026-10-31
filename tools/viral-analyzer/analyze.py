#!/usr/bin/env python3
"""떡상 영상 분석기 (초안)

YouTube URL 목록 → 메타데이터 + 자막 수집 → 특징 추출 → 떡상군/비교군 비교 → 공식 카드 HTML 리포트.

사용법:
    python3 analyze.py urls.txt            # out/data.json, out/report.html 생성
    python3 analyze.py urls.txt --no-subs  # 자막 수집 생략 (메타데이터만)

urls.txt 형식 (한 줄에 하나, # 주석 가능):
    https://www.youtube.com/watch?v=XXXXXXXXXXX  viral
    https://www.youtube.com/watch?v=YYYYYYYYYYY  control
    https://youtu.be/ZZZZZZZZZZZ                 # 라벨 생략 시 구독자 대비 조회수 배율로 자동 분류

자막을 자동으로 못 받으면 transcripts/<videoId>.vtt 또는 .txt 를 직접 넣으면 그 파일을 사용한다.
의존성: Python 3.9+, yt-dlp (자막용, 선택)
"""
import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
VIRAL_RATIO = 10.0  # 라벨이 없을 때: 조회수 / 구독자 ≥ 10 이면 떡상군

STAKES_WORDS = r"\b(save|saving|die|dies|dead|death|cost|everything|never|last|only|lose|losing|forever|kill|danger|choose)\b"
SCIENCE_WORDS = r"\b(real|science|scientist|scientists|study|studies|experiment|research|actually|in \d{4})\b"
CTA_WORDS = r"\b(comment|comments|subscribe|like|next|tell us|what do you think)\b"
NUMBER_WORDS = (r"\b(\d[\d,.]*x?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                r"twenty|thirty|forty|fifty|hundred|thousand|million|billion|half|quarter|"
                r"double|twice|times)\b")


# ---------------------------------------------------------------- 수집

def video_id(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
    return m.group(1) if m else None


def fetch_page(vid, tries=4):
    req = urllib.request.Request(
        f"https://www.youtube.com/watch?v={vid}",
        headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001  일시적 차단·네트워크 오류 → 2, 4, 8초 후 재시도
            if i == tries - 1:
                raise
            time.sleep(2 ** (i + 1))


def _find(pattern, s, group=1, flags=0):
    m = re.search(pattern, s, flags)
    return m.group(group) if m else None


def parse_count(text):
    """'57.4 thousand subscribers' / '1.2M' / '379,070' → int"""
    if not text:
        return None
    t = text.lower().replace(",", "")
    m = re.search(r"([\d.]+)\s*(thousand|million|billion|k|m|b)?", t)
    if not m:
        return None
    mult = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "billion": 1e9, "b": 1e9}
    return int(float(m.group(1)) * mult.get(m.group(2) or "", 1))


def parse_meta(vid, page):
    desc = _find(r'"attributedDescription":\{"content":"((?:[^"\\]|\\.)*)"', page)
    if desc is None:
        desc = _find(r'"shortDescription":"((?:[^"\\]|\\.)*)"', page)
    desc = json.loads(f'"{desc}"') if desc else ""
    likes = _find(r'"accessibilityText":"[^"]*along with ([\d,]+) other', page)
    meta = {
        "id": vid,
        "url": f"https://www.youtube.com/watch?v={vid}",
        "title": _find(r'"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)*)"\}\]', page)
                 or _find(r"<title>(.*?) - YouTube</title>", page),
        "channel": _find(r'"channel":\{"simpleText":"([^"]+)"', page)
                   or _find(r'"ownerChannelName":"([^"]+)"', page),
        "subscribers": parse_count(_find(
            r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([^"]+)"', page)),
        "views": int(_find(r'"originalViewCount":"(\d+)"', page) or _find(r'"viewCount":"(\d+)"', page) or 0) or None,
        "likes": int(likes.replace(",", "")) + 1 if likes else None,
        "comments": parse_count(_find(r'"contextualInfo":\{"runs":\[\{"text":"([^"]+)"', page)),
        "published": _find(r'"dateText":\{"simpleText":"([^"]+)"', page) or _find(r'"publishDate":"([^"]+)"', page),
        "length_s": int(_find(r'"lengthSeconds":"(\d+)"', page) or 0) or None,
        "description": desc,
    }
    meta["chapters"] = parse_chapters(desc)
    if meta["title"]:
        meta["title"] = html.unescape(json.loads(f'"{meta["title"]}"') if "\\" in meta["title"] else meta["title"])
    return meta


def parse_chapters(desc):
    out = []
    for line in desc.splitlines():
        m = re.match(r"\s*((?:\d+:)?\d{1,2}:\d{2})\s+(.+)", line)
        if m:
            out.append({"t": to_sec(m.group(1)), "title": m.group(2).strip()})
    return out if len(out) >= 2 and out[0]["t"] == 0 else []


def to_sec(ts):
    parts = [float(p) for p in ts.split(":")]
    s = 0
    for p in parts:
        s = s * 60 + p
    return s


def fetch_subs(vid, workdir):
    """transcripts/ 수동 파일 우선, 없으면 yt-dlp 자동 자막."""
    for ext in ("vtt", "txt"):
        manual = ROOT / "transcripts" / f"{vid}.{ext}"
        if manual.exists():
            return parse_transcript(manual.read_text(encoding="utf-8"))
    if not shutil.which("yt-dlp"):
        return None
    workdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
         "--sub-langs", "en,en-orig,ko", "--sub-format", "vtt",
         "-o", str(workdir / f"{vid}.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"],
        capture_output=True, text=True, timeout=180)
    for lang in ("en", "en-orig", "ko"):
        f = workdir / f"{vid}.{lang}.vtt"
        if f.exists() and f.stat().st_size > 200:
            return parse_transcript(f.read_text(encoding="utf-8"))
    return None


def parse_transcript(text):
    """VTT 또는 '[mm:ss] 문장' 형식 텍스트 → [{t, text}] (롤링 자막 중복 제거)"""
    lines, last = [], ""
    if "-->" in text:
        for block in re.split(r"\n\s*\n", text):
            m = re.search(r"((?:\d+:)?\d{2}:\d{2})\.\d+\s*-->", block)
            if not m:
                continue
            body = " ".join(l for l in block.splitlines()[1:] if "-->" not in l)
            body = re.sub(r"<[^>]+>", "", body).strip()
            if body and body != last:
                lines.append({"t": to_sec(m.group(1)), "text": body})
                last = body
    else:
        for raw in text.splitlines():
            m = re.match(r"\s*\[?((?:\d+:)?\d{1,2}:\d{2})\]?\s+(.*)", raw)
            if m and m.group(2).strip():
                lines.append({"t": to_sec(m.group(1)), "text": m.group(2).strip()})
    return lines or None


# ---------------------------------------------------------------- 특징 추출

def words(s):
    return re.findall(r"[A-Za-z']+|\d[\d,.]*", s)


def features(meta, subs):
    f = {}
    v, sub = meta.get("views"), meta.get("subscribers")
    f["views_per_sub"] = round(v / sub, 2) if v and sub else None
    f["like_rate_pct"] = round(meta["likes"] / v * 100, 2) if v and meta.get("likes") else None
    f["comment_rate_pct"] = round(meta["comments"] / v * 100, 3) if v and meta.get("comments") else None

    title = meta.get("title") or ""
    f["title_len"] = len(title)
    f["title_what_if"] = bool(re.match(r"\s*what if", title, re.I))
    f["title_number"] = bool(re.search(NUMBER_WORDS, title, re.I))
    f["title_question"] = title.strip().endswith("?")
    f["title_you"] = bool(re.search(r"\byou(r)?\b", title, re.I))

    desc = meta.get("description") or ""
    f["series"] = bool(re.search(r"\bpart\s*\d|\bpart\s*(one|two|three)|\bepisode\b|▶", desc + " " + title, re.I))
    f["chapters"] = len(meta.get("chapters") or [])
    f["hashtags"] = len(re.findall(r"#\w+", desc))

    if not subs:
        f["has_transcript"] = False
        return f
    f["has_transcript"] = True
    length = meta.get("length_s") or (subs[-1]["t"] + 5)
    f["length_min"] = round(length / 60, 1)
    full = " ".join(x["text"] for x in subs)
    w = words(full)
    f["wpm"] = round(len(w) / (length / 60))
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", full) if words(s)]
    f["avg_sentence_words"] = round(len(w) / max(len(sentences), 1), 1)
    f["you_per_100w"] = round(len(re.findall(r"\byou(r|rs|rself)?\b", full, re.I)) / max(len(w), 1) * 100, 1)
    f["numbers_per_min"] = round(len(re.findall(NUMBER_WORDS, full, re.I)) / (length / 60), 1)
    f["ellipsis_count"] = full.count("...") + full.count("…")

    hook = " ".join(x["text"] for x in subs if x["t"] < 20)
    f["hook_first_line"] = (sentences[0] if sentences else "")[:140]
    f["hook_has_number"] = bool(re.search(NUMBER_WORDS, hook, re.I))
    stake = next((x["t"] for x in subs if re.search(STAKES_WORDS, x["text"], re.I)), None)
    f["stakes_at_s"] = stake

    tail15 = " ".join(x["text"] for x in subs if x["t"] >= length * 0.85)
    tail10 = " ".join(x["text"] for x in subs if x["t"] >= length * 0.90)
    f["science_outro"] = len(re.findall(SCIENCE_WORDS, tail15, re.I)) >= 2
    f["cta_end"] = bool(re.search(CTA_WORDS, tail10, re.I))
    f["cta_asks_next_topic"] = bool(re.search(r"\bnext\b|\bwhich\b.*\b(should|do)\b", tail10, re.I))
    f["callbacks"] = count_callbacks(subs)
    return f


def count_callbacks(subs):
    """복선·회수 대용 지표: 30초 이상 떨어져 다시 등장하는 3단어 구절 수."""
    seen, hits = {}, set()
    for x in subs:
        toks = [t.lower() for t in re.findall(r"[A-Za-z']+", x["text"])]
        for i in range(len(toks) - 2):
            g = " ".join(toks[i:i + 3])
            if len(g) < 12:
                continue
            if g in seen and x["t"] - seen[g] >= 30:
                hits.add(g)
            seen.setdefault(g, x["t"])
    return len(hits)


# ---------------------------------------------------------------- 공식 도출

BOOL_KEYS = {
    "title_what_if": "제목이 'What If'로 시작",
    "title_number": "제목에 숫자",
    "title_question": "질문형 제목",
    "title_you": "제목에 You/Your",
    "series": "시리즈 구성",
    "hook_has_number": "첫 20초에 숫자",
    "science_outro": "마지막 과학 해설",
    "cta_end": "엔딩 시청자 행동 유도",
    "cta_asks_next_topic": "'다음 주제' 댓글 질문",
}
NUM_KEYS = {
    "length_min": ("영상 길이(분)", 1),
    "chapters": ("챕터 수", 0),
    "stakes_at_s": ("대가·위기 첫 등장(초)", 0),
    "wpm": ("분당 단어 수", 0),
    "avg_sentence_words": ("문장당 단어 수", 1),
    "you_per_100w": ("2인칭 비율(100단어당)", 1),
    "numbers_per_min": ("분당 숫자 언급", 1),
    "callbacks": ("반복 구절(복선 대용)", 0),
}  # 좋아요율 같은 성과 지표는 결과값이라 공식 후보에서 제외


def mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float)) and not isinstance(x, bool)]
    return sum(xs) / len(xs) if xs else None


def derive_formula(rows):
    viral = [r for r in rows if r["group"] == "viral"]
    ctrl = [r for r in rows if r["group"] == "control"]
    items = []
    for k, label in BOOL_KEYS.items():
        vv = [r["f"].get(k) for r in viral if k in r["f"]]
        cc = [r["f"].get(k) for r in ctrl if k in r["f"]]
        if not vv:
            continue
        vr = sum(bool(x) for x in vv) / len(vv)
        cr = sum(bool(x) for x in cc) / len(cc) if cc else None
        lift = vr - cr if cr is not None else None
        keep = vr >= 0.7 and (lift is None or lift >= 0.2)
        items.append({"kind": "bool", "label": label, "viral": vr, "control": cr, "lift": lift, "keep": keep})
    for k, (label, nd) in NUM_KEYS.items():
        vm = mean([r["f"].get(k) for r in viral])
        cm = mean([r["f"].get(k) for r in ctrl])
        if vm is None:
            continue
        diff = (vm - cm) / cm if cm else None
        keep = diff is not None and abs(diff) >= 0.2
        items.append({"kind": "num", "label": label, "viral": round(vm, nd), "control": round(cm, nd) if cm is not None else None,
                      "lift": diff, "keep": keep or (cm is None)})
    return {"n_viral": len(viral), "n_control": len(ctrl), "items": items}


# ---------------------------------------------------------------- 리포트

def fmt(v):
    if v is None:
        return "–"
    if isinstance(v, bool):
        return "✔" if v else "·"
    if isinstance(v, int) and v >= 10000:
        return f"{v:,}"
    return str(v)


def render_report(rows, formula, path):
    tpl = (ROOT / "report_template.html").read_text(encoding="utf-8")
    payload = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "rows": rows, "formula": formula,
               "boolKeys": BOOL_KEYS, "numKeys": {k: v[0] for k, v in NUM_KEYS.items()}}
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    path.write_text(tpl.replace("/*__DATA__*/null", data), encoding="utf-8")


# ---------------------------------------------------------------- main

def read_list(p):
    out = []
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        vid = video_id(parts[0]) or (parts[0] if re.fullmatch(r"[\w-]{11}", parts[0]) else None)
        if vid:
            out.append((vid, parts[1].lower() if len(parts) > 1 else None))
    return out


def main():
    ap = argparse.ArgumentParser(description="떡상 영상 분석기")
    ap.add_argument("urls")
    ap.add_argument("--out", default=str(ROOT / "out"))
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--delay", type=float, default=3.0, help="영상 사이 대기(초) — 429 방지")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, (vid, label) in enumerate(read_list(a.urls)):
        if i:
            time.sleep(a.delay)
        print(f"[{i + 1}] {vid} ...", file=sys.stderr)
        try:
            meta = parse_meta(vid, fetch_page(vid))
        except Exception as e:  # noqa: BLE001
            print(f"    페이지 실패: {e}", file=sys.stderr)
            continue
        subs = None if a.no_subs else fetch_subs(vid, out / "subs")
        f = features(meta, subs)
        group = label if label in ("viral", "control") else (
            "viral" if (f.get("views_per_sub") or 0) >= VIRAL_RATIO else "control")
        meta.pop("description", None)
        rows.append({"meta": meta, "f": f, "group": group})
        print(f"    {meta.get('title')} | {fmt(meta.get('views'))} views | x{f.get('views_per_sub')} | "
              f"자막 {'O' if subs else 'X'} | {group}", file=sys.stderr)
    formula = derive_formula(rows)
    (out / "data.json").write_text(json.dumps({"rows": rows, "formula": formula}, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    render_report(rows, formula, out / "report.html")
    print(f"완료: {out / 'report.html'}", file=sys.stderr)


if __name__ == "__main__":
    main()
