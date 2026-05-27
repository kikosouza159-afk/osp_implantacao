function setView(name){
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById(name).classList.add('active');
  const tab=document.querySelector(`.tab[data-view="${name}"]`);
  if(tab) tab.classList.add('active');
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>setView(t.dataset.view));
document.querySelectorAll('[data-view-target]').forEach(b=>b.onclick=()=>setView(b.dataset.viewTarget));

function openModal(){document.getElementById('projectForm').reset();document.getElementById('projectForm').action='/projeto/novo';document.getElementById('modalTitle').innerText='Novo Projeto';document.getElementById('projectModal').classList.add('open')}
function closeModal(){document.getElementById('projectModal').classList.remove('open')}

function toInputDate(value){
  if(!value || value==='(vazio)') return '';
  const p=value.split('/');
  if(p.length===3) return `${p[2]}-${p[1]}-${p[0]}`;
  return value;
}

function editProject(p){
  openModal();
  document.getElementById('modalTitle').innerText='Editar Projeto';
  document.getElementById('projectForm').action=`/projeto/${p.id}/editar`;
  ['produto','projeto','org','cliente','carteira','etapa_atual','situacao'].forEach(k=>{
    const el=document.getElementById(k); if(el) el.value=p[k]||'';
  });
  document.getElementById('inicio_poc').value=toInputDate(p.inicio_poc);
  document.getElementById('prazo_final_poc').value=toInputDate(p.prazo_final_poc);
  document.getElementById('data_alvo_faturamento').value=toInputDate(p.data_alvo_faturamento);
}

function applyFilter(type,value){
  document.querySelectorAll('.data-table tbody tr').forEach(row=>{
    row.style.display = row.dataset[type]===value ? '' : 'none';
  });
}
document.querySelectorAll('[data-filter-produto]').forEach(c=>c.onclick=()=>applyFilter('produto',c.dataset.filterProduto));
document.querySelectorAll('[data-filter-etapa]').forEach(c=>c.onclick=()=>applyFilter('etapa',c.dataset.filterEtapa));
