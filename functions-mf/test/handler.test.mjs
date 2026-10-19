// mfLatest 처리 로직 시험 — 네트워크·Firebase 없이. 실행: node --test functions-mf/test/handler.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {createMfLatestHandler, ERR} from '../handler.js';

const OWNER = 'owner-uid-123';
const goodUser = {uid: OWNER, email_verified: true, firebase: {sign_in_provider: 'google.com'}};
const goodPayload = JSON.stringify({schema: 'multifactor_kr/1', items: [{code: '005930'}], n: 1});

function mkRes() {
  const r = {headers: {}, statusCode: 200, body: undefined};
  r.set = (k, v) => { r.headers[k] = v; return r; };
  r.status = (c) => { r.statusCode = c; return r; };
  r.json = (b) => { r.body = b; return r; };
  return r;
}
function setup(opts = {}) {
  const {user = goodUser, verifyThrows = false, doc = {payload: goodPayload}, readThrows = false} = opts;
  const owner = 'owner' in opts ? opts.owner : OWNER;       // undefined 를 명시적으로 넘기면 "비밀값 누락" 상황을 재현
  const calls = {verify: [], read: 0};
  const handler = createMfLatestHandler({
    verifyIdToken: async (t, rev) => { calls.verify.push([t, rev]); if (verifyThrows) throw new Error('bad token'); return user; },
    readLatest: async () => { calls.read++; if (readThrows) throw new Error('boom'); return doc; },
    ownerUid: () => owner,
  });
  return {handler, calls};
}
const req = (over = {}) => ({method: 'POST', headers: {authorization: 'Bearer tok'}, ...over});

test('본인 계정이면 결과를 돌려주고 no-store 로 응답한다', async () => {
  const {handler, calls} = setup(); const res = mkRes();
  await handler(req(), res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.schema, 'multifactor_kr/1');
  assert.equal(res.headers['Cache-Control'], 'no-store');
  assert.deepEqual(calls.verify[0], ['tok', true]);        // 폐기된 토큰까지 확인(checkRevoked=true)
});

test('POST 외 메서드는 405 이고 토큰 검증·읽기를 하지 않는다', async () => {
  for (const method of ['GET', 'PUT', 'DELETE', 'OPTIONS']) {
    const {handler, calls} = setup(); const res = mkRes();
    await handler(req({method}), res);
    assert.equal(res.statusCode, 405, method);
    assert.equal(calls.verify.length, 0); assert.equal(calls.read, 0);
  }
});

test('토큰이 없거나 형식이 틀리면 401 이고 읽지 않는다', async () => {
  for (const authorization of [undefined, '', 'Bearer', 'Bearer ', 'Basic abc', 'tok']) {
    const {handler, calls} = setup(); const res = mkRes();
    await handler(req({headers: authorization === undefined ? {} : {authorization}}), res);
    assert.equal(res.statusCode, 401, String(authorization));
    assert.equal(res.body.error, ERR.auth); assert.equal(calls.read, 0);
  }
});

test('토큰 검증이 실패하면 401 이고 오류 내용을 노출하지 않는다', async () => {
  const {handler, calls} = setup({verifyThrows: true}); const res = mkRes();
  await handler(req(), res);
  assert.equal(res.statusCode, 401); assert.equal(JSON.stringify(res.body).includes('bad token'), false); assert.equal(calls.read, 0);
});

test('다른 사용자(UID 불일치)는 401', async () => {
  const {handler, calls} = setup({user: {...goodUser, uid: 'someone-else'}}); const res = mkRes();
  await handler(req(), res);
  assert.equal(res.statusCode, 401); assert.equal(calls.read, 0);
});

test('이메일 미인증 계정은 401', async () => {
  for (const email_verified of [false, undefined, 'true']) {
    const {handler, calls} = setup({user: {...goodUser, email_verified}}); const res = mkRes();
    await handler(req(), res);
    assert.equal(res.statusCode, 401, String(email_verified)); assert.equal(calls.read, 0);
  }
});

test('구글 이외 로그인(익명·비밀번호 등)은 401', async () => {
  for (const sign_in_provider of ['anonymous', 'password', 'custom', undefined]) {
    const {handler, calls} = setup({user: {...goodUser, firebase: {sign_in_provider}}}); const res = mkRes();
    await handler(req(), res);
    assert.equal(res.statusCode, 401, String(sign_in_provider)); assert.equal(calls.read, 0);
  }
  const {handler} = setup({user: {uid: OWNER, email_verified: true}}); const res = mkRes();   // firebase 항목 자체가 없음
  await handler(req(), res); assert.equal(res.statusCode, 401);
});

test('본인 UID 비밀값이 비어 있으면 누구도 통과하지 못한다(빈 UID 토큰 포함)', async () => {
  for (const owner of ['', undefined, null]) {
    for (const uid of ['', undefined, OWNER]) {
      const {handler, calls} = setup({owner, user: {...goodUser, uid}}); const res = mkRes();
      await handler(req(), res);
      assert.equal(res.statusCode, 401, `owner=${owner} uid=${uid}`); assert.equal(calls.read, 0);
    }
  }
});

test('결과가 아직 없으면 404', async () => {
  const {handler} = setup({doc: null}); const res = mkRes();
  await handler(req(), res); assert.equal(res.statusCode, 404); assert.equal(res.body.error, ERR.empty);
});

test('읽기 실패·손상된 문서·다른 형식은 502 이고 내부 정보를 노출하지 않는다', async () => {
  const cases = [
    {readThrows: true},
    {doc: {payload: 123}},
    {doc: {payload: '{not json'}},
    {doc: {payload: JSON.stringify({schema: 'other/1', items: []})}},
    {doc: {payload: JSON.stringify({schema: 'multifactor_kr/1', items: 'x'})}},
    {doc: {}},
  ];
  for (const c of cases) {
    const {handler} = setup(c); const res = mkRes();
    await handler(req(), res);
    assert.equal(res.statusCode, 502, JSON.stringify(c)); assert.equal(res.body.error, ERR.read);
  }
});

test('모든 응답에 Cache-Control: no-store (오류 포함)', async () => {
  for (const s of [{}, {verifyThrows: true}, {doc: null}, {readThrows: true}]) {
    const {handler} = setup(s); const res = mkRes();
    await handler(req(), res); assert.equal(res.headers['Cache-Control'], 'no-store');
  }
});
