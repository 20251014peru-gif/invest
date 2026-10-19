// mfLatest 요청 처리(순수 로직 — Firebase 의존성 없음, 단위 시험 가능).
// 검증 규칙은 기존 macroAi(chatgpt/backend/index.js)와 같다: Bearer ID 토큰 → 폐기 확인 포함 검증 → 본인 UID·이메일 인증·google.com 로그인만 허용.
// 저장소의 결과는 chatgpt_macro_private/multifactor_kr/snapshots/latest 문서의 payload(JSON 문자열)이며, 이 함수만(관리자 권한) 읽는다.
export const ERR = {
  method: 'POST만 지원합니다',
  auth: '본인 Google 로그인 확인이 필요합니다',
  empty: '아직 계산 결과가 없습니다',
  read: '결과를 읽지 못했습니다. 잠시 뒤 다시 시도하세요',
};

export function createMfLatestHandler({verifyIdToken, readLatest, ownerUid}) {
  return async function mfLatest(req, res) {
    res.set('Cache-Control', 'no-store');
    if (req.method !== 'POST') { res.status(405).json({error: ERR.method}); return; }

    try {
      const token = String(req.headers?.authorization || '').match(/^Bearer (.+)$/)?.[1];
      if (!token) throw new Error('no token');
      const user = await verifyIdToken(token, true);
      const owner = String(ownerUid() || '');
      // 본인 UID 가 비어 있으면(비밀값 누락) 누구도 통과시키지 않는다.
      if (!owner || !user || user.uid !== owner || user.email_verified !== true || user.firebase?.sign_in_provider !== 'google.com') throw new Error('not owner');
    } catch {
      res.status(401).json({error: ERR.auth});
      return;
    }

    let doc;
    try { doc = await readLatest(); } catch { res.status(502).json({error: ERR.read}); return; }
    if (!doc) { res.status(404).json({error: ERR.empty}); return; }
    try {
      if (typeof doc.payload !== 'string') throw new Error('bad doc');
      const data = JSON.parse(doc.payload);
      if (data?.schema !== 'multifactor_kr/1' || !Array.isArray(data.items)) throw new Error('bad schema');
      res.status(200).json(data);
    } catch {
      res.status(502).json({error: ERR.read});
    }
  };
}
