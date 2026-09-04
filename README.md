# invest — 투자 시스템 통폐합 (v 20260904-1310)

한 방향: `raw/`(원본) → `facts/`(사실) → `analysis/`(분석) → `log/`(이력). 규칙·출처는 `data/` 설정 파일. 프로그램끼리 직접 부르지 않고 JSON 으로만 대화.

| 폴더/파일 | 역할 | 누가 쓰나 |
|---|---|---|
| `index.html` | 문 하나(허브) — 첫 화면 7칸 | 사람이 본다 |
| `js/status.js` | 공통: 상단 경고 띠 + 🐞 오버레이 [복사] | 모든 화면이 `<script src="js/status.js">` 로 얹는다 |
| `data/status.json` | 작업 상태(ok/fail/stale/stopped, due) | 워크플로가 쓴다 |
| `data/registry.json` | 프로그램 목록 — 추가 = 파일 1개 + 한 줄 | 사람(Claude) |
| `data/features.json` | 모든 설명 한 곳 → 툴팁·매뉴얼·? 버튼 | 사람(Claude) |
| `data/axes.json` `data/strategies.json` | 대변화 축 8개×6단계 / 전략 카드 5개 | 다음 단계 |
| `raw/ facts/ analysis/ log/` | 데이터 4단(하류가 상류를 읽는다) | 워크플로 |

시각은 전부 KST. 비밀(키·토큰)은 이 저장소에 없다. 실패는 조용히 넘기지 않는다 — status.json → 경고 띠.
