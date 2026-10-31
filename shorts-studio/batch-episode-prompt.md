# 여러 편 동시 제작용 회차 지시서

오케스트레이터가 편마다 general-purpose 에이전트에 이 파일을 읽게 하고 `{N}`(후보 번호), `{DIR}`(회차 폴더명), `{THEME}`(6개 분야 중 하나), `{NOTE}`(근거 newsId·주의점) 값을 함께 준다.

---

저장소 /home/user/visualize (브랜치 kkd/sense5060)에서 5060 유튜브 쇼츠 1편을 끝까지 만든다. 오늘 날짜는 `TZ=Asia/Seoul date`로 확인한다.
**git commit/push는 하지 않는다** (오케스트레이터가 한다). 다른 회차 폴더는 건드리지 않는다.

## 먼저 읽을 것
- `.claude/commands/shorts.md` (3~7-2단계 순서), `shorts-studio/channel-profile.md`, `shorts-studio/CHECKLIST.md`, `shorts-studio/brand/title-style.md`
- 역할 지침: `.claude/agents/shorts-scriptwriter.md`, `shorts-fact-checker.md`, `shorts-vrew-director.md`, `shorts-growth-manager.md`
- 형식 예시(완성 회차): `shorts-studio/episodes/2026-10-28-은퇴후-건보료/` 의 7개 md (특히 script.md 맨 위 "## Vrew 붙여넣기용 순수 원고" 블록, vrew.md의 ```vrew-scenes``` 블록, upload.md의 `### 추천: N안 "..."`·설명란·고정댓글·`## 업로드 직전 확인` 형식, factcheck.md의 `최종판정 = 통과` 줄, qa.md의 `QA = 통과` 줄). `shorts-studio/tools/make_vrew_pack.py`가 이 형식을 읽으므로 그대로 맞춘다.
- 트렌드·후보: `shorts-studio/episodes/{DIR}/trend.md` (오케스트레이터가 미리 넣어 둔 오늘 트렌드·후보 파일) 의 '## 후보' 목록 중 **{N}안**.

## 진행
1. 폴더 `shorts-studio/episodes/{DIR}/`의 trend.md를 읽는다. plan.md = {N}안 기획(사용자가 이 안을 골랐음을 기록).
2. 원고(scriptwriter 지침): 30~60초, 한 줄 25자 이내, 핵심 정보 3개 이하, 다음 편 예고·구독 유도 금지, 마지막 줄 면책 문구.
   1년 뒤에 봐도 맞는 문장만 쓴다: "지금/요즘/이번 달/올해/새로 바뀐", 연도·날짜·마감일 금지, 해마다 바뀌는 금액은 핵심으로 쓰지 않는다 (제목·제목 그림·고정댓글도 같음).
3. 사실 검증 게이트: **Agent 도구가 있으면 general-purpose 에이전트를 따로 띄워** `shorts-fact-checker.md` 지침대로 독립 검증시킨다(없으면 원고를 의심하는 별도 패스로 직접). 확인 판정에는 실제 `curl -sL`로 받은 원문 발췌+URL 필수. WebFetch는 DNS 실패하니 curl 사용. www.korea.kr 은 접속됨(보도자료 첨부 PDF/HWPX 포함), 정부 개별 사이트는 차단될 수 있음. 반려면 수정 후 재검증(최대 2회). 2회 후에도 반려면 멈추고 사유를 보고한다.
4. 통과 후 vrew.md(vrew-scenes: 나레이션이 원고와 글자까지 동일, 1번 장면에 큰글자 2줄·태그·테마="{THEME}") + upload.md 작성.
5. QA(growth-manager QA 모드)로 qa.md 작성. 미통과면 고쳐서 다시 판정. 휴대폰·Vrew에서만 볼 수 있는 항목은 '사용자 확인 필요'.
6. `node shorts-studio/tools/make_title_card.js shorts-studio/episodes/{DIR}` → `python3 shorts-studio/tools/make_vrew_pack.py shorts-studio/episodes/{DIR}`. 거부되면 원인을 고쳐 다시 실행. title-preview.png는 Read로 눈으로 확인.

## 주제별 주의
{NOTE}

## 최종 답변 (짧게)
결과(완료/중단), 폴더 경로, 최종 원고 전문, 글자수·예상 길이, 추천 제목, 사용자가 직접 열어볼 공식 링크 2개, '사용자 확인 필요' 항목.
