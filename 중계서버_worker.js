// 중계서버 (Cloudflare Worker) — v 20260904-2200
// 하는 일: 브라우저가 못 뚫는 사이트(야후·네이버 금융 등)를 대신 받아 CORS 열어 돌려준다.
// 공짜 공개 프록시(codetabs·allorigins)가 자꾸 죽는 문제를 이 '내 전용 프록시'로 대체.
// 쓰는 곳: 허브 index.html 의 ⚙ 중계서버 설정 → 배포된 주소(https://xxx.workers.dev) 붙여넣기.
//          같은 도메인이라 CYGNUS(invest)도 자동으로 이걸 씀.
export default {
  async fetch(request) {
    const { searchParams } = new URL(request.url);
    const target = searchParams.get("url");
    // 브라우저 사전요청(OPTIONS) 허용
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: cors() });
    }
    if (!target) {
      return new Response("사용법: ?url=<가져올주소>", { status: 400, headers: cors() });
    }
    try {
      const r = await fetch(target, {
        headers: { "User-Agent": "Mozilla/5.0 (relay)", "Accept": "application/json,text/plain,*/*" },
        cf: { cacheTtl: 20, cacheEverything: true },   // 20초 캐시(무료 한도 아끼기)
      });
      const body = await r.text();
      const h = cors();
      h["Content-Type"] = r.headers.get("content-type") || "application/json; charset=utf-8";
      return new Response(body, { status: r.status, headers: h });
    } catch (e) {
      return new Response("중계 실패: " + e, { status: 502, headers: cors() });
    }
  },
};
function cors() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Cache-Control": "no-store",
  };
}
