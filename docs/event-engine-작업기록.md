# 공시·속보 Event Engine — 작업기록

> 원칙: 테스트하지 않은 것은 완료라고 쓰지 않는다. UNKNOWN을 추측으로 메우지 않는다. 정정 관계가 불확실하면 자동 병합하지 않는다. AI가 투자잠금을 스스로 해제하지 않는다.

## 2026-09-15 현재 상태
- Wave A/B 코드는 `event-engine` 브랜치에 반영 중/완료.
- 운영 `main`의 `scripts/dart.py`, `records.html`, `.github/workflows/dart.yml`은 변경하지 않는다.
- 상태: **WAVE B CODE COMPLETE / LIVE VALIDATION PENDING**.
- Wave C는 설계만 보존. 라이브 검증 전 구현 금지.

## Wave A
- 제목 Unicode 정규화(`ㆍ · ∙ ･ ・`) 및 Event Dictionary.
- Event Family/Type/Version 분리.
- 정정/철회는 신규공시 알림으로 취급하지 않음.
- 명시 parent rcept 없이는 `CANDIDATE`만, 휴리스틱 자동병합 금지.
- sourceLevel / claimStatus / dataStatus 분리.
- unknown title = OTHER/UNMAPPED + Decision Locked.

## 독립 검수 보완
업로드된 Claude patch를 그대로 신뢰하지 않고 별도 환경에서 적용·테스트했다.

발견/수정:
1. 업로드 patch CRLF + 마지막 개행 누락으로 `git apply`가 corrupt patch로 실패 → LF 정규화 시 정상 적용.
2. 기존 validator는 `facts/events/index.json`에 없는 `stock_code/rcept_no`를 읽어 exact match가 0이 되는 문제 → index writer 보완 및 live validator를 7일 index 비의존 구조로 변경.
3. `days=180/365`가 기존 7일 index의 Event Type만 조회해 표본 확대가 실질적으로 안 되던 문제 → 관심종목 corp_code 기준 상세 API를 180/365일 직접 탐색.
4. 검증기 기준 미달에도 exit 0 → live pass 조건 미달 시 exit 1.
5. workflow가 검증 결과를 자동 commit/push하던 구조 → `contents: read` + artifact 업로드로 변경.
6. 일반 `감사보고서`를 U3 FAST_RISK로 오분류 가능 → AUDIT_REPORT(U0)와 문제 감사의견 분리.
7. `영업정지/거래정지`를 규모/원인 확인 전 자동 M3 처리 → 방어 검토만 빠르게 열고 자동 M3 금지.
8. Event ID 마지막 4자리 기반 충돌 가능 → 전체 식별자 기반 결정론적 SHA1 suffix 사용.
9. materiality 비율 중복 계산 제거.

## 오프라인 검증
독립 검수 환경:
- Python syntax compile: PASS
- `scripts/replay_test.py`: **17/17 PASS**
- `tests/test_waveb_offline.py`: **22/22 PASS**
- mock network live-validator 경로: PASS (실 OpenDART가 아닌 mock임을 명시)

## Live Validation 기준
GitHub Actions `Event Engine Validate (manual)`에서:
- corpCode mapping 성공
- 상세 endpoint 실제응답 3종 이상
- schema mismatch 0
- `rcept_no` exact MATCHED ≥1
- 실제 Materiality 계산 ≥1
- UNKNOWN/NO_DETAIL_RECORD가 오류와 구분됨

실 OpenDART 호출 전에는 Wave B 완료로 표현하지 않는다.

## Wave C
`docs/event-engine-wave-c-설계.md` 참고. 수집~G3 AI 0, 사용자가 Event 분석을 눌렀을 때만 G4/G5 AI 사용. AI 비용/토큰/당시 단가 snapshot/fingerprint 예산게이트 포함.
