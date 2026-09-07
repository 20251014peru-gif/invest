# OpenAI 연결 준비 상태

실제 서버 배포·API 호출은 아직 수행하지 않았다. UI만 보고 AI가 작동한다고 판단하지 않는다.

## 다음 설정
1. 현재 Firebase 프로젝트의 Google 로그인을 활성화하고 GitHub 호스트를 인증 도메인에 추가한다. 보안에 민감한 접근 설정이므로 브라우저 작업 시 사용자 확인이 필요하다.
2. 본인 Google 인증 UID를 확인한다. 새 chatgpt_macro_private 경로는 공개 읽기·쓰기에서 제외해야 한다. records는 본인만, aiCache와 aiUsage는 클라이언트 전체 거부하고 Admin 서버만 접근한다. 기존 규칙의 넓은 allow가 겹치면 더 좁은 deny는 효과가 없으므로 겹침을 제거한다.
3. Firebase Secret Manager에 OPENAI_API_KEY와 MACRO_OWNER_UID를 등록한다. 공개 파일이나 브라우저 저장소에 키를 넣지 않는다. 사용자는 비밀키를 채팅에 붙이지 않는다.
4. backend 디렉터리에서 공식 패키지 의존성을 설치하고 잠금 파일을 생성·검토한다. 현재 SDK 실제 설치/배포 검증은 미완료다. 별도 codebase macro-private-ai의 macroAi 함수만 배포한다. 기존 함수를 삭제하거나 전체 프로젝트 배포하지 않는다.
5. 본인 인증·다른 계정 거절·무인증 거절·기사 재사용·서울 날짜 상한을 실제 연결로 검사한 뒤 config.json의 cloudReady와 aiEndpoint를 설정하고 새 버전을 발행한다.

## 처리 흐름과 비용 제어
- Firebase ID 토큰을 서버에서 검증하고 지정 UID·Google 인증·이메일 검증 조건을 모두 확인.
- 클라이언트가 선택한 뉴스 1건 요약 또는 35개 지표와 관련 뉴스 최대 8건 질문. 내 메모는 사용자가 포함을 선택한 경우에만 전달.
- OpenAI Responses API, store:false, JSON 구조 응답. 미완성 응답·자료에 없는 인용 ID 거절. 실제 API 품질·토큰비용은 키 연결 후 측정해야 한다.
- 초기 모델은 공식 문서에서 확인한 gpt-5-mini, 서버 모델 설정으로 변경 가능. 답변 품질 평가 후 질문용 상위 모델 분리 여부를 결정한다.
- 뉴스 내용·모델·질문·프롬프트 버전이 같으면 서버 결과 재사용. 새 내용은 새 키. 실패 자동 재시도 없음.
- 서울 날짜별 최대 30회 API 시도. 거래적으로 호출 전 예약하며 실패도 상한에 포함한다. 실제 금액 상한을 뜻하지 않는다. max_output_tokens=5000, 서버 동시성 1, 최대 인스턴스 1.
- 웹 검색 도구는 호출하지 않는다. 답변은 전달된 자료 범위에 제한된다. 질문 전체/근거 원문을 일반 로그에 남기지 않는다. 기사 결과는 private 경로에 저장하고 질문 대화는 현재 창 메모리에만 보존한다.

## 참고
- https://developers.openai.com/api/docs/models/gpt-5-mini
- https://developers.openai.com/api/docs/guides/migrate-to-responses
- https://firebase.google.com/docs/functions/http-events
