# Event Engine Wave C 설계 — AI 분석 + 비용관리

> 상태: **DESIGN ONLY**. Wave A/B GitHub 반영 → `Event Engine Validate (manual)` LIVE PASS 후 구현한다.

## 원칙
- G0 탐지 · G1 출처 · G2 Fact · G3 Materiality = deterministic Python, AI 비용 0.
- G4 Risk Analysis · G5 Thesis Comparison = 사용자가 요청할 때만 AI.
- G6 Decision Ready = 사용자 확인. AI 혼자 잠금 해제 금지.
- `autoAnalysisEnabled=false` 기본. M3/FAST_RISK도 자동 유료 호출하지 않는다.

## 모델 역할과 현재 가격
가격 계산에는 Anthropic 공식 Pricing/Platform Docs만 사용하고 `verifiedAt`을 남긴다.

| 용도 | 모델 | Input / MTok | Output / MTok |
|---|---|---:|---:|
| 짧은 사실정리 | claude-haiku-4-5 | $1 | $5 |
| Risk/Thesis 분석 | claude-sonnet-5 | $2 | $10 |
| 사용자가 선택한 고난도 분석 | claude-opus-5 | $5 | $25 |

가격은 향후 변할 수 있으므로 구현 시 `data/ai_pricing.json` 한 곳에서 effective-date 이력과 검증 메타를 관리한다. 호출 장부에는 **그 호출 당시 단가 snapshot**을 저장한다.

## 비용 기록
분석 전 `count_tokens`로 `estimatedInputTokens`/`estimatedCostUsd`를 표시한다. 호출 후 API usage의 `input_tokens`/`output_tokens`를 기준으로 `costFromUsageUsd`를 계산한다. 청구 시스템과 대조한 값이 있을 때만 `billedCostUsd`를 별도로 쓴다.

월별 장부 예: `facts/ai_usage/YYYY-MM.json`
- eventId, model, analysisType
- inputTokens, outputTokens
- input/output price snapshot
- estimatedCostUsd, costFromUsageUsd, billedCostUsd(optional)
- promptVersion, requestedAt/completedAt, status

실패 호출도 usage가 반환되면 기록한다. 비용 0으로 단정하지 않는다.

## 중복 호출 방지
`analysisFingerprint = hash(event/schema + field_map/schema + event_id + latest rcept_no + verified facts + metrics + unknowns + thesis version + promptVersion + model)`.
동일 fingerprint면 기존 분석을 재사용하고 API 호출 0.

## 최소 입력
기본 입력은 Event Type · 확인 Fact · Materiality metrics · UNKNOWN · 정정 Delta · 현재 Thesis. 공시 원문 전체를 기본 전송하지 않는다. AI 분석 내부 web search/server-side tool도 기본 OFF; 외부조사가 필요하면 `추가 조사 필요`를 반환한다.

## AI 출력
FACT_SUMMARY / POSITIVE_CASE / NEGATIVE_CASE / COUNTER_ARGUMENT / KEY_RISKS / UNKNOWN_IMPORTANCE / THESIS_IMPACT(T-2~T+2) / THESIS_REASON / NEXT_CONFIRMATION / INVALIDATION_TRIGGER.
없는 값은 UNKNOWN. 근거 없는 목표가·예상수익률 생성 금지.

## 비용 예산
서버 AI Gateway에서 원자적으로 예산을 검사한다. 예시 설정: daily $1, monthly $20, 80% 경고. 브라우저만으로 예산 차단하지 않는다. API KEY는 `records.html`에 넣지 않고 백엔드 전용으로 둔다.

## Wave C 진입 게이트
A. Wave A/B GitHub 반영
B. Actions 실행
C. 상세 endpoint 3종+ 실제 응답
D. rcept exact match ≥1
E. Materiality 실계산 ≥1
F. UNKNOWN 정상유지 사례 ≥1
G. CONFLICT 잠금 시험 통과

AI 비용추적 없이 Wave C 완료 선언하지 않는다.
