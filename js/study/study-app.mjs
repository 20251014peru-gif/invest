// 기록보관실(records.html) ↔ 공부노트 모듈 연결점. 읽기 화면은 가볍게, 편집기·가져오기는 필요할 때만 불러온다.
import * as core from './study-core.mjs';
import {makeStudyStore} from './study-store.mjs';
import {renderStudyPage, bindStudyPage, relationListHTML} from './study-view.mjs';

export const STUDY_RELEASE = {version: 'study-1.0-20260917', summary: '공부노트 · 서식 편집기 · MarkFlow 가져오기'};

export function init(bridge) {
  const kstDate = t => new Date(t + 9 * 3600000).toISOString().slice(0, 10);
  const store = makeStudyStore(bridge.db, bridge.storage, {kstDate});
  const editorMod = () => import('./study-editor.mjs');
  const importMod = () => import('./study-import.mjs');
  const openEditor = async (id, opts = {}) => (await editorMod()).openStudyEditor({bridge, store, id, ...opts});
  return {
    core, store, release: STUDY_RELEASE,
    isStudy: core.isStudy,
    renderPage: r => renderStudyPage(r, {records: bridge.records(), KINDS: bridge.KINDS, VERIFY_STATES: bridge.VERIFY_STATES}),
    bindPage: (host, handlers) => bindStudyPage(host, handlers),
    relationListHTML: id => relationListHTML(bridge.records(), id, bridge.KINDS),
    openEditor,
    newNote: async () => (await editorMod()).openStudyEditor({bridge, store, offerDrafts: true}),
    isEditorOpen: async () => (await editorMod()).isOpen(),
    openImport: async () => (await importMod()).openImport({bridge, store, openEditor}),
    openRestore: async () => (await importMod()).openRestore({bridge, store, openEditor}),
    exportNote: async id => (await importMod()).exportNote({bridge, store, id}),
    changeRelations: (id, change) => store.changeRelations(id, change)
  };
}
