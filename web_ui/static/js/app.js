// Auto-CF Sniper Bot Dashboard Controller

let isSniperActive = true;

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));

  event.currentTarget.classList.add('active');
  const target = document.getElementById(tabId);
  if (target) target.classList.add('active');

  if (tabId === 'tab-rules') loadRules();
  if (tabId === 'tab-history') loadCfHistory();
  if (tabId === 'tab-radar') loadRecentRadar();
}

document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  loadRecentRadar();
  // Auto refresh stats and radar every 4 seconds
  setInterval(() => {
    loadStats();
    if (document.getElementById('tab-radar').classList.contains('active')) {
      loadRecentRadar();
    }
  }, 4000);
});

// Load Overview Metrics
async function loadStats() {
  try {
    const res = await fetch('/api/sniper/stats');
    if (!res.ok) return;
    const data = await res.json();

    isSniperActive = data.is_sniper_active;
    updateSniperStatusUI();

    document.getElementById('stat-active-rules').textContent = `${data.active_rules || 0} กฎ`;
    document.getElementById('stat-total-wins').textContent = `${data.total_wins || 0} รายการ`;
    document.getElementById('stat-platform-mode').textContent = `แพลตฟอร์ม: ${data.platform === 'windows' ? 'LINE PC (Windows)' : 'Android / LDPlayer'}`;
  } catch (err) {
    console.error('Error fetching sniper stats:', err);
  }
}

function updateSniperStatusUI() {
  const ind = document.getElementById('sniper-indicator');
  const txt = document.getElementById('sniper-status-text');
  const btn = document.getElementById('sniper-toggle-btn');
  const label = document.getElementById('sniper-toggle-label');
  const statVal = document.getElementById('stat-sniper-state');

  if (isSniperActive) {
    ind.style.background = 'var(--line-green)';
    ind.style.boxShadow = '0 0 10px var(--line-green)';
    txt.textContent = 'ระบบสไนเปอร์พร้อมทำงาน 24 ชม.';
    btn.className = 'btn';
    label.textContent = '⚡ สไนเปอร์เปิดทำงาน (คลิกเพื่อหยุดฉุกเฉิน)';
    statVal.textContent = '🟢 พร้อมยิง CF ทันที';
    statVal.style.color = 'var(--line-green)';
  } else {
    ind.style.background = 'var(--accent-red)';
    ind.style.boxShadow = '0 0 10px var(--accent-red)';
    txt.textContent = 'สไนเปอร์หยุดทำงานชั่วคราว';
    btn.className = 'btn btn-danger';
    label.textContent = '▶ คลิกเพื่อเริ่มทำงานใหม่';
    statVal.textContent = '🔴 หยุดทำงาน (PAUSED)';
    statVal.style.color = 'var(--accent-red)';
  }
}

async function toggleSniperMaster() {
  try {
    const res = await fetch('/api/sniper/toggle-master', { method: 'POST' });
    const data = await res.json();
    isSniperActive = data.is_sniper_active;
    updateSniperStatusUI();
  } catch (err) {
    alert('เกิดข้อผิดพลาดในการสลับสถานะ');
  }
}

// Simulator Test Flight
async function testSniperMessage(e) {
  e.preventDefault();
  const roomInput = document.getElementById('sim-room');
  const textInput = document.getElementById('sim-text');
  const room = roomInput.value.trim() || 'OpenChat ปล่อยของ';
  const text = textInput.value.trim();
  if (!text) return;

  const win = document.getElementById('simulator-window');

  // Append user bubble
  const userBubble = document.createElement('div');
  userBubble.className = 'msg-bubble user';
  userBubble.innerHTML = `<div class="msg-meta">📢 ข้อความแม่ค้าใน [${escapeHtml(room)}]</div>${escapeHtml(text)}`;
  win.appendChild(userBubble);
  textInput.value = '';
  win.scrollTop = win.scrollHeight;

  // Placeholder thinking bubble
  const evalBubble = document.createElement('div');
  evalBubble.className = 'msg-bubble bot';
  evalBubble.innerHTML = `<div class="msg-meta">🎯 กำลังสแกนคีย์เวิร์ดและราคา...</div><em>วิเคราะห์เงื่อนไข...</em>`;
  win.appendChild(evalBubble);
  win.scrollTop = win.scrollHeight;

  try {
    const res = await fetch('/api/sniper/test-flight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ room_name: room, message: text, sender_name: 'แม่ค้าทดสอบ' })
    });
    const data = await res.json();

    if (data.matched) {
      evalBubble.innerHTML = `
        <div class="msg-meta">
          <span class="cf-win-tag">🎯 MATCHED & CF!</span>
          <span>กฎ: ${escapeHtml(data.rule_name || '-')}</span>
          <span>รหัสที่สกัดได้: <strong>${escapeHtml(data.extracted_code || '-')}</strong></span>
        </div>
        <div style="margin-top:0.3rem; font-size:1.05rem; font-weight:700; color:#042410;">
          ข้อความ CF ที่พิมพ์ส่ง: "${escapeHtml(data.cf_message)}"
        </div>
        <div style="font-size:0.75rem; color:#042410; margin-top:0.2rem; opacity:0.85;">
          หน่วงเวลาจำลอง: ${data.delay_ms || 200} ms | ราคาสินค้า: ${data.extracted_price ? data.extracted_price + ' บาท' : 'ไม่ระบุ'}
        </div>
      `;
    } else {
      evalBubble.innerHTML = `
        <div class="msg-meta">
          <span class="badge badge-sniper-off">SKIPPED</span>
          <span>ไม่ยิง CF</span>
        </div>
        <div>เหตุผล: ${escapeHtml(data.reason || 'ไม่ตรงกับเงื่อนไข')}</div>
      `;
    }
  } catch (err) {
    evalBubble.innerHTML = `<div class="msg-meta">⚠ ขัดข้อง</div>ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้`;
  }
  win.scrollTop = win.scrollHeight;
  loadStats();
}

// Live Radar Feed
async function loadRecentRadar() {
  try {
    const res = await fetch('/api/sniper/radar-feed');
    if (!res.ok) return;
    const items = await res.json();

    const win = document.getElementById('radar-feed-window');
    if (!items || items.length === 0) {
      win.innerHTML = '<div style="color:var(--text-muted); text-align:center; padding:2rem;">ยังไม่มีข้อความเข้าใหม่ในเรดาร์</div>';
      return;
    }

    win.innerHTML = '';
    items.forEach(it => {
      const el = document.createElement('div');
      const isHit = it.status === 'SUCCESS' || it.triggered;
      el.className = `msg-bubble ${isHit ? 'bot' : 'user'}`;

      el.innerHTML = `
        <div class="msg-meta">
          <span class="badge ${isHit ? 'badge-matched' : 'badge-oa'}">${escapeHtml(it.room_name || 'Group')}</span>
          <strong>${escapeHtml(it.sender_name || 'สมาชิก')}</strong>
          <span>${it.created_at || ''}</span>
        </div>
        <div style="margin-bottom:0.25rem;">${escapeHtml(it.original_message || it.content)}</div>
        ${isHit ? `<div style="font-weight:700; color:#042410;">⚡ ยิงส่ง: "${escapeHtml(it.cf_text || it.cf_message)}" (${it.execution_time_ms || 200}ms)</div>` : ''}
      `;
      win.appendChild(el);
    });
  } catch (err) {
    console.error('Error loading radar feed:', err);
  }
}

// Rules Manager
async function loadRules() {
  try {
    const res = await fetch('/api/sniper/rules');
    const rules = await res.json();
    const tbody = document.getElementById('rules-table-body');
    tbody.innerHTML = '';

    if (!rules || rules.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">ยังไม่มีกฎการ CF</td></tr>';
      return;
    }

    rules.forEach(r => {
      const tr = document.createElement('tr');
      const isActive = r.is_active === 1;

      tr.innerHTML = `
        <td>
          <span class="badge ${isActive ? 'badge-sniper-on' : 'badge-sniper-off'}">
            ${isActive ? '🟢 เปิดทำงาน' : '🔴 ปิดใช้งาน'}
          </span>
        </td>
        <td><strong>${escapeHtml(r.name)}</strong></td>
        <td><code>${escapeHtml(r.target_rooms)}</code></td>
        <td style="max-width: 250px; color:#cbd5e1;">${escapeHtml(r.target_keywords)}</td>
        <td><strong style="color:var(--line-green);">${escapeHtml(r.cf_format)}</strong></td>
        <td>${r.price_limit > 0 ? r.price_limit + ' บ.' : 'ไม่จำกัด'}</td>
        <td>${r.delay_ms} ms</td>
        <td>
          <button class="btn btn-secondary" style="padding:0.25rem 0.5rem; font-size:0.75rem;" onclick="toggleRule(${r.id}, ${!isActive})">
            ${isActive ? 'ปิด' : 'เปิด'}
          </button>
          <button class="btn btn-danger" style="padding:0.25rem 0.5rem; font-size:0.75rem;" onclick="deleteRule(${r.id})">
            ลบ
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading rules:', err);
  }
}

function toggleAddRuleModal() {
  const form = document.getElementById('add-rule-form');
  form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

async function saveNewRule() {
  const name = document.getElementById('rule-name').value.trim();
  const rooms = document.getElementById('rule-rooms').value.trim() || '*';
  const keywords = document.getElementById('rule-keywords').value.trim();
  const negative = document.getElementById('rule-negative').value.trim();
  const format = document.getElementById('rule-format').value.trim() || 'CF {code} พร้อมโอน';
  const price = parseFloat(document.getElementById('rule-price').value) || 0;
  const delay = parseInt(document.getElementById('rule-delay').value) || 200;

  if (!name || !keywords) {
    alert('กรุณากรอกชื่อกฎและคีย์เวิร์ดเป้าหมายให้ครบถ้วน');
    return;
  }

  try {
    const res = await fetch('/api/sniper/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        target_rooms: rooms,
        target_keywords: keywords,
        negative_keywords: negative,
        cf_format: format,
        price_limit: price,
        delay_ms: delay
      })
    });
    if (res.ok) {
      document.getElementById('rule-name').value = '';
      document.getElementById('rule-keywords').value = '';
      toggleAddRuleModal();
      loadRules();
      loadStats();
    }
  } catch (err) {
    alert('เกิดข้อผิดพลาดในการบันทึกกฎ');
  }
}

async function toggleRule(id, newState) {
  try {
    await fetch(`/api/sniper/rules/${id}/toggle?active=${newState}`, { method: 'POST' });
    loadRules();
    loadStats();
  } catch (err) {
    alert('เกิดข้อผิดพลาด');
  }
}

async function deleteRule(id) {
  if (!confirm('ต้องการลบกฎนี้ใช่หรือไม่?')) return;
  try {
    await fetch(`/api/sniper/rules/${id}`, { method: 'DELETE' });
    loadRules();
    loadStats();
  } catch (err) {
    alert('เกิดข้อผิดพลาดในการลบ');
  }
}

// CF History / Wins
async function loadCfHistory() {
  try {
    const res = await fetch('/api/sniper/history');
    const items = await res.json();
    const tbody = document.getElementById('history-table-body');
    tbody.innerHTML = '';

    if (!items || items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">ยังไม่มีประวัติการ CF</td></tr>';
      return;
    }

    items.forEach(h => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${h.created_at || '-'}</td>
        <td><span class="badge badge-personal">${escapeHtml(h.room_name)}</span></td>
        <td><strong>${escapeHtml(h.rule_name || '-')}</strong></td>
        <td style="max-width: 320px; color:#cbd5e1;">${escapeHtml(h.original_message)}</td>
        <td><span class="cf-win-tag">${escapeHtml(h.cf_text)}</span></td>
        <td>${h.execution_time_ms} ms</td>
        <td><span class="badge badge-sniper-on">✓ สำเร็จ</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading history:', err);
  }
}

// Settings
async function saveSniperSettings(e) {
  e.preventDefault();
  const platform = document.getElementById('cfg-platform').value;
  const jitter = document.getElementById('cfg-jitter').value;
  const secret = document.getElementById('cfg-bridge-secret').value;

  try {
    const res = await fetch('/api/sniper/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform, jitter, secret })
    });
    if (res.ok) {
      alert('บันทึกการตั้งค่าแพลตฟอร์มเรียบร้อยแล้ว!');
      loadStats();
    }
  } catch (err) {
    alert('เกิดข้อผิดพลาดในการเชื่อมต่อ');
  }
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
