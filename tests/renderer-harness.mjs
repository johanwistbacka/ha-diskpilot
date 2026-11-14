import {readFile} from 'node:fs/promises';
const rootUrl=new URL('../custom_components/dishwasher_optimizer/www/',import.meta.url);
const helpers=await readFile(new URL('plan-data.js',rootUrl),'utf8');
const view=await readFile(new URL('plan-view.js',rootUrl),'utf8');
const dataUrl='data:text/javascript;base64,'+Buffer.from(helpers).toString('base64');
export const {renderPlanning}=await import('data:text/javascript;base64,'+Buffer.from(view.replace("new URL('./plan-data.js',import.meta.url)",`new URL(${JSON.stringify(dataUrl)})`)).toString('base64'));

// Minimal DOM surface: exercise the shipped renderer and request queue, with plotting disabled.
export class Node {
  constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.style={};this.attrs={};this.isConnected=true;this.clientWidth=0;this.text='';this.listeners={};}
  set textContent(value){this.text=value;this.children=[];}
  get textContent(){return this.text+this.children.map(n=>n.textContent).join('');}
  append(...nodes){for(const n of nodes){n.remove();this.children.push(n);n.parentNode=this;}}
  remove(){if(this.parentNode){this.parentNode.children=this.parentNode.children.filter(n=>n!==this);this.parentNode=null;}}
  replaceChildren(...nodes){for(const n of this.children)n.parentNode=null;this.children=[];this.text='';this.append(...nodes);}
  setAttribute(key,value){this.attrs[key]=value;}
  removeAttribute(key){delete this.attrs[key];}
  setCustomValidity(value){this.validity=value;}
  addEventListener(type,listener){(this.listeners[type]??=[]).push(listener);}
  fire(type,event={}){for(const listener of this.listeners[type]||[])listener(event);}
  getRootNode(){return{activeElement:null};}
}
export const el=(tag,text='')=>{const n=new Node(tag);n.textContent=text;return n;};
export const tick=()=>new Promise(resolve=>setImmediate(resolve));
export const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve};};

