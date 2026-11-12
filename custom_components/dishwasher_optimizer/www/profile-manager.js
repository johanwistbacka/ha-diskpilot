/* Local file import. No third-party scripts or AI service calls. */
export function renderProfileControls(card, entryId, profiles, el, number) {
  if (this._formEntry !== entryId) {
    this._formEntry = entryId;
    this._form = {target:"new",name:"",newName:"",filename:"",content:"",preview:null,confirmed:false,busy:false,message:""};
  }
  const f = this._form;
  const details = el("details");
  details.open = Boolean(this._manageOpen || !profiles.length);
  details.addEventListener("toggle",()=>{if(details.isConnected)this._manageOpen=details.open;});
  details.append(el("summary","Profiler och filimport"));
  const links = el("p",undefined,"note");
  const guide = el("a","Instruktion och exempelprompt");
  guide.href="/dishwasher_optimizer/profile-import.html";guide.target="_blank";guide.rel="noopener";
  const settings=el("a","Inställningar");settings.href="/config/integrations/integration/dishwasher_optimizer";
  links.append(guide,document.createTextNode(" · "),settings);details.append(links);
  const message=el("p",f.message,"message");message.setAttribute("role","status");message.setAttribute("aria-live","polite");details.append(message);
  const execute=async operation=>{
    f.busy=true;f.message="Arbetar…";this.render();
    try{await operation();}catch(error){f.message=`Kunde inte spara: ${error.message||error}`;}
    finally{f.busy=false;this._manageOpen=true;this.render();}
  };
  details.append(el("h3","Lägg till profil"));
  const add=el("div",undefined,"controls");
  const name=el("input");name.type="text";name.maxLength=80;name.placeholder="Till exempel Eco eller Snabb";name.value=f.newName;name.setAttribute("aria-label","Namn på ny profil");
  name.addEventListener("input",()=>{f.newName=name.value;});
  const addButton=el("button","Skapa profil");addButton.disabled=f.busy;
  addButton.addEventListener("click",()=>execute(async()=>{
    const result=await this.service(entryId,"save_profile",{name:f.newName});
    f.target=result.profile_id;f.newName="";f.message="Profilen är skapad. Du kan nu importera dess körningar.";
  }));add.append(name,addButton);details.append(add);
  if(profiles.length){
    details.append(el("h3","Byt profilnamn"));
    const rename=el("div",undefined,"controls");
    const select=el("select");select.setAttribute("aria-label","Profil att byta namn på");
    for(const p of profiles){const o=el("option",p.name);o.value=p.id;select.append(o);}
    if(!profiles.some(p=>p.id===f.renameId)){f.renameId=profiles[0].id;f.renameName=profiles[0].name;}
    select.value=f.renameId;
    const text=el("input");text.type="text";text.maxLength=80;text.value=f.renameName;text.setAttribute("aria-label","Nytt profilnamn");
    select.addEventListener("change",()=>{f.renameId=select.value;f.renameName=profiles.find(p=>p.id===select.value).name;text.value=f.renameName;});
    text.addEventListener("input",()=>{f.renameName=text.value;});
    const save=el("button","Spara namn");save.disabled=f.busy;
    save.addEventListener("click",()=>execute(async()=>{await this.service(entryId,"save_profile",{profile_id:f.renameId,name:f.renameName});f.message="Profilnamnet är sparat. Underlaget är kvar.";}));
    rename.append(select,text,save);details.append(rename);
  }
  details.append(el("h3","Importera egna körningar"),el("p","Välj en CSV- eller JSON-fil enligt filformatet i instruktionen. Filen behandlas i din Home Assistant. Ingen AI-tjänst används.","note"));
  const picker=el("input");picker.type="file";picker.accept=".json,.csv,application/json,text/csv";picker.hidden=true;picker.setAttribute("aria-label","Profilfil");
  const choose=el("button","Välj profilfil");choose.disabled=f.busy;choose.addEventListener("click",()=>picker.click());
  picker.addEventListener("change",async()=>{
    const file=picker.files?.[0];if(!file)return;
    f.preview=null;f.confirmed=false;f.content="";f.filename=file.name;f.busy=true;this._manageOpen=true;this.render();
    try{
      if(file.size>524288)throw new Error("Filen får vara högst 512 KiB.");
      f.content=await file.text();
      f.preview=await this.service(entryId,"preview_profile_file",{filename:f.filename,content:f.content});
      if(!f.name&&f.preview.profile_name)f.name=f.preview.profile_name;
      f.message="Filen är kontrollerad. Granska underlaget innan du importerar.";
    }catch(error){f.message=`Filen kunde inte läsas: ${error.message||error}`;}
    finally{f.busy=false;this.render();}
  });details.append(picker,choose);
  if(f.filename)details.append(el("p",`Vald fil: ${f.filename}`,"note"));
  if(f.preview){
    const p=f.preview,preview=el("div",undefined,"preview");
    preview.append(el("strong",`${p.run_count} körning${p.run_count===1?"":"ar"}`));
    preview.append(el("p",`Energi: ${number(p.energy_min_kwh,4)}–${number(p.energy_max_kwh,4)} kWh · Längd: ${number(p.duration_min_minutes,1)}–${number(p.duration_max_minutes,1)} min`));
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");svg.setAttribute("viewBox","0 0 360 70");svg.setAttribute("role","img");svg.setAttribute("aria-label","Minutenergi för filens första körning");
    const curve=p.first_curve_energy_wh,peak=Math.max(...curve,0.001),line=document.createElementNS(svg.namespaceURI,"polyline");
    line.setAttribute("points",curve.map((value,i)=>`${i*360/Math.max(curve.length-1,1)},${65-value/peak*60}`).join(" "));line.setAttribute("fill","none");line.setAttribute("stroke","currentColor");line.setAttribute("stroke-width","2");svg.append(line);preview.append(svg,el("p",p.warning,"note"));details.append(preview);
    const target=el("select");target.setAttribute("aria-label","Importera till profil");const fresh=el("option","Ny profil");fresh.value="new";target.append(fresh);
    for(const profile of profiles){const o=el("option",profile.name);o.value=profile.id;target.append(o);}
    target.value=profiles.some(p=>p.id===f.target)?f.target:"new";
    target.addEventListener("change",()=>{f.target=target.value;this.render();});details.append(el("p","Importera till"),target);
    if(target.value==="new"){
      const input=el("input");input.type="text";input.maxLength=80;input.value=f.name;input.placeholder="Profilnamn";input.setAttribute("aria-label","Namn på importerad profil");input.addEventListener("input",()=>{f.name=input.value;});details.append(input);
    }
    const review=el("label",undefined,"review"),checked=el("input");checked.type="checkbox";checked.checked=f.confirmed;
    const submit=el("button","Importera körningarna");submit.disabled=!f.confirmed||f.busy;
    checked.addEventListener("change",()=>{f.confirmed=checked.checked;submit.disabled=!checked.checked||f.busy;});review.append(checked,document.createTextNode("Jag har granskat att körningarna hör till rätt profil."));details.append(review);
    submit.addEventListener("click",()=>execute(async()=>{
      const destination=f.target==="new"?{name:f.name}:{profile_id:f.target};
      const result=await this.service(entryId,"import_profile_file",{filename:f.filename,content:f.content,...destination});
      f.message=`${result.imported_runs} körning${result.imported_runs===1?"":"ar"} importerad${result.imported_runs===1?"":"e"}. Profilen har uppdaterats.`;
      f.preview=null;f.content="";f.filename="";f.confirmed=false;
    }));details.append(submit);
  }
  card.append(details);
}
