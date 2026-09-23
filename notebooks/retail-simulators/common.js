'use strict';
const DATA = JSON.parse(document.getElementById('model-data').textContent);
const ENGINE = globalThis.RetailEngine;
const $ = selector => document.querySelector(selector);
const escapeHtml = value => String(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const icon = name => RetailIcons[name] || '';
const format = (number, digits = 1) => Number(number).toLocaleString('en-US', {minimumFractionDigits:digits, maximumFractionDigits:digits});
const titleCase = text => text.toLowerCase().replace(/\b\w/g, character => character.toUpperCase());
function category(name) {
  if (/BAG|SHOPPER/.test(name)) return 'bag';
  if (/MUG|CUP|TEAPOT|CAKE|KITCHEN|PLATE/.test(name)) return 'cup';
  if (/DOORMAT|MAT /.test(name)) return 'mat';
  if (/FRAME|MIRROR/.test(name)) return 'frame';
  if (/HEART|HANGING|ORNAMENT|BUNTING|CHRISTMAS/.test(name)) return 'decor';
  return 'box';
}
function productPhoto(code, name, compact = false) {
  const photo = DATA.productImages[code];
  if (!photo) return `<span class="photo-missing ${compact?'compact':''}" data-photo-code="${escapeHtml(code)}">${compact?'No photo':'Photo unavailable'}</span>`;
  const label = photo.kind === 'matched' ? 'Product photo' : 'Name-matched reference';
  const image = `<img class="product-photo" data-photo-code="${escapeHtml(code)}" src="${photo.src}" alt="${escapeHtml(titleCase(name))} / ${label}" title="${escapeHtml(label+' - '+photo.credit)}" decoding="async">`;
  return compact ? `<span class="photo-thumb">${image}</span>` : `<figure class="product-media">${image}<figcaption><a href="${escapeHtml(photo.sourcePage)}" target="_blank" rel="noopener" title="${escapeHtml(photo.match)}">${label} / ${escapeHtml(photo.credit)}</a></figcaption></figure>`;
}
function photoCredits() {
  const container = $('#photo-credits');
  if (!container) return;
  const records = Object.entries(DATA.productImages);
  container.innerHTML = `<summary>Product photographs &amp; credits / ${records.length} images</summary><p>Stock-code matches use merchant product photos. Name-matched references are labeled separately and are not independently verified as the historical SKU. Products without a reviewed image show Photo unavailable; no category drawing is substituted.</p><p>${escapeHtml(DATA.imageRights)}</p><div class="table-wrap"><table class="data-table"><thead><tr><th>Product</th><th>Image source</th></tr></thead><tbody>${records.map(([code,photo])=>`<tr><td>${escapeHtml(code)} / ${escapeHtml(titleCase(photo.name))}</td><td><a href="${escapeHtml(photo.sourcePage)}" target="_blank" rel="noopener">${escapeHtml(photo.credit)}</a><br>${photo.kind==='matched'?'Stock-code match':'Name-matched reference'}</td></tr>`).join('')}</tbody></table></div>`;
}
const plotConfig = {responsive:true, displayModeBar:false, scrollZoom:false, staticPlot:false};
const plotBase = {template:'plotly_dark',paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{family:'Inter, sans-serif',size:13,color:'#f5f3f0'},hoverlabel:{bgcolor:'#222530',bordercolor:'#7eaeb8',font:{color:'#f5f3f0',size:14}},margin:{l:55,r:22,t:25,b:45},autosize:true};
const chartResize = new ResizeObserver(entries => {
  for (const {target} of entries) {
    const width = target.clientWidth, height = target.clientHeight;
    if (width > 0 && height > 0 && target._fullLayout &&
        (Math.abs(target._fullLayout.width - width) > 1 || Math.abs(target._fullLayout.height - height) > 1)) {
      Plotly.relayout(target, {width, height});
    }
  }
});
function plot(id, traces, layout = {}) {
  const target = document.getElementById(id);
  return Plotly.react(target,traces,{...plotBase,...layout,width:target.clientWidth,height:target.clientHeight},plotConfig)
    .then(() => chartResize.observe(target));
}
function mountIcons(){document.querySelectorAll('[data-icon]').forEach(element=>{element.innerHTML=icon(element.dataset.icon)});}
function announce(message) {$('#announcement').textContent = message;}
function downloadJson(filename,value){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const anchor=document.createElement('a');anchor.href=url;anchor.download=filename;anchor.click();URL.revokeObjectURL(url);}
mountIcons();
photoCredits();
document.querySelector('[data-fullscreen]')?.addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{announce('Full screen is unavailable in this browser.');}});