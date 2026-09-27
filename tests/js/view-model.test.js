import test from 'node:test';
import assert from 'node:assert/strict';
import {formatPercent, selectGroups, sortGroups, relativeSeries} from '../../web/src/model.js';

test('missing values stay missing, zero is not positive',()=>{
  assert.equal(formatPercent(null),'—');
  assert.equal(formatPercent(NaN),'—');
  assert.equal(formatPercent(.1234),'+12.3%');
  assert.equal(formatPercent(0),'0.0%');
});
test('sort missing values last in either direction',()=>{
  const gs=[null,.2,-.1].map((rs,i)=>({id:i,periods:{'1M':{rs}}}));
  assert.deepEqual(sortGroups(gs,'1M','rs',-1).map(g=>g.id),[1,2,0]);
  assert.deepEqual(sortGroups(gs,'1M','rs',1).map(g=>g.id),[2,1,0]);
});
test('filters use actual level and valid membership',()=>{
  const groups=[{id:'a',level:'L1',valid_count:2},{id:'b',level:'L2',valid_count:5}];
  assert.equal(selectGroups({groups},{level:'L1',minNames:3}).length,0);
});
test('relative curve starts at 100 and uses ratio',()=>{
  const g={index:[{date:'1',value:100},{date:'2',value:110}]};
  const b=[{date:'1',value:100},{date:'2',value:105}];
  assert.deepEqual(relativeSeries(g,b,1).map(p=>p[1]),[100,100*1.1/1.05]);
});
test('relative curve refuses to compare across an index reset',()=>{
  const g={index:[{date:'1',value:140},{date:'2',value:null},{date:'3',value:100}]};
  const b=['1','2','3'].map(date=>({date,value:100}));
  assert.deepEqual(relativeSeries(g,b,2),[]);
});
