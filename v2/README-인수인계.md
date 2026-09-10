# invest2 인수인계 (v 20260908-0130) — 집·회사 어디서든 이어서 수정하기

> 새 Claude 세션을 열면 이 파일을 통째로 붙여 넣고 "여기서부터 이어가자"고 하면 됩니다.

## 1. 지금 뭘 하고 있나 (한 줄)
투자 프로그램을 **하나씩 새로 만드는 중**. 1번 「지표 보기」가 만들어져 있고, 달님이 며칠 써보고 "됐다" 하면 2번 「레짐 보기」로 넘어감.

## 2. 규칙 (달님이 정한 것 — 바꾸지 말 것)
- 프로그램 **하나 만들고 마무리한 뒤** 다음 것. 한 파일에 여러 기능 얹지 않기.
- 새 화면은 **git 폴더 말고 `invest2` 폴더**에 순서 번호로 (`01-지표보기.html`, `02-…`). 단, 집에서도 열기 위해 같은 파일을 invest 저장소 `v2/` 폴더에 **복사본**으로 올림 (아래 4번).
- 기존 코드(수집기 macro.py·regime.py·rules)는 **재사용**, 옛 화면(index/cygnus/journal/predict/manual)은 버림(나중에 `_old/`).
- **확인 / 추정 / 미확인** 구분해서 말하기. 짐작으로 코드 쓰지 않기(칸 이름·값·구조는 실제 파일에서 확인).
- 비밀키(ECOS·Firebase·relay 등)는 달님이 직접 GitHub Secret 에 넣음. **대화·코드에 적지 않기**.
- 자동화는 알림까지, 주문은 사람 손. 예측 기능은 뺌(유튜브 요약 쪽).
- 답 끝에 「지금 한 것 / 다음 / 남은 것」 표.
- 시간 상한은 달님이 판단(Claude 가 먼저 끊지 않기).

## 3. 파일이 어디 있나
| 무엇 | 회사 PC | 집(또는 어디서나) |
|---|---|---|
| 프로그램 1 원본 | `C:\Users\bini6\Desktop\git\invest2\01-지표보기.html` | GitHub 저장소 `20251014peru-gif/invest` 의 `v2/01-지표보기.html` |
| 바로 열기(설치 없음) | 파일 더블클릭 | `https://20251014peru-gif.github.io/invest/v2/01-지표보기.html` (올리기.bat 실행 후 1~2분) |
| 데이터(읽기 전용) | — | `https://20251014peru-gif.github.io/invest/` 의 `data/indicators.json`(정의·규칙) · `facts/macro.json`(값) · `facts/macro_history.json`(날짜별 이력) |
| 수집기 | `Desktop\git\invest\scripts\macro.py, regime.py, calendar.py, journal.py` | GitHub Actions `macro.yml` 이 매일 돌려서 facts/ 갱신 |
| 이 문서 | `invest2\README-인수인계.md` | `v2/README-인수인계.md` |

집에서 수정하는 법: GitHub 에서 `v2/01-지표보기.html` 을 받아(또는 `git clone https://github.com/20251014peru-gif/invest`) 고치고, GitHub 웹에서 업로드하거나 git push. 회사에 오면 `invest2` 폴더에 **덮어쓰기**(둘 중 최신 버전이 어느 쪽인지는 파일 첫 줄 `v 날짜-시각` 으로 판단).

## 4. 프로그램 1 「지표 보기」 지금 상태 (v 20260908-0110)
파일 하나. 인터넷만 되면 어디서 열어도 됨(GitHub Pages 에서 JSON 을 읽음. 채팅 미리보기 창은 인터넷 차단이라 거기선 안 열림).
- **카드 목록**: 한국·미국·국제 탭. 카드 = 값·이전 값·전일(전월) 대비 ▲▼·이력 추세(↗↘→)·미니 추이선·판정·기준일.
- **카드 클릭 → 지표 페이지** (주소 `#kospi` 처럼 지표마다 고유): 값·방향·판정·규칙 → 출처 → **차트** → 내 이력 표 | 관련 뉴스 → 바로가기 → 메모.
- 차트 출처(2026-09-08 크롬에서 열림 확인):
  - 코스피·코스닥: 네이버 이미지 `https://ssl.pstatic.net/imgfinance/chart/mobile/{day|candle/day|candle/week|candle/month}/KOSPI_end.png`
  - TradingView 무료 위젯(`embed-widget-advanced-chart.js`): **지수 원본은 전부 거부**(KRX:KOSPI, SP:SPX, NASDAQ:IXIC, CBOE:VIX, TVC:DXY, TVC:US10Y …) → 대용 심볼: usdkrw `FX_IDC:USDKRW`, sp500 `CAPITALCOM:US500`, nasdaq `CAPITALCOM:US100`(나스닥100), sox `NASDAQ:SOXX`, vix `CAPITALCOM:VIX`, dxy `CAPITALCOM:DXY`, us10y `FRED:DGS10`, us2y `FRED:DGS2`, hsi `CAPITALCOM:HK50`, wti `TVC:USOIL`, copper `CAPITALCOM:COPPER`, gold `TVC:GOLD`, bdry `AMEX:BDRY`
  - FRED 지표: `https://fred.stlouisfed.org/graph/fredgraph.png?id=시리즈` 이미지
  - 한국 금리·CPI·선행·수출·ISM·중국PMI·신용스프레드: 끼울 차트 없음(내 이력 그래프 + 링크)
- 뉴스: Bing 뉴스 RSS `https://www.bing.com/news/search?q=키워드&format=rss` 를 중계(relay) 로 읽음. Google News 는 중계에서 503.
- 메모: 브라우저 localStorage(`ind_memo_<id>`) — **그 PC 그 브라우저에만** 남음. 프로그램 3에서 Firestore 로 옮길 예정.
- 코드 안 표: `NAVER_IDX`(네이버 차트) · `TV`(TradingView 심볼) · `TVNOTE`(대용 설명) · `FREDG`(FRED 시리즈) · `NEWSQ`(뉴스 키워드). 지표별 차트·뉴스를 바꾸려면 이 표만 고치면 됨.

## 5. 알려진 문제 · 미확인
- 이력(macro_history)이 09-07 기준 4일치(한국은행 지표는 1일) → 추세·내 이력 그래프는 며칠 지나야 의미.
- 원달러: 카드 전일비(ECOS 1360→1355 ▼)와 이력(1346→1355 ↗)이 반대 — 출처 차이로 보이나 **미확인**.
- 수출금액지수 전년비 64.2% 는 값이 이상함 — **검증 필요**(ECOS 403Y001 항목 선택 확인).
- 나스닥 차트는 나스닥100 CFD 라 카드 값(나스닥 종합)과 다름(페이지에 표기).

## 6. 다음에 할 순서
1. 달님이 01 을 며칠 써보고 피드백(카드 크기·페이지 순서·차트 선택).
2. **02-레짐보기.html**: `analysis/regime.json`(regime.py 결과: 성장·물가·유동성 판정, 확인/추정, 근거 지표, review) 를 읽어 "지금 어느 국면인가 + 왜 + 바뀌는 조건"을 한 페이지로. 지표 카드는 01 로 링크(`01-지표보기.html#kospi`).
3. 03-내 기록(Firestore, 종목/지표 페이지 하나에 기록 여러 개 — 실적 자료·오늘의 생각·다음 주 예측·반증 조건을 각각 별도 기록) → 04 발표·보고서 → 05 공시·근거글 → 06 축·전략 설명서.
4. 옛 화면 `_old/` 이동, Firestore 규칙 확인(03 때).

## 7. 검증 방법(Claude 용)
- 회사 PC 셸·클라우드 컨테이너는 github.io·FRED·네이버에 **못 붙음**(프록시 403). 실제 확인은 **크롬(Claude in Chrome)** 에서 fetch/iframe 으로.
- 파일 전달: device_commit_files 는 같은 이름 캐시 문제가 있어 **매번 새 파일명**으로 보내고, 기기에서 `wc -c`·첫 줄 버전으로 확인.
- 화면 확인은 컨테이너 Playwright(외부 요청은 route 로 가짜 응답) → 스크린샷.
