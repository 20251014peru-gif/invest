export {legacyDestination} from './research-routing.mjs';
export function pushTool(history,tool){if(history.at(-1)?.identity===tool.identity)return history;return [...history,tool];}
export function popTool(history){return history.slice(0,-1);}
export function viewFor(context,preferences){return ['card','list','table','board','topic','calendar','timeline','gallery'].includes(preferences[context])?preferences[context]:context==='news'?'list':'card';}
