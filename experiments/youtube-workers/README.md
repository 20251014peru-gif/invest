# PC 서버 없이 쓰는 자막 요약 — Cloudflare 배포 준비본

이 폴더가 이번 Cloudflare용 배포본이다. Python·PC 서버·브라우저 자동화 없이 Workers와 Durable Objects에서 자막을 처리하고 결과를 보관한다. 실제 배포와 AI 호출은 아직 수행하지 않았다. 기본 설정은 `LIVE_AI=0`, 월 한도 0인 합성 시험이다.

## 포함한 비용 절감

- 같은 입력·옵션·처리 버전의 작업은 새로 만들지 않는다. 새로고침·중복 클릭에도 기존 작업을 반환한다.
- 채널 프로필과 성공한 구간 정리·최종 요약은 입력 해시로 재사용한다. 실패한 작업을 명시적으로 재개할 때 성공한 단계는 반복하지 않는다.
- 판단노트는 기본 해제다. 선택했을 때만 최근 최대 10편과 현재 요약을 사용해 추가로 생성한다.
- 구간 정리와 프로필에 Haiku를 쓰는 절약 옵션이 있다. 기본은 기존 Sonnet이며 최종 요약은 Sonnet을 유지한다. Haiku 품질 비교는 미실시다.
- 단계별 모델·추정 달러 비용·재사용 여부, 월 합계·예약액·한도를 표시한다. 단가는 Sonnet 4.6 입력/출력 $3/$15, Haiku 4.5 $1/$5 per 1M tokens 기준이다. 실제 청구서와 대조해야 한다.
- 실제 호출 전 보수적인 토큰 상한 추정액을 예약한다. 사용량 누락·통신 결과 불명확·저장 실패 때 예약액을 해제하지 않고 추가 호출을 중단한다. 서비스 쪽 처리는 HTTP 취소 후에도 비용을 발생시킬 수 있으므로 자동 재호출하지 않는다. 이 한도는 이 앱의 추정 통제이며 Anthropic 계정 전체의 청구 상한을 보장하지 않는다.

## 배포 순서

Cloudflare 계정과 Node가 있는 환경에서 이 폴더를 열고 실행한다. 이 준비본에 계정 ID나 실제 비밀키는 없다.

```text
npm install
npx wrangler login
npm test
npx wrangler deploy
npx wrangler secret put APP_TOKEN
```

APP_TOKEN에는 이 앱에만 쓰는 무작위 32자 이상의 접근 코드를 넣는다. 배포 출력의 workers.dev 주소를 열어 같은 코드를 입력하면 합성 시험을 할 수 있다. AI 키는 브라우저나 GitHub 파일에 넣지 않는다.

실제 요약을 켜는 단계는 별도다.

```text
npx wrangler secret put ANTHROPIC_API_KEY
```

그 다음 `wrangler.jsonc`의 `MONTHLY_LIMIT_USD`를 본인이 정한 양수 한도로, `LIVE_AI`를 `1`로 바꾸고 `npx wrangler deploy`한다. 이 변경부터 실제 Anthropic 비용이 발생할 수 있다. 현재 제공된 설정은 이를 켜지 않는다. Cloudflare 자체 사용료는 별도이며 선택 플랜의 한도를 확인한다.

## 쓰는 방법

접근 코드 입력 → 영상 제목·채널·자막 붙여넣기 → 필요하면 영상 주소·게시일·타임라인 추가 → 요약 접수. 접수 확인 후에는 브라우저와 PC를 꺼도 클라우드가 처리를 맡는다. 다시 같은 주소에서 작업을 불러와 결과를 연다. 결과 JSON 내려받기가 가능하다.

현재는 개인 한 명의 공유 비밀코드 방식이다. 그 코드를 가진 사람은 이 앱의 모든 작업을 볼 수 있다. 여러 사용자용 권한 분리 서비스가 아니다. 원문 자막과 결과는 Cloudflare 저장소에 보관한다. 작업은 최대 100개, 대기는 최대 10개다. 자동 삭제는 구현하지 않았다.

`비용 설정 확인`은 키/한도/모드를 수정한 뒤 `재개`할 수 있다. `실패`는 추가 비용 안내를 확인하고 실패 단계부터 재개한다. `확인 필요`는 자동 재호출이나 화면 재개를 허용하지 않는다. Anthropic 사용량과 보관된 작업의 `period`, `reserved`, 월 ledger를 대조한 뒤 운영자가 복구해야 한다. 해결 전에는 새 유료 작업도 차단된다. 장부를 삭제하거나 새 저장소로 바꾸어 우회하지 않는다.

## 검증과 남은 범위

- Node 로컬 시험 15개 통과: 중복 동시 접수, 긴 자막 전체 분할, 프로필/구간 재사용, 판단노트 선택, 상태 복원, 인증, 비용 사전 차단, 사용량 누락 차단, 잘린 응답 비용 기록과 명시적 재개, 시험 작업의 유료 전환 방지 등.
- Edge에서 붙여넣기 → 중복 접수 → 창 닫기 → 저장 상태 복원 → 결과·비용·책갈피 조회 통과. 모든 요청을 로컬 처리기에 연결했고 외부 요청 0이다.
- 실제 AI 호출 0, 운영 Firestore 읽기/쓰기 0. 기존 원본·records.html·D6 수정 0.
- 테스트 저장소는 Durable Objects 저장 API를 모사한 것이다. Cloudflare Wrangler 설치를 시도했지만 환경의 npm 네트워크 접근이 EACCES로 거절되어 Wrangler 빌드/로컬 런타임 검증은 못 했다. 실제 계정 배포·Durable Objects 클라우드 복구·실제 AI 품질은 미검증이다.
- 기존 COMMON_CORE·프로필·구간 추출·판단노트 프롬프트를 원본에서 추출했다. 기존 앱의 모든 기능을 옮긴 것은 아니다. 자막 교정 사전·영상 재생/캡처·AI 시각 매핑·자료함·메모·질문·기록보관실 연계는 이 독립 요약 화면에 없다. 수동 타임라인은 보존한다. 전체 내용 완전성은 미검증으로 표시한다.

로컬 검증: `npm test`. 브라우저 검증: Playwright와 Edge가 있는 환경에서 `node test-browser.mjs` (필요하면 TEST_PLAYWRIGHT_MODULE 지정). `preview.png`는 합성 시험 화면이다.

## 참고한 공식 문서

- [Cloudflare Durable Objects 시작](https://developers.cloudflare.com/durable-objects/get-started/)
- [알람의 최소 1회 실행·재시도 동작](https://developers.cloudflare.com/durable-objects/api/alarms/)
- [Claude API 가격](https://platform.claude.com/docs/en/about-claude/pricing)
- [Claude Messages API](https://platform.claude.com/docs/en/api/http/messages/create)
