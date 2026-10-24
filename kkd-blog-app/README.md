# KKD 블로그 카드 (안드로이드 앱)

원본 이미지나 메모를 넣으면 Claude가 네이버 블로그용 **지식카드 이미지 · 본문 원고 · 발행 전 검수**를 만들어 주는 앱입니다.

## 할 수 있는 일

1. **입력**: 원본 이미지(여러 장 가능)와 메모를 넣고 글 유형(A~D), 실무자:일반인 비중, 분량을 고릅니다.
2. **지식카드**: 흰 배경, 3색, 900px 디자인으로 새로 그립니다. 원본에서 틀린 내용은 바로잡고, 무엇을 고쳤는지 따로 보여 줍니다.
3. **원고**: 네이버 에디터에 그대로 붙여 넣을 수 있는 본문(마크다운 기호 없음), 제목 후보 3개, 키워드를 만듭니다.
4. **검수**: 기술 오류, 실무자에게 당연한 내용, 일반인이 막힐 용어, 회사 정보 노출을 점검합니다.
5. **반영**: 버튼 한 번으로 검수 지적을 카드와 원고에 모두 반영합니다.
6. **내보내기**: 카드를 갤러리(`Pictures/KKDBlog`)에 1800px PNG로 저장하고, 원고를 복사하고, 네이버 블로그 앱으로 공유합니다.

워터마크(기본 `KKD`, 농도 6%)와 모델(Opus 5.5 / Sonnet 5.5)은 설정에서 바꿀 수 있습니다.

## 준비물: Anthropic API 키

claude.ai 구독과 API는 **결제가 따로**입니다.

1. https://console.anthropic.com 에 가입하고 결제 수단(크레딧)을 등록합니다.
2. **API Keys**에서 키를 만들고 앱의 **설정 → Anthropic API 키**에 붙여 넣습니다.

키는 휴대폰 안의 앱 저장소에만 보관되고, Anthropic API로 요청할 때만 쓰입니다.

## 설치

GitHub Actions가 APK를 자동으로 빌드합니다.

1. 휴대폰 브라우저로 저장소의 **Releases**에 들어가 최신 `KKD 블로그 카드` 릴리스의 `KKDBlogCard.apk`를 내려받습니다.
2. 처음 설치할 때 "출처를 알 수 없는 앱 설치"를 허용합니다.
3. 새 버전은 같은 방법으로 덮어 설치하면 됩니다(설정·작업 내용 유지).

## 네이버 블로그 업로드에 대해

네이버는 블로그 자동 발행을 공식 지원하지 않아서, 앱은 **발행 직전 단계까지** 자동으로 처리합니다.
"네이버 블로그로 보내기"를 누르면 카드 이미지가 블로그 앱으로 넘어가고 원고는 클립보드에 복사됩니다. 에디터에서 붙여 넣은 뒤 표·서식만 다듬어 발행하세요.

## 구조

```
kkd-blog-app/
├── web/        # 화면 + Claude 호출 (Anthropic TypeScript SDK, esbuild 번들)
│   └── src/
│       ├── main.js           # 화면 동작, 단계별 Claude 호출
│       ├── prompts.js        # 시스템 프롬프트, 단계별 요청, JSON 스키마
│       ├── card-template.js  # 카드 CSS, 워터마크, HTML 정리
│       └── example-card.html # 디자인 예시 카드
└── android/    # WebView 앱 (Java, 외부 라이브러리 없음)
    └── app/src/main/java/com/kkd/blogcard/MainActivity.java
                # 카드 PNG 캡처·갤러리 저장·클립보드·공유·설정 저장
```

로컬 빌드: `cd web && npm ci && npm run build` 실행 후 `cd ../android && gradle assembleRelease` (Android SDK 필요).

서명 키(`android/app/kkd-blogcard.keystore`)는 개인 설치용입니다. 앱을 공개 배포하려면 새 키를 만들어 GitHub Secrets로 옮기세요.
