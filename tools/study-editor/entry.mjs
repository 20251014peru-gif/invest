// 공부노트 편집기용 외부 라이브러리 묶음 — 이 파일만 번들해 js/study/vendor/ 에 커밋한다.
// 버전은 package.json 에 고정. 앱 코드는 이 번들의 export 만 사용한다.
export {Editor, Extension, Node, Mark, mergeAttributes, getSchema} from '@tiptap/core';
export {default as StarterKit} from '@tiptap/starter-kit';
export {Table, TableRow, TableHeader, TableCell} from '@tiptap/extension-table';
export {default as Image} from '@tiptap/extension-image';
export {TextStyle, Color, BackgroundColor} from '@tiptap/extension-text-style';
export {default as Highlight} from '@tiptap/extension-highlight';
export {TaskList, TaskItem} from '@tiptap/extension-list';
export {Placeholder} from '@tiptap/extensions';
export {Plugin, PluginKey} from '@tiptap/pm/state';
export {Decoration, DecorationSet} from '@tiptap/pm/view';
export {DOMParser as PMDOMParser, Slice} from '@tiptap/pm/model';
export {marked} from 'marked';
