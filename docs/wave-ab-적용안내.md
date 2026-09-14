# Wave A/B 적용안내

## 브랜치
`event-engine`

## 운영 영향
현재 단계에서는 기존 `scripts/dart.py`, `records.html`, `.github/workflows/dart.yml`을 수정하지 않는다. Event Engine은 검증용 신규 코드로만 존재한다.

## GitHub 검증 순서
`Event Engine Validate (manual)` workflow를 `event-engine` 브랜치 대상으로 실행한다.

기본 입력: `days=180`
표본 부족 시: `days=365`

Workflow가 자동으로 실행:
1. Python syntax check
2. `python scripts/replay_test.py` → 기대 17/17 PASS
3. `python tests/test_waveb_offline.py` → 기대 22/22 PASS
4. OpenDART corpCode/detail/list 실제 호출
5. schema/rcept exact match/Materiality/Risk Gate 검증
6. 검증 산출물을 artifact로 보관(운영 branch 자동 commit 없음)

## Live PASS 기준
- corpCode cache 성공, count > 0
- 실제 응답 endpoint ≥ 3종
- schema mismatch = 0
- rcept exact MATCHED ≥ 1
- VERIFIED/CALCULATED/REPORTED_ONLY 중 실제 Materiality ≥ 1

미달이면 workflow는 실패(exit 1)한다. 단 NO_SAMPLE/NO_DETAIL_RECORD는 코드오류와 분리해 로그로 확인한다.

## 다음 단계
LIVE PASS 후에만 Wave C: ntfy 분리 → records Event 연결 → news candidate 연계 → 사용자 수동 AI Risk/Thesis 분석 + 비용 추적.
