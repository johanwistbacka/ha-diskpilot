import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
const rootUrl=new URL('../custom_components/dishwasher_optimizer/www/',import.meta.url);
const helpers=await readFile(new URL('plan-data.js',rootUrl),'utf8');
const view=await readFile(new URL('plan-view.js',rootUrl),'utf8');
const dataUrl='data:text/javascript;base64,'+Buffer.from(helpers).toString('base64');
const {renderPlanning}=await import('data:text/javascript;base64,'+Buffer.from(view.replace("new URL('./plan-data.js',import.meta.url)",`new URL(${JSON.stringify(dataUrl)})`)).toString('base64'));

// Minimal DOM surface: exercise the shipped renderer and request queue, with plotting disabled.
class Node {
  constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.style={};this.attrs={};this.isConnected=true;this.clientWidth=0;this.text='';this.listeners={};}
  set textContent(value){this.text=value;this.children=[];}
  get textContent(){return this.text+this.children.map(n=>n.textContent).join(' ');}
  append(...nodes){for(const n of nodes){n.remove();this.children.push(n);n.parentNode=this;}}
  remove(){if(this.parentNode){this.parentNode.children=this.parentNode.children.filter(n=>n!==this);this.parentNode=null;}}
  replaceChildren(...nodes){for(const n of this.children)n.parentNode=null;this.children=[];this.text='';this.append(...nodes);}
  setAttribute(key,value){this.attrs[key]=value;}
  addEventListener(event,handler){this.listeners[event]=handler;}
  click(){if(!this.disabled)this.listeners.click?.();}
  setCustomValidity(message){this.validityMessage=message;}
  getRootNode(){return{activeElement:null};}
}
const el=(tag,text='')=>{const n=new Node(tag);n.textContent=text;return n;};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve};};

test('contract invalidation clears all prices and rejects an old inflight response',async()=>{
  const old=deferred(),fresh=deferred();let calls=0;
  const profile={id:'p',name:'Program',sample_count:1,energy_kwh:1,duration_seconds:60,energy_wh:[1000]};
  const response=(cost,basis)=>({entry_id:'e',now:1000,selected_start:1000,currency:'SEK',prices:[[1000,2000,cost]],price_status:'ok',price_basis:basis,profiles:[{...profile,cost,selected_cost:cost,optimal_start:1200}]});
  const card={_config:{},_hass:{user:{is_admin:true},config:{time_zone:'UTC'},states:{sensor:{state:'3',attributes:{diskpilot_entry_id:'e',program:'p',optimal_start:'2026-01-01T01:00:00Z'}}}},service:()=>++calls===1?Promise.resolve(response(3,'Old contract')):calls===2?old.promise:fresh.promise};
  const root=el('article');const draw=status=>renderPlanning.call(card,root,'e',[profile],status,el,String,()=>{});
  draw({plan_revision:1,price_status:'ok'});await tick();
  const row=card._planState.rows.get('p');assert.equal(row.bestPrice.textContent,'3 kr');
  draw({plan_revision:2,price_status:'ok'}); // A previous contract's response is still pending.
  draw({plan_revision:3,price_status:'updating'});
  assert.equal(card._planState.data,null);
  assert.equal(row.value.textContent,'—');assert.equal(row.bestTime.textContent,'—');assert.equal(row.bestPrice.textContent,'');
  assert.doesNotMatch(row.body.textContent,/Old contract/);
  assert.equal(card._planState.nodes.chart.children.length,0);
  assert.match(card._planState.nodes.message.textContent,/uppdateras/);
  old.resolve(response(99,'Obsolete response'));await tick();
  assert.equal(card._planState.data,null);assert.equal(row.bestPrice.textContent,'');
  fresh.resolve(response(5,'New contract'));await tick();
  draw({plan_revision:3,price_status:'ok'});
  assert.equal(row.bestPrice.textContent,'5 kr');assert.equal(row.value.textContent,'5 kr');
  assert.match(row.body.textContent,/New contract/);assert.doesNotMatch(row.body.textContent,/Obsolete|Old contract/);
  card._planningDisconnect();
});


test('start shortcuts accumulate while pending, clamp to now and use each program optimum',async()=>{
  const realNow=Date.now;let clock=Date.parse('2026-11-17T12:00:00Z');Date.now=()=>clock;
  try{
    const pending=deferred(),calls=[];
    let nextResponse;
    const profile={id:'p',name:'Eco',sample_count:2,duration_seconds:60,energy_wh:[10]};
    const response=input=>({entry_id:'e',now:clock/1000,selected_start:input.started_at?Date.parse(input.started_at)/1000:clock/1000,currency:'SEK',prices:[],price_status:'ok',profiles:[{...profile,cost:1,selected_cost:2,optimal_start:clock/1000+7200}]});
    const card={_config:{},_hass:{user:{is_admin:true},config:{time_zone:'Europe/Stockholm'},states:{}},service:(_entry,_service,input)=>{
      calls.push(input);
      const held = calls.length === 2 ? pending : nextResponse;
      nextResponse = null;
      return held ? held.promise : Promise.resolve(response(input));
    }};
    const root=el('article'),status={plan_revision:1,price_status:'ok'};
    const draw=()=>renderPlanning.call(card,root,'e',[profile],status,el,String,()=>{});
    draw();await tick();
    const f=card._planState,n=f.nodes;
    assert.equal(n.earlier.disabled,true);
    n.later.click();n.later.click();n.later.click();
    assert.equal(f.fixed,'2026-11-17T15:00:00.000Z');
    assert.equal(n.input.value,'2026-11-17T16:00');
    assert.equal(f.rows.get('p').value.textContent,'—');
    pending.resolve(response(calls[1]));await tick();
    assert.equal(calls.at(-1).started_at,'2026-11-17T15:00:00.000Z');
    assert.equal(f.data.selected_start,Date.parse(f.fixed)/1000);
    n.earlier.click();await tick();assert.equal(f.fixed,'2026-11-17T14:00:00.000Z');
    // Only half an hour remains: one decrement returns to following now.
    clock=Date.parse('2026-11-17T13:30:00Z');
    const clamped = nextResponse = deferred();
    n.earlier.click();
    assert.equal(f.followNow,true);assert.equal(n.earlier.disabled,true);assert.deepEqual(calls.at(-1),{});
    assert.equal(n.input.value,'2026-11-17T14:30');
    assert.equal(f.rows.get('p').value.textContent,'—');
    clamped.resolve(response({}));await tick();
    const best=f.rows.get('p').body.children.find(n=>n.tag==='button');
    const cheapest = nextResponse = deferred();
    best.click();
    assert.equal(f.rows.get('p').body.children.find(n=>n.tag==='button'),best);
    cheapest.resolve(response(calls.at(-1)));await tick();
    assert.equal(f.rows.get('p').body.children.find(n=>n.tag==='button'),best);
    assert.equal(f.fixed,'2026-11-17T15:30:00.000Z');
    // Existing selections survive a normal HA refresh.
    draw();await tick();assert.equal(f.fixed,'2026-11-17T15:30:00.000Z');
    const reset = nextResponse = deferred();
    n.now.click();
    assert.equal(n.input.value,'2026-11-17T14:30');
    assert.equal(f.fixed,null);assert.equal(f.followNow,true);
    reset.resolve(response({}));await tick();
    card._hass.user.is_admin=false;draw();assert.equal(n.later.disabled,true);assert.equal(n.earlier.disabled,true);assert.equal(n.now.disabled,true);
    card._planningDisconnect();
  }finally{Date.now=realNow;}
});

test('an expired cheapest start refreshes the proposal without changing a fixed selection',async()=>{
  const realNow=Date.now;
  const start=Date.parse('2026-11-17T12:00:00Z');
  let clock=start;
  Date.now=()=>clock;
  try{
    const calls=[], refresh=deferred();
    const profile={id:'p',name:'Eco',sample_count:2,duration_seconds:60,energy_wh:[10]};
    const response=(input,optimalStart)=>({entry_id:'e',now:clock/1000,selected_start:input.started_at?Date.parse(input.started_at)/1000:clock/1000,currency:'SEK',prices:[],price_status:'ok',profiles:[{...profile,cost:1,selected_cost:2,optimal_start:optimalStart/1000}]});
    const card={_config:{},_hass:{user:{is_admin:true},config:{time_zone:'UTC'},states:{}},service:(_entry,_service,input)=>{
      calls.push(input);
      return calls.length===3?refresh.promise:Promise.resolve(response(input,start+(calls.length<3?1800:10800)*1000));
    }};
    const root=el('article');
    const draw=revision=>renderPlanning.call(card,root,'e',[profile],{plan_revision:revision,price_status:'ok'},el,String,()=>{});
    draw(1);
    await tick();
    const f=card._planState;
    f.nodes.later.click();
    await tick();
    const originalSelection=f.fixed;
    const best=f.rows.get('p').bestButton;
    clock=start+1800*1000;
    best.click();
    assert.deepEqual(calls.at(-1),{started_at:originalSelection,refresh_program:'p'});
    assert.equal(f.nodes.input.value,'2026-11-17T13:00');
    assert.match(f.nodes.message.textContent,/har passerat/);
    best.click();
    assert.equal(calls.length,3);
    draw(2); // The latest HA revision should carry the specific refresh through.
    refresh.resolve(response(calls.at(-1),start+10800*1000));
    await tick();
    assert.equal(calls.length,4);
    assert.deepEqual(calls.at(-1),{started_at:originalSelection,refresh_program:'p'});
    assert.equal(f.fixed,originalSelection);
    assert.equal(f.rows.get('p').value.textContent,'2 kr');
    draw(3);
    await tick();
    assert.deepEqual(calls.at(-1),{started_at:originalSelection});
    best.click();
    await tick();
    assert.deepEqual(calls.at(-1),{started_at:'2026-11-17T15:00:00.000Z'});
    assert.equal(f.nodes.message.textContent,'');
    card._planningDisconnect();
  }finally{Date.now=realNow;}
});
