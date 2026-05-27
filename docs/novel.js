(async function(){
const slug = new URLSearchParams(location.search).get('slug');
const library = await (await fetch('library.json?v='+Date.now())).json();
const history = await (await fetch('build-history.json?v='+Date.now())).json().catch(()=>[]);
const novel = (library||[]).find(n=>n.slug===slug);
const el=document.getElementById('novelDetail');
if(!novel){el.innerHTML='<p>Novel not found.</p>';return;}
const d=(novel.downloads||[]).slice().sort((a,b)=>(a.start||0)-(b.start||0));
const max=d.reduce((m,x)=>Math.max(m,Number(x.end||0)),0);
const lastBuild=(history||[]).filter(h=>h.novel_slug===slug).slice(-1)[0]||{};
el.innerHTML=`<h1>${novel.title||slug}</h1><img class='novel-cover' src='${novel.cover||'covers/default.svg'}' style='max-width:180px'><p><b>Source site:</b> ${novel.source_site||novel.site||'Unknown'}</p><p><b>Source URL:</b> <a href='${novel.source_url||'#'}'>${novel.source_url||'N/A'}</a></p><p><b>Status:</b> ${novel.status||'Unknown'}</p><p><b>Last built:</b> ${novel.last_updated||''}</p><p><b>Last checked:</b> ${novel.last_checked||''}</p><p><b>Highest chapter:</b> ${max||novel.last_chapter_number||0}</p><p><a class='button' href='index.html'>Continue from next chapter</a> <a class='button' href='https://github.com/issues/new' target='_blank'>Combine chunks</a></p><div>${d.map(x=>`<div class='download-row'><span>${x.label||('Chapters '+x.start+'-'+x.end)}</span> <a class='button' href='${x.url}' download>Download</a> <button class='button button-secondary copy' data-url='${new URL(x.url,location.href).href}'>Copy link</button></div>`).join('')}</div>`;
document.querySelectorAll('.copy').forEach(b=>b.onclick=()=>navigator.clipboard.writeText(b.dataset.url));
})();
