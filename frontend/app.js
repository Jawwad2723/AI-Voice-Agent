const API = '';

const SCENARIO_LABELS = {
  appointment_reminder: 'Appt Reminder',
  lead_qualification: 'Lead Qual',
  customer_survey: 'Survey',
  payment_followup: 'Payment',
  event_confirmation: 'Event Conf'
};

const AGENT_IDENTITIES = {
  appointment_reminder: { name: 'Aria', label: '🏥 Appointment Reminder' },
  lead_qualification: { name: 'Ethan', label: '🎯 Lead Qual' },
  customer_survey: { name: 'Chloe', label: '📊 Customer Survey' },
  payment_followup: { name: 'Marcus', label: '💳 Payment Follow-up' },
  event_confirmation: { name: 'David', label: '🎟️ Event Conf' }
};

let calls = [];
let activeCallId = null;

// ── Boot ──
document.addEventListener('DOMContentLoaded', async () => {
  await checkHealth();
  await loadCalls();
  // Poll every 1.5 seconds for snappy updates
  setInterval(loadCalls, 1500);
});

// ── Health ──
async function checkHealth() {
  const dot  = document.getElementById('sdot');
  const stxt = document.getElementById('stxt');
  const warn = document.getElementById('warn');

  try {
    const r = await fetch(`${API}/api/health`);
    const d = await r.json();

    const allOk = d.status === 'healthy' && d.deepgram_configured && d.elevenlabs_configured;

    dot.className  = 'sdot ' + (allOk ? 'on' : 'err');
    stxt.textContent = allOk ? 'Pipeline Ready' : 'Partially Configured';

    // update chips
    setChip('chip-dg',  d.deepgram_configured,  'Deepgram');
    setChip('chip-el',  d.elevenlabs_configured, 'ElevenLabs');
    setChip('chip-llm', true,                    d.llm_model ? 'Qwen' : 'LLM');

    if (!allOk) {
      warn.style.display = 'flex';
      warn.querySelector('.w-msg').textContent =
        !d.deepgram_configured   ? 'Set DEEPGRAM_API_KEY in .env' :
        !d.elevenlabs_configured ? 'Set ELEVENLABS_API_KEY in .env' : 'Check your .env configuration';
    } else {
      warn.style.display = 'none';
    }
  } catch {
    dot.className = 'sdot err';
    stxt.textContent = 'Backend Offline';
    warn.style.display = 'flex';
    warn.querySelector('.w-msg').textContent = 'Run: uvicorn main:app --reload in /backend';
  }
}

function setChip(id, ok, label) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = 'chip ' + (ok ? 'ok' : 'err');
  el.querySelector('.chip-lbl').textContent = label;
}

// ── Load Calls & Monitor ──
async function loadCalls() {
  try {
    const r = await fetch(`${API}/api/calls/`);
    const d = await r.json();
    calls = d.calls || [];
    renderTable(calls);
    updateLiveMonitor(calls);
  } catch (err) {
    console.error("Error polling calls:", err);
  }
}

function updateLiveMonitor(callList) {
  // Find first active/live call (ringing or in-progress)
  const activeCall = callList.find(c => ['ringing', 'in-progress', 'initiated'].includes(c.status));
  
  const activePanel = document.getElementById('monitor-active');
  const idlePanel = document.getElementById('monitor-idle');
  const indicator = document.getElementById('live-indicator');
  const statusText = document.getElementById('live-status-text');

  if (!activeCall) {
    activePanel.style.display = 'none';
    idlePanel.style.display = 'block';
    indicator.classList.remove('active');
    statusText.textContent = 'NO ACTIVE CALL';
    activeCallId = null;
    return;
  }

  // Active call detected!
  activeCallId = activeCall.call_id;
  activePanel.style.display = 'block';
  idlePanel.style.display = 'none';
  indicator.classList.add('active');
  statusText.textContent = activeCall.status.toUpperCase();

  // Update Stats
  const identity = AGENT_IDENTITIES[activeCall.scenario_type] || { name: 'AI Bot', label: activeCall.scenario_type };
  document.getElementById('m-scenario').textContent = identity.label;
  document.getElementById('m-agent').textContent = identity.name;
  document.getElementById('m-caller').textContent = activeCall.customer_name === "Inbound Caller" 
    ? `Incoming (${activeCall.phone_number})`
    : `${activeCall.customer_name} (${activeCall.phone_number})`;

  // Calculate & show live duration
  const start = new Date(activeCall.started_at);
  const diffSecs = Math.max(0, Math.floor((new Date() - start) / 1000));
  const mins = Math.floor(diffSecs / 60);
  const secs = diffSecs % 60;
  document.getElementById('m-duration').textContent = `${mins}:${secs.toString().padStart(2, '0')}`;

  // Update live transcript feed
  const feedEl = document.getElementById('live-transcript-feed');
  if (activeCall.transcript) {
    const lines = activeCall.transcript.split('\n').filter(Boolean);
    const scrollAtBottom = feedEl.scrollHeight - feedEl.clientHeight <= feedEl.scrollTop + 40;
    
    feedEl.innerHTML = lines.map(line => {
      const isAgent = line.startsWith('Agent:');
      const role = isAgent ? 'agent' : 'user';
      const label = isAgent ? `🤖 ${identity.name}` : '👤 Caller';
      const text = line.replace(/^(Agent|User):\s*/, '');
      return `<div class="live-t-line role-${role}">
        <div class="live-t-role ${role}">${label}</div>
        <div class="live-t-text">${esc(text)}</div>
      </div>`;
    }).join('');

    // Auto-scroll if user wasn't scrolling up to read
    if (scrollAtBottom || feedEl.innerHTML.includes('live-t-line')) {
      feedEl.scrollTop = feedEl.scrollHeight;
    }
  } else {
    feedEl.innerHTML = `<div style="color:var(--text3); font-size:12px; font-family:var(--mono);">Awaiting conversation feed...</div>`;
  }
}

function renderTable(list) {
  const el = document.getElementById('calls-list');
  if (!list.length) {
    el.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div>No calls yet. Dial 5001 on Zoiper to begin.</div>`;
    return;
  }
  
  // Sort descending by start time
  const sorted = [...list].sort((a, b) => new Date(b.started_at) - new Date(a.started_at));

  el.innerHTML = `<table>
    <thead><tr><th>Customer</th><th>Scenario</th><th>Status</th><th>Time</th></tr></thead>
    <tbody>${sorted.map(c => `
      <tr onclick="showDetail('${c.call_id}')">
        <td><div class="t-name">${esc(c.customer_name)}</div><div class="t-num">${esc(c.phone_number)}</div></td>
        <td><span class="t-scen">${SCENARIO_LABELS[c.scenario_type] || c.scenario_type}</span></td>
        <td>${badge(c.status)}</td>
        <td class="t-time">${fmtTime(c.started_at)}</td>
      </tr>`).join('')}
    </tbody></table>`;
}

function badge(s) {
  const labels = {
    initiated: 'Initiated',
    ringing: 'Ringing',
    'in-progress': 'Live',
    in_progress: 'Live',
    completed: 'Completed',
    failed: 'Failed',
    'no-answer': 'No Answer',
    busy: 'Busy'
  };
  const cls = (s || '').replace('_', '-');
  return `<span class="badge ${cls}"><span class="bdot"></span>${labels[s] || s}</span>`;
}

// ── Detail Card ──
async function showDetail(id) {
  try {
    // Try to fetch from database first
    let c = null;
    try {
      const dbResponse = await fetch(`${API}/api/calls/history/${id}`);
      if (dbResponse.ok) {
        c = await dbResponse.json();
      }
    } catch(e) {
      console.warn("Database fetch failed, falling back to call list data");
    }
    
    // Fallback: find call from current list
    if (!c) {
      c = calls.find(call => call.call_id === id);
    }
    
    if (!c) {
      toast('error','Error','Call not found');
      return;
    }
    
    const panel = document.getElementById('detail-card');
    panel.classList.add('open');

    document.getElementById('d-title').textContent = `${c.caller_name || c.customer_name || 'Caller'} — ${c.phone_number || c.caller_number}`;

    // Build metadata fields - from database if available
    const metadata = [
      ['Call ID',       c.call_id ? c.call_id.slice(0,16) + '…' : '—'],
      ['Status',        badge(c.call_status || c.status)],
      ['Scenario',      c.scenario_type || '—'],
      ['Bot Name',      c.bot_name || '—'],
      ['Voice ID',      c.bot_voice_id ? c.bot_voice_id.slice(0,16) + '…' : '—'],
      ['Started',       fmtTime(c.started_at || c.created_at)],
      ['Duration',      c.duration_seconds ? Math.round(c.duration_seconds) + 's' : (c.duration_seconds !== null ? c.duration_seconds + 's' : '—')],
      ['Goal Achieved', c.goal_achieved ? '✓ Yes' : '✗ No'],
      ['Recording',     c.recording_path ? '📁 ' + c.recording_path.split('/').pop() : '—'],
    ];
    
    document.getElementById('d-meta').innerHTML = metadata.map(([l,v]) => 
      `<div class="d-meta-item"><label>${l}</label><div class="val">${v}</div></div>`
    ).join('');

    const tb = document.getElementById('d-transcript');
    const identity = AGENT_IDENTITIES[c.scenario_type] || { name: 'Agent' };
    if (c.transcript) {
      const lines = c.transcript.split('\n').filter(Boolean);
      tb.innerHTML = lines.map(line => {
        const isAgent = line.startsWith('Agent:');
        const role  = isAgent ? 'agent' : 'user';
        const label = isAgent ? `🤖 ${identity.name}` : '👤 Caller';
        const text  = line.replace(/^(Agent|User):\s*/, '');
        return `<div class="t-line"><span class="role-${role}">${label}:</span> ${esc(text)}</div>`;
      }).join('');
    } else {
      tb.innerHTML = '<div style="color:var(--text3);font-size:12px;font-family:var(--mono)">No transcript yet.</div>';
    }

    panel.scrollIntoView({ behavior:'smooth', block:'nearest' });
  } catch (err) {
    console.error("Error showing detail:", err);
    toast('error','Error','Could not load call details');
  }
}

function closeDetail() {
  document.getElementById('detail-card').classList.remove('open');
}

// Close detail modal when clicking outside
document.addEventListener('click', (e) => {
  const detailCard = document.getElementById('detail-card');
  if (e.target === detailCard) {
    closeDetail();
  }
});

// ── Utils ──
function fmtTime(s) {
  if (!s) return '—';
  const d = new Date(s);
  return d.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'}) + ' ' +
         d.toLocaleDateString('en-US',{month:'short',day:'numeric'});
}

function esc(s) {
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function toast(type, title, msg) {
  const icons = { success:'✅', error:'❌', info:'ℹ️' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="t-icon">${icons[type]}</span>
    <div><div class="t-title">${title}</div><div class="t-msg">${msg}</div></div>`;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => {
    el.style.animation = 'tout 0.25s ease forwards';
    setTimeout(() => el.remove(), 250);
  }, 4000);
}
