import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import Anthropic from '@anthropic-ai/sdk';
import {initializeApp} from 'firebase-admin/app';
import {getFirestore, FieldValue} from 'firebase-admin/firestore';
import {onCall, HttpsError} from 'firebase-functions/v2/https';
import {defineSecret} from 'firebase-functions/params';
import * as logger from 'firebase-functions/logger';
import {
  MODEL_POLICY, PROMPT_VERSION, AI_POLICY_VERSION, ANALYSIS_OUTPUT_SCHEMA,
  analysisFingerprint, buildAnalysisPrompt, getPrice, decisionPolicy,
  estimateCostUsd, costFromUsageUsd, kstKeys, pricingIsStale, sha256
} from './lib/ai_core.js';

initializeApp();
const db = getFirestore();
const ANTHROPIC_API_KEY = defineSecret('ANTHROPIC_API_KEY');
const REGION = 'asia-northeast3';
const DEFAULT_BUDGET = {dailyBudgetUsd: 1.0, monthlyBudgetUsd: 20.0, warningAtPercent: 80, autoAnalysisEnabled: false};
const here = path.dirname(fileURLToPath(import.meta.url));
const RAW_EVENT_BASE = 'https://raw.githubusercontent.com/20251014peru-gif/invest/main';
const RAW_CACHE_MS = 60_000;
const rawCache = new Map();

function loadPricing() {
  const p = path.join(here, 'generated', 'ai_pricing.json');
  if (!fs.existsSync(p)) throw new Error('generated/ai_pricing.json missing; run npm run sync-config before deploy');
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}
function assertPayloadSize(data) {
  const bytes = Buffer.byteLength(JSON.stringify(data || {}), 'utf8');
  if (bytes > 20000) throw new HttpsError('invalid-argument', 'Request payload is too large. Send event_id/tier/decision only.');
}
async function assertAuthorized(uid) {
  if (!uid) throw new HttpsError('unauthenticated', 'Firebase sign-in required.');
  const snap = await db.collection('ai_users').doc(uid).get();
  if (!snap.exists || snap.data()?.enabled !== true) throw new HttpsError('permission-denied', 'This Firebase UID is not allowed to use Event decision/AI functions.');
}
async function settings() {
  const snap = await db.collection('ai_settings').doc('default').get();
  const raw = snap.exists ? snap.data() : {};
  return {
    dailyBudgetUsd: Number(raw?.dailyBudgetUsd ?? DEFAULT_BUDGET.dailyBudgetUsd),
    monthlyBudgetUsd: Number(raw?.monthlyBudgetUsd ?? DEFAULT_BUDGET.monthlyBudgetUsd),
    warningAtPercent: Number(raw?.warningAtPercent ?? DEFAULT_BUDGET.warningAtPercent),
    autoAnalysisEnabled: raw?.autoAnalysisEnabled === true
  };
}
function choosePolicy(tier) {
  const key = ['routine','analysis','deep'].includes(tier) ? tier : 'analysis';
  return {tier: key, ...MODEL_POLICY[key]};
}
function anthropicClient() { return new Anthropic({apiKey: ANTHROPIC_API_KEY.value()}); }
function outputConfig(policy) {
  const out = {format: {type: 'json_schema', schema: ANALYSIS_OUTPUT_SCHEMA}};
  if (policy?.effort) out.effort = policy.effort;
  return out;
}
async function countInputTokens(client, policy, prompt) {
  const counted = await client.messages.countTokens({
    model: policy.model,
    system: prompt.system,
    messages: [{role: 'user', content: prompt.user}],
    output_config: outputConfig(policy)
  });
  return Number(counted.input_tokens || 0);
}
function eventIdFrom(data) {
  return String(data?.eventId || data?.event_id || data?.event?.event_id || data?.event?.eventId || '').trim().slice(0, 180);
}
async function rawJson(relPath) {
  const now=Date.now(); const hit=rawCache.get(relPath);
  if(hit && now-hit.at<RAW_CACHE_MS) return hit.value;
  const url=`${RAW_EVENT_BASE}/${relPath}`;
  const r=await fetch(url,{headers:{'User-Agent':'invest-event-ai/1'},cache:'no-store'});
  if(!r.ok) throw new HttpsError('failed-precondition',`Authoritative Event source unavailable: ${relPath} (${r.status})`);
  const value=await r.json(); rawCache.set(relPath,{at:now,value}); return value;
}
async function authoritativeEvent(eventId) {
  if(!eventId) throw new HttpsError('invalid-argument','event_id required.');
  const idx=await rawJson('facts/events/index.json');
  const summary=(idx.events||[]).find(x=>String(x.event_id||'')===eventId);
  if(!summary) throw new HttpsError('failed-precondition','Event not found in authoritative index.');
  const d=String(summary.date||'');
  if(!/^\d{8}$/.test(d)) throw new HttpsError('failed-precondition','Authoritative Event date invalid.');
  const daily=await rawJson(`facts/events/${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}.json`);
  const event=(daily.events||[]).find(x=>String(x.event_id||'')===eventId);
  if(!event) throw new HttpsError('failed-precondition','Event details not found in authoritative daily file.');
  if(!String(event.schema||'').startsWith('event/')) throw new HttpsError('failed-precondition','Authoritative Event schema invalid.');
  return event;
}
async function serverThesis(company) {
  const snap=await db.collection('records_meta').doc('stocks').get();
  const list=snap.exists && Array.isArray(snap.data()?.list) ? snap.data().list : [];
  const hit=list.find(x=>String(typeof x==='object' ? x?.name||'' : x||'')===String(company||''));
  return hit && typeof hit==='object' ? hit : null;
}

async function reserveBudget(reserveUsd, cfg) {
  const {day, month} = kstKeys();
  const dref = db.collection('ai_cost_daily').doc(day);
  const mref = db.collection('ai_cost_monthly').doc(month);
  await db.runTransaction(async tx => {
    const ds = await tx.get(dref);
    const ms = await tx.get(mref);
    const d = ds.exists ? ds.data() : {}; const m = ms.exists ? ms.data() : {};
    const dUsed = Number(d.spentUsd || 0) + Number(d.reservedUsd || 0) + Number(d.unreconciledUsd || 0);
    const mUsed = Number(m.spentUsd || 0) + Number(m.reservedUsd || 0) + Number(m.unreconciledUsd || 0);
    if (dUsed + reserveUsd > cfg.dailyBudgetUsd) throw new HttpsError('resource-exhausted', `Daily AI budget limit: $${cfg.dailyBudgetUsd}`);
    if (mUsed + reserveUsd > cfg.monthlyBudgetUsd) throw new HttpsError('resource-exhausted', `Monthly AI budget limit: $${cfg.monthlyBudgetUsd}`);
    const common = {updatedAt: FieldValue.serverTimestamp()};
    tx.set(dref, {...common, reservedUsd: Number(d.reservedUsd || 0) + reserveUsd}, {merge: true});
    tx.set(mref, {...common, reservedUsd: Number(m.reservedUsd || 0) + reserveUsd}, {merge: true});
  });
  return {day, month};
}
async function reconcileBudget(keys, reserveUsd, actualUsd, unreconciled = false) {
  const dref = db.collection('ai_cost_daily').doc(keys.day);
  const mref = db.collection('ai_cost_monthly').doc(keys.month);
  await db.runTransaction(async tx => {
    const ds = await tx.get(dref);
    const ms = await tx.get(mref);
    for (const [ref, snap] of [[dref, ds], [mref, ms]]) {
      const v = snap.exists ? snap.data() : {};
      tx.set(ref, {
        reservedUsd: Math.max(0, Number(v.reservedUsd || 0) - reserveUsd),
        spentUsd: Number(v.spentUsd || 0) + (unreconciled ? 0 : actualUsd),
        unreconciledUsd: Number(v.unreconciledUsd || 0) + (unreconciled ? reserveUsd : 0),
        updatedAt: FieldValue.serverTimestamp()
      }, {merge: true});
    }
  });
}
function priceSnapshot(model, price, pricing) {
  return {model, inputPricePerMillion:Number(price.inputPerMillion), outputPricePerMillion:Number(price.outputPerMillion), cacheReadPerMillion:Number(price.cacheReadPerMillion||0), cache5mWritePerMillion:Number(price.cache5mWritePerMillion||0), pricingVerifiedAt:pricing.verifiedAt, pricingSource:pricing.source};
}
function publicAnalysis(doc) {
  if (!doc) return null;
  const {uid, createdAt, ...safe} = doc;
  return safe;
}

export const estimateEventAnalysis = onCall({region: REGION, secrets: [ANTHROPIC_API_KEY], timeoutSeconds: 60, memory: '256MiB'}, async request => {
  const uid=request.auth?.uid; await assertAuthorized(uid); assertPayloadSize(request.data);
  const event=await authoritativeEvent(eventIdFrom(request.data));
  const thesis=await serverThesis(event.company);
  const pricing=loadPricing(), policy=choosePolicy(request.data?.tier), price=getPrice(pricing,policy.model);
  const prompt=buildAnalysisPrompt(event,thesis);
  const inputTokens=await countInputTokens(anthropicClient(),policy,prompt);
  const cfg=await settings();
  return {
    provider:'anthropic',tier:policy.tier,model:policy.model,effort:policy.effort||null,
    aiPolicyVersion:AI_POLICY_VERSION,eventId:event.event_id,
    estimatedInputTokens:inputTokens,estimatedOutputTokens:policy.estimateOutputTokens,
    estimatedCostUsd:estimateCostUsd(inputTokens,policy.estimateOutputTokens,price),
    maxOutputTokens:policy.maxTokens,maxCostUsd:estimateCostUsd(inputTokens,policy.maxTokens,price),
    pricingStale:pricingIsStale(pricing),pricingVerifiedAt:pricing.verifiedAt,
    budgets:{dailyBudgetUsd:cfg.dailyBudgetUsd,monthlyBudgetUsd:cfg.monthlyBudgetUsd},
    note:'Estimate only. Server reloaded authoritative Event + stored Thesis; final cost uses API response usage.'
  };
});

export const analyzeEvent = onCall({region: REGION, secrets: [ANTHROPIC_API_KEY], timeoutSeconds: 180, memory: '512MiB'}, async request => {
  const uid=request.auth?.uid; await assertAuthorized(uid); assertPayloadSize(request.data);
  const event=await authoritativeEvent(eventIdFrom(request.data));
  const thesis=await serverThesis(event.company);
  const pricing=loadPricing(), cfg=await settings(), policy=choosePolicy(request.data?.tier), price=getPrice(pricing,policy.model);
  const prompt=buildAnalysisPrompt(event,thesis);
  const fingerprint=analysisFingerprint({event,thesis,model:policy.model,promptVersion:PROMPT_VERSION,policyVersion:AI_POLICY_VERSION});
  const aref=db.collection('event_ai_analysis').doc(fingerprint); const existing=await aref.get();
  if (existing.exists && existing.data()?.status==='success') return {cacheHit:true,apiCalled:false,incrementalCostUsd:0,analysis:publicAnalysis(existing.data())};

  const client=anthropicClient();
  const inputTokens=await countInputTokens(client,policy,prompt);
  const estimatedCostUsd=estimateCostUsd(inputTokens,policy.estimateOutputTokens,price);
  const reserveMaxCostUsd=estimateCostUsd(inputTokens,policy.maxTokens,price);
  const budgetKeys=await reserveBudget(reserveMaxCostUsd,cfg);
  const usageRef=db.collection('ai_usage').doc(); const snapshot=priceSnapshot(policy.model,price,pricing); const requestedAt=new Date().toISOString();
  let message=null, budgetSettled=false;
  try {
    message=await client.messages.create({
      model:policy.model,max_tokens:policy.maxTokens,system:prompt.system,messages:[{role:'user',content:prompt.user}],
      output_config:outputConfig(policy),metadata:{user_id:sha256(uid).slice(0,64)}
    });
    if (message.stop_reason === 'max_tokens') throw new Error('Claude output hit max_tokens before a complete structured answer.');
    if (message.stop_reason === 'refusal') throw new Error('Claude refused this analysis request.');
    const text=message.content?.find?.(b=>b.type==='text')?.text; if(!text) throw new Error('Claude returned no text block');
    const output=JSON.parse(text); const actualUsd=costFromUsageUsd(message.usage||{},price);
    await reconcileBudget(budgetKeys,reserveMaxCostUsd,actualUsd,false); budgetSettled=true;
    const completedAt=new Date().toISOString();
    const analysisPublic={
      schema:'event-ai-analysis/1',status:'success',reviewRequired:true,g6Unlocked:false,eventId:event.event_id,fingerprint,
      provider:'anthropic',tier:policy.tier,model:policy.model,effort:policy.effort||null,aiPolicyVersion:AI_POLICY_VERSION,
      promptVersion:PROMPT_VERSION,stopReason:message.stop_reason||null,output,usage:message.usage||{},estimatedCostUsd,
      costFromUsageUsd:actualUsd,billedCostUsd:null,priceSnapshot:snapshot,pricingStale:pricingIsStale(pricing),requestedAt,completedAt
    };
    await aref.set({...analysisPublic,uid,createdAt:FieldValue.serverTimestamp()},{merge:false});
    await usageRef.set({
      schema:'ai_usage/1',status:'success',eventId:event.event_id,analysisType:'risk_thesis',fingerprint,uid,
      provider:'anthropic',tier:policy.tier,model:policy.model,effort:policy.effort||null,aiPolicyVersion:AI_POLICY_VERSION,
      promptVersion:PROMPT_VERSION,stopReason:message.stop_reason||null,
      inputTokens:Number(message.usage?.input_tokens||0),outputTokens:Number(message.usage?.output_tokens||0),
      cacheReadInputTokens:Number(message.usage?.cache_read_input_tokens||0),cacheCreationInputTokens:Number(message.usage?.cache_creation_input_tokens||0),
      estimatedInputTokens:inputTokens,estimatedCostUsd,reservedMaxCostUsd,costFromUsageUsd:actualUsd,billedCostUsd:null,
      priceSnapshot:snapshot,requestedAt,completedAt,createdAt:FieldValue.serverTimestamp()
    });
    return {cacheHit:false,apiCalled:true,incrementalCostUsd:actualUsd,analysis:analysisPublic};
  } catch(err) {
    const usage=message?.usage||err?.usage||null; const actualUsd=usage?costFromUsageUsd(usage,price):0;
    if(!budgetSettled) await reconcileBudget(budgetKeys,reserveMaxCostUsd,actualUsd,!usage);
    const completedAt=new Date().toISOString();
    try {
      await usageRef.set({
        schema:'ai_usage/1',status:'error',eventId:event.event_id,analysisType:'risk_thesis',fingerprint,uid,
        provider:'anthropic',tier:policy.tier,model:policy.model,effort:policy.effort||null,aiPolicyVersion:AI_POLICY_VERSION,
        promptVersion:PROMPT_VERSION,stopReason:message?.stop_reason||null,usage:usage||null,
        estimatedInputTokens:inputTokens,estimatedCostUsd,reservedMaxCostUsd,costFromUsageUsd:usage?actualUsd:null,billedCostUsd:null,
        costStatus:usage?'USAGE_RECONCILED':'UNRECONCILED',errorType:err?.name||'Error',errorMessage:String(err?.message||err).slice(0,500),
        priceSnapshot:snapshot,requestedAt,completedAt,createdAt:FieldValue.serverTimestamp()
      });
    } catch(logErr) { logger.error('Failed to persist AI usage error', {eventId:event.event_id,error:logErr?.message}); }
    logger.error('Event AI analysis failed',{eventId:event.event_id,fingerprint,error:err?.message});
    throw new HttpsError('internal',usage?'AI analysis failed after usage was recorded.':'AI analysis failed; budget reserve marked unreconciled for review.');
  }
});

export const getEventDecision = onCall({region:REGION,timeoutSeconds:30,memory:'128MiB'}, async request => {
  const uid=request.auth?.uid; await assertAuthorized(uid); assertPayloadSize(request.data);
  const eventId=eventIdFrom(request.data); if(!eventId) throw new HttpsError('invalid-argument','event_id required.');
  const snap=await db.collection('event_decisions').doc(eventId).get();
  if(!snap.exists) return {exists:false,eventId};
  const d=snap.data()||{};
  return {exists:true,eventId,decision:d.decision||'',gate:d.gate||'',riskReviewed:d.riskReviewed===true,confirmedAt:d.confirmedAt?.toDate?.()?.toISOString?.()||null};
});

export const confirmEventDecision = onCall({region:REGION,timeoutSeconds:45,memory:'128MiB'}, async request => {
  const uid=request.auth?.uid; await assertAuthorized(uid); assertPayloadSize(request.data);
  const event=await authoritativeEvent(eventIdFrom(request.data));
  const policy=decisionPolicy(event,request.data?.decision,request.data?.riskReviewed===true);
  if(!policy.ok) throw new HttpsError('failed-precondition',policy.reason);
  const latest=(event.versions||[]).slice(-1)[0]||{};
  const analysisFingerprintValue=String(request.data?.analysisFingerprint||'').slice(0,128)||null;
  const doc={
    schema:'event-decision/1',eventId:event.event_id,rcept_no:String(latest.rcept_no||''),decision:policy.decision,
    userConfirmed:true,riskReviewed:true,analysisFingerprint:analysisFingerprintValue,gate:'G6',uid,
    sourceSnapshot:{claimStatus:event.claimStatus||'',materiality:event.materiality||'UNKNOWN',materialityStatus:event.materialityStatus||'UNKNOWN'},
    confirmedAt:FieldValue.serverTimestamp()
  };
  await db.collection('event_decisions').doc(event.event_id).set(doc,{merge:true});
  return {ok:true,eventId:event.event_id,decision:policy.decision,gate:'G6'};
});
