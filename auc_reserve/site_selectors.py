"""사이트 셀렉터 모음.

⚠ 아래 값은 실제 사이트를 보지 못하고 넣은 '추정값'이다.
   반드시 `python main.py --inspect`로 실제 화면을 저장한 뒤 맞게 고칠 것.
   (파일 이름을 selectors.py로 하면 파이썬 표준 모듈과 충돌하므로 site_selectors.py)

Playwright 셀렉터 문법: CSS, 'a:has-text("로그아웃")', 'text=예약' 등. 쉼표(,)로 여러 후보 지정 가능.
"""

MAIN_URL = "https://www.auc.or.kr/"
LOGIN_URL = "https://www.auc.or.kr/member/login"          # TODO: 실제 로그인 페이지 URL
SERVER_TIME_URL = "https://www.auc.or.kr/"

# 달력 URL의 yearMonthDay를 그 달 1일로 넣을지(True), 목표 날짜 그대로 넣을지(False)
CALENDAR_FIRST_OF_MONTH = True

# ── 로그인 ──────────────────────────────────────────────
LOGIN_ID_INPUT = 'input[name="userId"], input[name="id"], input#userId, input#id'
LOGGED_IN_MARKER = 'a:has-text("로그아웃"), button:has-text("로그아웃")'

# ── 달력 ────────────────────────────────────────────────
# {ymd}=2026-11-10, {ymd8}=20261110, {day}=10 으로 치환됨
DATE_CELL = ('[data-date="{ymd}"], [data-day="{ymd}"], a[onclick*="{ymd}"], '
             'a[onclick*="{ymd8}"], a[href*="yearMonthDay={ymd}"]')
DATE_CELL_CLICK = True            # 날짜를 눌러야 시간표가 나오면 True
NOT_OPEN_TEXTS = ["예약불가", "준비중", "오픈예정", "접수예정", "예약기간"]

# ── 시간표(슬롯) ─────────────────────────────────────────
# 한 행(또는 카드)에 '시간'과 '시설명'이 함께 들어 있는 요소
SLOT_ITEM = "table tbody tr"
# 행 안에서 누를 요소 (없으면 행 자체를 클릭)
SLOT_CLICK = ('a:has-text("신청"), button:has-text("신청"), a:has-text("예약"), '
              'button:has-text("예약"), input[type="checkbox"], input[type="radio"]')
UNAVAILABLE_TEXTS = ["마감", "예약완료", "신청불가", "불가", "종료"]
UNAVAILABLE_DIALOG_TEXTS = ["마감", "이미 예약", "초과", "불가"]

# ── 신청서 ──────────────────────────────────────────────
# config.json applicant의 키 → 입력칸 셀렉터
APPLICANT_FIELDS = {
    "인원": 'input[name="personCnt"], select[name="personCnt"]',
    "단체명": 'input[name="groupName"]',
    "연락처": 'input[name="phone"], input[name="tel"]',
}
AGREE_CHECKBOXES = ('input[type="checkbox"][name*="agree" i], '
                    'input[type="checkbox"][id*="agree" i]')
# 최종 신청 전 중간 단계 버튼 (여러 단계면 순서대로 시도)
FLOW_NEXT_BUTTONS = [
    'button:has-text("다음")', 'a:has-text("다음")',
    'button:has-text("신청서 작성")', 'a:has-text("신청서 작성")',
    'button:has-text("선택완료")', 'a:has-text("선택완료")',
]

# ── 최종 신청 (스크립트는 절대 누르지 않음, 감지만) ──────────
FINAL_SUBMIT = ('button:has-text("신청완료"), a:has-text("신청완료"), '
                'button:has-text("예약신청"), a:has-text("예약신청"), '
                'button:has-text("결제"), a:has-text("결제"), input[type="submit"]')
# 중간 버튼 글자에 이 단어가 있으면 누르지 않고 멈춤 (안전장치)
FINAL_BUTTON_TEXTS = ["신청완료", "예약신청", "결제", "최종", "확정"]
# 이 문구의 confirm() 창은 자동 단계에서 '취소'하고 사용자에게 넘김
FINAL_CONFIRM_KEYWORDS = ["신청하시겠습니까", "예약하시겠습니까", "결제하시겠습니까", "확정하시겠습니까"]

# ── 완료 감지 ────────────────────────────────────────────
COMPLETE_TEXTS = ["예약이 완료", "신청이 완료", "예약완료되었습니다", "접수되었습니다", "신청되었습니다"]
COMPLETE_URL_PARTS = ["complete", "finish", "result"]

# ── 자동화하지 않는 단계 (감지되면 멈추고 사용자 호출) ─────
BLOCKER_SELECTORS = {
    "보안문자": 'img[src*="captcha" i], iframe[src*="captcha" i], iframe[src*="recaptcha"], input[name*="captcha" i]',
    "본인인증": 'iframe[src*="nice" i], iframe[src*="kcb" i], iframe[src*="pass" i]',
}
BLOCKER_TEXTS = {
    "대기열": ["접속 대기", "대기순번", "대기 순번", "접속자가 많아"],
}
