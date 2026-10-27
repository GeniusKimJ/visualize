---
description: 5060 유튜브 쇼츠 1편을 트렌드 조사부터 팩트체크, Vrew 편집 지시서, 업로드 패키지까지 만든다
argument-hint: "[주제(선택)] [길이초(기본 45)]"
---

5060 중장년 대상 유튜브 쇼츠 1편을 만든다. 인자: $ARGUMENTS
(주제가 없으면 트렌드 조사부터, 길이를 주지 않으면 45초)

모든 단계는 `shorts-studio/channel-profile.md`를 기준으로 한다.
각 서브에이전트에는 이전 단계 결과 전문과 회차 폴더 경로를 넘긴다.

## 진행 순서
1. **트렌드 조사**: 주제 인자가 없으면 `shorts-trend-researcher`를 실행해 TOP 10을 받는다.
2. **기획**: `shorts-planner`로 주제 3안을 받고, 사용자에게 1안을 고르게 한다 (추천안 표시).
3. **원고**: `shorts-scriptwriter`로 원고를 받는다.
4. **사실 검증 (게이트)**: `shorts-fact-checker`를 실행한다.
   - `최종판정 = 반려`면 판정표를 `shorts-scriptwriter`에 넘겨 수정 원고를 받고 다시 검증한다 (최대 2회).
   - 2회 수정 후에도 통과하지 못하면 사용자에게 주제 교체를 제안하고 멈춘다.
   - 통과하기 전에는 5단계로 넘어가지 않는다.
5. **편집·업로드 준비**: 통과 원고로 `shorts-vrew-director`와 `shorts-growth-manager`(업로드 패키지 모드)를 병렬 실행한다.
   growth-manager에는 factcheck의 출처 목록을 넘긴다.
6. **업로드 전 QA (게이트)**: `shorts-growth-manager`(QA 모드)로 `shorts-studio/CHECKLIST.md`를 판정한다.
   미통과 항목은 해당 단계로 되돌려 고친 뒤 다시 판정한다.
7. **저장**: `shorts-studio/episodes/<YYYY-MM-DD>-<주제>/` 아래에
   `trend.md`, `plan.md`, `script.md`, `factcheck.md`, `vrew.md`, `upload.md`, `qa.md`로 저장한다.
   Vrew 화면·휴대폰에서만 확인할 수 있는 항목은 `qa.md`에 '사용자 확인 필요'로 남긴다.
7-1. **강조 제목 카드**: `node shorts-studio/tools/make_title_card.js shorts-studio/episodes/<회차폴더>` 실행
   (`vrew-pack/title-overlay.png`, `title-preview.png` 생성. 스타일 규칙은 `shorts-studio/brand/title-style.md`).
7-2. **Vrew 복사용 패키지**: `python3 shorts-studio/tools/make_vrew_pack.py shorts-studio/episodes/<회차폴더>` 실행.
   검증·QA가 통과가 아니거나 장면 데이터가 원고와 다르면 스크립트가 거부하니, 출력된 이유대로 해당 단계로 되돌린다.
8. **요약 출력**: 사용자에게 다음만 짧게 보여준다.
   - `vrew-pack/index.html` 경로 (이 페이지를 열고 위에서부터 복사하면 된다는 안내)
   - Vrew에 붙여넣을 원고
   - 추천 제목 1안
   - 직접 열어볼 출처 링크 2~3개
   - '사용자 확인 필요' QA 항목
