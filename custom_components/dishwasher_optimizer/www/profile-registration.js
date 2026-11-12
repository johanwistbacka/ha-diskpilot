/* Registration is local to HA. Drafts are kept by the backend until explicit review. */
const iso = seconds => new Date(seconds * 1000).toISOString();
function localDate(seconds, zone) {
  const parts = new Intl.DateTimeFormat("sv-SE", {timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"}).formatToParts(new Date(seconds*1000));
  const p=Object.fromEntries(parts.map(v=>[v.type,v.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}`;
}
export function zonedTimestamp(value, zone) {
  // datetime-local has no offset. Resolve against HA's zone, never the browser's.
  const normalized=value.length===16?value+":00":value;
  if(!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(normalized))throw Error("Ange datum och klockslag.");
  const desired=Date.parse(normalized+"Z")/1000;
  if(!Number.isFinite(desired))throw Error("Ange datum och klockslag.");
  // Examine adjacent-day offsets: DST shifts need not be a whole hour.
  const offsets=new Set([-86400,0,86400].map(delta=>Date.parse(localDate(desired+delta,zone)+"Z")/1000-(desired+delta)));
  const candidates=[...offsets].map(offset=>desired-offset).filter(t=>localDate(t,zone)===normalized);
  if(!candidates.length)throw Error("Klockslaget finns inte i Home Assistants tidszon.");
  if(candidates.length>1)throw Error("Klockslaget är tvetydigt vid vintertidsbytet. Välj en tid före eller efter den upprepade timmen.");
  return iso(candidates[0]);
}

function plot(container, draft, selection, el, number) {
  container.replaceChildren();
  if(!draft?.energy_wh?.length)return;
  const ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg");
  const width=Math.max(230,container.clientWidth||500),height=170,left=40,right=12,top=16,bottom=30;
  svg.setAttribute("viewBox",`0 0 ${width} ${height}`);svg.setAttribute("role","img");svg.setAttribute("aria-label","Minutmedeleffekt i W. Start och slut markeras i kurvan.");
  const watts=draft.energy_wh.map((wh,i)=>wh*3600/Math.min(60,draft.duration_seconds-i*60)),peak=Math.max(1,...watts)*1.1;
  const x=t=>left+(t-draft.selected_start)/draft.duration_seconds*(width-left-right),y=w=>height-bottom-w/peak*(height-top-bottom);
  const add=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;svg.append(n);};
  if(selection)add("rect",{x:x(selection.start),y:top,width:Math.max(0,x(selection.end)-x(selection.start)),height:height-top-bottom,fill:"currentColor",opacity:".1"});
  for(const value of [0,peak/2,peak]){add("line",{x1:left,x2:width-right,y1:y(value),y2:y(value),stroke:"var(--divider-color)"});add("text",{x:left-6,y:y(value)+4,"text-anchor":"end",fill:"var(--secondary-text-color)","font-size":11},number(value,0));}
  let d="";for(let i=0;i<watts.length;i++){const a=draft.selected_start+i*60,b=Math.min(draft.selected_end,a+60);d+=(i?"L":"M")+x(a)+","+y(watts[i])+"L"+x(b)+","+y(watts[i]);}
  add("path",{d,fill:"none",stroke:"currentColor","stroke-width":2});
  if(selection)for(const t of [selection.start,selection.end])add("line",{x1:x(t),x2:x(t),y1:top,y2:height-bottom,stroke:"currentColor"});
  for(const fraction of [0,.5,1])add("text",{x:left+fraction*(width-left-right),y:height-9,"text-anchor":fraction===0?"start":fraction===1?"end":"middle",fill:"var(--secondary-text-color)","font-size":11},number(draft.duration_seconds*fraction/60,1)+(fraction===1?" min":""));
  add("text",{x:4,y:11,fill:"var(--secondary-text-color)","font-size":11},"W · minutmedel");
  container.append(svg);
  if(draft.energy_kwh===null)container.append(el("p","Kurvan innehåller ofullständiga eller ogiltiga mätvärden. Noll i en sådan del är ingen uppmätt nollförbrukning.","note"));
}

export function renderRegistration(card, entryId, profiles, status, el, number) {
  if(this._recordEntry!==entryId){
    this._recordEntry=entryId;
    this._record={open:false,mode:"now",target:"new",name:"",endMode:"manual",endAt:"",from:"",to:"",draft:null,selected:null,preview:null,confirmed:false,busy:false,message:"",request:0,lastLoad:0};
    this._recordNode=null;
  }
  const f=this._record,zone=this._hass.config?.time_zone||"Europe/Stockholm";
  const profilesChanged=f.profiles&&JSON.stringify(f.profiles)!==JSON.stringify(profiles);
  f.profiles=profiles;f.status=status;
  const valid=()=>this._record===f&&this._recordEntry===entryId;
  const node=this._recordNode||el("details",undefined,"registration");this._recordNode=node;
  const call=(name,data={})=>this.service(entryId,name,data);
  const textTime=t=>new Date(t*1000).toLocaleString("sv-SE",{timeZone:zone,month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit"});
  const selectedData=()=>({draft_id:f.draft.draft_id,started_at:iso(f.selected.start),ended_at:iso(f.selected.end)});
  const checkedDraft=data=>{
    if(data.stage==="none"){f.draft=null;f.selected=null;f.preview=null;return;}
    const fresh=f.draft?.draft_id!==data.draft_id||f.draft?.stage!==data.stage;
    f.draft=data;
    if(fresh){f.selected={start:data.suggested_start??data.started_at,end:data.suggested_end??data.observed_end};f.preview=null;f.confirmed=false;}
  };
  async function execute(operation){
    if(f.busy)return;f.request++;f.busy=true;f.message="Arbetar…";draw();
    try{await operation();}catch(error){if(valid())f.message=error.message||String(error);}
    finally{if(valid()){f.busy=false;draw();}}
  }
  async function load(){
    const id=++f.request;f.lastLoad=Date.now();
    const data=await call("get_registration");
    if(!valid()||id!==f.request)return;
    checkedDraft(data);
    if(f.draft?.stage==="review"&&f.draft.energy_wh?.length)await preview();
  }
  async function preview(){
    const id=++f.request;f.confirmed=false;f.preview=null;
    const selection=selectedData();
    const data=await call("get_registration",selection);
    if(valid()&&id===f.request&&f.draft?.draft_id===selection.draft_id)f.preview=data;
  }
  function action(label,fn,secondary=false){const b=el("button",label);b.type="button";b.disabled=f.busy;if(secondary)b.className="secondary";b.addEventListener("click",()=>execute(fn));return b;}
  function field(label,type,value,change){const wrap=el("label",undefined,"registration-field"),input=el("input");input.type=type;input.value=value;input.setAttribute("aria-label",label);if(type==="text")input.maxLength=80;input.disabled=f.busy;input.addEventListener("input",()=>change(input.value));wrap.append(el("span",label),input);return wrap;}
  function destination(){
    const row=el("div",undefined,"registration-grid"),wrap=el("label",undefined,"registration-field"),select=el("select");select.setAttribute("aria-label","Lägg körningen i");select.disabled=f.busy;
    for(const p of [{id:"new",name:"Ny profil"},...f.profiles]){const o=el("option",p.name);o.value=p.id;select.append(o);}
    if(!f.profiles.some(p=>p.id===f.target))f.target="new";select.value=f.target;
    select.addEventListener("change",()=>{f.target=select.value;f.confirmed=false;draw();});wrap.append(el("span","Lägg körningen i"),select);row.append(wrap);
    if(f.target==="new")row.append(field("Profilnamn","text",f.name,v=>{f.name=v;f.confirmed=false;const confirm=node.querySelector('.registration-confirm'),save=node.querySelector('.registration-save');if(confirm)confirm.checked=false;if(save)save.disabled=true;}));return row;
  }
  function drawLive(){
    if(!f.draft)return;
    const summary=node.querySelector(".registration-live-summary"),curve=node.querySelector(".registration-chart");
    if(summary)summary.textContent=`${number((f.draft.observed_end-f.draft.started_at)/60,1)} min · ${f.draft.energy_kwh==null?"Energi saknas":number(f.draft.energy_kwh,4)+" kWh"}`;
    if(curve)plot(curve,f.draft,null,el,number);
  }
  function updateReview(){
    if(f.draft?.stage!=="review")return;
    const summary=f.preview,interrupted=["interrupted","measurement_changed","sample_limit"].includes(f.draft.reason);
    const metrics=node.querySelector('.registration-metrics'),check=node.querySelector('.registration-confirm'),save=node.querySelector('.registration-save'),warning=node.querySelector('.registration-gap');
    if(metrics)metrics.textContent=`${number((f.selected.end-f.selected.start)/60,1)} min · ${summary?.energy_kwh!=null?number(summary.energy_kwh,4)+" kWh":"Energi ej bekräftad"}`;
    if(check){check.checked=f.confirmed;check.disabled=f.busy||!Number.isFinite(summary?.energy_kwh)||Boolean(summary?.missing_seconds)||interrupted;}
    if(save)save.disabled=f.busy||!f.confirmed||!Number.isFinite(summary?.energy_kwh)||Boolean(summary?.missing_seconds)||interrupted;
    if(warning){const invalid=summary?.issues?.includes('invalid_energy');warning.hidden=!summary?.missing_seconds&&!invalid;warning.textContent=invalid?'Ogiltig energimätning i markeringen. Kontrollera sensorns enhet och värden.':summary?.missing_seconds?`Mätdata saknas under ${number(summary.missing_seconds,1)} sekunder i markeringen. Körningen kan inte sparas som komplett underlag.`:"";}
    const message=node.querySelector('.message');if(message)message.textContent=f.message;
  }
  function draw(){
    const active=node.getRootNode().activeElement,label=node.contains(active)?active?.getAttribute('aria-label'):null;
    if(label&&!f.busy)queueMicrotask(()=>{if(!valid()||f.busy)return;const target=[...node.querySelectorAll('input,select')].find(e=>e.getAttribute('aria-label')===label);if(target&&!target.disabled)target.focus({preventScroll:true});});
    node.replaceChildren();node.open=f.open;node.append(el("summary","Registrera profil"));
    const content=el("div",undefined,"registration-body"),message=el("p",f.message,"message");message.setAttribute("role","status");message.setAttribute("aria-live","polite");content.append(message);node.append(content);
    const draft=f.draft;
    if(!draft){
      const tabs=el("div",undefined,"controls");
      for(const[mode,label]of [["now","Registrera nu"],["history","Använd historik"]]){const b=el("button",label);b.type="button";b.disabled=f.busy;b.className=f.mode===mode?"":"secondary";b.setAttribute("aria-pressed",String(f.mode===mode));b.onclick=()=>{f.mode=mode;draw();};tabs.append(b);}content.append(tabs,destination());
      content.append(el("p",`Effektsensor: ${f.status.power_entity||"Ingen vald"} · Tidszon: ${zone}`,"note"));
      if(f.mode==="now"){
        const wrap=el("label",undefined,"registration-field"),end=el("select");end.setAttribute("aria-label","Avslut");
        for(const[value,label]of [["manual","Jag avslutar själv"],["time","Vid ett klockslag"]]){const o=el("option",label);o.value=value;end.append(o);}end.value=f.endMode;end.disabled=f.busy;end.onchange=()=>{f.endMode=end.value;draw();};wrap.append(el("span","Avslut"),end);content.append(wrap);
        if(f.endMode==="time")content.append(field("Avsluta registreringen","datetime-local",f.endAt,v=>{f.endAt=v;}));
        content.append(el("p","Start sker nu. Väntetid vid fördröjd start kan tas bort i granskningen. Registreringen avslutas senast efter åtta timmar och styr inte apparaten.","note"));
      }else{
        const row=el("div",undefined,"registration-grid");row.append(field("Från","datetime-local",f.from,v=>{f.from=v;}),field("Till","datetime-local",f.to,v=>{f.to=v;}));content.append(row,el("p","Välj ett avslutat intervall på högst åtta timmar. Effektsensorns detaljerade historik måste finnas i Recorder.","note"));
      }
      const start=action(f.mode==="now"?"Starta registrering":"Hämta och granska",async()=>{
        if(f.target==="new"&&!f.name.trim())throw Error("Ange ett profilnamn.");
        const data=f.mode==="now"?await call("start_registration",f.endMode==="time"?{end_at:zonedTimestamp(f.endAt,zone)}:{}):await call("history_registration",{started_at:zonedTimestamp(f.from,zone),ended_at:zonedTimestamp(f.to,zone)});
        if(!valid())return;checkedDraft(data);f.message="";
        if(f.draft.stage==="review"&&f.draft.energy_wh?.length)await preview();
      });start.disabled=f.busy||!f.status.measurement_enabled;content.append(start);
      if(!f.status.measurement_enabled)content.append(el("p","Välj en effektsensor i integrationens inställningar. Filimport och planering fungerar utan effektmätare.","note"));
      return;
    }
    content.append(el("h3",draft.stage==="recording"?"Registrering pågår":"Granska körningen"),el("p",`${draft.entity_id} · ${textTime(draft.started_at)}`,"note"));
    if(draft.stage==="recording"){
      content.append(el("p","","registration-live-summary"));const curve=el("div",undefined,"registration-chart");content.append(curve,el("p",`Senaste avslut: ${textTime(draft.end_at)}. Körningen läggs inte till en profil innan du granskat den.` ,"note"));
      const buttons=el("div",undefined,"controls");buttons.append(action("Avsluta och granska",async()=>{checkedDraft(await call("stop_registration",{draft_id:draft.draft_id}));f.message="";if(f.draft.energy_wh?.length)await preview();}),action("Avbryt registrering",async()=>{await call("discard_registration",{draft_id:draft.draft_id});checkedDraft({stage:"none"});f.message="Registreringen avbröts. Ingen körning har lagts till.";},true));content.append(buttons);drawLive();return;
    }
    if(!draft.energy_wh?.length){content.append(el("p","Registreringen innehåller ingen mätt tid.","note"));}
    else{
      const summary=f.preview;
      const interrupted=["interrupted","measurement_changed","sample_limit"].includes(draft.reason);
      if(interrupted)content.append(el("p","Registreringen avbröts och kan inte användas som komplett profilunderlag. Hämta en hel körning från historiken eller registrera på nytt.","error"));
      const curve=el("div",undefined,"registration-chart");content.append(curve);plot(curve,draft,f.selected,el,number);
      content.append(el("p",`${number((f.selected.end-f.selected.start)/60,1)} min · ${summary?.energy_kwh!=null?number(summary.energy_kwh,4)+" kWh":"Energi ej bekräftad"}`,"registration-metrics"));
      const trims=el("div",undefined,"registration-grid");
      for(const[key,label]of [["start","Start"],["end","Slut"]]){
        const wrap=el("label",undefined,"registration-field"),range=el("input"),caption=el("span",`${label}: ${textTime(f.selected[key])}`);range.type="range";range.min=0;range.max=draft.observed_end-draft.started_at;range.step="1";range.value=f.selected[key]-draft.started_at;range.disabled=f.busy;range.setAttribute("aria-label",`Justera ${label.toLowerCase()}`);range.setAttribute("aria-valuetext",textTime(f.selected[key]));
        range.oninput=()=>{f.request++;f.selected[key]=draft.started_at+Number(range.value);if(f.selected.end<=f.selected.start){f.selected[key]=key==="start"?f.selected.end-.001:f.selected.start+.001;range.value=f.selected[key]-draft.started_at;}f.confirmed=false;f.preview=null;caption.textContent=`${label}: ${textTime(f.selected[key])}`;range.setAttribute("aria-valuetext",textTime(f.selected[key]));updateReview();plot(curve,draft,f.selected,el,number);};
        range.onchange=async()=>{const request=f.request+1;f.message="Beräknar energi…";updateReview();try{await preview();if(valid()&&request===f.request)f.message="";}catch(error){if(valid()&&request===f.request)f.message=error.message||String(error);}finally{if(valid()&&request===f.request)updateReview();}};wrap.append(caption,range);trims.append(wrap);
      }content.append(trims,el("p","Gränserna är förslag. Kontrollera hela körningen och ta bort väntetid före start och efter avslut. Vila är inte samma sak som verifierad färdigtid.","note"));
      const warning=el('p','', 'error registration-gap');warning.hidden=true;content.append(warning);
      content.append(destination());
      const confirm=el("label",undefined,"review"),check=el("input");check.type="checkbox";check.className="registration-confirm";check.checked=f.confirmed;check.disabled=f.busy||!Number.isFinite(summary?.energy_kwh)||Boolean(summary?.missing_seconds)||interrupted;check.setAttribute("aria-label","Jag har granskat hela körningen och valt rätt profil");confirm.append(check,document.createTextNode("Jag har granskat hela körningen och valt rätt profil."));content.append(confirm);
      const save=action("Spara körning",async()=>{
        const result=await call("save_registration",{...selectedData(),confirmed:f.confirmed,...(f.target==="new"?{name:f.name}:{profile_id:f.target})});
        if(!valid())return;f.target=result.profile_id;checkedDraft({stage:"none"});f.message=`Körningen är sparad: ${number(result.energy_kwh,4)} kWh. Profilens underlag har uppdaterats.`;
      });save.classList.add("registration-save");save.disabled=f.busy||!f.confirmed||!Number.isFinite(summary?.energy_kwh)||Boolean(summary?.missing_seconds)||interrupted;check.onchange=()=>{f.confirmed=check.checked;save.disabled=!check.checked||f.busy;};content.append(save);
    }
    content.append(action("Kasta utkast",async()=>{await call("discard_registration",{draft_id:draft.draft_id});checkedDraft({stage:"none"});f.message="Utkastet är borttaget. Sparade körningar är kvar.";},true));
    updateReview();
  }
  if(!node._registrationToggle){node._registrationToggle=true;node.addEventListener("toggle",()=>{
    if(!valid()||!node.isConnected)return;f.open=node.open;
    if(f.open&&!f.busy)execute(async()=>{await load();f.message="";});
  });}
  this._registrationUpdate=next=>{
    f.status=next;
    const remote=next.registration;
    if(!f.open||f.busy)return;
    if((remote?.draft_id||null)!==(f.draft?.draft_id||null)||remote?.stage!==f.draft?.stage){execute(async()=>{await load();f.message="";});}
    else if(remote?.stage==="recording"&&Date.now()-f.lastLoad>5000){
      f.lastLoad=Date.now();const id=++f.request;
      call("get_registration").then(data=>{if(valid()&&id===f.request&&!f.busy){if(data.stage!==f.draft?.stage){execute(async()=>{checkedDraft(data);if(f.draft?.stage==='review'&&f.draft.energy_wh?.length)await preview();f.message='';});}else{f.draft=data;drawLive();}}}).catch(()=>{});
    }
  };
  if(!node.childNodes.length||(profilesChanged&&!f.busy))draw();
  card.append(node);
  this._registrationUpdate(status);
}
