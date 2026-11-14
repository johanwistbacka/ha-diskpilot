import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const source=await readFile(new URL('../custom_components/dishwasher_optimizer/www/plan-data.js',import.meta.url),'utf8');
const {localInput,priceRange,priceFraction,powerSegments,chartDomain,LatestPlanRequests}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

test('HA zone determines input, regardless of browser zone',()=>{
 assert.equal(localInput(Date.parse('2026-11-14T12:34Z')/1000,'Europe/Stockholm'),'2026-11-14T13:34');
 assert.equal(localInput(Date.parse('2026-07-14T12:34Z')/1000,'Europe/Stockholm'),'2026-07-14T14:34');
});
test('relative palette supports negative, flat and absent prices',()=>{
 const range=priceRange([[0,1,-2],[1,2,1],[2,3,4]]);
 assert.equal(priceFraction(-2,range),0);assert.equal(priceFraction(1,range),.5);assert.equal(priceFraction(4,range),1);
 assert.equal(priceFraction(5,priceRange([[0,1,5]])),.5);assert.equal(priceRange([]),null);
});
test('partial minute watts integrate back to original energy',()=>{
 const segments=powerSegments({duration_seconds:90,energy_wh:[10,5]},100);
 assert.deepEqual(segments,[{start:100,end:160,watts:600},{start:160,end:190,watts:600}]);
 assert.equal(segments.reduce((s,p)=>s+p.watts*(p.end-p.start)/3600,0),15);
 assert.deepEqual(powerSegments({duration_seconds:null,energy_wh:[]},100),[]);
});
test('chart covers all known prices and selected profile; no coverage implied',()=>{
 assert.deepEqual(chartDomain({now:100,selected_start:200,prices:[[0,9000,2]],profiles:[{selected_end:400}]}),{start:60,end:9000});
 assert.equal(chartDomain({now:100,selected_start:10000,prices:[[0,9000,2]],profiles:[{selected_end:11000}]}).end,11000);
});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
test('coalesces rapid selections, ignores stale success and preserves latest',async()=>{
 const a=deferred(),c=deferred(),calls=[],received=[],errors=[];
 const q=new LatestPlanRequests(v=>{calls.push(v);return v==='a'?a.promise:c.promise;},v=>received.push(v),e=>errors.push(e));
 q.request('a','a');q.request('b','b');q.request('c','c');a.resolve('old');await tick();
 assert.deepEqual(calls,['a','c']);assert.deepEqual(received,[]);c.resolve('new');await tick();
 assert.deepEqual(received,['new']);assert.deepEqual(errors,[]);q.request('c','duplicate');assert.deepEqual(calls,['a','c']);
});
test('stale failure is ignored and current failure permits explicit retry',async()=>{
 const a=deferred(),b=deferred(),received=[],errors=[];
 const q=new LatestPlanRequests(v=>v===1?a.promise:b.promise,v=>received.push(v),e=>errors.push(e.message));
 q.request('a',1);q.request('b',2);a.reject(Error('old'));await tick();b.reject(Error('current'));await tick();
 assert.deepEqual(received,[]);assert.deepEqual(errors,['current']);q.invalidate();q.request('b',2);await tick();assert.deepEqual(errors,['current','current']);
});
test('editing invalidation and disconnection discard inflight results',async()=>{
 for(const action of ['invalidate','dispose']){const a=deferred(),values=[];const q=new LatestPlanRequests(()=>a.promise,v=>values.push(v),e=>values.push(e));q.request('a',1);q[action]();a.resolve(1);await tick();assert.deepEqual(values,[]);}
});
