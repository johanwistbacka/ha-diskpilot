/* Card-local planning. Every cost comes from the backend's existing energy engine. */
const dataUrl=new URL('./plan-data.js',import.meta.url);dataUrl.search=new URL(import.meta.url).search;
const {localInput,priceRange,powerSegments,chartDomain,LatestPlanRequests}=await import(dataUrl.href);
let instance=0;
const palette=['#039be5','#a66dd4','#008f83','#cf791d','#d96a9a','#8c8176'];
const ns='http://www.w3.org/2000/svg';
const svgNode=(tag,attrs={},text)=>{const n=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;};
const statuses={not_configured:'Välj en prissensor i integrationens inställningar.',unavailable:'Prissensorn är inte tillgänglig.',no_intervals:'Prissensorn saknar prisintervall.',invalid_format:'Kontrollera prissensorns format i inställningarna.'};
const css=`
.plan-view{--plan-low:var(--success-color,#36884d);--plan-mid:var(--warning-color,#c69900);--plan-high:var(--error-color,#d7473e);color:var(--primary-text-color);min-width:0;container-type:inline-size}
.plan-view [hidden]{display:none!important}
.plan-head{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.plan-title{flex:1;min-width:100px}.plan-title h2{font-size:18px;margin:0;font-weight:600}.plan-title small{font-size:11px;color:var(--secondary-text-color)}
.plan-start{display:flex;align-items:end;gap:6px;flex:1;min-width:215px}.plan-field{display:grid;gap:3px;flex:1;min-width:0;font-size:11px;color:var(--secondary-text-color)}
.plan-view input[type=datetime-local]{width:100%;min-width:0;font-size:14px;min-height:36px;padding:5px 6px}.plan-view button{min-height:36px;padding:5px 9px;font-size:12px}.plan-status{font-size:11px;color:var(--secondary-text-color);margin:6px 0 8px;line-height:1.4}
.plan-columns,.plan-row>summary{display:grid;grid-template-columns:minmax(70px,1fr) 85px minmax(130px,1.3fr) 9px;gap:8px;align-items:center}.plan-columns{font-size:11px;color:var(--secondary-text-color);padding-bottom:4px}.plan-columns span:not(:first-child){text-align:right}
.plan-row{margin:0;border-top:1px solid var(--divider-color)}.plan-row>summary{min-height:44px;box-sizing:border-box;padding:6px 0;line-height:1.35;list-style:none;font-size:13px}.plan-row>summary::-webkit-details-marker{display:none}.plan-row>summary::after{content:'⌄';color:var(--secondary-text-color);grid-column:4}.plan-row[open]>summary::after{content:'⌃'}
.plan-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}.plan-cost{text-align:right;white-space:nowrap;font-size:15px;font-weight:600;font-variant-numeric:tabular-nums}.plan-best{text-align:right;font-size:12px;font-variant-numeric:tabular-nums}.plan-best-price{margin-left:6px;color:var(--secondary-text-color);white-space:nowrap}.plan-body{padding:4px 0 10px;display:flex;flex-wrap:wrap;gap:5px 16px;font-size:12px;color:var(--secondary-text-color)}.plan-body p{flex-basis:100%;margin:0;font-size:12px}
.plan-graph{border-top:1px solid var(--divider-color);margin:4px 0 0}.plan-graph>summary{min-height:36px;line-height:1.4;display:flex;align-items:center;justify-content:space-between;font-size:12px;font-weight:600;list-style:none}.plan-graph>summary::after{content:'⌄';color:var(--secondary-text-color)}.plan-graph[open]>summary::after{content:'⌃'}.plan-graph>summary::-webkit-details-marker{display:none}
.plan-legend{display:flex;align-items:center;gap:4px 6px;flex-wrap:wrap;font-size:11px}.plan-legend>span,.plan-view .curve-toggle{display:inline-flex;align-items:center;gap:5px}.plan-view .curve-toggle{background:var(--secondary-background-color);color:var(--primary-text-color);border:0;min-height:30px;padding:3px 6px;font-size:11px;max-width:calc(50% - 6px);overflow-wrap:anywhere}.plan-view .curve-toggle[aria-pressed=false]{color:var(--secondary-text-color);text-decoration:line-through}.plan-view .curve-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.plan-swatch{display:inline-block;width:17px;height:0;border-top:3px solid;flex:none}.plan-price-swatch{height:3px;border:0;width:22px;background:linear-gradient(90deg,var(--plan-low),var(--plan-mid),var(--plan-high))}
.plan-chart{position:relative;min-width:0}.plan-chart svg{display:block;width:100%;height:auto;font-size:11px;color:var(--secondary-text-color);overflow:visible}.plan-chart svg text{fill:var(--secondary-text-color)}.plan-chart .grid{stroke:var(--divider-color);stroke-width:1}.plan-chart .start-line{stroke:var(--secondary-text-color);stroke-width:1;stroke-dasharray:3 4}.plan-motion{transition:transform 300ms ease}.plan-scale{display:flex;justify-content:space-between;gap:4px 12px;flex-wrap:wrap;font-size:11px;color:var(--secondary-text-color);font-variant-numeric:tabular-nums}.plan-color-bar{display:inline-block;vertical-align:middle;width:48px;height:4px;margin:0 5px;background:linear-gradient(90deg,var(--plan-low),var(--plan-mid),var(--plan-high))}
.plan-message{font-size:12px;line-height:1.4;margin:5px 0!important;color:var(--secondary-text-color)}.plan-message:empty{display:none}.plan-tooltip{position:absolute;z-index:2;max-width:min(240px,90%);white-space:pre-line;pointer-events:none;background:var(--card-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);border-radius:6px;padding:7px 9px;font-size:12px;box-shadow:0 2px 8px #0002}.plan-tooltip[hidden]{display:none}.plan-retry{margin-top:5px}.plan-chart svg:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
@container(max-width:480px){.plan-head{gap:6px}.plan-title{display:flex;gap:8px;align-items:baseline}.plan-start{flex-basis:100%;min-width:0}.plan-view input[type=datetime-local]{font-size:16px;min-height:40px}.plan-columns,.plan-row>summary{grid-template-columns:minmax(40px,1fr) 64px 88px 8px;gap:5px}.plan-best{font-size:11px}.plan-best-price{display:block;margin:1px 0 0}.plan-cost{font-size:14px}.plan-name{font-size:12px}.plan-chart svg{font-size:11px}}
@media(pointer:coarse){.plan-view button,.plan-view input[type=datetime-local]{min-height:44px}.plan-view .curve-toggle{min-height:44px}}@media(prefers-reduced-motion:reduce){.plan-motion{transition:none}}
`;

export function renderPlanning(card,entryId,profiles,status,el,number,zonedTimestamp) {
  if(this._planEntry!==entryId){
    this._planState?.queue?.dispose();this._planState?.observer?.disconnect();
    this._planEntry=entryId;this._planState={id:++instance,entryId,followNow:true,fixed:null,editing:false,waiting:false,error:'',data:null,rows:new Map(),hidden:new Set(),nodes:null,queue:null,geometry:null,revision:null};
  }
  const f=this._planState;f.hass=this._hass;f.status=status;f.profiles=profiles;
  if(!f.hass.user?.is_admin){f.queue?.dispose();f.queue=null;f.data=null;f.waiting=false;f.geometry=null;f.nodes?.chart.replaceChildren();f.nodes?.legend.replaceChildren();f.nodes?.scale.replaceChildren();}
  const valid=()=>this._planState===f&&!f.closed;
  const zone=()=>f.hass.config?.time_zone||'Europe/Stockholm';
  const unit=()=>f.currency==='SEK'?'kr':f.currency||'SEK';
  const format=(seconds,compact=false)=>Number.isFinite(seconds)?new Date(seconds*1000).toLocaleString(f.hass.locale?.language||'sv-SE',{timeZone:zone(),...(compact?{day:'2-digit',month:'2-digit'}:{day:'numeric',month:'short'}),hour:'2-digit',minute:'2-digit'}):'—';
  const amount=value=>Number.isFinite(value)?`${number(value)} ${unit()}`:'—';
  if(!f.nodes){
    const node=el('section',undefined,'plan-view'),style=el('style');style.textContent=css;node.append(style);
    const head=el('div',undefined,'plan-head'),title=el('div',undefined,'plan-title'),h2=el('h2'),mode=el('small');title.append(h2,mode);
    const controls=el('div',undefined,'plan-start'),label=el('label',undefined,'plan-field'),input=el('input');input.type='datetime-local';input.setAttribute('aria-label','Beräknad start');input.dataset.focusKey='planning-start';label.append(el('span','Beräknad start'),input);
    const now=el('button','Nu','secondary');now.type='button';now.setAttribute('aria-label','Använd aktuell tid som start');controls.append(label,now);head.append(title,controls);
    const info=el('div',undefined,'plan-status');const columns=el('div',undefined,'plan-columns');columns.append(el('span','Program'),el('span','Kostnad'),el('span','Billigast start'));
    const rows=el('div');const graph=el('details',undefined,'plan-graph');graph.open=true;const summary=el('summary','Pris och förbrukning');summary.dataset.focusKey='planning-graph';
    const legend=el('div',undefined,'plan-legend'),chart=el('div',undefined,'plan-chart'),scale=el('div',undefined,'plan-scale'),message=el('p','', 'plan-message'),retry=el('button','Försök igen','secondary plan-retry');retry.type='button';retry.hidden=true;message.setAttribute('role','status');message.setAttribute('aria-live','polite');graph.append(summary,legend,chart,scale);
    node.append(head,info,columns,rows,message,retry,graph);f.nodes={node,h2,mode,input,now,info,rows,graph,legend,chart,scale,message,retry};
    input.addEventListener('input',()=>{f.editing=true;f.error='';f.queue?.invalidate();f.waiting=false;draw();});
    input.addEventListener('change',()=>{try{const iso=zonedTimestamp(input.value,zone());input.setCustomValidity('');f.fixed=iso;f.followNow=false;f.editing=false;request(true);}catch(error){f.error=error.message||String(error);input.setCustomValidity(f.error);draw();}});
    now.addEventListener('click',()=>{f.fixed=null;f.followNow=true;f.editing=false;f.error='';input.setCustomValidity('');input.value=localInput(Date.now()/1000,zone());request(true);});
    retry.addEventListener('click',()=>request(true));
    graph.addEventListener('toggle',()=>{if(graph.open)drawPlot();});
    if(typeof ResizeObserver!=='undefined'){f.observer=new ResizeObserver(()=>drawPlot());f.observer.observe(chart);}
  }
  const n=f.nodes;card.append(n.node);
  function request(force=false){
    if(!valid()||!n.node.isConnected||!f.hass.user?.is_admin||f.editing)return;
    if(!f.queue)f.queue=new LatestPlanRequests(
      input=>thisCard.service(entryId,'get_plan',input),
      data=>{if(!valid())return;if(data?.entry_id!==entryId||!Array.isArray(data.profiles)||!Array.isArray(data.prices)||!Number.isFinite(data.now)||!Number.isFinite(data.selected_start))throw Error('Ogiltigt planeringssvar.');f.data=data;f.waiting=false;f.error='';draw();},
      error=>{if(!valid())return;f.waiting=false;f.error=error.message||String(error);draw();}
    );
    const key=JSON.stringify([f.status.plan_revision,f.fixed]);
    if(force)f.queue.invalidate();
    if(force||key!==f.queue.key){f.waiting=true;f.error='';f.queue.request(key,f.followNow?{}:{started_at:f.fixed});draw();}
  }
  const thisCard=this;
  function draw(){
    if(!valid())return;
    const admin=Boolean(f.hass.user?.is_admin);n.h2.textContent=thisCard._config.title||'Diskpilot';
    n.mode.textContent=f.status.registration?.stage==='recording'?'Registrering pågår':f.status.registration?.stage==='review'?'Utkast väntar på granskning':f.status.start_pending?'Kontrollerar diskstart':statusState()==='running'?'Körning pågår':statusState()==='source_unavailable'?'Effektsensorn saknas':'Planering';
    n.input.disabled=!admin;n.now.disabled=!admin;n.now.setAttribute('aria-pressed',String(f.followNow&&!f.editing));
    const changedZone=f.inputZone!==zone();f.inputZone=zone();
    if(changedZone&&f.editing){f.editing=false;f.error='';n.input.setCustomValidity('');}
    if(!f.editing&&(changedZone||n.node.getRootNode().activeElement!==n.input))n.input.value=localInput(f.followNow?f.data?.selected_start||Date.now()/1000:Date.parse(f.fixed)/1000,zone());
    const data=f.data;f.currency=data?.currency||nativeProfiles()[0]?.currency||'SEK';const prices=data?.prices||[];let lastPrice=null;for(const p of prices)lastPrice=Math.max(lastPrice??p[1],p[1]);
    n.info.textContent=!admin?'Billigaste kostnad och start · enligt programsensorerna':data?`${lastPrice?'Priser till '+format(lastPrice):statuses[data.price_status]||'Framtida priser saknas.'} · ${f.followNow?'Följer Nu':'Vald start'} · ${data.currency}/kWh`:'Planering med sparade profiler';
    const source=data?.profiles||nativeProfiles();const ids=new Set(source.map(p=>p.id));
    for(const[id,row]of f.rows)if(!ids.has(id)){row.section.remove();f.rows.delete(id);}
    source.forEach((p,index)=>{
      let row=f.rows.get(p.id);
      if(!row){const section=el('details',undefined,'plan-row'),summary=el('summary');summary.dataset.focusKey=`plan-${entryId}-${p.id}`;const name=el('span','', 'plan-name'),value=el('span','', 'plan-cost'),best=el('span','', 'plan-best'),bestTime=el('span'),bestPrice=el('span','', 'plan-best-price'),body=el('div',undefined,'plan-body');best.append(bestTime,bestPrice);summary.append(name,value,best);section.append(summary,body);row={section,summary,name,value,bestTime,bestPrice,body};f.rows.set(p.id,row);}
      if(row.section.parentNode!==n.rows)n.rows.append(row.section);
      row.name.textContent=p.name;row.name.title=p.name;const value=admin?(!f.waiting&&!f.editing&&!f.error?p.selected_cost:null):p.cost;
      row.value.textContent=amount(value);row.bestTime.textContent=format(p.optimal_start,true);row.bestPrice.textContent=Number.isFinite(p.cost)?amount(p.cost):'';
      row.summary.setAttribute('aria-label',`${p.name}, ${admin?'kostnad vid vald start':'billigaste kostnad'} ${amount(value)}, billigast ${format(p.optimal_start)}, ${amount(p.cost)}`);
      row.body.replaceChildren(el('span',p.name),el('span',`Energi: ${p.energy_kwh==null?'—':number(p.energy_kwh,3)+' kWh'}`),el('span',`Tid: ${p.duration_seconds==null?'—':number(p.duration_seconds/60,1)+' min'}`),el('span',`Underlag: ${p.sample_count||0} märkta körningar`),el('span',`Åter i vila vid vald start: ${format(f.waiting||f.editing||f.error?null:p.selected_end)}`),el('span',`Billigast före: ${format(data?.planning_deadline)}`));
      if(Number.isFinite(value)&&Number.isFinite(p.cost))row.body.append(el('span',`Skillnad mot billigaste start: ${amount(value-p.cost)}`));
      if(!p.sample_count)row.body.append(el('p','Behöver en komplett märkt körning.'));
      else if(p.sample_count===1)row.body.append(el('p','Första uppskattningen · baserad på en körning.'));
      row.body.append(el('p','Beräknat från sparade minutprofiler. Åter i vila är inte verifierad färdigtid.'));
      row.color=palette[index%palette.length];row.dash=['','5 3','2 3','8 3','5 2 1 2','1 2'][index%6];
    });
    n.retry.hidden=!f.error||!admin;n.message.textContent=!admin?'Graf och valbar start kräver administratör, eftersom profilkurvorna är skyddade.':f.error?`Kunde inte hämta planeringen: ${f.error}`:f.editing?'Välj och bekräfta starttiden.':f.waiting?'Beräknar vald start…':data&&source.some(p=>p.sample_count&&p.selected_cost===null)?'Priser saknas för en hel körning vid vald start.':data&&data.price_status!=='ok'?statuses[data.price_status]||'Framtida priser saknas.':'';
    n.chart.hidden=Boolean(f.waiting||f.editing||f.error);n.legend.hidden=n.chart.hidden;n.scale.hidden=n.chart.hidden;
    n.graph.setAttribute('aria-busy',String(f.waiting));
    drawPlot();
  }
  function statusState(){return thisCard._hass.states&&Object.values(thisCard._hass.states).find(s=>s.attributes.diskpilot_entry_id===entryId&&'recent_runs'in s.attributes)?.state;}
  function nativeProfiles(){const entities=Object.values(f.hass.states).filter(s=>s.attributes.diskpilot_entry_id===entryId&&s.attributes.program);return f.profiles.map(p=>{const a=entities.find(s=>s.attributes.program===p.id)?.attributes||{};return {id:p.id,name:p.name,...a,cost:Number.isFinite(Number(entities.find(s=>s.attributes.program===p.id)?.state))?Number(entities.find(s=>s.attributes.program===p.id)?.state):null,duration_seconds:a.duration_minutes*60,optimal_start:a.optimal_start?Date.parse(a.optimal_start)/1000:null,optimal_end:a.optimal_end?Date.parse(a.optimal_end)/1000:null};});}
  function drawPlot(){
    if(!valid()||!n.graph.open||!f.data||!f.hass.user?.is_admin)return;
    const view=f.data,width=Math.floor(n.chart.clientWidth);if(width<160)return;
    const domain=chartDomain(view),range=priceRange(view.prices),height=width<440?190:220;
    const key=JSON.stringify([width,domain,view.currency,zone(),view.prices,view.profiles.map(p=>[p.id,p.name,p.duration_seconds,p.energy_wh])]);
    if(key!==f.geometry){
      const focused=n.node.getRootNode().activeElement===f.svg;f.geometry=key;f.groups=new Map();
      const left=40,right=43,top=25,bottom=38,pw=width-left-right,ph=height-top-bottom,span=domain.end-domain.start;
      const low=Math.min(0,range?.min||0),high=Math.max(0,range?.max||0),pad=high===low?1:0;const py=v=>top+ph*(1-(v-low)/(high-low+pad));
      let peak=1;for(const p of view.profiles)for(const seg of powerSegments(p,0))peak=Math.max(peak,seg.watts);peak*=1.1;
      const wy=v=>top+ph*(1-v/peak),x=t=>left+pw*(t-domain.start)/span,rx=t=>left+pw*t/span;
      f.geometryInfo={left,right,top,pw,ph,span,domain};
      const svg=svgNode('svg',{viewBox:`0 0 ${width} ${height}`,height,role:'img',tabindex:'0','data-focus-key':`planning-chart-${entryId}`,'aria-label':'Elpris och beräknad effekt i W. Använd höger och vänster pil för att läsa värden; Esc stänger värderutan.'});
      svg.append(svgNode('desc',{},'Priskurvan färgas relativt lägsta och högsta tillgängliga pris. Programkurvorna är beräknade från sparade minutprofiler. Saknade prisintervall ritas som luckor.'));
      const defs=svgNode('defs'),clip=svgNode('clipPath',{id:`plan-clip-${f.id}`});clip.append(svgNode('rect',{x:left,y:top,width:pw,height:ph}));defs.append(clip);
      const gradientId=`plan-price-${f.id}`;if(range&&!range.flat){const gradient=svgNode('linearGradient',{id:gradientId,gradientUnits:'userSpaceOnUse',x1:0,x2:0,y1:py(range.max),y2:py(range.min)});for(const[offset,color]of[['0%','var(--plan-high)'],['50%','var(--plan-mid)'],['100%','var(--plan-low)']])gradient.append(svgNode('stop',{offset,'stop-color':color}));defs.append(gradient);}svg.append(defs);
      for(let i=0;i<3;i++){const yy=top+ph*i/2;svg.append(svgNode('line',{x1:left,x2:width-right,y1:yy,y2:yy,class:'grid'}),svgNode('text',{x:left-5,y:yy+4,'text-anchor':'end'},number(high+pad-(high-low+pad)*i/2,2)),svgNode('text',{x:width-right+5,y:yy+4},number(peak*(1-i/2),0)));}
      svg.append(svgNode('text',{x:left,y:12},`${view.currency}/kWh`),svgNode('text',{x:width-right,y:12,'text-anchor':'end'},'Effekt · W'));
      const ticks=width<440?4:6;for(let i=0;i<=ticks;i++){const t=domain.start+span*i/ticks;svg.append(svgNode('text',{x:x(t),y:height-7,'text-anchor':i===0?'start':i===ticks?'end':'middle'},new Date(t*1000).toLocaleTimeString('sv-SE',{timeZone:zone(),hour:'2-digit',minute:'2-digit'})),svgNode('text',{x:x(t),y:height-20,'text-anchor':i===0?'start':i===ticks?'end':'middle'},new Date(t*1000).toLocaleDateString('sv-SE',{timeZone:zone(),day:'numeric',month:'numeric'})));}
      const drawing=svgNode('g',{'clip-path':`url(#plan-clip-${f.id})`});svg.append(drawing);
      // Each interval is its own segment: a missing price never becomes zero or a bridge.
      let pricePath='',previous=null;
      for(const[a,b,value]of view.prices){if(previous&&previous[1]===a)pricePath+=`L ${x(a)} ${py(value)} L ${x(b)} ${py(value)} `;else pricePath+=`M ${x(a)} ${py(value)} L ${x(b)} ${py(value)} `;previous=[a,b,value];}
      drawing.append(svgNode('path',{d:pricePath,fill:'none',stroke:range?.flat?'var(--plan-mid)':`url(#${gradientId})`,'stroke-width':3.5,'stroke-linejoin':'round'}));
      for(const p of view.profiles){const row=f.rows.get(p.id),g=svgNode('g',{class:'plan-motion'});const segments=powerSegments(p,0);let d='';for(const seg of segments)d+=`${d?'L':'M'} ${rx(seg.start)} ${wy(seg.watts)} L ${rx(seg.end)} ${wy(seg.watts)} `;if(segments.length)d+=`L ${rx(p.duration_seconds)} ${wy(0)}`;g.append(svgNode('path',{d,fill:'none',stroke:row.color,'stroke-width':2,'stroke-dasharray':row.dash}));drawing.append(g);f.groups.set(p.id,g);}
      const marker=svgNode('g',{class:'plan-motion'});marker.append(svgNode('line',{x1:left,x2:left,y1:top,y2:top+ph,class:'start-line'}));drawing.append(marker);f.marker=marker;
      const tip=el('div','', 'plan-tooltip');tip.id=`plan-tooltip-${f.id}`;tip.hidden=true;tip.setAttribute('role','tooltip');svg.setAttribute('aria-describedby',tip.id);
      const show=(t,clientX=null,clientY=null)=>{f.inspect=Math.max(domain.start,Math.min(domain.end-.001,t));const price=view.prices.find(([a,b])=>a<=f.inspect&&b>f.inspect);const lines=[format(f.inspect),price?`Elpris: ${number(price[2],3)} ${view.currency}/kWh`:'Pris saknas'];for(const p of f.data.profiles)if(!f.hidden.has(p.id)){const seg=powerSegments(p,f.data.selected_start).find(p=>p.start<=f.inspect&&p.end>f.inspect);lines.push(`${p.name}: ${p.sample_count?`${seg?number(seg.watts,0):'0'} W`:'underlag saknas'}`);}tip.textContent=lines.join('\n');tip.hidden=false;tip.style.left=`${Math.min(Math.max(0,(clientX??width/2)-left),Math.max(0,width-245))}px`;tip.style.top=`${Math.max(12,Math.min(70,clientY??30))}px`;};
      svg.addEventListener('pointermove',event=>{const r=svg.getBoundingClientRect();show(domain.start+(event.clientX-r.left-left)/pw*span,event.clientX-r.left,event.clientY-r.top);});svg.addEventListener('pointerleave',()=>{tip.hidden=true;});
      svg.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const step=event.key==='ArrowLeft'?-900:900;show(event.key==='Home'?domain.start:event.key==='End'?domain.end-.001:(f.inspect??f.data.selected_start)+step);}else if(event.key==='Escape')tip.hidden=true;});svg.addEventListener('blur',()=>{tip.hidden=true;});
      f.svg=svg;n.chart.replaceChildren(svg,tip);if(focused)svg.focus({preventScroll:true});
      n.legend.replaceChildren();const priceLabel=el('span');priceLabel.append(el('span',undefined,'plan-swatch plan-price-swatch'),el('span','Elpris'));n.legend.append(priceLabel);
      for(const p of view.profiles){const row=f.rows.get(p.id),button=el('button',undefined,'curve-toggle');const caption=el('span',p.name,'curve-name');button.append(caption);button.title=p.name;button.type='button';button.setAttribute('aria-label',`Visa eller dölj ${p.name} i grafen`);const swatch=el('span',undefined,'plan-swatch');swatch.style.borderTopColor=row.color;swatch.style.borderTopStyle=row.dash?'dashed':'solid';button.prepend(swatch);button.addEventListener('click',()=>{if(f.hidden.has(p.id))f.hidden.delete(p.id);else f.hidden.add(p.id);drawPlot();});row.legend=button;n.legend.append(button);}
      n.scale.replaceChildren();if(range){const rangeLabel=el('span');rangeLabel.append(document.createTextNode(range.flat?`Oförändrat pris: ${number(range.min,3)} ${view.currency}/kWh`:`Lägst ${number(range.min,3)}`));if(!range.flat)rangeLabel.append(el('span',undefined,'plan-color-bar'),document.createTextNode(`Högst ${number(range.max,3)} ${view.currency}/kWh`));n.scale.append(rangeLabel,el('span','Relativt prognosen'));}
    }
    const translate=(view.selected_start-f.geometryInfo.domain.start)/f.geometryInfo.span*f.geometryInfo.pw;
    for(const p of view.profiles){const g=f.groups.get(p.id);if(g){g.style.transform=`translateX(${translate}px)`;g.style.display=f.hidden.has(p.id)?'none':'';}f.rows.get(p.id)?.legend?.setAttribute('aria-pressed',String(!f.hidden.has(p.id)));}f.marker.style.transform=`translateX(${translate}px)`;
  }
  this._planningDisconnect=()=>{f.queue?.dispose();f.queue=null;f.observer?.disconnect();};
  this._planningConnect=()=>{f.observer?.observe(n.chart);request(true);};
  draw();request();
}
