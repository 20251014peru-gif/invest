# 매크로·분석 통합 이력

## macro_periods 수집기 안정화 · 2026-09-30
- 문제: 2026-09-30 운영 실행(10:40Z)에서 macro_periods 전 시리즈 18/18이 `TimeoutError: The read operation timed out`. 신규 4개 시계열이 적재되지 않았고 기존 14개도 마지막 관측 9/10(수집 9/13)에서 멈춤. 같은 실행에서 macro.py·macro_extra.py의 FRED 요청은 성공.
- 원인(코드 근거, 운영 재현은 못 함): 시리즈마다 전체 이력을 별도 요청(18건), 읽기 제한 25초, 재시도 없음, 4개 병렬. 워크플로가 `|| echo ::warning::`으로 실패를 삼켜 Actions는 초록으로 끝남. CI 전체 시간 제한이 아니라 요청 단위 시간초과로 판단.
- 변경: 기간(cosd) 제한, 같은 기간 그룹은 한 요청(id=A,B,C), 묶음 실패 시 시리즈별 재시도(제한 40초, 2회 재시도), 시리즈마다 결과·오류 분리와 중간 저장(원자적 쓰기), 전체 제한 360초 전 중단, `status`(complete/partial/failed)·`counts`·`errors`·`collected_at`·항목별 `last_observation` 기록, 전체 실패 시 종료코드 1과 `::error::`, 부분 실패 시 `::warning::`. 워크플로 문구를 error로 변경(수집기 전체는 계속).
- 후속 수정(PR 검토 반영): (1) 워크플로가 `macro_periods.py` 종료코드를 `PERIODS_RC`에 보관하고, 나머지 수집·커밋·push 를 끝낸 뒤 0이 아니면 `exit 1`(변경 없음 경로와 push 재시도 뒤에도 유지). 실패 알림 단계(`if: failure()`)가 실제로 실행됨. (2) `counts` 를 `defined/collected/series_failed/batch_fallbacks/retained_items` 로 분리하고 `status` 는 실제 시리즈 성공·실패로만 판정, 묶음 요청 오류는 `batch_errors`(경고)로만 기록. (3) 시리즈마다 실제 사용한 요청 주소를 `source_url` 로 저장. (4) 모든 JSON·한글 파일 입출력에 `encoding='utf-8'`, 표준출력 UTF-8 재설정으로 비UTF-8 로케일에서도 실행.
- 검증: `tests/test_macro_periods.py`(가짜 FRED 서버)로 정상·묶음 실패 후 개별 성공·한 시리즈 실패·전체 시간초과·기존 자료 보존·종료코드·counts 일치·source_url 정확 통과. `tests/test_macro_workflow.py`가 macro.yml 의 실행 단계를 꺼내 임시 git 저장소에서 실패 전파(실패+변경/실패+무변경/성공/push 재시도 후 유지/push 전부 실패)를 검사. 이전 워크플로에서는 이 시험이 실패함을 확인. 실제 FRED 묶음 요청(id=A,B,C)과 운영 실행 결과는 병합 후 Actions에서 `facts/macro_periods.json`의 status·collected_at·last_observation으로 확인해야 함(미검증).

## v1.1 시장 톱니바퀴 보고서 자료 보강 · 2026-09-30
- 요청: 위험 3·4단계와 실제 20거래일 차트에 필요한 미국 30년물, 하이일드 OAS, CCC 이하 OAS, SOFR를 PC 없이 GitHub Actions에서 수집.
- 변경: `data/macro_extra_indicators.json`에 FRED `DGS30`, `BAMLH0A0HYM2`, `BAMLH0A3HYC`, `SOFR`를 추가했다. 기존 `macro_extra.py`와 `macro_periods.py`가 최신값과 실제 관측일 시계열을 각각 저장한다.
- 원/달러: 기존 ECOS `731Y001/0000001` 일간 매매기준율 수집을 확인해 중복 경로를 만들지 않았다. Yahoo 실시간 차트와 값·시각이 다를 수 있다는 기존 설명을 유지한다.
- 자료 정직성: 보강 최신값에 공식 FRED 직접수집 상태 `D`, 관측일 경과일, `available/stale`를 기록한다. 결측은 이전 값을 새 값처럼 채우지 않는다.
- 검증: 신규 시리즈 ID·심볼·단위·주기와 기존 ECOS 원달러 코드를 검사하는 Python 자동검사를 추가했다. 2026-09-30 로컬 격리 실행에서 보강 수집 8/8, 기간 차트 18/18에 성공했고 새 네 시리즈는 모두 2026-09-28 공식 관측값과 120개 기간값을 반환했다. GitHub Actions 운영 실행은 병합 후 별도 확인한다.
- 보고서 연결: 기존 `facts/macro_extra.json`은 최신값·기준일을, `facts/macro_periods.json`은 실제 관측일 차트를 제공한다. 별도 중복 시계열 파일은 만들지 않는다.

## v016-20260913-214952-KST
- 요청: 공식 발표일·다음 발표일, 카드 스파크라인 유지, 상세 막대그래프, 기존 분석 대시보드와 통합.
- 구조: research.html에서 macro.html, chatgpt/, records.html을 필요할 때 열고 메뉴 전환 시 보존. 기존 URL·개인 저장소 유지. ID로 매크로 상세에서 분석·뉴스·메모 연결.
- 데이터: data/official_releases.json은 실제 보도자료와 공식 예정일을 별도로 관리. 현재값 기준기간에 맞는 발표만 표시. 예정일이 지나도 발표 완료로 바꾸지 않음. 일정은 확인일 기준이며 자동 일정 수집은 없음.
- 차트: js/macro-detail.js를 두 앱에서 공유. facts/macro_periods.json에 FRED 14개 실제 기간별 원자료와 계산식·수집시각 저장. 빈 기간 보간 금지. 0은 막대의 크기 기준이며 경제적 중립선 아님. 공식 확인된 ISM 50·한국 CPI 목표 2%만 별도 선 표시.
- 수집: 기존 macro.json과 snapshot 이력 불변. 독립 macro_periods.py가 매시 기존 워크플로에 합류. 실패 시 이전 기간별 원자료 보존.
- 확인한 문제: CPIAUCSL 계절조정 지수 전년비가 BLS 비계절조정 전년비와 다를 수 있어 설명 추가.
- 작업 중 실패: 번들 Git의 HTTPS helper 누락으로 GitHub ZIP 사용. 네트워크 제한은 승인된 다운로드로 해결. 치환 중 $$ 축약으로 카드 초기화 실패 → 브라우저 오류 확인 후 수정. 기존 날짜 고정 테스트는 9/8과 현재 수집본 9/13 불일치 → 수집본 시각 사용.
- 복구: 이 변경 커밋의 코드만 되돌리고 기존 facts와 개인 Firestore 데이터를 삭제하지 않음. 기존 독립 주소로 접근 가능.
- 검증: 최종 결과는 아래에 기록. 로그인 후 실제 계정 저장·AI 호출·기기간 동기화는 재검증하지 않음.

### 최종 검증
- Node 자동검사 52개 및 Python 자동검사 4개 통과.
- CPI/고용/PCE 공식 일정, 서머타임, 경과 일정 차단, null 기준선, 음수·한 개·동일 값 막대, 누락 월 계산, 원본 값 보존 검사.
- 브라우저에서 CPI 상단 6칸·기간별 막대·24기간 전환, 분석 대시보드 같은 CPI 상세, 메뉴 전환 시 선택 유지, records 진입 확인. 390px 모바일에서 상세 가로 넘침 없음.
- 로컬 미리보기의 뉴스 원격 연결 실패는 기존 오류 표시로 격리됨. 뉴스 UI와 개인 저장·인증 코드는 변경하지 않음.
- 추가 원인: CPI 원자료 결측월 때문에 기존 행 번호 기반 전년비가 3.71로 계산됨. 실제 같은 연·월 비교값은 3.353%. 두 수집기의 연·월 대응 계산을 수정하고 화면은 더 최근 동일 시리즈 원자료를 사용, 기존 원본값과 차이를 안내. 값이 달라지면 과거 설정 판정을 재사용하지 않음.
- 수집기 코드 수정 범위는 전년 같은 달 비교와 별도 기간별 수집 추가. 기존 record 시스템 변경은 통합 메뉴 링크 한 곳뿐.
