# Event Engine Wave C — 배포 체크

> 현재 상태: **CODE/CI PASS · NOT DEPLOYED · PAID AI API CALL 0**

## 이미 검증됨
- Wave A replay 17/17 PASS
- Wave B offline 38/38 PASS
- OpenDART LIVE_VALIDATION PASS
- Wave C Event runtime/notifier PASS
- 첫 실행 baseline 알림폭탄 방지 + 기존 Event 메타 보존 PASS
- Browser inline JS syntax PASS
- Wave C AI cost/fingerprint core 10/10 PASS
- Firebase/Anthropic SDK install + `event-ai` / `event-access` import PASS
- `records.html` 변경 없음

## 배포 전 사용자가 딱 한 번 준비할 것

### 1. Firebase 프로젝트 Blaze 확인
Cloud Functions for Firebase 배포에는 프로젝트가 Blaze 요금제여야 한다. 프로젝트는 `my-system-25497`.

> Blaze는 함수 사용량에 따라 과금될 수 있다. 이번 함수는 minInstances를 두지 않고 자동 AI 호출도 OFF로 유지한다.

### 2. 배포용 Google Cloud Service Account
GitHub Actions에서 Firebase CLI를 인증할 JSON 키를 하나 만든다.

권장 역할(공식 Firebase IAM 기준 + Secret 설정용):
- Cloud Functions Admin: `roles/cloudfunctions.admin`
- Service Account User: `roles/iam.serviceAccountUser`
- Secret Manager Admin: `roles/secretmanager.admin` (두 앱 Secret 생성/갱신용)

가능하면 이후 Workload Identity Federation으로 바꾸되, 1차 배포는 사용자가 관리하는 전용 배포 계정의 JSON 키를 GitHub Secret에만 저장한다.

### 3. GitHub Repository Secrets 3개
저장소 Settings → Secrets and variables → Actions 에서 다음만 등록한다.

| Secret | 값 |
|---|---|
| `GCP_SERVICE_ACCOUNT_KEY` | 위 전용 배포 Service Account JSON 전체 |
| `ANTHROPIC_API_KEY` | **새로 발급한** Anthropic API key. 과거 코드에 노출된 키 재사용 금지 |
| `AI_ACCESS_CODE` | 집/회사/폰에서 기기 등록할 개인 Access Code. **16자 이상**의 긴 문자열/문구 사용 |

**Secret 값은 채팅/코드/HTML에 붙여넣지 않는다.** 짧은 숫자 PIN은 사용하지 않는다.

## 배포 버튼
main에 수동 workflow가 이미 준비되어 있다.

`Actions → Event Engine Wave C Deploy (manual) → Run workflow`

기본 `source_ref=event-engine-wave-c`, `confirm_no_paid_test=true` 그대로 실행한다.

workflow가 하는 일:
1. Secret 존재만 검사(값 출력 없음)
2. `event-engine-wave-c` checkout
3. Google Cloud 인증
4. Wave C 핵심 테스트 재실행
5. `ANTHROPIC_API_KEY`, `AI_ACCESS_CODE`를 Firebase Secret Manager에 저장
6. `functions:event-access` codebase 배포
7. `functions:event-ai` codebase 배포
8. 배포 함수 목록 확인

**이 workflow는 `analyzeEvent`를 호출하지 않는다. 따라서 Anthropic 유료 메시지 분석은 실행하지 않는다.**

## codebase 분리 이유
`firebase.json`:
- `event-access` → 기기 Access Code 등록 함수
- `event-ai` → 예상비용/AI 분석 함수

서로 다른 codebase로 분리해 한쪽 배포가 다른 Firebase 함수들을 삭제하는 위험을 낮춘다.

## 기기 등록 보안
- 등록 비밀값은 `AI_ACCESS_CODE`, 최소 16자.
- 브라우저에는 비밀값이나 Anthropic 키가 저장되지 않는다.
- 실패 시 익명 UID 기준 하루 5회 제한.
- IP는 원문을 저장하지 않고 SHA-256 일부값으로만 카운트하며 하루 20회 제한.
- 등록 후 실제 AI 호출에도 일/월 예산 제한이 별도로 적용된다.

## 배포 후 무료/최소비용 검증 순서
1. `ai-register.html`에서 집/회사/폰 각 기기를 Access Code로 1회 등록.
2. `events.html`에서 Event 선택.
3. **예상비용 확인**만 실행 → Anthropic Token Counting으로 입력 token/예상비용 확인.
4. 이 단계까지 메시지 생성 비용은 0.
5. 그 다음 작은 Event 1건만 Sonnet 5 실제 분석을 사용자가 명시적으로 승인.
6. Firestore 확인:
   - `event_ai_analysis/{fingerprint}`
   - `ai_usage/{id}`
   - `ai_cost_daily/{YYYY-MM-DD}`
   - `ai_cost_monthly/{YYYY-MM}`
7. 동일 Event 재호출 → `cacheHit:true`, `apiCalled:false`, 추가비용 0 확인.
8. `g6Unlocked:false` 유지 확인. G6는 사용자 확인으로만 저장.

## 기본 비용 안전장치
- `autoAnalysisEnabled=false`
- daily budget 기본 `$1`
- monthly budget 기본 `$20`
- 분석 전 무료 token count + 예상비용 표시
- 분석 실행 전 사용자 확인
- fingerprint 동일 시 API 재호출 0
- API 사용량 기반 `costFromUsageUsd` 기록
- 실패했는데 usage를 알 수 없으면 `UNRECONCILED`, 임의로 $0 처리 금지

## 운영 DART merge 전 확인
- 첫 `facts/events/index.json` 생성 시 baseline 모드 → 기존 7일 공시를 저장만 하고 알림 0.
- 이후 새 `rcept_no`만 신규 Event 알림.
- `FAST_RISK`는 `is_held=true`가 확인된 경우에만 사용. 보유 정보가 아직 GitHub Runtime에 연결되지 않으면 `RISK_REVIEW`로 보수적으로 알림.
- `records.html`은 현재 그대로 유지하고 `events.html`을 독립 검토 화면으로 먼저 운영한다.

## Merge 게이트
Draft PR #9는 다음을 모두 확인한 후에만 main으로 merge한다.
1. Functions 배포 성공
2. 기기등록 성공
3. Token Count 예상비용 성공
4. 작은 Event 1건 실제 분석 + 비용 장부 확인
5. cache hit 추가비용 0 확인
6. 첫 Event runtime baseline/신규알림 동작 확인
