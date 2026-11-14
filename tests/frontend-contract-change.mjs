import assert from 'node:assert/strict';
import test from 'node:test';
import {renderPlanning,el,tick,deferred} from './renderer-harness.mjs';

test('contract invalidation clears all prices and rejects an old inflight response',async()=>{
  const old=deferred(),fresh=deferred();let calls=0;
  const profile={id:'p',name:'Program',sample_count:1,energy_kwh:1,duration_seconds:60,energy_wh:[1000]};
  const response=(cost,basis)=>({entry_id:'e',now:1000,selected_start:1000,currency:'SEK',prices:[[1000,2000,cost]],price_status:'ok',price_basis:basis,profiles:[{...profile,cost,selected_cost:cost,optimal_start:1200}]});
  const card={_config:{},_hass:{user:{is_admin:true},config:{time_zone:'UTC'},states:{sensor:{state:'3',attributes:{diskpilot_entry_id:'e',program:'p',optimal_start:'2026-01-01T01:00:00Z'}}}},service:()=>++calls===1?Promise.resolve(response(3,'Old contract')):calls===2?old.promise:fresh.promise};
  const root=el('article');const draw=status=>renderPlanning.call(card,root,'e',[profile],status,el,String,()=>{});
  draw({plan_revision:1,price_status:'ok'});await tick();
  const row=card._planState.rows.get('p');assert.equal(row.bestPrice.textContent,'3,00 kr');
  draw({plan_revision:2,price_status:'ok'}); // A previous contract's response is still pending.
  draw({plan_revision:3,price_status:'updating'});
  assert.equal(card._planState.data,null);
  assert.equal(row.value.textContent,'—');assert.equal(row.bestTime.textContent,'—');assert.equal(row.bestPrice.textContent,'');
  assert.doesNotMatch(card._planState.nodes.basisText.textContent,/Old contract/);
  assert.equal(card._planState.nodes.chart.children.length,0);
  assert.match(card._planState.nodes.message.textContent,/uppdateras/);
  old.resolve(response(99,'Obsolete response'));await tick();
  assert.equal(card._planState.data,null);assert.equal(row.bestPrice.textContent,'');
  fresh.resolve(response(5,'New contract'));await tick();
  draw({plan_revision:3,price_status:'ok'});
  assert.equal(row.bestPrice.textContent,'5,00 kr');assert.equal(row.value.textContent,'5,00 kr');
  assert.match(card._planState.nodes.basisText.textContent,/New contract/);assert.doesNotMatch(card._planState.nodes.basisText.textContent,/Obsolete|Old contract/);
  card._planningDisconnect();
});
