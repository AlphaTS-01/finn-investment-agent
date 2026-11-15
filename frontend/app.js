'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = value => { try {const u=new URL(value); return u.protocol==='https:' ? u.href : '#';} catch{return '#';} };
const state = {tickers:[], feed:null, feedRequest:0, researchBusy:false, context:null};
const categories = ['results','management_change','M&A','capex','litigation','credit_rating','fund_raise','pledging','insider_trading','dividend','bonus_split','earnings_call','investor_meetings','postal_ballot','agm_egm','press_release','unclassified'];
const label = s => s === 'M&A' ? s : s.replaceAll('_',' ').replace(/^./, c=>c.toUpperCase());
const date = s => s ? new Date(s).toLocaleString('en-IN',{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+' IST' : 'Date unavailable';
function relativeTime(value){const delta=Math.max(0,Date.now()-new Date(value).getTime());if(!Number.isFinite(delta))return 'Unknown';const mins=Math.floor(delta/60000);return mins<1?'Just now':mins<60?mins+'m ago':mins<1440?Math.floor(mins/60)+'h ago':Math.floor(mins/1440)+'d ago';}
function timeMarkup(value){return value?`<button type="button" class="timestamp" data-time="${esc(value)}" aria-label="Show exact time: ${esc(date(value))}">${relativeTime(value)}</button>`:'Unknown';}
document.addEventListener('click',e=>{const t=e.target.closest('[data-time]');if(t){$('exact-time').textContent=date(t.dataset.time);$('time-dialog').showModal();}});
$('close-time').onclick=()=>$('time-dialog').close();
let watchlistExpanded=false;
function renderWatchlist(){
 const rows=watchlistExpanded?state.tickers:state.tickers.slice(0,5);
 $('watchlist').innerHTML=rows.map(t=>{const c=state.feed?.companies.find(x=>x.ticker===t);const status=c?.status==='ok'?'fresh':c?.status==='stale'?'cached':c?'unavailable':'pending';const caption={fresh:'Updated',cached:'Cached',unavailable:'Unavailable',pending:'Checking'}[status];return `<div class="watchlist-row"><button class="ticker-link" data-research-ticker="${esc(t)}">${esc(t)}</button><span class="company-status"><i class="feed-dot ${status}" aria-hidden="true"></i>${caption} ${c?.fetched_at&&status!=='unavailable'?timeMarkup(c.fetched_at):''}</span></div>`;}).join('');
 $('watchlist-more').hidden=state.tickers.length<=5;$('watchlist-more').textContent=watchlistExpanded?'Show less':`Show all ${state.tickers.length}`;$('watchlist-more').setAttribute('aria-expanded',String(watchlistExpanded));
}
$('watchlist-more').onclick=()=>{watchlistExpanded=!watchlistExpanded;renderWatchlist();};
async function api(path, method='GET', body) {
  const response=await fetch(path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
  let data;
  try{data=await response.json();}
  catch{throw Error(response.ok?'The server returned an unreadable response. Please try again.':`The server could not complete this request (${response.status}). Please try again shortly.`);}
  if(!response.ok) throw Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(x=>x.msg).join('; '):'The request could not be completed. Please try again.');
  return data;
}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,5000);}
function errorBox(message){return `<div class="notice error">${esc(message)}</div>`;}
function route(){
  const page=['today','research','network','settings'].includes(location.hash.slice(1))?location.hash.slice(1):'today';
  document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!=='page-'+page);
  document.querySelectorAll('[data-nav]').forEach(el=>{const active=el.dataset.nav===page;el.classList.toggle('active',active);if(active)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
  document.title=`FINN — ${page==='settings'?'Preferences':label(page)}`;
  $('date-label').hidden=false;document.body.dataset.page=page;
  if(page==='settings')loadDataPreferences();
  window.scrollTo({top:0,behavior:'instant'});
}
window.addEventListener('hashchange',route);
$('date-label').textContent=new Date().toLocaleDateString('en-IN',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'Asia/Kolkata'});
function renderPortfolio(){
  renderWatchlist();
  const current=$('company-filter').value;
  $('company-filter').innerHTML='<option value="">All companies</option>'+state.tickers.map(t=>`<option value="${esc(t)}">${esc(t)}</option>`).join('');
  if(state.tickers.includes(current))$('company-filter').value=current;
  const companyRows=state.tickers.map(t=>`<div class="watch-row"><strong>${esc(t)}</strong><button class="text-button" data-remove="${esc(t)}" aria-label="Remove ${esc(t)} from watchlist">Remove ×</button></div>`);
  $('settings-watchlist').innerHTML=companyRows.length?companyRows.slice(0,5).join('')+(companyRows.length>5?`<details><summary>${companyRows.length-5} more companies</summary>${companyRows.slice(5).join('')}</details>`:''):'<p class="muted">No companies tracked.</p>';
}
function networkHook(matches){
 const match=matches?.[0];
 if(!match)return '<p class="network-cue muted">No relevant contact recorded. <a href="#network">Add one</a></p>';
 const c=match.contact,job=c.employment.find(j=>j.current)||c.employment[0],name=c.provenance==='synthetic_demo'?c.name.replace(/\s*\(demo\)$/i,''):c.name;
 return `<div class="network-hook"><button class="text-button" data-person="${esc(c.id)}">${esc(name)} may help</button>${c.provenance==='synthetic_demo'?'<span class="badge">Demo</span>':''}<p>${job?esc((job.current?'At ':'Ex-')+job.company):esc(c.occupation)}</p><small>${esc(match.reasons?.[0]||'Relevant recorded expertise.')}</small></div>`;
}
function smartCard(event){
 const a=event.analysis;
 if(event.category==='results'){
   const rows=['Revenue','EBITDA','PBT','PAT'].map(metric=>a?.financials?.find(x=>x.metric===metric)||{metric,values:{},qoq_pct:null,yoy_pct:null});
   const percent=n=>n==null?'—':`${n>0?'+':''}${n}%`;
   const current=rows.find(x=>x.values?.current)?.values.current;
   const scopes=new Set(rows.filter(x=>x.values?.current).map(x=>x.values.current.unit+'|'+x.values.current.basis));
   return `<div class="smart-results"><div class="table-scroll"><table><caption>Quarterly comparison</caption><thead><tr><th>Metric</th><th>Quarter</th><th>QoQ</th><th>YoY</th></tr></thead><tbody>${rows.map(x=>`<tr><th scope="row">${esc(x.metric)}</th><td>${x.values?.current?esc(Number(x.values.current.value).toLocaleString('en-IN')+(scopes.size>1?' '+x.values.current.unit+' / '+x.values.current.basis:'')):'—'}</td><td>${percent(x.qoq_pct)}</td><td>${percent(x.yoy_pct)}</td></tr>`).join('')}</tbody></table></div><small class="muted">${current?esc(scopes.size>1?'Mixed units or reporting basis; inspect source.':current.period_end+' · '+current.basis+' · '+current.unit):'Figures not verified yet.'} — means unavailable or not comparable.</small></div>`;
 }
 if(event.category==='management_change'){
   const incoming=a?.executives?.filter(x=>/appoint|join|induct/i.test(x.quote||''))||[];
   const overlaps=a?.executive_overlaps||[];
   return `<div class="management-brief">${incoming.length?incoming.slice(0,2).map(x=>`<strong>${esc(x.name)}</strong><p>${esc(x.role)} · ${esc(x.background||'Bio not disclosed in this filing.')}</p>`).join(''):'<p class="muted">Incoming-person bio not verified in the available filing.</p>'}${overlaps.length?overlaps.map(x=>`<p><button class="text-button" data-person="${esc(x.contact_id)}">${esc(x.name)}</button> · ${esc(x.reason)}</p>`).join(''):'<small class="muted">No worked/studied-together connection verified.</small>'}</div>`;
 }
 return '';
}
function eventCard(event){
 const summary=event.analysis?.summary?.text,why=event.analysis?.why_it_matters?.text;
 const title=event.subject.replace(/^Announcement under Regulation 30 \(LODR\)\s*[-–:]?\s*/i,'').trim();
 return `<article class="event-card"><div class="event-meta"><strong>${esc(event.ticker)}</strong><span class="badge">${esc(label(event.category))}</span>${event.revision?'<span class="badge">Updated</span>':''}</div><h3><button class="filing-title" data-event="${esc(event.id)}">${esc(title)}</button></h3>${summary?`<p class="card-reason">${esc(summary)}</p>`:'<small class="muted">Source analysis pending. Open the filing for details.</small>'}${why?`<p class="why-matters"><strong>Why it matters:</strong> ${esc(why)}</p>`:''}${smartCard(event)}${networkHook(event.network_matches)}<div class="event-bottom"><span>${esc(event.provider)} · ${timeMarkup(event.published_at)}</span>${event.related_filings?.length?`<span>${event.related_filings.length+1} related filings</span>`:''}</div></article>`;
}
function renderFeed(){
 if(!state.feed)return;
 const groups=state.feed.groups||state.feed.items,ticker=$('company-filter').value;
 const all=groups.flatMap(e=>[e,...(e.related_filings||[])]);
 const visible=($('show-all-filings').checked?all:groups).filter(e=>!ticker||e.ticker===ticker);
 const review=visible.filter(e=>e.priority>20),routine=visible.filter(e=>e.priority<=20);
 $('filing-count').textContent=all.filter(e=>!ticker||e.ticker===ticker).length;$('priority-count').textContent=review.length;
 $('feed').innerHTML=review.length?review.map(eventCard).join(''):'<p class="empty-inline">No updates to review in this period.</p>';
 $('routine-feed').innerHTML=routine.map(eventCard).join('');$('routine-count').textContent=routine.length;$('routine-wrap').hidden=!routine.length;
 const selected=state.feed.companies.filter(c=>!ticker||c.ticker===ticker),fetched=selected.map(c=>c.fetched_at).filter(Boolean).sort();
 const cached=selected.filter(c=>c.status==='stale').length,unavailable=selected.filter(c=>c.status==='unavailable').length;
 $('feed-freshness').innerHTML=(fetched.length?(cached?'Cached · updated ':'Updated ')+timeMarkup(fetched[0]):'Sources unavailable')+(unavailable?` · ${unavailable} unavailable`:'');
 renderWatchlist();
}
async function loadFeed(refresh=false){
  const request=++state.feedRequest;
  $('feed').innerHTML='<div class="loading">Loading filings…</div>';
  $('routine-wrap').hidden=true;$('refresh-feed').disabled=true;
  try {const data=await api('/briefing?days='+$('window').value+'&refresh='+(refresh===true));if(request!==state.feedRequest)return;state.feed=data;renderFeed();}
  catch(e){if(request===state.feedRequest)$('feed').innerHTML=errorBox(e.message);}
  finally{if(request===state.feedRequest)$('refresh-feed').disabled=false;}
}
function alertReason(a){
 if(a.trigger_reasons?.length)return a.trigger_reasons.join(' ');
 if(a.type==='market')return (a.triggers||[]).map(t=>t==='volume'?`Volume ${Number(a.volume_ratio).toFixed(2)}× the preceding 20-session average.`:`Price moved ${Number(a.change_pct).toFixed(2)}%.`).join(' ')+' Recorded threshold crossing; original threshold not stored.';
 return 'Recorded announcement alert; original rule not stored.';
}
async function loadAlerts(){try{const data=await api('/alerts');const alerts=data.items.filter(a=>['market','announcement'].includes(a.type));$('alert-list').innerHTML=alerts.slice(0,5).map(a=>`<article class="alert-item"><div class="event-meta"><strong>${esc(a.ticker)}</strong>${timeMarkup(a.created_at||a.published_at)}</div>${a.subject?`<p>${esc(a.subject)}</p>`:''}<p>${esc(alertReason(a))}</p>${a.type==='market'?`<small class="muted">Trading session · ${timeMarkup(a.trading_date+'T15:30:00+05:30')}</small>`:''}${networkHook(a.network_matches)}</article>`).join('')||'<p class="empty-inline">No threshold alerts triggered.</p>';}catch{$('alert-list').innerHTML='<p class="empty-inline">Alerts unavailable. Try refreshing.</p>';}}
function openResearch(ticker,context=null){
  $('ticker').value=ticker;state.context=context;
  $('event-context').hidden=!context;
  if(context){$('event-context').textContent='From your briefing: '+context.subject;$('question').value='';}
  location.hash='research';route();$('question').focus();
}
function analysisMarkup(d){
  if(d.status==='unavailable')return `<div class="notice">${esc(d.message)}</div>`;
  const fact=f=>f?`<p>${esc(f.text)}</p><details><summary>Evidence · PDF page ${f.page}</summary><blockquote>${esc(f.quote)}</blockquote><a class="text-link" href="${esc(safeUrl(d.source_url))}#page=${f.page}" target="_blank" rel="noopener noreferrer">Open source page ↗</a></details>`:'';
  let html='<h3>What changed</h3>'+fact(d.summary)+'<h3 class="spaced">Why it may matter</h3>'+fact(d.why_it_matters);
  if(d.executives?.length)html+='<h3 class="spaced">People in this filing</h3>'+d.executives.map(x=>`<div class="source-detail"><strong>${esc(x.name)} · ${esc(x.role)}</strong><p>${esc(x.background||'Background not disclosed in this filing.')}</p><details><summary>Filing evidence · PDF page ${x.page}</summary><p>${esc(x.quote)}</p></details></div>`).join('');
  if(d.financials?.length){html+='<h3 class="spaced">Results at a glance</h3><p class="muted">First-cut extraction. Units, reporting basis and period evidence are shown below. Blank comparisons mean not verified or not comparable.</p><div class="table-scroll"><table><thead><tr><th>Metric</th><th>Current quarter</th><th>QoQ</th><th>YoY</th></tr></thead><tbody>'+d.financials.map(x=>`<tr><td>${esc(x.metric)}</td><td>${x.values.current?esc(x.values.current.value)+' '+esc(x.values.current.unit):'Not verified'}</td><td>${x.qoq_pct==null?'—':x.qoq_pct+'%'}</td><td>${x.yoy_pct==null?'—':x.yoy_pct+'%'}</td></tr>`).join('')+'</tbody></table></div><details><summary>Verify financial periods and source figures</summary>'+d.financials.map(x=>Object.entries(x.values).map(([key,v])=>`<p><strong>${esc(x.metric)} · ${esc(label(key))}</strong><br>${esc(v.period_end)} · ${esc(v.basis)} · ${esc(v.unit)} · PDF page ${v.page}</p><blockquote>${esc(v.quote)}</blockquote>`).join('')).join('')+'</details>';}
  html+=`<details><summary>Coverage & limitations</summary><p class="muted">Reviewed ${d.pages_reviewed?.length||0} of ${d.total_pages||0} PDF pages. Analyzed ${esc(date(d.analyzed_at))}.</p><ul>${(d.limitations||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>`;
  return html;
}
async function openEvent(id){
  const groups=state.feed?.groups||[];const e=groups.find(x=>x.id===id)||groups.flatMap(x=>x.related_filings||[]).find(x=>x.id===id)||state.feed?.items.find(x=>x.id===id);if(!e)return;
  state.activeEvent=id;
  $('event-body').innerHTML=`<div class="event-meta"><strong>${esc(e.ticker)}</strong><span class="badge">${esc(label(e.category))}</span></div><h2>${esc(e.subject)}</h2>${e.revision?'<p class="badge">Updated filing</p>':''}${e.previous_filing?.source_url?`<a class="text-link" href="${esc(safeUrl(e.previous_filing.source_url))}" target="_blank" rel="noopener">Previous filing ↗</a>`:''}<p class="muted">${esc(e.provider)} · ${timeMarkup(e.published_at)}</p><details><summary>Why am I seeing this?</summary><p>${esc(e.priority_reason)}</p><p class="muted">${esc(e.priority_basis||'Subject-based triage.')} Alert preferences never remove filings from your briefing.</p></details><div id="filing-analysis">${e.analysis?analysisMarkup(e.analysis):'<div class="loading">Reading the original filing for a source-backed first cut…</div>'}</div>${e.source_url?`<a class="button" href="${esc(safeUrl(e.source_url))}" target="_blank" rel="noopener noreferrer">Open original filing ↗</a>`:''}<button class="button secondary" id="investigate-event">Research company</button>${e.related_filings?.length?`<details><summary>${e.related_filings.length} related filings</summary><p class="muted">${esc(e.group_note)}</p>${e.related_filings.map(r=>`<button class="related-filing text-button" data-event="${esc(r.id)}">${esc(r.subject)}</button>`).join('')}</details>`:''}<hr><h3>Who could add context?</h3><div id="event-network">${typeof renderMatches==='function'?renderMatches(e.network_matches):''}</div>`;
  $('investigate-event').onclick=()=>{$('event-dialog').close();openResearch(e.ticker,e);};
  if(!$('event-dialog').open)$('event-dialog').showModal();
  try{const d=await api('/events/'+id+'/analysis');if(state.activeEvent!==id)return;$('filing-analysis').innerHTML=analysisMarkup(d);$('event-network').innerHTML=renderMatches(d.network_matches);if(d.summary)e.analysis=d;renderFeed();}catch(err){if(state.activeEvent===id)$('filing-analysis').innerHTML=errorBox(err.message);}
}
$('close-dialog').onclick=()=>$('event-dialog').close();
document.addEventListener('click',async e=>{
  const card=e.target.closest('[data-event]');if(card)openEvent(card.dataset.event);
  const ticker=e.target.closest('[data-research-ticker]');if(ticker)openResearch(ticker.dataset.researchTicker);
  const remove=e.target.closest('[data-remove]');if(remove){remove.disabled=true;try{const result=await api('/portfolio/'+encodeURIComponent(remove.dataset.remove),'DELETE');state.tickers=result.tickers;renderPortfolio();loadFeed();toast('Company removed from your watchlist.');}catch(err){toast(err.message);remove.disabled=false;}}
});
$('window').onchange=()=>loadFeed();$('company-filter').onchange=renderFeed;$('show-all-filings').onchange=renderFeed;$('refresh-feed').onclick=()=>{loadFeed(true);loadAlerts();};
$('ticker').addEventListener('input',()=>{$('monitor-this').hidden=true;state.context=null;$('event-context').hidden=true;});
$('research-form').onsubmit=async e=>{
  e.preventDefault();if(state.researchBusy)return;
  const ticker=$('ticker').value.trim().toUpperCase(),question=$('question').value.trim();
  if(!/^[A-Z0-9][A-Z0-9&_\-.]{0,24}$/.test(ticker)){toast('Enter an NSE ticker, such as TCS or M&M.');return;}
  state.researchBusy=true;$('research-submit').disabled=true;
  $('research-output').innerHTML='<div class="loading">Finding primary documents and reading the evidence…<br>First-time research can take a minute or two. You can explore the other tabs while it runs.</div>';
  try{
    const d=await api('/research','POST',{ticker,question,max_documents:4,event_id:state.context?.id||null});
    const partial=d.status!=='ok';
    let html=`<article class="answer"><div class="event-meta"><span class="badge">${esc(d.status.replaceAll('_',' '))}</span><span>${d.cached?'Cached answer':'New research'} · ${timeMarkup(d.fetched_at)}</span></div><h2>${esc(d.company)}</h2><p class="muted">${esc(question)}</p>`;
      const failureMessages={no_documents:'The source documents could not be retrieved.',no_matching_passages:'Documents were read, but no passages matched this question.',answer_validation_failed:'The answer failed citation checks. You can still read the source excerpts below.',question_not_supported:'The available documents do not support an answer to this question.',model_api_error:'Gemini could not complete the request. The provider error is shown below.',invalid_model_output:'Gemini returned an unreadable answer.'};
      if(partial)html+='<div class="notice">'+(d.claims.length?'This answer uses the available evidence. Some source coverage is missing.':esc(failureMessages[d.failure_reason]||'A supported answer could not be completed. See the evidence gaps below.'))+'</div>';
      if(d.diagnostics)html+=`<p class="muted">${d.diagnostics.documents_read} documents read · ${d.diagnostics.passages_found} matching passages</p>`;
    html+=d.claims.map(c=>`<div class="claim">${esc(c.text)} ${c.source_ids.map(id=>`<a class="source-link" href="#source-${esc(id)}" data-source="${esc(id)}">${esc(id)}</a>`).join('')}</div>`).join('');
    if(d.retrieval_plan)html+=`<details><summary>Research scope</summary><p>${esc(label(d.retrieval_plan.topic))} · ${esc(d.retrieval_plan.period)}</p><p>${d.retrieval_plan.required_document_types.map(label).map(esc).join(', ')}</p></details>`;
    if(d.limitations?.length)html+=`<details ${partial?'open':''}><summary>Scope & evidence gaps</summary><ul class="muted">${d.limitations.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>`;
    if(d.warnings?.length)html+=`<div class="notice">${d.warnings.map(esc).join('<br>')}</div>`;
    html+=`<details id="sources-details"><summary>Source evidence (${d.sources.length} passages)</summary>${d.sources.map(s=>`<div class="source-detail" id="source-${esc(s.id)}"><span class="badge">${esc(s.id)} · Page ${s.page}</span><h3>${esc(s.title)}</h3><a href="${esc(safeUrl(s.url))}#page=${s.page}" target="_blank" rel="noopener noreferrer">Open source document ↗</a><p>${esc(s.text)}</p></div>`).join('')}</details><details><summary>Documents & freshness (${d.documents_used?.length||0})</summary>${(d.documents_used||[]).map(doc=>`<p><strong>${esc(doc.title)}</strong><br>${esc(label(doc.kind))} · Retrieved ${timeMarkup(doc.fetched_at)}<br><a class="text-link" href="${esc(safeUrl(doc.url))}" target="_blank" rel="noopener noreferrer">Read original document ↗</a></p>`).join('')}${state.context?`<p>Selected event filing: ${d.event_filing_included?'included as evidence':'unavailable — not used as evidence'}</p>`:''}</details><div class="rail-section"><h3>Who could help you understand this?</h3>${renderMatches(d.network_matches)}</div></article>`;
    $('research-output').innerHTML=html;
    $('monitor-this').hidden=false;$('monitor-this').dataset.ticker=ticker;$('monitor-this').dataset.question=question;
    $('research-output').querySelectorAll('[data-source]').forEach(a=>a.onclick=ev=>{ev.preventDefault();$('sources-details').open=true;$('source-'+a.dataset.source).scrollIntoView({behavior:'smooth',block:'center'});});
    if(location.hash!=='#research')toast('Your research is ready in the Research tab.');
  }catch(err){$('research-output').innerHTML=errorBox(err.message);}
  finally{state.researchBusy=false;$('research-submit').disabled=false;}
};
$('add-form').onsubmit=async e=>{
  e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;
  try{const d=await api('/portfolio/'+encodeURIComponent($('add-ticker').value.trim().toUpperCase()),'PUT');state.tickers=d.tickers;renderPortfolio();$('add-ticker').value='';loadFeed();toast('Watchlist updated.');}
  catch(err){toast(err.message);}finally{button.disabled=false;}
};
$('category-options').innerHTML=categories.map(c=>`<label><input type="checkbox" name="category" value="${esc(c)}">${esc(label(c))}</label>`).join('');
$('rules-form').onsubmit=async e=>{
  e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;
  try{await api('/settings/alerts','PUT',{mode:$('alert-mode').value,price_pct:Number($('price-threshold').value),volume_ratio:Number($('volume-threshold').value),categories:[...document.querySelectorAll('[name=category]:checked')].map(x=>x.value)});await Promise.all([loadFeed(),loadAlerts()]);toast('Preferences saved.');}
  catch(err){toast(err.message);}finally{button.disabled=false;}
};
async function init(){
  document.querySelectorAll('#digest-form input,#digest-form select,#digest-form button,#rules-form input,#rules-form select,#rules-form button').forEach(e=>e.disabled=true);
  route();
  try{const d=await api('/portfolio');state.tickers=d.tickers;renderPortfolio();}catch(err){toast(err.message);}
  try{const d=await api('/settings/digest');$('default-window').value=String(d.default_days);$('window').value=String(d.default_days);$('show-all-filings').checked=d.ungroup_filings;}catch(err){toast(err.message);}finally{document.querySelectorAll('#digest-form input,#digest-form select,#digest-form button').forEach(e=>e.disabled=false);}
  loadFeed();loadAlerts();
  try{const r=await api('/settings/alerts');$('alert-mode').value=r.mode==='briefing_only'?'briefing_only':'custom';$('price-threshold').value=r.price_pct;$('volume-threshold').value=r.volume_ratio;document.querySelectorAll('[name=category]').forEach(el=>el.checked=r.categories.includes(el.value));}catch(err){toast(err.message);}finally{document.querySelectorAll('#rules-form input,#rules-form select,#rules-form button').forEach(e=>e.disabled=false);}
}
init();

async function loadMonitors(){
  try{const d=await api('/monitors');$('monitor-list').innerHTML=d.items.map(m=>`<div class="watch-row"><div><strong>${esc(m.ticker)}</strong><p>${esc(m.question)}</p>${m.latest?`<details><summary>Latest update</summary><p>${esc(m.latest.subject)}</p><p>${esc(m.latest.quote)}</p><a href="${esc(safeUrl(m.latest.source_url))}#page=${m.latest.page}" target="_blank" rel="noopener">Source · p${m.latest.page}</a></details>`:''}</div><button type="button" class="text-button" data-remove-monitor="${esc(m.id)}">Remove</button></div>`).join('')||'<p class="muted">No monitored questions.</p>';
  $('monitor-worker').innerHTML=d.worker?'Worker checked '+timeMarkup(d.worker.heartbeat):'Worker starting…';}catch(e){$('monitor-list').textContent=e.message;}
}
$('monitor-this').onclick=async()=>{const b=$('monitor-this');b.disabled=true;try{await api('/monitors','POST',{ticker:b.dataset.ticker,question:b.dataset.question});toast('Monitoring new filings for this question.');loadMonitors();}catch(e){toast(e.message);}finally{b.disabled=false;}};
document.addEventListener('click',async e=>{const b=e.target.closest('[data-remove-monitor]');if(!b)return;try{await api('/monitors/'+b.dataset.removeMonitor,'DELETE');loadMonitors();toast('Monitor removed.');}catch(err){toast(err.message);}});
loadMonitors();

$('digest-form').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const d=await api('/settings/digest','PUT',{default_days:Number($('default-window').value),ungroup_filings:$('show-all-filings').checked});$('window').value=String(d.default_days);loadFeed();toast('Digest defaults saved.');}catch(err){toast(err.message);}finally{b.disabled=false;}};
async function loadDataPreferences(){try{const [n,h]=await Promise.all([api('/network'),api('/health')]);$('network-data-count').textContent=n.contacts.length+' contacts stored.';$('provider-status').textContent='Gemini: '+(h.providers_configured.gemini?'configured':'not configured')+' · Tavily: '+(h.providers_configured.tavily?'configured':'not configured')+'. Configuration does not guarantee source availability.';}catch(e){$('provider-status').textContent=e.message;}}
$('delete-network').onclick=async()=>{if(!confirm('Delete all contacts stored in this workspace? This cannot be undone.'))return;try{await api('/network/contacts','DELETE');await loadNetwork();loadDataPreferences();loadFeed();loadAlerts();toast('All contacts removed.');}catch(e){toast(e.message);}};
loadDataPreferences();
