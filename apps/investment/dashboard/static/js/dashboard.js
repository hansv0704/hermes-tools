/**
 * Alice AI 投資代理人 v3.0 — Dashboard JS
 * Tab: AI任務 / 紙上實驗室 | 右側: 兆豐帳戶
 */
const API = '/api';
const ST = {
  mission: null, paperMission: null, loopRunning: false, paperLoopRunning: false,
  holdings: [], decisions: [], account: null,
  paperHoldings: [], paperDecisions: [], paperAccount: null,
  megaLoggedIn: false
};
let charts = {};
let currentTab = 'ai';

// ═══ SSE ═══
function connectSSE() {
  const es = new EventSource(API + '/stream');
  es.onopen = () => logS('system', '已連接');
  es.addEventListener('mission_created', e => { const d=JSON.parse(e.data); if(currentTab==='ai') loadMission(d.mission.id); loadMissionList(); loadPaperList(); });
  es.addEventListener('mission_deleted', e => { const d=JSON.parse(e.data); if(ST.mission&&ST.mission.id===d.mission_id){ST.mission=null;renderEmptyMission();loadMissionList();} if(ST.paperMission&&ST.paperMission.id===d.mission_id){ST.paperMission=null;renderEmptyPaper();loadPaperList();} });
  es.addEventListener('loop_started', () => { if(currentTab==='ai') updateLoopChip(true); });
  es.addEventListener('loop_stopped', () => { if(currentTab==='ai') updateLoopChip(false); });
  es.addEventListener('order_executed', e => { if(currentTab==='ai') refreshAI(); else refreshPaper(); });
  es.addEventListener('mega_login', e => { const d=JSON.parse(e.data); if(d.status==='success'){updateMegaChip(true);refreshMega();logS('mega','兆豐登入成功');} });
  es.addEventListener('mega_logout', () => { updateMegaChip(false); logS('mega','兆豐已登出'); });
  es.onerror = () => { es.close(); setTimeout(connectSSE, 5000); };
}
function logS(type, msg) {
  const el = document.getElementById('logStream'), t = new Date().toLocaleTimeString('zh-TW',{hour12:false});
  el.innerHTML = `<div class="ll"><span class="ts">${t}</span>${msg}</div>` + el.innerHTML;
  if (el.children.length > 40) el.lastChild.remove();
}

// ═══ API ═══
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (!r.ok) { const e = await r.json().catch(()=>({detail:r.statusText})); throw new Error(e.detail||'API error'); }
  return r.json();
}

// ═══ Tabs ═══
function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.id === 'tab-' + tab));
  if (tab === 'ai' && !ST.mission) { loadActiveMission(); loadMissionList(); }
  if (tab === 'paper' && !ST.paperMission) { loadPaperList(); }
}

// ═══ AI Mission ═══
async function loadMissionList() {
  try {
    const d = await api('GET', '/missions?limit=50');
    const sel = document.getElementById('selMission'), cur = sel.value;
    sel.innerHTML = '<option value="">選擇任務...</option>';
    (d.missions||[]).forEach(m => {
      const mode = m.mode === 'paper' ? '📝' : '🏦';
      sel.innerHTML += `<option value="${m.id}" ${String(m.id)===cur?'selected':''}>${mode} #${m.id} ${m.name||''}</option>`;
    });
  } catch(e) {}
}
async function switchMission(id) {
  if (!id) { ST.mission = null; renderEmptyMission(); return; }
  await loadMission(parseInt(id));
}
async function loadActiveMission() {
  try {
    const d = await api('GET', '/missions/active');
    if (d.mission) { ST.mission = d.mission; renderMission(); await refreshAI(); updateLoopStatus(); }
    else renderEmptyMission();
    await loadMissionList();
  } catch(e) { console.error(e); }
}
async function loadMission(id) {
  const d = await api('GET', '/missions/' + id);
  ST.mission = d.mission; renderMission(); await refreshAI(); updateLoopStatus();
  await loadMissionList();
}
function renderMission() {
  const m = ST.mission;
  const modeLabel = m.mode === 'paper' ? '<span class="mode-badge mode-paper">📝 紙上</span>' : '<span class="mode-badge mode-live">🏦 實盤</span>';
  document.getElementById('cardMission').innerHTML = `
    <div class="card-header"><span class="icon">🎯</span><h3>${m.name||'任務'} ${modeLabel}</h3>
      <span class="tag ${m.status==='active'?'tag-buy':'tag-sell'}" style="margin-left:auto">${m.status}</span>
    </div>
    <div class="progress-ring-wrap">
      <div class="progress-ring"><svg viewBox="0 0 90 90"><defs><linearGradient id="prGrad" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#6366f1"/><stop offset="100%" stop-color="#8b5cf6"/></linearGradient></defs>
      <circle class="bg" cx="45" cy="45" r="39"/><circle class="fill" id="prFill" cx="45" cy="45" r="39" stroke-dasharray="245" stroke-dashoffset="245"/></svg>
      <div class="center" id="prPct">0%</div></div>
      <div class="progress-info">
        <div class="pi-row"><span style="color:var(--text-muted)">起始資金</span><strong>NT$ ${(m.budget||0).toLocaleString()}</strong></div>
        <div class="pi-row"><span style="color:var(--text-muted)">目前資產</span><strong style="color:var(--accent)">NT$ ${(m.total_asset||0).toLocaleString()}</strong></div>
        <div class="pi-row"><span style="color:var(--text-muted)">目標金額</span><strong>NT$ ${(m.target_amount||0).toLocaleString()}</strong></div>
        <div class="pi-row"><span style="color:var(--text-muted)">截止日期</span><strong>${(m.deadline||'').slice(0,10)}</strong></div>
        <div class="pi-row"><span style="color:var(--text-muted)">交易模式</span><strong>${m.mode==='paper'?'📝 紙上交易':'🏦 實盤交易'}</strong></div>
      </div></div>`;
  const pct = m.target_amount > 0 ? Math.min(100, (m.total_asset/m.target_amount)*100) : 0;
  setTimeout(() => { const f=document.getElementById('prFill'); if(f) f.style.strokeDashoffset = 245*(1-pct/100); document.getElementById('prPct').textContent = pct.toFixed(0)+'%'; }, 100);
  document.getElementById('mAI_asset').textContent = 'NT$ '+(m.total_asset||0).toLocaleString();
  const pnl = m.start_pnl||0;
  document.getElementById('mAI_pnl').textContent = (pnl>=0?'+':'')+'NT$ '+pnl.toLocaleString();
  document.getElementById('mAI_pnl').className = 'value '+(pnl>=0?'green':'red');
  document.getElementById('mAI_pnlpct').textContent = (m.start_pnl_pct>=0?'+':'')+(m.start_pnl_pct||0).toFixed(2)+'%';
  document.getElementById('mAI_pnlpct').className = 'sub '+(pnl>=0?'green':'red');
  document.getElementById('btnLoop').disabled = (m.status !== 'active');
}
function renderEmptyMission() {
  ST.mission = null;
  document.getElementById('cardMission').innerHTML = '<div class="card-header"><span class="icon">🎯</span><h3>任務進度</h3></div><div class="empty"><span class="icon">📋</span><p>尚未建立任務<br><span class="text-xs">點擊 ＋ 開始 AI 自主投資</span></p></div>';
  document.getElementById('mAI_asset').textContent='-';document.getElementById('mAI_pnl').textContent='-';document.getElementById('mAI_pos').textContent='0';document.getElementById('mAI_cycles').textContent='0';
  document.getElementById('btnLoop').disabled=true;updateLoopChip(false);
  document.getElementById('aiHoldingsBody').innerHTML='<tr><td colspan="6"><div class="empty"><p>尚無 AI 持倉</p></div></td></tr>';
  document.getElementById('decisionFeed').innerHTML='<div class="empty"><p>等待 AI 開始思考…</p></div>';
}
async function refreshAI() {
  if (!ST.mission) return; const mid = ST.mission.id;
  try {
    const [acc, dec, lp] = await Promise.all([
      api('GET','/missions/'+mid+'/account'), api('GET','/missions/'+mid+'/decisions?limit=25'), api('GET','/missions/'+mid+'/loop/status')
    ]);
    ST.account=acc.account;ST.holdings=acc.account.positions||[];ST.decisions=dec.decisions||[];
    document.getElementById('mAI_pos').textContent=ST.holdings.length;
    document.getElementById('mAI_cycles').textContent=lp.loop.cycle_count||0;
    updateLoopChip(lp.loop.running);
    renderAIHoldings();renderDecisions('decisionFeed',ST.decisions);renderChart('chartAsset',ST.account,ST.mission);
  } catch(e) { console.error(e); }
}
function renderAIHoldings() {
  const b=document.getElementById('aiHoldingsBody');document.getElementById('aiPosCount').textContent=(ST.holdings.length||0)+' 檔';
  if (!ST.holdings.length) { b.innerHTML='<tr><td colspan="6"><div class="empty"><p>尚無 AI 持倉</p></div></td></tr>'; return; }
  b.innerHTML=ST.holdings.map(p=>`<tr><td class="sym">${p.symbol}</td><td style="color:var(--text-dim);font-size:11px">${p.name||''}</td><td>${(p.shares||0).toLocaleString()}</td><td>${(p.avg_cost||0).toFixed(1)}</td><td>${(p.current_price||0).toFixed(1)}</td><td class="pnl ${(p.pnl||0)>=0?'green':'red'}">${(p.pnl||0)>=0?'+':''}${(p.pnl||0).toLocaleString()} <span style="font-size:10px">${(p.pnl_pct||0).toFixed(1)}%</span></td></tr>`).join('');
}

// ═══ Paper Lab ═══
async function loadPaperList() {
  try {
    const d = await api('GET', '/missions?limit=50');
    const sel = document.getElementById('selPaperMission'), cur = sel.value;
    sel.innerHTML = '<option value="">選擇實驗...</option>';
    (d.missions||[]).forEach(m => { sel.innerHTML += `<option value="${m.id}" ${String(m.id)===cur?'selected':''}>📝 #${m.id} ${m.name||''}</option>`; });
  } catch(e) {}
}
async function switchPaperMission(id) {
  if (!id) { ST.paperMission=null; renderEmptyPaper(); return; }
  const d = await api('GET', '/missions/'+parseInt(id));
  ST.paperMission = d.mission; renderPaper(); await refreshPaper(); updatePaperLoopStatus();
}
function renderEmptyPaper() {
  ST.paperMission=null;
  document.getElementById('cardPaperMission').innerHTML='<div class="card-header"><span class="icon">🔬</span><h3>實驗進度</h3></div><div class="empty"><span class="icon">🧪</span><p>尚未建立紙上實驗</p></div>';
  document.getElementById('mP_asset').textContent='-';document.getElementById('mP_pnl').textContent='-';document.getElementById('mP_pos').textContent='0';document.getElementById('mP_cycles').textContent='0';
  document.getElementById('btnPaperLoop').disabled=true;updatePaperLoopChip(false);
  document.getElementById('paperHoldingsBody').innerHTML='<tr><td colspan="6"><div class="empty"><p>尚無持倉</p></div></td></tr>';
  document.getElementById('paperDecisionFeed').innerHTML='<div class="empty"><p>等待 AI 開始思考…</p></div>';
}
function renderPaper() {
  const m=ST.paperMission;
  document.getElementById('cardPaperMission').innerHTML=`
    <div class="card-header"><span class="icon">🔬</span><h3>${m.name||'實驗'} <span class="mode-badge mode-paper">📝 紙上</span></h3><span class="tag ${m.status==='active'?'tag-buy':'tag-sell'}" style="margin-left:auto">${m.status}</span></div>
    <div class="progress-ring-wrap"><div class="progress-ring"><svg viewBox="0 0 90 90"><defs><linearGradient id="prGradP" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#f59e0b"/><stop offset="100%" stop-color="#f97316"/></linearGradient></defs><circle class="bg" cx="45" cy="45" r="39"/><circle class="fill" id="prFillP" cx="45" cy="45" r="39" stroke-dasharray="245" stroke-dashoffset="245"/></svg><div class="center" id="prPctP">0%</div></div>
    <div class="progress-info"><div class="pi-row"><span style="color:var(--text-muted)">起始資金</span><strong>NT$ ${(m.budget||0).toLocaleString()}</strong></div>
    <div class="pi-row"><span style="color:var(--text-muted)">目前資產</span><strong style="color:var(--amber)">NT$ ${(m.total_asset||0).toLocaleString()}</strong></div>
    <div class="pi-row"><span style="color:var(--text-muted)">目標金額</span><strong>NT$ ${(m.target_amount||0).toLocaleString()}</strong></div>
    <div class="pi-row"><span style="color:var(--text-muted)">截止日期</span><strong>${(m.deadline||'').slice(0,10)}</strong></div></div></div>`;
  const pct=m.target_amount>0?Math.min(100,(m.total_asset/m.target_amount)*100):0;
  setTimeout(()=>{const f=document.getElementById('prFillP');if(f)f.style.strokeDashoffset=245*(1-pct/100);document.getElementById('prPctP').textContent=pct.toFixed(0)+'%'},100);
  document.getElementById('mP_asset').textContent='NT$ '+(m.total_asset||0).toLocaleString();
  const pnl=m.start_pnl||0;document.getElementById('mP_pnl').textContent=(pnl>=0?'+':'')+'NT$ '+pnl.toLocaleString();
  document.getElementById('mP_pnl').className='value '+(pnl>=0?'green':'red');
  document.getElementById('mP_pnlpct').textContent=(m.start_pnl_pct>=0?'+':'')+(m.start_pnl_pct||0).toFixed(2)+'%';
  document.getElementById('btnPaperLoop').disabled=(m.status!=='active');
}
async function refreshPaper() {
  if (!ST.paperMission) return; const mid=ST.paperMission.id;
  try {
    const [acc,dec,lp]=await Promise.all([api('GET','/missions/'+mid+'/account'),api('GET','/missions/'+mid+'/decisions?limit=25'),api('GET','/missions/'+mid+'/loop/status')]);
    ST.paperAccount=acc.account;ST.paperHoldings=acc.account.positions||[];ST.paperDecisions=dec.decisions||[];
    document.getElementById('mP_pos').textContent=ST.paperHoldings.length;document.getElementById('mP_cycles').textContent=lp.loop.cycle_count||0;
    updatePaperLoopChip(lp.loop.running);
    renderPaperHoldings();renderDecisions('paperDecisionFeed',ST.paperDecisions);renderChart('chartPaper',ST.paperAccount,ST.paperMission);
  } catch(e) { console.error(e); }
}
function renderPaperHoldings() {
  const b=document.getElementById('paperHoldingsBody');document.getElementById('paperPosCount').textContent=(ST.paperHoldings.length||0)+' 檔';
  if(!ST.paperHoldings.length){b.innerHTML='<tr><td colspan="6"><div class="empty"><p>尚無持倉</p></div></td></tr>';return;}
  b.innerHTML=ST.paperHoldings.map(p=>`<tr><td class="sym">${p.symbol}</td><td style="color:var(--text-dim);font-size:11px">${p.name||''}</td><td>${(p.shares||0).toLocaleString()}</td><td>${(p.avg_cost||0).toFixed(1)}</td><td>${(p.current_price||0).toFixed(1)}</td><td class="pnl ${(p.pnl||0)>=0?'green':'red'}">${(p.pnl||0)>=0?'+':''}${(p.pnl||0).toLocaleString()} <span style="font-size:10px">${(p.pnl_pct||0).toFixed(1)}%</span></td></tr>`).join('');
}

// ═══ Decisions ═══
function renderDecisions(elId, list) {
  const el=document.getElementById(elId);if(!list.length){el.innerHTML='<div class="empty"><p>等待 AI 開始思考…</p></div>';return;}
  const icons={Scout:'🔍',Analyst:'📊',Risk:'⚠️',Executor:'💰',Reflector:'📈',System:'⚙️'};
  const cls={Scout:'dec-scout',Analyst:'dec-analyst',Risk:'dec-risk',Executor:'dec-exec',Reflector:'dec-reflect',System:'dec-system'};
  el.innerHTML=list.slice(0,20).map(d=>`<div class="dec-item"><div class="dec-icon ${cls[d.role]||'dec-system'}">${icons[d.role]||'•'}</div><div class="dec-body"><div class="dec-role">${d.role||'System'}</div><div class="dec-msg">${d.summary||''}</div><div class="dec-time">${(d.created_at||'').slice(11,19)}</div></div></div>`).join('');
}

// ═══ Charts ═══
function renderChart(canvasId, account, mission) {
  const ctx=document.getElementById(canvasId).getContext('2d');
  const key=canvasId==='chartAsset'?'asset':'paper';
  if(charts[key]) charts[key].destroy();
  const total=account?.total_asset||mission?.total_asset||0,budget=mission?.budget||0;
  charts[key]=new Chart(ctx,{type:'line',data:{labels:['起始','現在'],datasets:[{label:'總資產',data:[budget,total],borderColor:canvasId==='chartAsset'?'#6366f1':'#f59e0b',backgroundColor:canvasId==='chartAsset'?'rgba(99,102,241,0.08)':'rgba(245,158,11,0.08)',fill:true,tension:0.4,pointRadius:5}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#58627a'},grid:{color:'rgba(255,255,255,0.03)'}},y:{ticks:{color:'#58627a',callback:v=>'NT$ '+v.toLocaleString()},grid:{color:'rgba(255,255,255,0.03)'}}}}});
}

// ═══ Loop ═══
async function toggleLoop() { if(!ST.mission)return;const mid=ST.mission.id;ST.loopRunning?await api('POST','/missions/'+mid+'/loop/stop'):await api('POST','/missions/'+mid+'/loop/start?interval_minutes=15'); }
async function togglePaperLoop() { if(!ST.paperMission)return;const mid=ST.paperMission.id;ST.paperLoopRunning?await api('POST','/missions/'+mid+'/loop/stop'):await api('POST','/missions/'+mid+'/loop/start?interval_minutes=15'); }
function updateLoopChip(r) { ST.loopRunning=r;document.getElementById('chipLoop').className='status-chip '+(r?'chip-live':'chip-offline');document.getElementById('chipLoopText').textContent=r?'AI 運行中':'待命';document.getElementById('btnLoop').textContent=r?'⏸':'▶';document.getElementById('btnLoop').className='btn btn-xs '+(r?'btn-outline':'btn-success'); }
function updatePaperLoopChip(r) { ST.paperLoopRunning=r;document.getElementById('chipPaperLoop').className='status-chip '+(r?'chip-live':'chip-offline');document.getElementById('chipPaperLoopText').textContent=r?'運行中':'待命';document.getElementById('btnPaperLoop').textContent=r?'⏸':'▶';document.getElementById('btnPaperLoop').className='btn btn-xs '+(r?'btn-outline':'btn-success'); }
async function updateLoopStatus() { if(!ST.mission)return;try{const d=await api('GET','/missions/'+ST.mission.id+'/loop/status');updateLoopChip(d.loop.running);}catch(e){updateLoopChip(false);} }
async function updatePaperLoopStatus() { if(!ST.paperMission)return;try{const d=await api('GET','/missions/'+ST.paperMission.id+'/loop/status');updatePaperLoopChip(d.loop.running);}catch(e){updatePaperLoopChip(false);} }

// ═══ MEGA ═══
async function checkMegaStatus() { try { const d=await api('GET','/mega/status'); if(d.mega&&d.mega.logged_in){updateMegaChip(true);refreshMega();} } catch(e) {} }
function updateMegaChip(loggedIn) { ST.megaLoggedIn=loggedIn;document.getElementById('chipMega').className='status-chip '+(loggedIn?'chip-online':'chip-offline');document.getElementById('chipMegaText').textContent=loggedIn?'兆豐已連線':'兆豐未登入';document.getElementById('btnMegaLogin').textContent=loggedIn?'登出':'登入';document.getElementById('btnMegaLogin').onclick=loggedIn?doMegaLogout:showMegaLogin; }
async function refreshMega() { if(!ST.megaLoggedIn)return;try{const[acct,pos]=await Promise.all([api('GET','/mega/account'),api('GET','/mega/positions')]);const a=acct.account;document.getElementById('cardMegaAcct').innerHTML=`<div class="card-header"><span class="icon">💳</span><h3>帳戶總覽</h3></div><div class="metrics-3" style="margin-bottom:0"><div class="metric"><div class="label">持股市值</div><div class="value">NT$ ${(a.market_value||0).toLocaleString()}</div></div><div class="metric"><div class="label">未實現損益</div><div class="value ${(a.pnl||0)>=0?'green':'red'}">${(a.pnl||0)>=0?'+':''}NT$ ${(a.pnl||0).toLocaleString()}</div></div><div class="metric"><div class="label">持股檔數</div><div class="value">${(a.positions||[]).length}</div></div></div>`;document.getElementById('megaPosCount').textContent=(pos.positions||[]).length+' 檔';const b=document.getElementById('megaHoldingsBody');if(!pos.positions||!pos.positions.length){b.innerHTML='<tr><td colspan="6"><div class="empty"><p>尚無持倉</p></div></td></tr>'}else{b.innerHTML=pos.positions.map(p=>`<tr><td class="sym">${p.symbol}</td><td style="color:var(--text-dim);font-size:11px">${p.name||''}</td><td>${(p.shares||0).toLocaleString()}</td><td>${(p.avg_cost||0).toFixed(1)}</td><td>${(p.current_price||0).toFixed(1)}</td><td class="pnl ${(p.pnl||0)>=0?'green':'red'}">${(p.pnl||0)>=0?'+':''}${(p.pnl||0).toLocaleString()} <span style="font-size:10px">${(p.pnl_pct||0).toFixed(1)}%</span></td></tr>`).join('')}}catch(e){console.error(e)}}

// ═══ MEGA Login ═══
function showMegaLogin() { document.getElementById('modalMega').classList.add('active');api('GET','/mega/credentials').then(d=>{if(d.status==='success'){document.getElementById('mUserID').value=d.user_id||'';document.getElementById('mAccount').value=d.account||'';document.getElementById('mBrokerID').value=d.broker_id||''}}).catch(()=>{}); }
function closeMegaModal() { document.getElementById('modalMega').classList.remove('active'); }
async function doMegaLogin() { const body={user_id:document.getElementById('mUserID').value,password:document.getElementById('mPassword').value,account:document.getElementById('mAccount').value,broker_id:document.getElementById('mBrokerID').value,pfx_password:document.getElementById('mPfxPwd').value};if(!body.user_id||!body.password||!body.account||!body.pfx_password){alert('請填寫所有欄位');return;}try{const d=await api('POST','/mega/login',body);if(d.status==='success'){closeMegaModal();updateMegaChip(true);refreshMega()}else{alert('登入失敗: '+(d.message||'未知'))}}catch(e){alert('登入失敗: '+e.message)} }
async function doMegaLogout() { await api('POST','/mega/logout');updateMegaChip(false);document.getElementById('cardMegaAcct').innerHTML='<div class="card-header"><span class="icon">💳</span><h3>帳戶總覽</h3></div><div class="empty"><span class="icon">🔐</span><p>請先登入兆豐</p></div>';document.getElementById('megaHoldingsBody').innerHTML='<tr><td colspan="6"><div class="empty"><p>請先登入兆豐</p></div></td></tr>'; }

// ═══ Mission Modal ═══
function showNewMission() { document.getElementById('modalMission').classList.add('active');const d=new Date();d.setDate(d.getDate()+30);document.getElementById('fDeadline').value=d.toISOString().slice(0,10); }
function showNewPaperMission() { showNewMission();document.getElementById('fMode').value='paper'; }
function closeMissionModal() { document.getElementById('modalMission').classList.remove('active'); }
async function createMission() {
  const body = {
    name: document.getElementById('fName').value || '自主投資任務',
    description: document.getElementById('fDesc').value,
    budget: parseFloat(document.getElementById('fBudget').value),
    target_amount: parseFloat(document.getElementById('fTarget').value),
    deadline: document.getElementById('fDeadline').value + 'T23:59:59',
    risk_level: document.getElementById('fRisk').value,
    mode: document.getElementById('fMode').value || 'paper',
    config: {
      buy_score: parseInt(document.getElementById('fBuyScore').value) || 60,
      stop_loss: parseFloat(document.getElementById('fStopLoss').value) || 5,
      take_profit: parseFloat(document.getElementById('fTakeProfit').value) || 12,
      max_positions: parseInt(document.getElementById('fMaxPos').value) || 5,
      max_single_pct: parseInt(document.getElementById('fMaxSingle').value) || 25,
      interval_minutes: parseInt(document.getElementById('fInterval').value) || 15,
    }
  };
  if (!body.budget || !body.target_amount || !body.deadline) { alert('請填寫所有必填欄位'); return; }
  try {
    const d = await api('POST', '/missions', body);
    closeMissionModal();
    if (body.mode === 'paper' && currentTab === 'paper') {
      ST.paperMission = d.mission; renderPaper(); refreshPaper(); updatePaperLoopStatus();
      document.getElementById('selPaperMission').value = d.mission.id;
    } else if (currentTab === 'ai') {
      ST.mission = d.mission; renderMission(); refreshAI(); updateLoopStatus();
      document.getElementById('selMission').value = d.mission.id;
    }
    loadMissionList(); loadPaperList();
  } catch (e) { alert('建立失敗: ' + e.message); }
}

// ═══ Export log ═══
function exportPaperLog() {
  if (!ST.paperMission || !ST.paperDecisions.length) { alert('尚無日誌可匯出'); return; }
  let csv = '時間,角色,動作,摘要\n';
  ST.paperDecisions.forEach(d => {
    csv += `"${d.created_at||''}","${d.role||''}","${d.action||''}","${(d.summary||'').replace(/"/g,'""')}"\n`;
  });
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = `paper_log_${ST.paperMission.id}_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  logS('system', '日誌已匯出');
}
async function deleteMission() { if(!ST.mission)return;if(!confirm('確定清除任務「'+(ST.mission.name||'')+'」？此操作無法復原。'))return;try{await api('DELETE','/missions/'+ST.mission.id);ST.mission=null;renderEmptyMission();loadMissionList();loadPaperList()}catch(e){alert('清除失敗: '+e.message)} }
async function deletePaperMission() { if(!ST.paperMission)return;if(!confirm('確定清除實驗「'+(ST.paperMission.name||'')+'」？'))return;try{await api('DELETE','/missions/'+ST.paperMission.id);ST.paperMission=null;renderEmptyPaper();loadMissionList();loadPaperList()}catch(e){alert('清除失敗: '+e.message)} }

// ═══ Init ═══
function init() { connectSSE();loadActiveMission();loadPaperList();checkMegaStatus();setInterval(()=>{if(ST.mission&&currentTab==='ai')refreshAI();if(ST.paperMission&&currentTab==='paper')refreshPaper();if(ST.megaLoggedIn)refreshMega()},30000); }
document.addEventListener('DOMContentLoaded', init);
['modalMission','modalMega'].forEach(id=>{document.getElementById(id).addEventListener('click',function(e){if(e.target===this)this.classList.remove('active')})});
