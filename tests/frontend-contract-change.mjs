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
  constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.style={};this.attrs={};this.isConnected=true;this.clientWidth=0;this.text='';}
  set textContent(value){this.text=value;this.children=[];}
  get textContent(){return this.text+this.children.map(n=>n.textContent).join(' ');}
  append(...nodes){for(const n of nodes){n.remove();this.children.push(n);n.parentNode=this;}}
  remove(){if(this.parentNode){this.parentNode.children=this.parentNode.children.filter(n=>n!==this);this.parentNode=null;}}
  replaceChildren(...nodes){for(const n of this.children)n.parentNode=null;this.children=[];this.text='';this.append(...nodes);}
  setAttribute(key,value){this.attrs[key]=value;}
  addEventListener(){}
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
