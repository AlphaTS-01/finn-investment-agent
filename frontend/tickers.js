'use strict';
let companyInputCounter=0;
function attachTickerSearch(input,onChoose=null){
  if(input.dataset.autocompleteReady)return;input.dataset.autocompleteReady='true';
  if(!input.id)input.id='company-input-'+(++companyInputCounter);
  const wrapper=document.createElement('div');wrapper.className='ticker-search';
  input.parentNode.insertBefore(wrapper,input);wrapper.appendChild(input);
  const list=document.createElement('div');list.className='ticker-options';list.id=input.id+'-options';list.hidden=true;list.setAttribute('role','listbox');wrapper.appendChild(list);
  input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-controls',list.id);input.setAttribute('aria-expanded','false');input.autocomplete='off';
  let timer,version=0,items=[],active=-1;
  const close=()=>{list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');active=-1;};
  const choose=i=>{const item=items[i];input.value=onChoose?item.name:item.ticker;if(onChoose)onChoose(item);version++;clearTimeout(timer);close();input.dispatchEvent(new Event('change',{bubbles:true}));input.focus();};
  input.addEventListener('input',()=>{
    const request=++version,q=input.value.trim();clearTimeout(timer);close();if(!q)return;
    timer=setTimeout(async()=>{
      try{
        const data=await api('/companies/search?q='+encodeURIComponent(q));if(request!==version)return;
        items=data.items;active=-1;
        list.innerHTML=(data.stale?'<div class="ticker-hint">Cached directory</div>':'')+(items.length?items.map((x,i)=>`<button type="button" role="option" aria-selected="false" id="${list.id}-${i}" data-index="${i}"><strong>${esc(x.ticker)}</strong><span>${esc(x.name)}</span></button>`).join(''):'<div class="ticker-hint">No matching company. Enter a ticker directly.</div>');
        list.hidden=false;input.setAttribute('aria-expanded','true');
      }catch(e){if(request!==version)return;items=[];list.innerHTML=`<div class="ticker-hint">${esc(e.message)}</div>`;list.hidden=false;input.setAttribute('aria-expanded','true');}
    },200);
  });
  list.addEventListener('mousedown',e=>e.preventDefault());
  list.addEventListener('click',e=>{const b=e.target.closest('[data-index]');if(b)choose(Number(b.dataset.index));});
  input.addEventListener('keydown',e=>{
    if(e.key==='Escape'){version++;clearTimeout(timer);close();return;}
    if(list.hidden||!items.length)return;
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){
      e.preventDefault();active=(active+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;
      list.querySelectorAll('[role=option]').forEach((el,i)=>el.setAttribute('aria-selected',String(i===active)));
      const selected=document.getElementById(list.id+'-'+active);input.setAttribute('aria-activedescendant',selected.id);selected.scrollIntoView({block:'nearest'});
    }else if(e.key==='Enter'&&active>=0){e.preventDefault();choose(active);}
  });
  input.addEventListener('blur',()=>{version++;clearTimeout(timer);close();});
}
attachTickerSearch($('ticker'));
attachTickerSearch($('add-ticker'));
function attachEmploymentSearch(){document.querySelectorAll('.job-row [data-field="company"]').forEach(input=>attachTickerSearch(input,item=>{input.closest('.job-row').querySelector('[data-field="ticker"]').value=item.ticker;}));}
new MutationObserver(attachEmploymentSearch).observe($('employment-rows'),{childList:true});
attachEmploymentSearch();
