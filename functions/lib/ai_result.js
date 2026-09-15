import {ANALYSIS_OUTPUT_SCHEMA} from './ai_core.js';

export class AnalysisParseError extends Error {
  constructor(code) { super(code); this.name = 'AnalysisParseError'; this.code = code; }
}

// Accept only a complete structured answer. Never guess missing investment facts.
export function parseAnalysisOutput(message) {
  const fail = code => { throw new AnalysisParseError(code); };
  if (message?.stop_reason !== 'end_turn') fail(`STOP_${String(message?.stop_reason || 'MISSING').toUpperCase()}`);
  let text = (Array.isArray(message.content) ? message.content : [])
    .filter(b => b?.type === 'text' && typeof b.text === 'string').map(b => b.text).join('').trim();
  if (!text) fail('EMPTY_TEXT');
  const fence = text.match(/^```(?:json)?\s*\n?([\s\S]*?)\n?```$/i);
  if (fence) text = fence[1].trim();
  let output;
  try { output = JSON.parse(text); } catch { fail('INVALID_JSON'); }
  if (!output || typeof output !== 'object' || Array.isArray(output)) fail('INVALID_SCHEMA');
  const schema = ANALYSIS_OUTPUT_SCHEMA;
  if (Object.keys(output).some(k => !Object.hasOwn(schema.properties, k))) fail('INVALID_SCHEMA');
  for (const key of schema.required) {
    const value = output[key], rule = schema.properties[key];
    if (!Object.hasOwn(output, key)) fail('INVALID_SCHEMA');
    if (rule.type === 'string' && typeof value !== 'string') fail('INVALID_SCHEMA');
    if (rule.type === 'array' && (!Array.isArray(value) || value.some(x => typeof x !== 'string'))) fail('INVALID_SCHEMA');
    if (rule.type === 'integer' && !Number.isInteger(value)) fail('INVALID_SCHEMA');
    if (rule.enum && !rule.enum.includes(value)) fail('INVALID_SCHEMA');
  }
  return output;
}

// For plain API/config payloads only; add Firestore sentinels AFTER sanitizing.
// Preserve array positions; nested arrays are represented as maps for Firestore.
export function firestoreSafe(value, inArray = false, seen = new Set(), depth = 0) {
  if (value == null || typeof value === 'function' || typeof value === 'symbol') return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' || typeof value === 'boolean') return value;
  if (typeof value === 'bigint') return String(value);
  if (value instanceof Date) return Number.isFinite(value.getTime()) ? value.toISOString() : null;
  if (depth > 15 || seen.has(value)) throw new Error('UNSAFE_DOCUMENT_STRUCTURE');
  seen.add(value);
  try {
    if (Array.isArray(value)) {
      const items = Array.from(value, x => firestoreSafe(x, true, seen, depth + 1));
      return inArray ? {items} : items;
    }
    const out = {};
    for (const [key, item] of Object.entries(value)) {
      if (item === undefined || /^__.*__$/.test(key)) continue;
      Object.defineProperty(out, key, {value: firestoreSafe(item, false, seen, depth + 1), enumerable: true});
    }
    return out;
  } finally { seen.delete(value); }
}

// Ledger marker and both totals commit together. A lost commit acknowledgement
// can safely be retried using the SAME usageRef without incrementing totals twice.
export async function settleUsage(db, {usageRef, dailyRef, monthlyRef, reserveUsd, actualUsd, usageDoc, timestamp}) {
  return db.runTransaction(async tx => {
    const ledger = await tx.get(usageRef);
    if (ledger.exists && ledger.data().costStatus) return ledger.data().costStatus;
    const daily = await tx.get(dailyRef), monthly = await tx.get(monthlyRef);
    const known = actualUsd !== null;
    const costStatus = known ? 'USAGE_RECONCILED' : 'UNRECONCILED';
    for (const [ref, snap] of [[dailyRef, daily], [monthlyRef, monthly]]) {
      const v = snap.exists ? snap.data() : {};
      tx.set(ref, {
        reservedUsd: Math.max(0, Number(v.reservedUsd || 0) - reserveUsd),
        spentUsd: Number(v.spentUsd || 0) + (known ? actualUsd : 0),
        unreconciledUsd: Number(v.unreconciledUsd || 0) + (known ? 0 : reserveUsd),
        updatedAt: timestamp()
      }, {merge: true});
    }
    tx.set(usageRef, {...firestoreSafe(usageDoc), costStatus, createdAt: timestamp()}, {merge: true});
    return costStatus;
  });
}
