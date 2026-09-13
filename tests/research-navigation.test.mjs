import test from 'node:test';import assert from 'node:assert/strict';
import {legacyDestination,pushTool,popTool,viewFor} from '../js/research-navigation.mjs';
test('old URLs preserve selected IDs and separate private records from archive',()=>{
assert.equal(legacyDestination('/invest/chatgpt/','#/indicators/kospi'),'research-dashboard.html#indicator%3Akospi');
assert.equal(legacyDestination('/invest/chatgpt/','#/records/abc?section=notes'),'research-dashboard.html#private%3Aabc');
assert.equal(legacyDestination('/invest/research.html','#records'),'research-dashboard.html?section=archive');
assert.equal(legacyDestination('/invest/research-cpi.html','','?record=abc'),'research-dashboard.html#record%3Aabc');
assert.equal(legacyDestination('/invest/research.html','#cpi'),'research-dashboard.html?cpi=1#indicator%3Acpi_yoy');
assert.equal(legacyDestination('/invest/chatgpt/','#/news/n123'),'research-dashboard.html?section=news&newsId=n123');
assert.doesNotThrow(()=>legacyDestination('/invest/chatgpt/','#/indicators/%invalid'));
});
test('news defaults to list independently of indicator preferences',()=>{assert.equal(viewFor('news',{indicators:'card'}),'list');assert.equal(viewFor('news',{news:'table'}),'table');assert.equal(viewFor('news',{news:'invalid'}),'list');});
test('third-page history preserves tool identity and never duplicates current content',()=>{const a={identity:'chart|cpi',scroll:120},b={identity:'editor|cpi'};let h=pushTool([],a);h=pushTool(h,b);assert.equal(pushTool(h,b),h);assert.deepEqual(popTool(h),[a]);});
