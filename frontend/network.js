'use strict';
const networkState={contacts:[],editing:null,provenance:'investor_entered',request:0};
const provenanceLabel=c=>c.provenance==='synthetic_demo'?'Synthetic demo':c.provenance==='profile_reviewed'?'Reviewed profile import':'Investor entered';
let expertiseExpanded=false,expertiseTags=[];
function renderExpertise(){const q=$('network-query').value.trim();let tags=expertiseExpanded?expertiseTags:expertiseTags.slice(0,5);if(expertiseTags.includes(q)&&!tags.includes(q))tags=[...tags.slice(0,4),q];$('expertise-map').innerHTML=tags.map(t=>`<button class="filter-pill" aria-pressed="${t===q}" data-expertise="${esc(t)}">${esc(t)}</button>`).join('');$('expertise-more').hidden=expertiseTags.length<=5;$('expertise-more').textContent=expertiseExpanded?'Show less':'Show more';$('expertise-more').setAttribute('aria-expanded',String(expertiseExpanded));}
$('expertise-more').onclick=()=>{expertiseExpanded=!expertiseExpanded;renderExpertise();};
const displayName=c=>c.provenance==='synthetic_demo'?c.name.replace(/\s*\(demo\)\s*$/i,''):c.name;
const tenure=r=>`${r.start_year||'?'}–${r.current?'present':r.end_year||'?'}`;
function personCard(c,match=null){
  const job=c.employment.find(j=>j.current)||c.employment[0];
  return `<article class="person-card"><div class="event-meta"><span class="badge">${esc(provenanceLabel(c))}</span><span>${esc(c.relationship_strength)}</span></div><button class="person-title" data-person="${esc(c.id)}">${esc(displayName(c))}</button><p>${esc(c.occupation||job?.role||'Occupation not recorded')}</p>${job?`<p class="contact-company">${esc(job.company)}</p>`:''}<div class="contact-tags">${c.expertise.slice(0,4).map(t=>`<span class="expertise-tag">${esc(t)}</span>`).join('')}</div>${match?`<div class="match-reasons"><strong>Why this person</strong><ul>${match.reasons.map(r=>`<li>${esc(r)}</li>`).join('')}</ul><p>${esc(match.connection_path)}</p>${match.reconnect?`<p class="reconnect">${esc(match.reconnect)}</p>`:''}<details><summary>Questions to ask</summary><ul>${match.suggested_questions.map(q=>`<li>${esc(q)}</li>`).join('')}</ul><p class="muted">${esc(match.basis)}</p></details></div>`:''}</article>`;
}
function renderMatches(items){return items?.length?items.slice(0,3).map(m=>personCard(m.contact,m)).join(''):'<p class="muted">No relevant contact recorded yet. Add someone’s experience in Network to make this useful.</p><a class="text-link" href="#network">Add contacts</a>';}
async function loadNetwork(){
  const request=++networkState.request,q=$('network-query').value.trim();
  $('network-results').innerHTML='<div class="loading">Finding people and relevant experience…</div>';
  try{const d=await api('/network?q='+encodeURIComponent(q));if(request!==networkState.request)return;networkState.contacts=d.contacts;
    expertiseTags=d.expertise;renderExpertise();
    $('network-results').innerHTML=q?(d.matches.length?`<p class="muted">${d.matches.length} relevant ${d.matches.length===1?'contact':'contacts'}</p><div class="people-grid">${d.matches.map(m=>personCard(m.contact,m)).join('')}</div>`:'<div class="empty-state"><h2>No relevant experience recorded.</h2><p>Try a company, expertise, major, or institution. Add more detail to your contacts to improve matching.</p></div>'):(d.contacts.length?`<p class="muted">${d.contacts.length} ${d.contacts.length===1?'contact':'contacts'}</p><div class="people-grid">${d.contacts.map(c=>personCard(c)).join('')}</div>`:'<div class="empty-state"><span class="empty-symbol">◎</span><h2>Who would you turn to?</h2><p>Add a person’s expertise, career and education.<br>FINN will connect that experience to your research.</p><button class="button secondary" data-new-person>Add your first person</button></div>');
  }catch(e){$('network-results').innerHTML=errorBox(e.message);}
}
function jobRow(job={}){return `<div class="repeat-row job-row"><div class="form-grid"><label>Company<input data-field="company" value="${esc(job.company||'')}" maxlength="160"></label><label>Role / title<input data-field="role" value="${esc(job.role||'')}" maxlength="160"></label><label>NSE ticker (if known)<input data-field="ticker" value="${esc(job.ticker||'')}" maxlength="25" placeholder="e.g. TCS"></label><label>Start year<input type="number" min="1940" max="2100" data-field="start_year" value="${job.start_year||''}"></label><label>End year<input type="number" min="1940" max="2100" data-field="end_year" value="${job.end_year||''}"></label><label class="check-label"><input type="checkbox" data-field="current" ${job.current?'checked':''}>Current role</label></div><button type="button" class="text-button" data-remove-row>Remove role</button></div>`;}
function educationRow(edu={}){return `<div class="repeat-row education-row"><div class="form-grid"><label>Institution<input data-field="institution" value="${esc(edu.institution||'')}" maxlength="160"></label><label>Degree<input data-field="degree" value="${esc(edu.degree||'')}" maxlength="120" placeholder="BTech, MBA…"></label><label>Major / field of study<input data-field="major" value="${esc(edu.major||'')}" maxlength="120" placeholder="Chemical Engineering…"></label><label>Start year<input type="number" min="1940" max="2100" data-field="start_year" value="${edu.start_year||''}"></label><label>End year<input type="number" min="1940" max="2100" data-field="end_year" value="${edu.end_year||''}"></label></div><button type="button" class="text-button" data-remove-row>Remove education</button></div>`;}
function fillContact(c={}){
  const f=$('contact-form');f.reset();
  for(const key of ['name','occupation','relationship','relationship_strength','last_contacted','location','notes'])if(c[key])f.elements[key].value=c[key];
  f.elements.expertise.value=(c.expertise||[]).join(', ');f.elements.sectors.value=(c.sectors||[]).join(', ');
  f.elements.introduced_by.innerHTML='<option value="">No recorded introducer</option>'+networkState.contacts.filter(x=>x.id!==networkState.editing).map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');
  f.elements.introduced_by.value=c.introduced_by||'';
  $('profile-url').value=c.linkedin_url||'';
  $('employment-rows').innerHTML=(c.employment?.length?c.employment:[{}]).map(jobRow).join('');
  $('education-rows').innerHTML=(c.education?.length?c.education:[{}]).map(educationRow).join('');
  networkState.provenance=c.provenance||'investor_entered';
  $('contact-provenance').textContent=provenanceLabel(c)+' · You confirm these details when saving.';
}
function editPerson(c=null){networkState.editing=c?.id||null;$('contact-dialog-title').textContent=c?'EDIT PERSON':'ADD A PERSON';$('profile-text').value='';$('prefill-status').innerHTML='';$('contact-error').innerHTML='';fillContact(c||{});$('contact-dialog').showModal();}
async function personDetail(identifier){
  let c=networkState.contacts.find(x=>x.id===identifier);
  if(!c){const d=await api('/network');networkState.contacts=d.contacts;c=d.contacts.find(x=>x.id===identifier);}
  if(!c)return;
  $('person-body').innerHTML=`<span class="badge">${esc(provenanceLabel(c))}</span><h2>${esc(displayName(c))}</h2><p>${esc(c.occupation)}</p><p class="muted">${esc(c.relationship||'Relationship not recorded')} · ${esc(c.relationship_strength)}</p><div class="chips">${[...c.expertise,...c.sectors].map(t=>`<span class="expertise-tag">${esc(t)}</span>`).join('')}</div><h3 class="spaced">Career</h3>${c.employment.map(j=>`<p><strong>${esc(j.role||'Role unspecified')}</strong> · ${esc(j.company)} ${j.ticker?'('+esc(j.ticker)+')':''}<br><span class="muted">${tenure(j)}</span></p>`).join('')||'<p class="muted">No career details recorded.</p>'}<h3 class="spaced">Education</h3>${c.education.map(j=>`<p><strong>${esc(j.institution)}</strong><br>${esc(j.degree)} · ${esc(j.major)}<br><span class="muted">${tenure(j)}</span></p>`).join('')||'<p class="muted">No education recorded.</p>'}<p class="muted">Last contacted: ${esc(c.last_contacted||'Not recorded')} · ${esc(c.location||'Location not recorded')}</p>${c.notes?`<p>${esc(c.notes)}</p>`:''}${c.linkedin_url?`<a class="text-link" href="${esc(safeUrl(c.linkedin_url))}" target="_blank" rel="noopener noreferrer">Open LinkedIn profile ↗</a>`:''}<div id="person-overlaps" class="notice">Checking recorded overlaps…</div><div class="actions"><button class="button" id="edit-person">Edit person</button><button class="button secondary" id="contacted-today">Mark contacted today</button><button class="text-button" id="delete-person">Remove person</button></div>`;
  $('person-dialog').showModal();
  $('edit-person').onclick=()=>{$('person-dialog').close();editPerson(c);};
  $('contacted-today').onclick=async()=>{const date=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());await api('/network/contacts/'+c.id,'PUT',{...c,last_contacted:date});$('person-dialog').close();await loadNetwork();toast('Last contacted updated.');};
  $('delete-person').onclick=async()=>{if(!confirm(`Remove ${c.name} from your local network?`))return;try{await api('/network/contacts/'+c.id,'DELETE');$('person-dialog').close();await loadNetwork();loadFeed();toast('Person removed.');}catch(e){toast(e.message);}};
  try{const d=await api('/network/contacts/'+c.id+'/overlaps');if(!$('person-dialog').open)return;$('person-overlaps').innerHTML=d.items.length?'<strong>Possible overlaps — not confirmed relationships</strong>'+d.items.map(x=>`<p>${esc(x.name)}: ${esc(x.reason)}<br>${esc(x.caveat)}</p>`).join(''):'No dated affiliation overlaps found with your other contacts.';}catch{$('person-overlaps').textContent='Overlap lookup unavailable.';}
}
$('network-search').onsubmit=e=>{e.preventDefault();loadNetwork();};
$('add-contact').onclick=()=>editPerson();$('close-contact').onclick=()=>$('contact-dialog').close();$('close-person').onclick=()=>$('person-dialog').close();
$('add-job').onclick=()=>$('employment-rows').insertAdjacentHTML('beforeend',jobRow());
$('add-education').onclick=()=>$('education-rows').insertAdjacentHTML('beforeend',educationRow());
document.addEventListener('click',e=>{
  if(e.target.closest('a[href="#network"]')){
    for(const id of ['event-dialog','person-dialog']) if($(id)?.open) $(id).close();
  }
  const row=e.target.closest('[data-remove-row]');if(row)row.closest('.repeat-row').remove();
  const person=e.target.closest('[data-person]');if(person)personDetail(person.dataset.person).catch(err=>toast(err.message));
  const tag=e.target.closest('[data-expertise]');if(tag){$('network-query').value=$('network-query').value===tag.dataset.expertise?'':tag.dataset.expertise;loadNetwork();}
  if(e.target.closest('[data-new-person]'))editPerson();
});
$('prefill-contact').onclick=async()=>{
  const button=$('prefill-contact');button.disabled=true;$('prefill-status').innerHTML='<div class="loading">Preparing an editable draft…</div>';
  try{const d=await api('/network/prefill','POST',{linkedin_url:$('profile-url').value.trim(),profile_text:$('profile-text').value});if(d.status==='review_required')fillContact(d.draft);$('prefill-status').innerHTML=`<div class="notice">${esc(d.message)}</div>`;}catch(e){$('prefill-status').innerHTML=errorBox(e.message);}finally{button.disabled=false;}
};
$('contact-form').onsubmit=async e=>{
  e.preventDefault();const f=e.target,button=$('save-contact');button.disabled=true;$('contact-error').innerHTML='';
  const rows=selector=>[...document.querySelectorAll(selector)].map(row=>Object.fromEntries([...row.querySelectorAll('[data-field]')].map(input=>[input.dataset.field,input.type==='checkbox'?input.checked:input.type==='number'?(input.value?Number(input.value):null):input.value.trim()])));
  const payload={};for(const key of ['name','occupation','relationship','relationship_strength','location','notes'])payload[key]=f.elements[key].value.trim();
  for(const key of ['expertise','sectors'])payload[key]=f.elements[key].value.split(',').map(x=>x.trim()).filter(Boolean);
  payload.employment=rows('.job-row').filter(x=>x.company||x.role||x.ticker);payload.education=rows('.education-row').filter(x=>x.institution||x.major||x.degree);
  payload.linkedin_url=$('profile-url').value.trim();payload.last_contacted=f.elements.last_contacted.value||null;payload.introduced_by=f.elements.introduced_by.value||null;payload.provenance=networkState.provenance;
  try{const d=await api('/network/contacts'+(networkState.editing?'/'+networkState.editing:''),networkState.editing?'PUT':'POST',payload);$('contact-dialog').close();await loadNetwork();loadFeed();toast(d.portfolio_overlaps?.length?'Saved. Experience overlaps with '+d.portfolio_overlaps.join(', ')+'.':'Person saved to your network.');}
  catch(err){$('contact-error').innerHTML=errorBox(err.message);}finally{button.disabled=false;}
};
$('seed-network').onclick=async()=>{const b=$('seed-network');b.disabled=true;try{await api('/network/demo','POST');await loadNetwork();loadFeed();toast('Demo contacts added. Existing contacts were kept.');}catch(e){toast(e.message);}finally{b.disabled=false;}};
loadNetwork();
