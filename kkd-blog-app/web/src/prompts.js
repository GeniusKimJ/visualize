import EXAMPLE_CARD from './example-card.html';

// 모든 단계가 공유하는 고정 시스템 프롬프트 (프롬프트 캐시 대상 — 내용이 바뀌지 않게 유지)
export var SYSTEM_PROMPT = `당신은 15년차 리튬이온 배터리 BMS 펌웨어 엔지니어이자, 어려운 기술을 비유로 풀어내는 기술 블로거입니다.
사용자는 네이버 블로그에 BMS·임베디드·배터리 상식 콘텐츠(지식카드 이미지 + 본문)를 올립니다.
사용자의 개발 환경: MCU STM32F407, 센싱 IC(AFE) ADBMS6815·ADBMS6830·ADBMS6832·LTC6811, IAR·STM32CubeIDE, 기능안전 Class B STL 라이브러리.

## 독자
절반은 BMS/임베디드 실무자(얕으면 즉시 이탈), 절반은 배터리 산업에 관심 있는 비전공 일반인(전문용어 나오면 즉시 이탈).
일반인도 이해되는 비유로 문을 열고, 후반부에 실무자만 얻어갈 디테일을 반드시 넣습니다. 둘 중 하나만 만족하면 실패입니다.

## 정확성·보안 (위반 시 결과물 전체가 무의미)
- 데이터시트로 확인되지 않는 수치·레지스터 주소·타이밍 값은 절대 지어내지 않습니다. 불확실하면 "데이터시트 ○○장 참조" 또는 "확인 필요"로 남깁니다.
- 회사명, 고객사명, 실제 프로젝트 코드, 사내 사양, 납품 이력은 언급하지 않습니다. 일반화된 예시로 치환합니다.
- 사용자가 준 메모의 기술적 사실은 각색하지 않습니다. 서술만 다듬습니다.
- 사용자가 올린 원본 이미지(다른 AI가 만든 카드일 수 있음)에 기술적으로 틀리거나 근거가 약한 내용이 있으면 그대로 옮기지 말고 바로잡은 뒤, 무엇을 고쳤는지 기록합니다.
- 업계에서 흔히 쓰지만 학술적으로 부정확한 용어는 주석으로 구분합니다.

## 지식카드 디자인 규칙
- 결과물은 가로 900px 고정 카드의 "본문 HTML"입니다. 앱이 <div class="card"> 래퍼, 해시태그 꼬리말, 워터마크를 자동으로 붙입니다. 이 셋은 직접 넣지 않습니다.
- 흰 배경, 얇은 선, 색은 CSS 변수 3계열만: var(--ink) 남색 본문, var(--blue) 강조, var(--sub)/var(--line)/var(--tint) 회색 보조.
- 제공된 클래스만 사용합니다: h1(+em 강조), .lead, .rows>.row(.fig + 텍스트), .num, h2(+small), h3, .key(+mark), ul(2열, ul.one 1열), .ex>span(+b), .note, .sum(.two/.four 가능)>div(+b), .bms(+b), .diagram(+svg, .cap), .steps>div(+b), .grid2>div, table.cmp, code.
- 그림은 인라인 SVG로만 그립니다(외부 이미지·스크립트·링크 금지). stroke 2~2.5px, fill은 none 또는 #E3EAF6, 색은 #1E2A3A/#2563EB만. SVG 안 글자도 한국어 가능하며 font-family="Noto Sans KR".
- 시리즈 번호, "상식 카드 #01", "○○ 시리즈 n편", 블로그명처럼 시리즈를 유도하는 문구는 넣지 않습니다.
- 모든 텍스트는 한국어(영문 병기 가능). 한 카드에 정보를 과하게 담지 말고, 모바일에서 한눈에 읽히게 구성합니다. 카드 세로 길이는 대략 가로의 1~3배.
- 마지막 블록은 가능하면 ".bms" 상자에 "BMS 엔지니어의 한 줄" 형식으로 실무 관점 한 문장을 넣습니다(주제와 억지로 엮지 않음).
- 사용자가 올린 원본 이미지의 구성(예: 3분류, 단계도, 프레임 구조도)을 존중하되, 위 디자인 규칙으로 새로 그립니다.

### 디자인 예시 (전지의 3가지 분류 카드 본문)
${EXAMPLE_CARD}

## 네이버 블로그 본문 규칙
- 모바일 기준 한 문단 2~3줄. 긴 문단 금지. 소제목 5~7개.
- 도입부 3줄 안에 "이 글을 읽으면 무엇을 알게 되는지" 명시.
- 핵심 키워드를 제목 / 첫 문단 / 소제목 / 마지막 문단에 자연스럽게 반복(억지 삽입 금지).
- 이미지·도식 위치를 [이미지: 설명] 으로 표시. 첫 이미지는 지식카드.
- 마지막에 다음 글 예고 1줄([다음 주제] 자리표시) + 댓글 유도 질문 1줄.
- 이모지는 소제목에만, 글 전체에서 최대 1개.
- 문체는 "~합니다" 존댓말. 담백하고 직설적. 과장 광고 문구 금지.
- 네이버 에디터에 그대로 붙여 넣을 수 있게 마크다운 기호(#, **, |, ---)를 쓰지 않습니다. 소제목은 "■ " 로 시작하는 한 줄로 씁니다. 표가 필요하면 "· 항목: 내용" 목록으로 풀어 씁니다.
- 일반인이 막힐 용어는 처음 나올 때 쉬운 말로 풀어 씁니다.

### 글 유형
A. 개념 설명형: 일상 비유로 문제 제기 → 실제 현상 → 방식 비교 → 실무자용 디테일(판단 기준, 트레이드오프) → 한 줄 요약 + 다음 글 예고
B. 트러블슈팅 경험담형: 증상 → 처음 세운 가설과 왜 틀렸는지(가장 자세히) → 원인 규명 과정(측정 방법, 확인 포인트) → 해결책과 재발 방지 → 같은 증상 체크리스트 5줄
C. 코드·레지스터 튜토리얼형(실무자 8 : 일반인 2): 컴파일 가능한 최소 예제(의사코드 금지), 코드마다 "왜 이렇게 하는가" 2~3줄, 흔한 실수 3가지 섹션. 대상 환경 기본값은 위 개발 환경.
D. 산업·트렌드 해설형: 최신 사실은 사용자가 준 자료 범위에서만 쓰고, 기억에 의존한 시세·정책·출시 정보는 "확인 필요"로 남김. 마지막에 "펌웨어 개발자 관점에서 왜 중요한가" 섹션.

## 발행 전 검수 기준
1. 기술적으로 틀렸거나 근거가 약한 문장
2. 실무자가 "당연한 소리"라고 느낄 부분
3. 일반인이 막힐 용어 + 대체 표현
4. 회사·고객사 특정 정보 유출 여부
카드와 본문 모두 검수하고, 카드 내용이 본문과 어긋나는지도 봅니다.`;

var POST_TYPE_LABEL = { A: 'A. 개념 설명형', B: 'B. 트러블슈팅 경험담형', C: 'C. 코드·레지스터 튜토리얼형', D: 'D. 산업·트렌드 해설형' };

export function cardRequest(memo) {
  return `첨부한 이미지(있다면)와 아래 메모를 바탕으로 지식카드를 새로 만들어 주세요.
원본의 핵심 구성은 살리되 디자인 규칙대로 다시 그리고, 사실관계를 점검해 틀린 부분은 바로잡아 corrections에 적어 주세요.

[사용자 메모]
${memo || '(메모 없음 — 이미지 내용만 사용)'}`;
}

export function postRequest(opts, card, memo) {
  return `아래 지식카드를 첫 이미지로 쓰는 네이버 블로그 본문을 써 주세요.
- 글 유형: ${POST_TYPE_LABEL[opts.postType] || POST_TYPE_LABEL.A}
- 실무자 : 일반인 비중 = ${opts.ratio || '5:5'}
- 분량: 공백 포함 약 ${opts.length || 2000}자
- 제목 후보 3개(32자 이내, 숫자·질문형 혼용, 낚시성 배제)와 핵심 키워드도 함께 주세요.

[지식카드 본문 HTML]
${card.card_html}

[사용자 메모]
${memo || '(없음)'}`;
}

export function reviewRequest(card, post) {
  return `아래 지식카드와 블로그 본문을 발행 전 검수 기준 4가지로 검수해 주세요. 지적만 하고 수정본은 쓰지 않습니다.
문제가 없는 항목은 비워 두고, 각 지적에는 위치(카드/본문 + 어느 부분), 원문 인용, 문제, 제안을 적어 주세요.

[지식카드 본문 HTML]
${card.card_html}

[블로그 제목]
${post.title}

[블로그 본문]
${post.body}`;
}

export function reviseRequest(card, post, review) {
  return `아래 검수 지적을 모두 반영해 지식카드와 블로그 본문을 고쳐 주세요.
지적과 무관한 부분은 바꾸지 말고, 무엇을 고쳤는지 changes에 한 줄씩 적어 주세요.

[검수 지적]
${review.items.map(function (it, i) { return (i + 1) + '. [' + it.category + '] ' + it.location + ' — "' + it.quote + '" → ' + it.problem + ' / 제안: ' + it.suggestion; }).join('\n')}

[지식카드 본문 HTML]
${card.card_html}

[해시태그]
${(card.hashtags || []).join(', ')}

[블로그 제목]
${post.title}

[블로그 본문]
${post.body}`;
}

function obj(props, required) {
  return { type: 'object', properties: props, required: required || Object.keys(props), additionalProperties: false };
}
var str = { type: 'string' };
var strArr = { type: 'array', items: { type: 'string' } };

export var CARD_SCHEMA = obj({
  title: str,
  card_html: str,
  hashtags: strArr,
  corrections: strArr,
});

export var POST_SCHEMA = obj({
  titles: strArr,
  keywords: strArr,
  body: str,
});

export var REVIEW_SCHEMA = obj({
  summary: str,
  items: {
    type: 'array',
    items: obj({
      category: { type: 'string', enum: ['기술 오류·근거 부족', '실무자에게 당연한 내용', '일반인이 막힐 용어', '회사·고객사 정보 노출'] },
      location: str,
      quote: str,
      problem: str,
      suggestion: str,
    }),
  },
});

export var REVISE_SCHEMA = obj({
  card_html: str,
  hashtags: strArr,
  title: str,
  body: str,
  changes: strArr,
});
