const state = {
  figures: [],
  filters: { category: new Set(), visual: new Set(), technique: new Set(), purpose: new Set() },
  query: "",
  sort: "relevance"
};

const $ = (id) => document.getElementById(id);
const list = (value) => Array.isArray(value) ? value : (value ? [value] : []);
const text = (value) => value == null ? "" : String(value);
const unique = (values) => [...new Set(values.flatMap(list).map(text).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
const titleCase = (value) => text(value).replaceAll("_"," ").replace(/\b\w/g, c => c.toUpperCase());
const escapeHtml = (value) => text(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fc = (r) => r.figure_characterization || {};
const pc = (r) => r.paper_characterization || {};
const paperTitle = (r) => r.paper_title || r.title || "Untitled paper";
const caption = (r) => r.caption || r.figure_label || r.figure_id || "Figure without caption";
const allTags = (r) => [...list(fc(r).visual_types), ...list(fc(r).experimental_techniques), ...list(fc(r).visualization_purposes)];

async function loadFigures() {
  $("loadError").classList.add("hidden");
  $("gallery").innerHTML = '<div class="loading">Loading figures…</div>';
  try {
    const response = await fetch("/api/figures", {cache:"no-store"});
    if (!response.ok) throw new Error("The local FigureLab server returned " + response.status);
    const data = await response.json();
    state.figures = data.figures || [];
    renderFilters();
    renderGallery();
    if (!state.figures.length) {
      $("resultsSubtitle").textContent = "No figure records found";
      $("gallery").innerHTML = "";
      $("emptyState").classList.remove("hidden");
      $("emptyState").querySelector("h2").textContent = "Your library is empty";
      $("emptyState").querySelector("p").textContent = "Run the PMC extraction and characterization steps, then refresh this page.";
    }
  } catch (error) {
    $("gallery").innerHTML = "";
    $("loadError").textContent = "Could not load the local figure library. Make sure you started it with python webapp.py. " + error.message;
    $("loadError").classList.remove("hidden");
    $("resultsSubtitle").textContent = "Unable to load data";
  }
}

function renderFilters() {
  const configs = [
    ["category","categoryFilters","categoryCount", state.figures.map(r=>fc(r).paper_figure_category)],
    ["visual","visualFilters","visualCount", state.figures.flatMap(r=>list(fc(r).visual_types))],
    ["technique","techniqueFilters","techniqueCount", state.figures.flatMap(r=>list(fc(r).experimental_techniques))],
    ["purpose","purposeFilters","purposeCount", state.figures.flatMap(r=>list(fc(r).visualization_purposes))]
  ];
  configs.forEach(([key, target, countId, values]) => {
    const options = unique(values);
    $(countId).textContent = options.length ? options.length : "";
    $(target).innerHTML = options.map(value => {
      const count = state.figures.filter(r => {
        const vals = key==="category" ? [fc(r).paper_figure_category] :
          key==="visual" ? list(fc(r).visual_types) :
          key==="technique" ? list(fc(r).experimental_techniques) : list(fc(r).visualization_purposes);
        return vals.includes(value);
      }).length;
      return '<label class="filter-option"><input type="checkbox" data-filter="'+key+'" value="'+escapeHtml(value)+'" '+(state.filters[key].has(value)?"checked":"")+'><span>'+escapeHtml(titleCase(value))+'</span><span class="option-number">'+count+'</span></label>';
    }).join("") || '<span class="filter-option">No labels yet</span>';
  });
}

function matches(r) {
  const f=fc(r);
  const selected = [
    ["category", [f.paper_figure_category]],
    ["visual", list(f.visual_types)],
    ["technique", list(f.experimental_techniques)],
    ["purpose", list(f.visualization_purposes)]
  ];
  if (selected.some(([key, vals]) => state.filters[key].size && ![...state.filters[key]].some(v=>vals.includes(v)))) return false;
  if (!state.query) return true;
  const haystack = [
    paperTitle(r), caption(r), r.abstract, r.doi, r.pmcid, r.journal,
    f.description, f.evidence, ...allTags(r), ...list(f.style_tags),
    ...list(pc(r).research_fields), ...list(pc(r).subfields)
  ].join(" ").toLowerCase();
  return state.query.toLowerCase().split(/\s+/).every(term=>haystack.includes(term));
}

function renderGallery() {
  const results=state.figures.filter(matches);
  if (state.sort==="title") results.sort((a,b)=>paperTitle(a).localeCompare(paperTitle(b)));
  if (state.sort==="category") results.sort((a,b)=>text(fc(a).paper_figure_category).localeCompare(text(fc(b).paper_figure_category)));
  $("resultsSubtitle").textContent = results.length + " of " + state.figures.length + " figures";
  $("emptyState").classList.toggle("hidden", results.length>0);
  $("gallery").innerHTML = results.map((r,i)=>card(r,i)).join("");
  renderActiveFilters();
}

function card(r,i) {
  const f=fc(r);
  const img=r.image_url ? '<img src="'+escapeHtml(r.image_url)+'" alt="'+escapeHtml(caption(r))+'" loading="lazy" onerror="this.parentElement.innerHTML=\'<div class=&quot;image-placeholder&quot;>▧</div>\'">' : '<div class="image-placeholder">▧</div>';
  const tags=unique([...list(f.visual_types),...list(f.experimental_techniques)]).slice(0,3);
  const status=f.status==="classified";
  return '<article class="figure-card" data-index="'+i+'" tabindex="0" role="button" aria-label="Open '+escapeHtml(caption(r))+'">'+
    '<div class="card-image">'+img+'</div><div class="card-body">'+
    '<div class="card-kicker"><span class="category-pill">'+escapeHtml(titleCase(f.paper_figure_category||"unclassified"))+'</span><span class="review-dot '+(f.needs_review?"":"ok")+'" title="'+(f.needs_review?"Needs review":"No review flagged")+'"></span></div>'+
    '<p class="card-caption">'+escapeHtml(caption(r))+'</p><div class="card-paper">'+escapeHtml(paperTitle(r))+'</div>'+
    '<div class="card-tags">'+tags.map(t=>'<span class="tag">'+escapeHtml(titleCase(t))+'</span>').join("")+'</div>'+
    '<div class="card-footer"><span>'+escapeHtml(r.journal||r.publication_year||"PMC article")+'</span><span class="arrow">↗</span></div>'+
    '</div></article>';
}

function renderActiveFilters() {
  const chips=[];
  Object.entries(state.filters).forEach(([key,values])=>values.forEach(value=>chips.push({key,value,label:titleCase(value)})));
  $("activeFilters").innerHTML=chips.map(c=>'<span class="active-chip">'+escapeHtml(c.label)+' <button data-remove="'+c.key+'" data-value="'+escapeHtml(c.value)+'" aria-label="Remove '+escapeHtml(c.label)+'">×</button></span>').join("");
}

function clearFilters() {
  Object.values(state.filters).forEach(s=>s.clear());
  state.query=""; $("searchInput").value="";
  renderFilters(); renderGallery();
}

function openDetail(r) {
  const f=fc(r), paper=pc(r);
  const tags=unique([...list(f.visual_types),...list(f.chart_types),...list(f.experimental_techniques),...list(f.visualization_purposes),...list(f.style_tags)]);
  const img=r.image_url ? '<img src="'+escapeHtml(r.image_url)+'" alt="'+escapeHtml(caption(r))+'">' : '<div class="image-placeholder">No local image available</div>';
  const panels=list(f.panels).map((p,i)=>'<div class="detail-section"><h3>Panel '+escapeHtml(p.panel_label||String(i+1))+'</h3><p>'+escapeHtml(p.description||"")+'</p></div>').join("");
  const doi=r.doi ? '<a class="source-link" href="https://doi.org/'+encodeURIComponent(r.doi)+'" target="_blank" rel="noreferrer">Open DOI ↗</a>' : "";
  const pmc=r.pmcid ? '<a class="source-link" href="https://pmc.ncbi.nlm.nih.gov/articles/'+encodeURIComponent(r.pmcid)+'/" target="_blank" rel="noreferrer">Open PMC ↗</a>' : "";
  $("detailContent").innerHTML='<div class="detail-grid"><div><div class="detail-visual">'+img+'</div><div class="detail-section"><h3>Figure caption</h3><p>'+escapeHtml(r.caption||"No caption was extracted.")+'</p></div>'+panels+'</div>'+
    '<div class="detail-info"><div class="detail-kicker">'+escapeHtml(titleCase(f.paper_figure_category||"Unclassified figure"))+'</div>'+
    '<h2 id="detailTitle">'+escapeHtml(paperTitle(r))+'</h2><div class="detail-paper">'+escapeHtml([r.journal,r.publication_year,r.figure_label||r.figure_id].filter(Boolean).join(" · "))+'</div>'+
    '<div class="detail-section"><h3>AI description</h3><p>'+escapeHtml(f.description||"No description available.")+'</p></div>'+
    '<div class="detail-section"><h3>Classification</h3><div class="detail-tags">'+tags.map(t=>'<span class="tag">'+escapeHtml(titleCase(t))+'</span>').join("")+'</div></div>'+
    '<div class="detail-section"><h3>Paper context</h3><div class="detail-meta">'+meta("Research fields",list(paper.research_fields).join(", ")||"—")+meta("Subfields",list(paper.subfields).join(", ")||"—")+meta("Panel count",f.panel_count??"—")+meta("Confidence",f.confidence==null?"—":Math.round(Number(f.confidence)*100)+"%")+meta("Needs review",f.needs_review?"Yes":"No")+meta("Technique",list(f.experimental_techniques).map(titleCase).join(", ")||"Not specified")+'</div></div>'+
    '<div class="detail-section"><h3>Source</h3><p>'+escapeHtml(r.doi||r.pmcid||"Source identifier unavailable")+'</p><div style="display:flex;gap:14px;margin-top:9px">'+doi+pmc+'</div></div>'+
    '<div class="detail-section"><h3>Model evidence</h3><p>'+escapeHtml(f.evidence||"No evidence note available.")+'</p></div></div></div>';
  $("detailBackdrop").classList.remove("hidden");
  document.body.style.overflow="hidden";
}
function meta(label,value){return '<div class="meta-item"><div class="meta-label">'+escapeHtml(label)+'</div><div class="meta-value">'+escapeHtml(value)+'</div></div>'}
function closeDetail(){$("detailBackdrop").classList.add("hidden");document.body.style.overflow=""}

document.addEventListener("change",e=>{
  const input=e.target.closest("input[data-filter]");
  if(input){const set=state.filters[input.dataset.filter];input.checked?set.add(input.value):set.delete(input.value);renderGallery();}
});
document.addEventListener("click",e=>{
  const cardEl=e.target.closest(".figure-card");
  if(cardEl){const visible=state.figures.filter(matches);let ordered=visible;if(state.sort==="title")ordered=[...visible].sort((a,b)=>paperTitle(a).localeCompare(paperTitle(b)));if(state.sort==="category")ordered=[...visible].sort((a,b)=>text(fc(a).paper_figure_category).localeCompare(text(fc(b).paper_figure_category)));openDetail(ordered[Number(cardEl.dataset.index)]);return;}
  const remove=e.target.closest("[data-remove]");
  if(remove){state.filters[remove.dataset.remove].delete(remove.dataset.value);renderFilters();renderGallery();}
});
document.addEventListener("keydown",e=>{
  if(e.key==="Escape")closeDetail();
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){e.preventDefault();$("searchInput").focus();}
  if(e.key==="Enter"&&e.target.classList.contains("figure-card"))e.target.click();
});
$("searchInput").addEventListener("input",e=>{state.query=e.target.value.trim();renderGallery();});
$("sortSelect").addEventListener("change",e=>{state.sort=e.target.value;renderGallery();});
$("clearFilters").addEventListener("click",clearFilters);
$("emptyClear").addEventListener("click",clearFilters);
$("refreshButton").addEventListener("click",loadFigures);
$("closeModal").addEventListener("click",closeDetail);
$("detailBackdrop").addEventListener("click",e=>{if(e.target===$("detailBackdrop"))closeDetail();});
loadFigures();
