# 떡상 영상 분석기 (초안)

YouTube URL 목록을 넣으면 메타데이터와 자막을 수집하고, 떡상군과 비교군을 비교해 **공식 카드** HTML 리포트를 만든다.

```bash
cp urls.example.txt urls.txt   # URL 추가, 줄 끝에 viral / control 라벨 (생략 시 조회수/구독자 ≥ 10 → viral)
python3 analyze.py urls.txt    # → out/report.html, out/data.json
```

- 필요: Python 3.9+, `yt-dlp` (자막용, 없으면 메타데이터만)
- 자막이 막히면 `transcripts/<videoId>.vtt` 또는 `.txt`(`[mm:ss] 문장`)를 직접 넣는다
- `out/`, `transcripts/`는 원본 자막이 들어 있으므로 커밋하지 않는다 (.gitignore)
- 반복 구절 수는 복선·회수의 대용 지표일 뿐이다. 실제 복선은 대본으로 확인한다
