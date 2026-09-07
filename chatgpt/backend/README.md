# OpenAI 서버 연결 상태

서울 리전의 macroAi 함수 배포 완료. 공개 화면은 v003부터 연결한다.
- Google 로그인과 운영 GitHub 도메인 설정 완료.
- 본인 UID를 Secret Manager의 MACRO_OWNER_UID로 제한. OPENAI_API_KEY는 서버에서만 읽는다.
- 새 chatgpt_macro_private 경로의 기록은 확인된 본인만 접근. aiCache/aiUsage는 클라이언트 접근 차단. 다른 기존 경로의 접근 조건은 유지.
- 규칙 허용/거부 7건, 서버 무인증/잘못된 토큰 401 확인.
- OpenAI 실제 연결 검사 성공. 실제 브라우저 본인 호출과 장기 사용은 추가 검증 필요.

## 배포
firebase deploy --only functions:macro-private-ai:macroAi --project my-system-25497
모델은 .env.my-system-25497의 MACRO_AI_MODEL=gpt-5-mini로 지정한다. 키 값은 이 파일에 넣지 않는다.
Node22 런타임. 배포 이미지 보관7일. 실제 배포 작업 폴더에 의존성 잠금 파일 생성.

## 비용과 데이터
선택한 뉴스 또는 지표/관련 뉴스만 전송한다. 메모는 사용자 포함 선택 시 전송.
OpenAI Responses store:false. 뉴스는 내용/모델/질문/프롬프트가 같으면 캐시 사용.
서울 날짜 기준 최대30회 시도(실패 포함). 실제 금액 상한을 뜻하지 않는다.
출력 토큰 최대5000, 서버 동시성1, 최대 인스턴스1. 자동 재시도 없음.
API 키·인증 토큰·질문 원문은 일반 로그에 출력하지 않는다.

## 남은 검사
본인 브라우저의 질문과 뉴스 요약, 동일 기사 캐시, 실제 메모 저장/다른 기기 동기화.
'배포 완료'를 '모든 기능 검증 완료'로 표시하지 않는다.
