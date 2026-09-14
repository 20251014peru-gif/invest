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
  MODEL_POLICY, PROMPT_VERSION, ANALYSIS_OUTPUT_SCHEMA,
  analysisFingerprint, buildAnalysisPrompt, getPrice,
  estimateCostUsd, costFromUsageUsd, kstKeys, pricingIsStale, sha256
} from './lib/ai_core.js';

initializeApp();
const db = getFirestore();
const ANTHROPIC_API_KEY = defineSecret('ANTHROPIC_API_KEY');
const REGION = 'asia-northeast3';
const DEFAULT_BUDGET = {dailyBudgetUsd: 1.0, monthlyBudgetUsd: 20.0, warningAtPercent: 80, autoAnalysisEnabled: false};
const here = path.dirname(fileURLToPath(import.meta.url));

function loadPricing() {
  const p = path.join(here, 'generated', 'ai_pricing.json');
  if (!fs.existsSync(p)) throw new Error('generated/ai_pricing.json missing; run npm run sync-config before deploy');
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}
function assertPayloadSize(data) {
  const bytes = Buffer.byteLength(JSON.stringify(data || {}), 'utf8');
  if (bytes > 70000) throw new HttpsError('invalid-argument', 'Event/Thesis payload is too large. Send verified structured data, not full filings.');
}
async function assertAuthorized(uid) {
  if (!uid) throw new HttpsError('unauthenticated', 'Firebase sign-in required.');
  const snap = await db.collection('ai_users').doc(uid).get();
  if (!snap.exists || snap.data()?.enabled !== true) throw new HttpsError('permission-denied', 'This Firebase UID is not allowed to spend AI budget.');
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
function outputConfig() { return {format: {type: 'json_schema', schema: ANALYSIS_OUTPUT_SCHEMA}}; }
async function countInputTokens(client, policy, prompt) {
  const counted = await client.messages.countTokens({model: policy.model, system: prompt.system, messages: [{role: 'user', content: prompt.user}], output_config: outputConfig()});
  return Number(counted.input_tokens || 0);
}
function requireEvent(prompt) {
  if (!prompt.event?.event_id || !String(prompt.event.schema || '').startsWith('event/')) {
    throw new HttpsError('invalid-argument', 'Valid normalized Event schema/event_id required.');
  }
}

async function reserveBudget(reserveUsd, cfg) {
  const {day, month} = kstKeys();
  const dref = db.collection('ai_cost_daily').doc(day);
  const mref = db.collection('ai_cost_monthly').doc(month);
  await db.runTransaction(async tx => {
    // Firestore transaction: all reads before writes.
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
  const uid = request.auth?.uid; await assertAuthorized(uid); assertPayloadSize(request.data);
  const pricing=loadPricing(), policy=choosePolicy(request.data?.tier), price=getPrice(pricing,policy.model);
  const prompt=buildAnalysisPrompt(request.data?.event,request.data?.thesis); requireEvent(prompt);
  const inputTokens=await countInputTokens(anthropicClient(),policy,prompt);
  const cfg=await settings();
  return {provider:'anthropic',tier:policy.tier,model:policy.model,estimatedInputTokens:inputTokens,estimatedOutputTokens:policy.estimateOutputTokens,estimatedCostUsd:estimateCostUsd(inputTokens,policy.estimateOutputTokens,price),maxCostUsd:estimateCostUsd(inputTokens,policy.maxTokens,price),pricingStale:pricingIsStale(pricing),pricingVerifiedAt:pricing.verifiedAt,budgets:{dailyBudgetUsd:cfg.dailyBudgetUsd,monthlyBudgetUsd:cfg.monthlyBudgetUsd},note:'Estimate only. Final cost uses API response usage.'};
});

export const analyzeEvent = onCall({region: REGION, secrets: [ANTHROPIC_API_KEY], timeoutSeconds: 180, memory: '512MiB'}, async request => {
  const uid=request.auth?.uid; await assertAuthorized(uid); assertPayloadSize(request.data);
  const pricing=loadPricing(), cfg=await settings(), policy=choosePolicy(request.data?.tier), price=getPrice(pricing,policy.model);
  const prompt=buildAnalysisPrompt(request.data?.event,request.data?.thesis); requireEvent(prompt);
  const fingerprint=analysisFingerprint({event:request.data?.event,thesis:request.data?.thesis,model:policy.model,promptVersion:PROMPT_VERSION});
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
    message=await client.messages.create({model:policy.model,max_tokens:policy.maxTokens,system:prompt.system,messages:[{role:'user',content:prompt.user}],output_config:outputConfig(),metadata:{user_id:sha256(uid).slice(0,64)}});
    const text=message.content?.find?.(b=>b.type==='text')?.text; if(!text) throw new Error('Claude returned no text block');
    const output=JSON.parse(text); const actualUsd=costFromUsageUsd(message.usage||{},price);
    await reconcileBudget(budgetKeys,reserveMaxCostUsd,actualUsd,false); budgetSettled=true;
    const completedAt=new Date().toISOString();
    const analysisPublic={schema:'event-ai-analysis/1',status:'success',reviewRequired:true,g6Unlocked:false,eventId:prompt.event.event_id,fingerprint,provider:'anthropic',tier:policy.tier,model:policy.model,promptVersion:PROMPT_VERSION,output,usage:message.usage||{},estimatedCostUsd,costFromUsageUsd:actualUsd,billedCostUsd:null,priceSnapshot:snapshot,pricingStale:pricingIsStale(pricing),requestedAt,completedAt};
    await aref.set({...analysisPublic,uid,createdAt:FieldValue.serverTimestamp()},{merge:false});
    await usageRef.set({schema:'ai_usage/1',status:'success',eventId:prompt.event.event_id,analysisType:'risk_thesis',fingerprint,uid,provider:'anthropic',tier:policy.tier,model:policy.model,promptVersion:PROMPT_VERSION,inputTokens:Number(message.usage?.input_tokens||0),outputTokens:Number(message.usage?.output_tokens||0),cacheReadInputTokens:Number(message.usage?.cache_read_input_tokens||0),cacheCreationInputTokens:Number(message.usage?.cache_creation_input_tokens||0),estimatedInputTokens:inputTokens,estimatedCostUsd,reservedMaxCostUsd,costFromUsageUsd:actualUsd,billedCostUsd:null,priceSnapshot:snapshot,requestedAt,completedAt,createdAt:FieldValue.serverTimestamp()});
    return {cacheHit:false,apiCalled:true,incrementalCostUsd:actualUsd,analysis:analysisPublic};
  } catch(err) {
    const usage=message?.usage||err?.usage||null; const actualUsd=usage?costFromUsageUsd(usage,price):0;
    if(!budgetSettled) await reconcileBudget(budgetKeys,reserveMaxCostUsd,actualUsd,!usage);
    const completedAt=new Date().toISOString();
    try {
      await usageRef.set({schema:'ai_usage/1',status:'error',eventId:prompt.event.event_id,analysisType:'risk_thesis',fingerprint,uid,provider:'anthropic',tier:policy.tier,model:policy.model,promptVersion:PROMPT_VERSION,usage:usage||null,estimatedInputTokens:inputTokens,estimatedCostUsd,reservedMaxCostUsd,costFromUsageUsd:usage?actualUsd:null,billedCostUsd:null,costStatus:usage?'USAGE_RECONCILED':'UNRECONCILED',errorType:err?.name||'Error',errorMessage:String(err?.message||err).slice(0,500),priceSnapshot:snapshot,requestedAt,completedAt,createdAt:FieldValue.serverTimestamp()});
    } catch(logErr) { logger.error('Failed to persist AI usage error', {eventId:prompt.event.event_id,error:logErr?.message}); }
    logger.error('Event AI analysis failed',{eventId:prompt.event.event_id,fingerprint,error:err?.message});
    throw new HttpsError('internal',usage?'AI analysis failed after usage was recorded.':'AI analysis failed; budget reserve marked unreconciled for review.');
  }
});
