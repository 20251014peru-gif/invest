# 아침보고서 자료 연결 · 2026-10-01.1

운영 주소: https://20251014peru-gif.github.io/invest/v2/market-report-data.html

## 연결 원칙과 범위

보고서 v2.3의 23개 고정 ID를 유지한다. 17개는 공식 역사자료를 수집하고, 정의·접근 경로가 정해지지 않은 6개는 이유를 남긴다. 사용자 선택에 따라 기존 FRED·한국은행·뉴욕연준 경로를 우선 사용한다. 새 유료 서비스나 증권사 계정을 만들지 않는다.

| 묶음 | 연결 계열 |
|---|---|
| 미국 주가지수 | FRED NASDAQCOM, SP500, DJIA, NASDAQSOX |
| 한국 주가지수 | ECOS 802Y001 / 0001000(KOSPI), 0089000(KOSDAQ) |
| 원/달러 주간 종가 | ECOS 731Y003 / 0000003. 원응답 항목명 `원/달러(종가 15:30)` 검사 |
| 미국 국채 | FRED DGS2·DGS10·DGS30, 미 재무부 CMT 공식 재배포 |
| 한국 국고채 | ECOS 817Y002 / 010200000(3년), 010210000(10년), 최종호가수익률 |
| 신용 | FRED BAMLH0A0HYM2(HY), BAMLC0A0CM(IG), BAMLH0A3HYC(CCC) |
| 펀딩 | 뉴욕연준 SOFR·EFFR 공식 API, effectiveDate와 percentRate |

FRED의 Nasdaq 원자료는 공표가 늦을 수 있다. 연결 성공과 최신성은 다르다. 관측일·조회시각·이전 관측일을 반드시 보여준다. 달력에 따른 예상 최신일은 아직 검증하지 않았으므로 이를 최신/정상이라고 단정하지 않는다. SOFR은 전 영업일 거래를 다음 영업일 공표하므로 단순 날짜 차이를 수집 실패로 해석하지 않는다.

미연결: ICE 현물 DXY(관측시각·역사경로), CL·Brent(계약월별 정산가), NQ 11시(계약월·시각별 거래가), KRX 외국인 현물·선물(시장/상품 범위와 원표 경로). 상세 이유와 다음 작업은 JSON에 있다. FRED 광의달러를 DXY로, 현물 원유를 선물 정산가로, Nasdaq Composite를 NQ로 대체하지 않는다.

## 원자료와 보고서 계약

공통 기준 파일은 `facts/market_report_feeds.json`, 검증 파일은 `facts/market_report_validation.json`이다. PDF·MD 작성 시 이 파일의 동일한 실행 결과를 잠그고 사용한다. 이 변경은 데이터 연결이며 기존 08:17 보고서를 최신 수치로 소급 덮어쓰지 않는다. PDF/MD/개인 이슈장부의 자동 생성·Drive 예약 업로드는 이번 수집기 범위에 포함되지 않는다.

각 항목은 고정 ID, 정의, 실제 관측일, 조회시각, 동일 계열 이전값, 최근 5개 관측, 원응답 SHA-256을 가진다. 가격 변화는 비율(%), 금리·OAS 변화는 bp다. 0·보간·휴일 복제값을 만들지 않는다. FRED의 결측 `.`는 관측으로 세지 않는다. ECOS 항목 코드·이름·단위를 함께 검사해 통계 정의 변경을 포착한다. 조회 당시 자료의 일중 공표시각은 알 수 없으면 null이다. `first_proven_available_at`은 이번 보존 시각이며 원래 공표시각이 아니다.

연결됐어도 달력 최신성, 독립 두 번째 출처, 사건 전후 비교창이 아직 검증되지 않은 경우 자동 매매·종합 위험등급을 산출하지 않는다. `signal_eligible:false`는 이 추가 판정이 구현되지 않았음을 뜻하며 연결 실패와 다르다.

## 기존 화면 교정

기존 Yahoo 중계 수집은 수집일과 달력상 어제를 가격에 붙였다. 이제 실제 일봉 timestamp를 거래소 시간대로 변환하고 같은 일봉 응답의 Close를 사용한다. 마지막 일봉은 장중일 수 있으며 보고서 확정 종가는 별도 공식 계열이다. WTI 연속선물 장애 시 FRED 현물 원유로 바뀌던 대체 경로도 제거했다. 기존 매매기준율·실시간 화면·개인 기록은 보존한다. 이전 `macro_history.json`은 수집일별 과거 기록이므로 이를 거래일별 원시계열로 재해석하지 않는다.

## 운영·비용·복구

야간 시세의 일봉과 최신 체결가가 동일한 현지 달력 날짜로 겹치면, 실제 관측시각이 가장 늦은 값만 표시하고 등락 비교를 비운다(`session_overlap_comparison_withheld`). 같은 관측시각에 서로 다른 값이면 수집 오류다. 이를 보고서 정산가·종가로 승격하지 않는다.

- 실행: 기존 GitHub Actions `Macro Collector`, 매시 05분 예약. 회사 PC나 브라우저가 꺼져도 GitHub에서 수행. 예약은 정시 실행을 보장하지 않음.
- 설정: GitHub의 기존 `FRED_API_KEY`, `ECOS_KEY` Secrets. 새 키를 코드/로그/브라우저에 노출하지 않음. ECOS 직접 네트워크 실패에만 기존 소유자 Cloudflare relay 사용; HTTP 인증/접근 거부를 우회하지 않음.
- 저장: 수치·검증 JSON은 기존 invest 저장소와 Pages. 개인 기록·매매규칙은 공개 파일에 쓰지 않음. 원응답은 각 Actions 실행의 `report-feeds-RUN_ID` artifact에 30일 보존. 장기 원응답 보존은 별도 백업 필요.
- 버전: 2026-10-01.1. 수집 JSON에 실행 URL과 코드 커밋 기록. Git 변경 이력으로 이전 수치/설정 복원 가능.
- 복구: 연결판 변경 전 기준 main `3a2d103a61b5d8fcaaa8dfa60132db330c183467`. 관련 코드 변경만 revert; 개인 자료나 기존 수집 기록 삭제 금지.
- 비용: 기존 GitHub Actions·Pages·FRED·ECOS·뉴욕연준 및 기존 relay 사용. 새 유료 구독을 신청하지 않음. 기존 공급자의 사용량/제한은 유지.
- 검증: 회귀검사와 로컬 공식 API 응답 시험 후 별도 브랜치의 GitHub runner에서 실제 실행하고, main 배포 후 Pages JSON을 다시 읽는다. 실제 휴대폰 로그인·사용 시험은 별도이며 수행하지 않았다.

## 공식 정의 근거

- https://fred.stlouisfed.org/series/NASDAQCOM
- https://fred.stlouisfed.org/series/NASDAQSOX (Nasdaq SOX 연결 명시)
- https://fred.stlouisfed.org/series/SP500 (가격지수·종가)
- https://fred.stlouisfed.org/series/DJIA
- https://ecos.bok.or.kr/ (통계코드와 API 원응답의 항목명·단위 검사)
- https://snapshot.bok.or.kr/search/%EA%B8%88%EB%A6%AC/A2 (국고채 최종호가수익률)
- https://www.newyorkfed.org/markets/reference-rates/sofr (전일 거래와 다음 날 공표)
- https://www.newyorkfed.org/markets/reference-rates/effr
- https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html (공개 정산가 공표 시차)
- https://openapi.krx.co.kr/contents/OPP/MAIN/main/index.cmd

공식 제공기관·원 저작자의 사용조건은 각 원자료 링크를 따른다.
