# 35개 지표 차트 연결 점검

2026-09-08. 정의·종목·변환·경로를 전수 대조. 모든 외부 사이트를 실제 브라우저에서 35회 열어 검증한 것은 아님. Yahoo 원달러와 ECOS 회사채·금리/물가/수출/선행지수 목록, FRED 변환 그래프를 대표 화면으로 확인. 외부 제공처의 지역·로그인·팝업·서비스 장애 제한은 별도.

- 기존 카드 제목은 수집 이력 모달을 열었음. 이제 직접 차트가 있는 제목과 웹 차트 버튼은 외부 그래프를 열고, 설명·뉴스·내 기록은 기존 상세로 이동.
- 기존 자체 차트의 전체/1개월/1년은 원출처 전체 이력이 아닌 짧은 수집 스냅샷만 필터링했음. 보조 접힘으로 이동하고 수집 전체로 명칭 변경.
- BBB- 회사채: 공식 조회 절차 확인, 공유 가능한 개별 링크 미확보. AA-로 대체하지 않음. 한국 신용 스프레드: 구성 금리 두 차트 제공, 단일 스프레드 그래프라고 표시하지 않음.

| ID | 지표 | 제공처 | 연결 상태 | 차트 | 정의·제약 |
|---|---|---|---|---|---|
| kospi | KOSPI | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/%5EKS11/chart/) | 웹 차트의 시세와 카드의 수집 기준 시각은 다를 수 있습니다. |
| kosdaq | KOSDAQ | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/%5EKQ11/chart/) | 웹 차트의 시세와 카드의 수집 기준 시각은 다를 수 있습니다. |
| usdkrw | 원달러 환율 | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/KRW%3DX/chart/) | 시장 환율 차트입니다. 카드의 ECOS 매매기준율과 시각·값이 다를 수 있습니다. |
| bok_rate | 한은 기준금리 | 한국은행 ECOS | 직접 차트 | [한국은행 ECOS](https://ecos.bok.or.kr/#/StatisticsByTheme/KoreanStat100/K051) | 결정일 기준 금리 이력입니다. 카드의 월간 집계와 구분해 보세요. |
| kr3y | 한국 국고채 3년 | 한국은행 ECOS | 직접 차트 | [한국은행 ECOS](https://ecos.bok.or.kr/#/StatisticsByTheme/KoreanStat100/K056) | 선택한 지표의 공식 차트·기간 조절 화면입니다. |
| kr10y | 한국 국고채 10년 | Investing.com | 직접 차트 | [Investing.com](https://www.investing.com/rates-bonds/south-korea-10-year-bond-yield-advanced-chart) | 한국 10년물 시장 수익률입니다. ECOS 고시 수익률과 시각·호가가 다를 수 있습니다. |
| kr_aa3 | 회사채 AA- 3년 | 한국은행 ECOS | 직접 차트 | [한국은행 ECOS](https://ecos.bok.or.kr/#/StatisticsByTheme/KoreanStat100/K057) | 선택한 지표의 공식 차트·기간 조절 화면입니다. |
| kr_bbb3 | 회사채 BBB- 3년 | 한국은행 ECOS | 항목 선택 필요 | [한국은행 ECOS](https://ecos.bok.or.kr/#/SearchStat) | BBB- 3년물은 공유 가능한 직접 차트 주소를 확보하지 못했습니다. ECOS에서 1.3.2.1 시장금리(일별) → 회사채(3년, BBB-) → 빠른 조회 → 차트를 선택하세요. 통계표 817Y002, 항목 010320000. |
| kr_cpi_yoy | 한국 CPI 전년비 | 한국은행 ECOS | 직접 차트 | [한국은행 ECOS](https://ecos.bok.or.kr/#/StatisticsByTheme/KoreanStat100/K401) | 공식 그래프에 원지수와 전년동기대비 증감률이 함께 표시됩니다. 카드와 비교할 때 증감률 축을 보세요. |
| sp500 | S&P500 | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/%5EGSPC/chart/) | 웹 차트의 시세와 카드의 수집 기준 시각은 다를 수 있습니다. |
| nasdaq | 나스닥 | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/%5EIXIC/chart/) | 웹 차트의 시세와 카드의 수집 기준 시각은 다를 수 있습니다. |
| sox | SOX 반도체 | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/%5ESOX/chart/) | 웹 차트의 시세와 카드의 수집 기준 시각은 다를 수 있습니다. |
| vix | VIX | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/%5EVIX/chart/) | 웹 차트의 시세와 카드의 수집 기준 시각은 다를 수 있습니다. |
| dxy | 달러지수 DXY | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/DX-Y.NYB/chart/) | 웹 차트의 시세와 카드의 수집 기준 시각은 다를 수 있습니다. |
| us10y | 미 10년물 | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/series/DGS10) | 동일한 FRED 시계열의 장기 그래프입니다. |
| us2y | 미 2년물 | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/series/DGS2) | 동일한 FRED 시계열의 장기 그래프입니다. |
| fedfunds | 연준 실효금리 FFR | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/series/FEDFUNDS) | 동일한 FRED 시계열의 장기 그래프입니다. |
| cpi_yoy | 미국 CPI 전년비 | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/graph/?g=1Yh9Z) | 전년 동월 대비 변화율(%)로 설정한 차트입니다. |
| core_pce_yoy | 미국 근원 PCE 전년비 | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/graph/?g=1Yha5) | 전년 동월 대비 변화율(%)로 설정한 차트입니다. |
| m2 | 미 M2 | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/series/M2SL) | 동일한 FRED 시계열의 장기 그래프입니다. |
| fed_bs | 연준 자산 | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/series/WALCL) | 동일한 FRED 시계열의 장기 그래프입니다. |
| ism_pmi | ISM 제조업 PMI | Trading Economics | 직접 차트 | [Trading Economics](https://tradingeconomics.com/united-states/business-confidence) | ISM 제조업 PMI입니다. S&P Global 제조업 PMI와 구분합니다. |
| hsi | 항셍지수 | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/%5EHSI/chart/) | 웹 차트의 시세와 카드의 수집 기준 시각은 다를 수 있습니다. |
| wti | 유가 WTI | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/CL%3DF/chart/) | 카드와 같은 선물 종목입니다. 만기 교체에 따른 가격 차이가 있을 수 있습니다. |
| copper | 구리 | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/HG%3DF/chart/) | 카드와 같은 선물 종목입니다. 만기 교체에 따른 가격 차이가 있을 수 있습니다. |
| gold | 금 | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/GC%3DF/chart/) | 카드와 같은 선물 종목입니다. 만기 교체에 따른 가격 차이가 있을 수 있습니다. |
| bdry | 해운 BDRY | Yahoo Finance | 직접 차트 | [Yahoo Finance](https://finance.yahoo.com/quote/BDRY/chart/) | BDRY ETF 가격입니다. 발틱운임 원지수가 아닙니다. |
| china_pmi | 중국 PMI | Trading Economics | 직접 차트 | [Trading Economics](https://tradingeconomics.com/china/business-confidence) | 중국 국가통계국 NBS 제조업 PMI입니다. 민간 RatingDog PMI와 구분합니다. |
| kr_lead | 선행지수순환변동치 | 한국은행 ECOS | 직접 차트 | [한국은행 ECOS](https://ecos.bok.or.kr/#/StatisticsByTheme/KoreanStat100/K254) | 선택한 지표의 공식 차트·기간 조절 화면입니다. |
| kr_export_yoy | 수출금액지수 전년비 | 한국은행 ECOS | 직접 차트 | [한국은행 ECOS](https://ecos.bok.or.kr/#/StatisticsByTheme/KoreanStat100/K358) | 공식 그래프에 원지수와 전년동기대비 증감률이 함께 표시됩니다. 카드와 비교할 때 증감률 축을 보세요. |
| payems_chg | 미 비농업고용 증감 | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/graph/?g=1Yhab) | 고용자 수 수준이 아닌 전월 대비 증감(천명) 차트입니다. |
| unrate | 미 실업률 | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/series/UNRATE) | 동일한 FRED 시계열의 장기 그래프입니다. |
| ahe_yoy | 미 시간당 임금 전년비 | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/graph/?g=1Yhaw) | 전년 동월 대비 변화율(%)로 설정한 차트입니다. |
| credit_spread | 신용 스프레드 AA-−국고3년 | 한국은행 ECOS | 구성금리 비교 (직접 스프레드 없음) | [한국은행 ECOS](https://ecos.bok.or.kr/#/StatisticsByTheme/KoreanStat100/K057) | 신용 스프레드 자체의 직접 차트 주소는 확인되지 않았습니다. AA- 회사채와 국고3년 차트를 각각 열어 비교합니다. 스프레드 = AA- 회사채 − 국고3년. |
| spread_10_2 | 장단기차 10y−2y | FRED | 직접 차트 | [FRED](https://fred.stlouisfed.org/series/T10Y2Y) | 동일한 FRED 시계열의 장기 그래프입니다. |
