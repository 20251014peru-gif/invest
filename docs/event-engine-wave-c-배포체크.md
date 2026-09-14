# Event Engine Wave C — 배포 체크

> 현재 상태: **CODE/CI PASS · NOT DEPLOYED · AI API CALL 0**

## 이미 검증됨
- Wave A replay 17/17 PASS
- Wave B offline 38/38 PASS
- OpenDART LIVE_VALIDATION PASS
- Wave C AI cost/fingerprint core 10/10 PASS
- Firebase/Anthropic SDK install + AI Gateway import PASS

## 실제 배포 전 필수 확인
1. Firebase 프로젝트: `my-system-25497`가 기록보관실 운영 프로젝트인지 재확인.
2. Cloud Functions 사용에 필요한 Firebase/Google Cloud 결제 조건 확인. 사용자 승인 없이 배포하지 않는다.
3. **새 Anthropic API key** 준비. 저장소 코드/HTML에 절대 넣지 않고 Secret Manager의 `ANTHROPIC_API_KEY`로만 등록.
4. 과거 저장소에 노출됐던 API key는 재사용하지 않고 회전/폐기한다.
5. `ai_users/{firebase_uid}` 문서에 실제 사용자 기기 UID만 `enabled:true`로 허용. 익명 사용자는 기본 거부.
6. `ai_settings/default` 권장 초기값:
   - `autoAnalysisEnabled:false`
   - `dailyBudgetUsd:1.0`
   - `monthlyBudgetUsd:20.0`
   - `warningAtPercent:80`

## 배포 명령(승인 후)
```bash
firebase functions:secrets:set ANTHROPIC_API_KEY
firebase deploy --only functions:estimateEventAnalysis,functions:analyzeEvent
```

`firebase.json` predeploy가 `data/ai_pricing.json`을 function bundle로 동기화한다.

## 배포 직후 테스트 순서
1. 허용되지 않은 UID → `permission-denied` 확인.
2. 허용 UID에서 `estimateEventAnalysis`만 호출 → Token Counting / 예상비용 확인. 분석 API 호출은 아직 하지 않음.
3. 작은 검증 Event 1건을 Sonnet 5로 분석.
4. Firestore 확인:
   - `event_ai_analysis/{fingerprint}` 생성
   - `ai_usage/{id}` 실제 token/cost 저장
   - `ai_cost_daily/{YYYY-MM-DD}` / `ai_cost_monthly/{YYYY-MM}` 정산
5. 동일 Event 재호출 → `cacheHit:true`, `apiCalled:false`, 추가비용 0 확인.
6. `g6Unlocked:false` 유지 확인.
7. 실패 호출 시 usage가 없으면 `unreconciledUsd`로 예약비용이 남아 조용히 0원 처리되지 않는지 확인.

## 브라우저 연결은 서버 검증 후
기록보관실 `records.html`에 Anthropic API key를 넣지 않는다. Firebase callable 함수만 호출한다.
AI 버튼은 호출 전에 estimate 결과(모델·token·예상비용)를 보여주고 사용자가 실행을 눌러야 실제 분석한다.
