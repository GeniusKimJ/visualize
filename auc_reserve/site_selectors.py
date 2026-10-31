"""사이트 셀렉터 모음.

✅ 확인됨 (2026-10-31, 로그인 전 화면 기준): 로그인 페이지, 로그인 상태 표시, 달력/시간표 구조
⚠ 추정값 (로그인 후 화면이라 미확인): 신청서(reservationStep2) 이후 단계
   → `python main.py --inspect`로 로그인 후 화면을 저장해서 맞출 것.
   (파일 이름을 selectors.py로 하면 파이썬 표준 모듈과 충돌하므로 site_selectors.py)

Playwright 셀렉터 문법: CSS, 'a:has-text("로그아웃")', 'text=예약' 등. 쉼표(,)로 여러 후보 지정 가능.
"""

MAIN_URL = "https://www.auc.or.kr/reservation/main/view"
LOGIN_URL = "https://www.auc.or.kr/sign/in/base/user?menuLevel=2&menuNo=346"
SERVER_TIME_URL = "https://www.auc.or.kr/"

# 달력 URL의 yearMonthDay를 그 달 1일로 넣을지(True), 목표 날짜 그대로 넣을지(False)
CALENDAR_FIRST_OF_MONTH = True

# ── 로그인 ──────────────────────────────────────────────
LOGIN_ID_INPUT = "#loginForm input#id"
# 로그아웃 상태일 때 상단에 보이는 '로그인' 링크
LOGGED_OUT_MARKER = "a.header__links__1__login"
LOGGED_IN_MARKER = 'a:has-text("로그아웃"), a[onclick*="fnLogout"]'

# ── 달력 ────────────────────────────────────────────────
# 달력은 월 단위 표 하나에 날짜별 시간표(ul.yy-list > li)가 함께 들어 있다.
#   li.possible  > a.possible[onclick="fn_facilityResSelect('1','','2026-11-02','1220','1350')"]  → 예약가능
#   li.impossible (불) / 환경정비(환) / 대기(대)                                                 → 예약불가
# 아직 안 열린 날짜는 ul.yy-list가 비어 있고, 그 뒤 날짜는 표에 아예 없다.
# {ymd}=2026-11-10, {ymd8}=20261110, {day}=10, {dd}=10(두 자리) 로 치환됨
DATE_CELL = '.calendar_table td:has(> div > span:text-is("{dd}")) ul.yy-list > li'
DATE_CELL_CLICK = False           # 날짜를 누를 필요 없음 (시간표가 달력 안에 있음)
NOT_OPEN_TEXTS = []

# ── 시간표(슬롯) ─────────────────────────────────────────
SLOT_ITEM = DATE_CELL             # 날짜 칸 안의 시간 하나하나
SLOT_CLICK = "a.possible"
SLOT_CLICK_REQUIRED = True        # SLOT_CLICK이 없으면 예약불가로 판단
UNAVAILABLE_TEXTS = ["불", "환", "대"]
UNAVAILABLE_DIALOG_TEXTS = ["마감", "이미 예약", "초과", "불가"]

# ── 신청서 (⚠ 추정값: 로그인 후 reservationStep2 화면 확인 필요) ──
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
