# study-editor-vendor.mjs 포함 라이브러리

`tools/study-editor`(package.json 버전 고정)에서 esbuild 로 묶은 파일이다. 직접 고치지 말고 `npm ci && npm run build` 로 다시 만든다.
모두 MIT 라이선스.

| 패키지 | 버전 |
|---|---|
| @tiptap/core · starter-kit · pm · extension-(table, image, text-style, highlight, list, link 등) · extensions | 3.31.3 |
| prosemirror-model | 1.25.11 |
| prosemirror-view | 1.42.3 |
| prosemirror-state | 1.4.4 |
| prosemirror-transform | 1.12.1 |
| prosemirror-tables | 1.8.5 |
| prosemirror-commands · history · keymap · inputrules · schema-list · dropcursor · gapcursor · changeset | 1.7.2 · 1.5.0 · 1.2.3 · 1.5.1 · 1.5.1 · 1.8.3 · 1.4.1 · 2.4.2 |
| marked | 18.0.13 |
| linkifyjs | 4.3.3 |
| orderedmap · rope-sequence · w3c-keyname | 2.1.1 · 1.3.4 · 2.2.8 |

MIT License 전문: https://opensource.org/license/mit — 각 패키지 저작권자: TipTap GmbH(überdosis), Marijn Haverbeke(ProseMirror), Christopher Jeffrey 외(marked), Hypercontext(linkifyjs).
