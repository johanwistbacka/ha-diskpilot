import assert from 'node:assert/strict';
import test from 'node:test';
import {renderPlanning,el,tick} from './renderer-harness.mjs';

function setup({admin=true,load}={}){
  const calls=[],profile={id:'p',name:'Program',cost:1.5,selected_cost:2,optimal_start:Date.parse('2026-11-15T02:00Z')/1000,sample_count:2,duration_seconds:90,energy_wh:[10,5],energy_kwh:.015};
  const response={entry_id:'e',now:Date.parse('2026-11-14T12:00Z')/1000,selected_start:Date.parse('2026-11-14T12:00Z')/1000,currency:'SEK',price_status:'ok',price_basis:'Nord Pool + Eltariff + påslag',planning_deadline:Date.parse('2026-11-15T12:00Z')/1000,prices:[],profiles:[profile]};
  const card={_config:{},_hass:{user:{is_admin:admin},config:{time_zone:'Europe/Stockholm'},locale:{language:'sv-SE'},states:{}},service:(entry,service,input)=>{calls.push({entry,service,input});return load?load(response,calls.length):Promise.resolve(response);}};
  const draw=(revision=1,status='ok')=>renderPlanning.call(card,el('article'),'e',[profile],{plan_revision:revision,price_status:status},el,String,value=>{if(!value)throw Error('Ange datum och klockslag.');return new Date(value).toISOString();});
  draw();return{card,calls,draw,response,profile,get state(){return card._planState;}};
}

test('local invalid time has an actionable message without a network retry',async()=>{
  const h=setup();await tick();const n=h.state.nodes;
  n.input.value='';n.input.fire('input');n.input.fire('change');
  assert.match(n.message.textContent,/Ange datum och klockslag.*tryck Nu/);
  assert.doesNotMatch(n.message.textContent,/Kunde inte hämta/);
  assert.equal(n.retry.hidden,true);assert.equal(h.calls.length,1);assert.equal(n.input.attrs['aria-invalid'],'true');
  assert.equal(h.state.rows.get('p').value.textContent,'—');
  n.now.fire('click');await tick();
  assert.equal(h.calls.length,2);assert.deepEqual(h.calls[1].input,{});
  assert.equal(h.state.followNow,true);assert.equal(h.state.inputError,'');assert.equal(n.input.validity,'');assert.equal(n.input.attrs['aria-invalid'],undefined);
  assert.equal(h.state.rows.get('p').value.textContent,'2,00 kr');h.card._planningDisconnect();
});

test('a backend failure still offers a working retry',async()=>{
  const h=setup({load:(data,count)=>count===1?Promise.reject(Error('Anslutningen bröts')):Promise.resolve(data)});await tick();const n=h.state.nodes;
  assert.equal(n.retry.hidden,false);assert.match(n.message.textContent,/Kunde inte hämta.*Anslutningen/);
  n.retry.fire('click');await tick();assert.equal(h.calls.length,2);assert.equal(n.retry.hidden,true);
  assert.equal(h.state.rows.get('p').value.textContent,'2,00 kr');h.card._planningDisconnect();
});

test('best-start shortcut uses latest program time and only requests a transient plan',async()=>{
  const h=setup();await tick();const row=h.state.rows.get('p');row.section.open=true;
  h.profile.optimal_start=Date.parse('2026-11-15T04:30Z')/1000;h.draw(2);await tick();
  let prevented=false,stopped=false;row.bestTime.fire('click',{preventDefault(){prevented=true;},stopPropagation(){stopped=true;}});await tick();
  assert.ok(prevented&&stopped);assert.equal(row.section.open,true);
  assert.deepEqual(h.calls.at(-1),{entry:'e',service:'get_plan',input:{started_at:'2026-11-15T04:30:00.000Z'}});
  assert.equal(h.calls.length,3);assert.equal(h.state.followNow,false);assert.equal(h.state.nodes.input.value,'2026-11-15T05:30');
  h.card._planningDisconnect();
});

test('chart zoom is local, survives plan refresh and does not issue a backend request',async()=>{
  const h=setup();await tick();const n=h.state.nodes;
  n.zoomRun.fire('click');assert.equal(h.state.zoom,'run');assert.equal(n.zoomRun.attrs['aria-pressed'],'true');assert.equal(h.calls.length,1);
  h.draw(2);await tick();assert.equal(h.state.zoom,'run');assert.equal(h.calls.length,2);
  n.zoomAll.fire('click');assert.equal(h.state.zoom,'all');assert.equal(n.zoomAll.attrs['aria-pressed'],'true');assert.equal(h.calls.length,2);h.card._planningDisconnect();
});

test('price basis appears once and row labels and money are unambiguous',async()=>{
  const h=setup();await tick();const n=h.state.nodes,row=h.state.rows.get('p');
  assert.equal(n.columns.children[1].textContent,'Vid vald start');assert.equal(n.columns.children[2].textContent,'Billigast');
  assert.equal(row.value.textContent,'2,00 kr');assert.equal(row.bestPrice.textContent,'1,50 kr');
  assert.equal(n.basisText.textContent,h.response.price_basis);assert.doesNotMatch(row.body.textContent,/Nord Pool|Eltariff/);
  n.basis.open=true;h.draw(2);await tick();assert.equal(n.basis.open,true);h.card._planningDisconnect();
});

test('no-quote and non-admin states cannot activate best-start controls',async()=>{
  const h=setup();await tick();h.draw(2,'updating');
  const row=h.state.rows.get('p');assert.equal(row.bestTime.disabled,true);assert.equal(row.bestPrice.textContent,'');
  h.card._planningDisconnect();
  const reader=setup({admin:false});await tick();assert.equal(reader.calls.length,0);assert.equal(reader.state.nodes.zoomRun.disabled,true);assert.equal(reader.state.rows.get('p').bestTime.disabled,true);reader.card._planningDisconnect();
});
