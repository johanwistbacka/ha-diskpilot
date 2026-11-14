/* Pure planning helpers; no network, DOM or persistent state. */
export function localInput(seconds, zone) {
  const parts = new Intl.DateTimeFormat("sv-SE", {timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(new Date(seconds*1000));
  const p=Object.fromEntries(parts.map(v=>[v.type,v.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
export function priceRange(prices) {
  let min=Infinity,max=-Infinity;
  for(const row of prices){if(Number.isFinite(row[2])){min=Math.min(min,row[2]);max=Math.max(max,row[2]);}}
  return min===Infinity?null:{min,max,flat:min===max};
}
export function priceFraction(value, range) {
  return !range||range.flat?0.5:Math.max(0,Math.min(1,(value-range.min)/(range.max-range.min)));
}
export function powerSegments(profile, start) {
  if(!Number.isFinite(profile.duration_seconds)||profile.duration_seconds<=0)return [];
  return (profile.energy_wh||[]).map((wh,i)=>{
    const a=i*60,b=Math.min((i+1)*60,profile.duration_seconds);
    return {start:start+a,end:start+b,watts:wh*3600/(b-a)};
  }).filter(p=>p.end>p.start&&Number.isFinite(p.watts)&&p.watts>=0);
}
export function chartDomain(view) {
  const start=Math.floor(Math.min(view.now,view.selected_start)/60)*60;
  let end=start+3600;
  for(const p of view.prices)end=Math.max(end,p[1]);
  for(const p of view.profiles)end=Math.max(end,p.selected_end||start);
  return {start,end};
}
export class LatestPlanRequests {
  constructor(load,receive,fail){this.load=load;this.receive=receive;this.fail=fail;this.epoch=0;this.pending=null;this.active=false;this.closed=false;this.key=null;}
  request(key,input){if(this.closed||key===this.key)return;this.key=key;this.pending={epoch:++this.epoch,input};this.pump();}
  invalidate(){this.epoch++;this.pending=null;this.key=null;}
  dispose(){this.closed=true;this.invalidate();}
  async pump(){
    if(this.active||this.closed)return;
    this.active=true;
    try{while(this.pending&&!this.closed){const item=this.pending;this.pending=null;
      try{const data=await this.load(item.input);if(!this.closed&&item.epoch===this.epoch)this.receive(data);}
      catch(error){if(!this.closed&&item.epoch===this.epoch)this.fail(error);}
    }}finally{this.active=false;}
  }
}
