/**
 * TIRE-MES 4.0 - Core Frontend Controller
 * Senior MES Engineer Implementation
 */

// Application Global State
const state = {
  currentTab: 'dashboard',
  pollingInterval: null,
  activeTbmWO: null,
  tbmBoms: {},
  tbmScannedLots: {},
  selectedQcTire: null,
  curingCavities: []
};

// ============================================================================
// INITIALIZATION
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  initClock();
  loadDashboard();
  loadWorkOrders();
  initTbmStation();
  loadCuringPresses();
  loadInspectionQueue();
  quickLookup('VN-T-202610-00101');

  // Start SCADA Live Polling Loop (3 seconds)
  state.pollingInterval = setInterval(() => {
    if (state.currentTab === 'dashboard') {
      loadDashboard(true);
    } else if (state.currentTab === 'curing') {
      loadCuringPresses(true);
    }
  }, 3000);
});

function initClock() {
  const clockEl = document.getElementById('live-clock');
  const update = () => {
    const d = new Date();
    clockEl.textContent = d.toLocaleTimeString('vi-VN');
  };
  update();
  setInterval(update, 1000);
}

function switchTab(tabId) {
  state.currentTab = tabId;

  // Update nav buttons
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick')?.includes(tabId));
  if (activeBtn) activeBtn.classList.add('active');

  // Update panes
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  const pane = document.getElementById(`pane-${tabId}`);
  if (pane) pane.classList.add('active');

  // Specific tab refreshes
  if (tabId === 'dashboard') loadDashboard();
  if (tabId === 'work-orders') loadWorkOrders();
  if (tabId === 'curing') loadCuringPresses();
  if (tabId === 'quality') loadInspectionQueue();
  if (tabId === 'master-data') showMasterSubTab('products');
  if (tabId === 'gateway') loadGatewayConnectors();
  if (tabId === 'ai') loadAiTab();
  if (tabId === 'bottleneck') loadBottleneckTab();
  if (tabId === 'shap') loadShapTab();
  if (tabId === 'graph') loadGraphTab();
}

function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add('active');
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove('active');
}

// ============================================================================
// TAB 1: EXECUTIVE DASHBOARD
// ============================================================================
async function loadDashboard(silent = false) {
  try {
    // 1. KPIs
    const kpiRes = await fetch('/api/dashboard/kpis');
    const kpi = await kpiRes.json();

    document.getElementById('kpi-oee').textContent = kpi.oee_percent;
    document.getElementById('kpi-avail').textContent = `${kpi.availability_percent}%`;
    document.getElementById('kpi-perf').textContent = `${kpi.performance_percent}%`;
    document.getElementById('kpi-qual').textContent = `${kpi.quality_percent}%`;

    document.getElementById('kpi-fpy').textContent = kpi.fpy_percent;
    document.getElementById('kpi-scrap').textContent = kpi.scrap_rate_percent;
    document.getElementById('kpi-scrap-count').textContent = kpi.scrap_count;

    document.getElementById('kpi-green-tires').textContent = kpi.total_green_tires;
    document.getElementById('kpi-cured-tires').textContent = kpi.total_cured_tires;

    document.getElementById('kpi-running-machines').textContent = kpi.running_machines;
    document.getElementById('kpi-active-wos').textContent = kpi.active_work_orders;

    // Quality counts
    document.getElementById('count-grade-a').textContent = kpi.grade_a_count;
    document.getElementById('count-grade-b').textContent = kpi.grade_b_count;
    document.getElementById('count-grade-rework').textContent = kpi.rework_count;
    document.getElementById('count-grade-scrap').textContent = kpi.scrap_count;

    if (!silent) {
      // 2. Lines Pipeline
      const linesRes = await fetch('/api/dashboard/lines-status');
      const lines = await linesRes.json();
      renderPipeline(lines);

      // 3. Quality Pareto
      const qRes = await fetch('/api/dashboard/quality-summary');
      const qData = await qRes.json();
      renderQualityPareto(qData.pareto);

      // 4. Live Events
      const evRes = await fetch('/api/dashboard/recent-events');
      const events = await evRes.json();
      renderRecentEvents(events);
    }
  } catch (err) {
    console.error('Error loading dashboard:', err);
  }
}

function renderPipeline(machines) {
  const container = document.getElementById('pipeline-areas');
  if (!container) return;

  // Group by area
  const areasMap = {
    'MIXING': { title: '1. LUYỆN CAO SU', desc: 'Banbury BB-270' },
    'PREP': { title: '2. BÁN THÀNH PHẨM', desc: 'Đùn mặt lốp & Cán mành' },
    'TBM': { title: '3. THÀNH HÌNH', desc: 'Máy đóng lốp sống VMI' },
    'CURING': { title: '4. LƯU HÓA LỐP', desc: 'Lò ép thủy lực 63.5"' },
    'FINISHING': { title: '5. KCS HOÀN THIỆN', desc: 'X-Ray & Cân bằng động' },
    'WAREHOUSE': { title: '6. KHO THÀNH PHẨM', desc: 'Dán mã vạch lưu kho' },
  };

  container.innerHTML = Object.keys(areasMap).map(areaKey => {
    const areaInfo = areasMap[areaKey];
    const areaMachines = machines.filter(m => m.area_code === areaKey);
    const runningCount = areaMachines.filter(m => m.status === 'RUNNING').length;

    return `
      <div class="pipeline-step">
        <div class="step-num">${areaKey}</div>
        <div class="step-title">${areaInfo.title}</div>
        <div class="step-desc">${areaInfo.desc}</div>
        <div class="step-status">
          <span>Trạng thái:</span>
          <span class="status-pill ${runningCount > 0 ? 'pill-green' : 'pill-amber'}">
            ${runningCount}/${areaMachines.length || 1} ĐANG CHẠY
          </span>
        </div>
      </div>
    `;
  }).join('');
}

function renderQualityPareto(pareto) {
  const container = document.getElementById('quality-pareto-list');
  if (!container) return;

  if (!pareto || pareto.length === 0) {
    container.innerHTML = '<div style="color: #94a3b8; font-size: 0.8rem;">Không có khuyết tật ghi nhận.</div>';
    return;
  }

  container.innerHTML = `
    <div style="font-size: 0.8rem; font-weight: 700; color: #94a3b8; margin-bottom: 0.5rem; text-transform: uppercase;">
      Biểu đồ Pareto Khuyết Tật Hàng Đầu:
    </div>
    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
      ${pareto.slice(0, 4).map(p => `
        <div style="background: #111827; padding: 0.55rem 0.8rem; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; border-left: 3px solid ${p.severity === 'CRITICAL' ? '#ef4444' : '#f59e0b'};">
          <div>
            <div style="font-size: 0.82rem; font-weight: 700; color: #fff;">${p.defect_code}: ${p.defect_name_vi}</div>
            <div style="font-size: 0.72rem; color: #94a3b8;">${p.defect_name_en}</div>
          </div>
          <span class="status-pill ${p.severity === 'CRITICAL' ? 'pill-red' : 'pill-amber'}">
            ${p.defect_count} lần
          </span>
        </div>
      `).join('')}
    </div>
  `;
}

function renderRecentEvents(events) {
  const container = document.getElementById('recent-events-stream');
  if (!container) return;

  container.innerHTML = events.map(ev => {
    let pillClass = 'pill-blue';
    if (ev.event_type === 'TIRE_CURED') pillClass = 'pill-cyan';
    if (ev.event_type === 'QUALITY_INSPECTED') pillClass = 'pill-green';

    return `
      <div style="padding: 0.55rem 0.75rem; border-bottom: 1px solid rgba(255, 255, 255, 0.05); display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem;">
        <div>
          <span class="status-pill ${pillClass}" style="margin-right: 0.5rem; font-size: 0.68rem;">${ev.location}</span>
          <span style="color: #f1f5f9;">${ev.message}</span>
        </div>
        <span style="color: #64748b; font-family: var(--font-mono); font-size: 0.72rem;">${ev.event_time.split(' ')[1] || ev.event_time}</span>
      </div>
    `;
  }).join('');
}

// ============================================================================
// TAB 2: WORK ORDERS
// ============================================================================
async function loadWorkOrders() {
  try {
    const res = await fetch('/api/work-orders');
    const wos = await res.json();

    document.getElementById('badge-wo-count').textContent = wos.length;

    const tbody = document.getElementById('wo-table-body');
    if (!tbody) return;

    tbody.innerHTML = wos.map(wo => {
      let statusPill = 'pill-blue';
      if (wo.status === 'COMPLETED') statusPill = 'pill-green';
      if (wo.status === 'RELEASED') statusPill = 'pill-amber';

      return `
        <tr>
          <td><strong style="color: #38bdf8; font-family: var(--font-mono);">${wo.wo_id}</strong></td>
          <td><span style="font-family: var(--font-mono); font-size: 0.8rem;">${wo.sku}</span></td>
          <td><strong>${wo.tire_size}</strong> <div style="font-size: 0.75rem; color: #94a3b8;">${wo.pattern_name}</div></td>
          <td><span class="status-pill pill-purple">${wo.segment}</span></td>
          <td><strong>${wo.target_qty}</strong></td>
          <td><strong style="color: #34d399;">${wo.completed_qty}</strong></td>
          <td style="min-width: 140px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 2px;">
              <span>${wo.progress_percent}%</span>
            </div>
            <div class="progress-track">
              <div class="progress-bar ${wo.progress_percent >= 100 ? 'success' : ''}" style="width: ${wo.progress_percent}%;"></div>
            </div>
          </td>
          <td><span style="color: ${wo.scrap_qty > 0 ? '#ef4444' : '#94a3b8'}; font-weight: 700;">${wo.scrap_qty}</span></td>
          <td>${wo.assigned_machine || 'TBM-01'}</td>
          <td><span class="status-pill ${statusPill}">${wo.status}</span></td>
          <td>
            ${wo.status === 'IN_PROGRESS' ? `
              <button class="btn btn-secondary btn-sm" onclick="setWOStatus('${wo.wo_id}', 'COMPLETED')">Hoàn Tất</button>
            ` : wo.status === 'RELEASED' ? `
              <button class="btn btn-primary btn-sm" onclick="setWOStatus('${wo.wo_id}', 'IN_PROGRESS')">Kích Hoạt</button>
            ` : `
              <span style="color: #64748b; font-size: 0.75rem;">Đã Đóng</span>
            `}
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading work orders:', err);
  }
}

async function setWOStatus(wo_id, newStatus) {
  try {
    const res = await fetch(`/api/work-orders/${wo_id}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      loadWorkOrders();
      loadDashboard();
    }
  } catch (err) {
    alert('Lỗi cập nhật trạng thái lệnh sản xuất: ' + err);
  }
}

function openCreateWOModal() {
  const d = new Date();
  const randNum = Math.floor(Math.random() * 900 + 100);
  document.getElementById('new-wo-id').value = `WO-${d.getFullYear()}-${randNum}`;
  openModal('modal-create-wo');
}

async function submitCreateWO() {
  const wo_id = document.getElementById('new-wo-id').value;
  const sku = document.getElementById('new-wo-sku').value;
  const target_qty = parseInt(document.getElementById('new-wo-target').value);
  const priority = document.getElementById('new-wo-priority').value;
  const assigned_machine = document.getElementById('new-wo-machine').value;

  try {
    const res = await fetch('/api/work-orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        wo_id,
        sku,
        target_qty,
        priority,
        assigned_machine,
        planned_start: new Date().toISOString().slice(0, 16).replace('T', ' '),
        planned_end: new Date(Date.now() + 28800000).toISOString().slice(0, 16).replace('T', ' ')
      })
    });

    if (res.ok) {
      closeModal('modal-create-wo');
      loadWorkOrders();
      initTbmStation();
      alert(`Đã tạo lệnh sản xuất ${wo_id} thành công!`);
    } else {
      const err = await res.json();
      alert(`Lỗi: ${err.detail || 'Không thể tạo lệnh'}`);
    }
  } catch (err) {
    alert('Lỗi mạng: ' + err);
  }
}

// ============================================================================
// TAB 3: TBM BUILDING TERMINAL (POKA-YOKE)
// ============================================================================
async function initTbmStation() {
  try {
    // 1. Load active work orders into dropdown
    const res = await fetch('/api/work-orders?status=IN_PROGRESS');
    const wos = await res.json();

    const woSelect = document.getElementById('tbm-active-wo');
    if (!woSelect) return;

    if (wos.length === 0) {
      woSelect.innerHTML = '<option value="">Không có lệnh IN_PROGRESS</option>';
      return;
    }

    woSelect.innerHTML = wos.map(w => `
      <option value="${w.wo_id}" data-sku="${w.sku}">
        ${w.wo_id} - ${w.tire_size} (${w.pattern_name}) [Mục tiêu: ${w.target_qty}]
      </option>
    `).join('');

    onTbmWOChange();
  } catch (err) {
    console.error('Error initializing TBM:', err);
  }
}

async function onTbmWOChange() {
  const woSelect = document.getElementById('tbm-active-wo');
  const wo_id = woSelect.value;
  if (!wo_id) return;

  try {
    const res = await fetch(`/api/work-orders/${wo_id}`);
    const data = await res.json();
    state.activeTbmWO = data;

    // Display info
    document.getElementById('tbm-tire-size-display').textContent = data.tire_size;
    document.getElementById('tbm-tire-pattern-display').textContent = `${data.pattern_name} &bull; ${data.segment} &bull; ${data.sku}`;
    document.getElementById('tbm-std-weight').textContent = `${data.standard_weight_kg} kg`;
    document.getElementById('tbm-std-cycle').textContent = `${data.std_tbm_time_sec} giây`;
    document.getElementById('tbm-actual-weight').value = data.standard_weight_kg;

    // Map BOM specs
    state.tbmBoms = {};
    data.bom_items.forEach(b => {
      state.tbmBoms[b.component_type] = b;
      const specEl = document.getElementById(`spec-${b.component_type}`);
      if (specEl) specEl.textContent = `${b.spec_code} (${b.compound_code})`;
    });

    // Reset scan state
    resetTbmScans();
  } catch (err) {
    console.error('Error fetching WO detail:', err);
  }
}

function onTbmMachineChange() {
  const machine = document.getElementById('tbm-machine-select').value;
  console.log('Switched TBM Machine to:', machine);
}

function resetTbmScans() {
  state.tbmScannedLots = {};
  const compTypes = ['TREAD', 'SIDEWALL', 'BELT_1', 'BELT_2', 'PLY', 'BEAD', 'INNERLINER'];
  compTypes.forEach(t => {
    const inp = document.getElementById(`lot-input-${t}`);
    if (inp) {
      inp.value = '';
      inp.classList.remove('input-error');
    }
    const stat = document.getElementById(`status-${t}`);
    if (stat) {
      stat.textContent = 'Chưa quét';
      stat.className = 'status-label';
      stat.style.color = '#94a3b8';
    }
  });

  const alarmBox = document.getElementById('poka-yoke-alarm-container');
  if (alarmBox) alarmBox.innerHTML = '';

  const globStat = document.getElementById('poka-yoke-global-status');
  if (globStat) {
    globStat.textContent = 'CHỜ QUÉT ĐỦ 7 HỢP PHẦN';
    globStat.className = 'status-pill pill-amber';
  }
}

async function validateLotSingle(compType) {
  if (!state.activeTbmWO) return;

  const input = document.getElementById(`lot-input-${compType}`);
  const statusEl = document.getElementById(`status-${compType}`);
  const lot_id = input.value.trim();

  if (!lot_id) {
    statusEl.textContent = 'Chưa nhập mã';
    statusEl.style.color = '#94a3b8';
    return;
  }

  try {
    const res = await fetch('/api/tbm/validate-lot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sku: state.activeTbmWO.sku,
        component_type: compType,
        lot_id: lot_id
      })
    });

    const data = await res.json();
    const alarmContainer = document.getElementById('poka-yoke-alarm-container');

    if (data.valid) {
      input.classList.remove('input-error');
      statusEl.textContent = '✓ HỢP LỆ';
      statusEl.style.color = '#34d399';
      statusEl.style.fontWeight = '700';
      state.tbmScannedLots[compType] = lot_id;
      checkAllLotsScanned();
    } else {
      input.classList.add('input-error');
      statusEl.textContent = '✗ TỪ CHỐI (POKA-YOKE)';
      statusEl.style.color = '#ef4444';
      statusEl.style.fontWeight = '700';
      delete state.tbmScannedLots[compType];

      // Display Poka-Yoke Alarm Banner
      alarmContainer.innerHTML = `
        <div class="alarm-banner">
          <div style="font-size: 1.5rem;">🚨</div>
          <div>
            <strong>CẢNH BÁO POKA-YOKE TẠI TRẠM [${compType}]:</strong><br>
            ${data.message}
          </div>
        </div>
      `;

      const globStat = document.getElementById('poka-yoke-global-status');
      if (globStat) {
        globStat.textContent = 'LỖI POKA-YOKE: BỊ KHÓA';
        globStat.className = 'status-pill pill-red';
      }
    }
  } catch (err) {
    console.error('Validation error:', err);
  }
}

function checkAllLotsScanned() {
  const compTypes = ['TREAD', 'SIDEWALL', 'BELT_1', 'BELT_2', 'PLY', 'BEAD', 'INNERLINER'];
  const count = compTypes.filter(t => state.tbmScannedLots[t]).length;
  const globStat = document.getElementById('poka-yoke-global-status');
  const alarmContainer = document.getElementById('poka-yoke-alarm-container');

  if (count === 7) {
    globStat.textContent = 'POKA-YOKE PASS: SẴN SÀNG ĐÓNG LỐP';
    globStat.className = 'status-pill pill-green';
    alarmContainer.innerHTML = '';
  } else {
    globStat.textContent = `ĐÃ QUÉT ${count}/7 HỢP PHẦN`;
    globStat.className = 'status-pill pill-amber';
  }
}

function quickFillValidLots() {
  const validLots = {
    'TREAD': 'LOT-TRD-202610-01',
    'SIDEWALL': 'LOT-SW-202610-01',
    'BELT_1': 'LOT-BLT1-202610-01',
    'BELT_2': 'LOT-BLT2-202610-01',
    'PLY': 'LOT-PLY-202610-01',
    'BEAD': 'LOT-BD-202610-01',
    'INNERLINER': 'LOT-INL-202610-01'
  };

  Object.entries(validLots).forEach(([type, lot]) => {
    const input = document.getElementById(`lot-input-${type}`);
    if (input) {
      input.value = lot;
      validateLotSingle(type);
    }
  });
}

function quickFillExpiredLot() {
  // Fill valid for 6 components and expired for Tread
  quickFillValidLots();
  setTimeout(() => {
    const treadInp = document.getElementById('lot-input-TREAD');
    if (treadInp) {
      treadInp.value = 'LOT-EXP-TRD-999';
      validateLotSingle('TREAD');
    }
  }, 200);
}

async function executeBuildGreenTire() {
  if (!state.activeTbmWO) {
    alert('Vui lòng chọn Lệnh sản xuất!');
    return;
  }

  const compTypes = ['TREAD', 'SIDEWALL', 'BELT_1', 'BELT_2', 'PLY', 'BEAD', 'INNERLINER'];
  const missing = compTypes.filter(t => !state.tbmScannedLots[t]);
  if (missing.length > 0) {
    alert(`CẢNH BÁO AN TOÀN: Chưa quét đầy đủ 7 hợp phần! Còn thiếu: ${missing.join(', ')}`);
    return;
  }

  const machine_id = document.getElementById('tbm-machine-select').value;
  const operator_id = document.getElementById('tbm-operator-select').value;
  const actual_weight = parseFloat(document.getElementById('tbm-actual-weight').value);

  const btn = document.getElementById('btn-build-green-tire');
  btn.disabled = true;
  btn.textContent = '⏳ ĐANG THÀNH HÌNH & ÉP LƯU NỞ TRỐNG...';

  try {
    const res = await fetch('/api/tbm/build-green-tire', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        wo_id: state.activeTbmWO.wo_id,
        sku: state.activeTbmWO.sku,
        tbm_machine_id: machine_id,
        operator_id: operator_id,
        actual_weight_kg: actual_weight,
        tread_lot: state.tbmScannedLots['TREAD'],
        sidewall_lot: state.tbmScannedLots['SIDEWALL'],
        belt1_lot: state.tbmScannedLots['BELT_1'],
        belt2_lot: state.tbmScannedLots['BELT_2'],
        ply_lot: state.tbmScannedLots['PLY'],
        bead_lot: state.tbmScannedLots['BEAD'],
        innerliner_lot: state.tbmScannedLots['INNERLINER']
      })
    });

    const data = await res.json();
    btn.disabled = false;
    btn.textContent = '🚀 KÍCH HOẠT ĐÓNG LỐP (BUILD GREEN TIRE)';

    if (data.success) {
      // Show Barcode Print Modal
      document.getElementById('lbl-gt-barcode').textContent = data.gt_barcode;
      document.getElementById('lbl-tire-size').textContent = data.tire_data.tire_size;
      document.getElementById('lbl-weight').textContent = `${data.tire_data.actual_weight_kg} kg`;
      document.getElementById('lbl-machine').textContent = data.tire_data.tbm_machine_id;
      document.getElementById('lbl-op').textContent = data.tire_data.operator_id;
      openModal('modal-gt-label');

      // Refresh data
      resetTbmScans();
      loadDashboard();
      loadWorkOrders();
    } else {
      alert(`Lỗi: ${data.detail || 'Không thể tạo lốp sống'}`);
    }
  } catch (err) {
    btn.disabled = false;
    btn.textContent = '🚀 KÍCH HOẠT ĐÓNG LỐP (BUILD GREEN TIRE)';
    alert('Lỗi kết nối: ' + err);
  }
}

// ============================================================================
// TAB 4: CURING PRESSES SCADA MATRIX
// ============================================================================
async function loadCuringPresses(silent = false) {
  try {
    const res = await fetch('/api/curing/cavities');
    const cavities = await res.json();
    state.curingCavities = cavities;

    const curingActiveCount = cavities.filter(c => c.state === 'CURING').length;
    document.getElementById('badge-curing-active').textContent = curingActiveCount;

    const grid = document.getElementById('curing-presses-grid');
    if (!grid) return;

    // Group cavities by press_id
    const pressMap = {};
    cavities.forEach(c => {
      if (!pressMap[c.press_id]) pressMap[c.press_id] = { machine_name: c.machine_name, model: c.model, cavities: [] };
      pressMap[c.press_id].cavities.push(c);
    });

    grid.innerHTML = Object.entries(pressMap).map(([pressId, pInfo]) => {
      return `
        <div class="press-card">
          <div class="press-header">
            <div>
              <div style="font-size: 1.05rem; font-weight: 800; color: #fff;">${pressId} &bull; ${pInfo.machine_name}</div>
              <div style="font-size: 0.75rem; color: #94a3b8;">${pInfo.model}</div>
            </div>
          </div>

          <div class="cavity-container">
            ${pInfo.cavities.map(cav => renderCavityBox(cav)).join('')}
          </div>
        </div>
      `;
    }).join('');

    // Update real-time stream historian
    updateLiveTelemetryStream();
  } catch (err) {
    console.error('Error loading curing presses:', err);
  }
}

// Global buffer for live waveform points
const waveformBuffer = {
  temps: [170.1, 170.2, 169.9, 170.3, 170.0, 170.2, 169.8, 170.1, 170.4, 170.0, 169.9, 170.2],
  pressures: [21.0, 21.1, 20.9, 21.0, 21.2, 20.9, 21.1, 21.0, 20.8, 21.1, 21.0, 21.1]
};

async function updateLiveTelemetryStream() {
  try {
    const res = await fetch('/api/stream/stats');
    const data = await res.json();

    const countEl = document.getElementById('stream-total-logged');
    if (countEl) countEl.textContent = data.total_points_logged.toLocaleString();

    const tbody = document.getElementById('stream-live-tbody');
    if (tbody && data.latest_records) {
      tbody.innerHTML = data.latest_records.slice(0, 5).map(r => `
        <tr>
          <td><strong style="color: #38bdf8; font-family: var(--font-mono);">#${r.id}</strong></td>
          <td><span style="font-family: var(--font-mono); color: #cbd5e1;">${r.timestamp}</span></td>
          <td><strong>${r.press_id}-${r.cavity_side}</strong></td>
          <td><span style="color: #f59e0b; font-weight: 700;">${r.mold_temp.toFixed(1)} &deg;C</span></td>
          <td><span style="color: #06b6d4; font-weight: 700;">${r.bladder_press.toFixed(1)} bar</span></td>
          <td><span>${r.steam_press.toFixed(1)} bar</span></td>
          <td><span class="status-pill pill-cyan" style="font-size: 0.68rem;">${r.phase}</span></td>
          <td><span class="status-pill pill-green" style="font-size: 0.68rem;">COMMITTED</span></td>
        </tr>
      `).join('');

      // Push latest value to waveform buffer
      if (data.latest_records.length > 0) {
        waveformBuffer.temps.push(data.latest_records[0].mold_temp);
        waveformBuffer.pressures.push(data.latest_records[0].bladder_press);
        if (waveformBuffer.temps.length > 30) waveformBuffer.temps.shift();
        if (waveformBuffer.pressures.length > 30) waveformBuffer.pressures.shift();
      }
    }

    // Render Canvas
    drawLiveWaveformCanvas();
  } catch (err) {
    console.error('Error updating live telemetry stream:', err);
  }
}

function drawLiveWaveformCanvas() {
  const canvas = document.getElementById('telemetry-live-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  // Clear background
  ctx.fillStyle = '#070a12';
  ctx.fillRect(0, 0, w, h);

  // Draw grid lines
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
  ctx.lineWidth = 1;
  for (let x = 0; x < w; x += 50) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
  }
  for (let y = 0; y < h; y += 25) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  // Draw Temperature Line (Orange, Setpoint 170C -> center at y = 35)
  if (waveformBuffer.temps.length > 1) {
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2;
    ctx.beginPath();
    const stepX = w / (waveformBuffer.temps.length - 1);
    waveformBuffer.temps.forEach((t, i) => {
      // Map 168C - 172C to y
      const y = 35 - (t - 170.0) * 18;
      if (i === 0) ctx.moveTo(0, y);
      else ctx.lineTo(i * stepX, y);
    });
    ctx.stroke();
  }

  // Draw Bladder Pressure Line (Cyan, Setpoint 21 bar -> center at y = 80)
  if (waveformBuffer.pressures.length > 1) {
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 2;
    ctx.beginPath();
    const stepX = w / (waveformBuffer.pressures.length - 1);
    waveformBuffer.pressures.forEach((p, i) => {
      // Map 20 - 22 bar to y
      const y = 80 - (p - 21.0) * 20;
      if (i === 0) ctx.moveTo(0, y);
      else ctx.lineTo(i * stepX, y);
    });
    ctx.stroke();
  }
}

function renderCavityBox(cav) {
  let stateClass = 'state-empty';
  let pillClass = 'pill-gray';
  let stateText = 'TRỐNG (EMPTY)';

  if (cav.state === 'CURING') {
    stateClass = 'state-curing';
    pillClass = 'pill-cyan';
    stateText = 'ĐANG LƯU HÓA';
  } else if (cav.state === 'COMPLETED') {
    stateClass = 'state-completed';
    pillClass = 'pill-green';
    stateText = 'ĐÃ CHÍN (XONG)';
  } else if (cav.state === 'LOADED') {
    stateClass = 'state-loaded';
    pillClass = 'pill-amber';
    stateText = 'ĐÃ NẠP LỐP';
  }

  const mm = Math.floor(cav.cure_elapsed_seconds / 60);
  const ss = cav.cure_elapsed_seconds % 60;
  const timeFormatted = `${mm}:${ss < 10 ? '0' : ''}${ss}`;

  const t_mm = Math.floor(cav.cure_target_seconds / 60);
  const t_ss = cav.cure_target_seconds % 60;
  const targetFormatted = `${t_mm}:${t_ss < 10 ? '0' : ''}${t_ss}`;

  return `
    <div class="cavity-box ${stateClass}">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
        <strong style="color: #38bdf8;">HỘC ${cav.cavity_side}</strong>
        <span class="status-pill ${pillClass}">${stateText}</span>
      </div>

      <div style="font-size: 0.75rem; color: #cbd5e1; margin-bottom: 0.25rem;">
        Khuôn: <strong style="color: #fff;">${cav.mold_id}</strong>
      </div>

      <div style="font-size: 0.72rem; color: #94a3b8; font-family: var(--font-mono); margin-bottom: 0.4rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
        ${cav.current_gt_barcode ? `Lốp: ${cav.current_gt_barcode}` : '(Chưa nạp lốp sống)'}
      </div>

      <!-- Gauges -->
      <div class="gauge-row">
        <div class="gauge-item">
          <div class="gauge-label">Nhiệt độ khuôn</div>
          <div class="gauge-val">${cav.mold_temp_c}&deg;C</div>
        </div>
        <div class="gauge-item">
          <div class="gauge-label">Áp suất bàng</div>
          <div class="gauge-val">${cav.bladder_press_bar} bar</div>
        </div>
      </div>

      <!-- Progress -->
      <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: #94a3b8;">
        <span>${timeFormatted} / ${targetFormatted}</span>
        <span>${cav.progress_percent}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-bar ${cav.state === 'COMPLETED' ? 'success' : ''}" style="width: ${cav.progress_percent}%;"></div>
      </div>

      <!-- Bladder Cycle Counter -->
      <div style="font-size: 0.7rem; color: ${cav.bladder_cycle_count > 300 ? '#f59e0b' : '#64748b'}; margin-top: 0.35rem; display: flex; justify-content: space-between;">
        <span>Tuổi thọ bàng:</span>
        <strong>${cav.bladder_cycle_count} / 350 lần</strong>
      </div>

      <!-- Action Buttons -->
      <div style="margin-top: 0.75rem; display: flex; flex-direction: column; gap: 0.35rem;">
        ${cav.state === 'EMPTY' ? `
          <button class="btn btn-primary btn-sm" onclick="promptLoadTire('${cav.press_id}', '${cav.cavity_side}')">
            + Nạp Lốp Sống
          </button>
        ` : cav.state === 'LOADED' ? `
          <button class="btn btn-warning btn-sm" onclick="startCuringCycle('${cav.press_id}', '${cav.cavity_side}')">
            🔥 Bắt Đầu Ép Lưu Hóa
          </button>
        ` : cav.state === 'CURING' ? `
          <button class="btn btn-secondary btn-sm" onclick="simulateFastCure('${cav.press_id}', '${cav.cavity_side}')" title="Tua nhanh thời gian chín để demo">
            ⏩ Tua Nhanh Chín (Demo)
          </button>
        ` : cav.state === 'COMPLETED' ? `
          <button class="btn btn-success btn-sm" onclick="unloadCuredTire('${cav.press_id}', '${cav.cavity_side}')">
            📦 Dỡ Lốp Chín & Cấp Sê-ri
          </button>
        ` : ''}
      </div>
    </div>
  `;
}

async function promptLoadTire(press_id, cavity_side) {
  // Find available built green tires
  try {
    const res = await fetch('/api/work-orders');
    // Fetch latest green tire built
    const evRes = await fetch('/api/dashboard/recent-events');
    const events = await evRes.json();
    const latestGT = events.find(e => e.event_type === 'GREEN_TIRE_BUILT');
    const defaultGT = latestGT ? latestGT.ref_id : 'GT-202610-0001';

    const gt_barcode = prompt(`Nạp lốp sống vào lò ${press_id} hộc ${cavity_side}:\nNhập mã vạch lốp sống:`, defaultGT);
    if (!gt_barcode) return;

    const loadRes = await fetch('/api/curing/load', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ press_id, cavity_side, gt_barcode })
    });

    const data = await loadRes.json();
    if (loadRes.ok) {
      loadCuringPresses();
    } else {
      alert(`Lỗi nạp lốp: ${data.detail || 'Không thể nạp'}`);
    }
  } catch (err) {
    alert('Lỗi: ' + err);
  }
}

async function startCuringCycle(press_id, cavity_side) {
  try {
    const res = await fetch('/api/curing/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ press_id, cavity_side })
    });
    if (res.ok) {
      loadCuringPresses();
    } else {
      const err = await res.json();
      alert(`Lỗi: ${err.detail}`);
    }
  } catch (err) {
    alert('Lỗi: ' + err);
  }
}

async function simulateFastCure(press_id, cavity_side) {
  try {
    const res = await fetch('/api/curing/simulate-complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ press_id, cavity_side })
    });
    if (res.ok) {
      loadCuringPresses();
    }
  } catch (err) {
    alert('Lỗi: ' + err);
  }
}

async function unloadCuredTire(press_id, cavity_side) {
  try {
    const res = await fetch('/api/curing/unload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ press_id, cavity_side })
    });

    const data = await res.json();
    if (res.ok) {
      loadCuringPresses();
      loadInspectionQueue();
      loadDashboard();
      alert(`ĐÃ DỠ LỐP CHÍN THÀNH CÔNG!\n\nSố Sê-ri Khắc Trên Lốp: ${data.tire_serial}\nMã Lốp Sống: ${data.gt_barcode}\nĐã chuyển sang hàng đợi KCS.`);
    } else {
      alert(`Lỗi: ${data.detail}`);
    }
  } catch (err) {
    alert('Lỗi: ' + err);
  }
}

// ============================================================================
// TAB 5: FINAL QUALITY INSPECTION (KCS)
// ============================================================================
async function loadInspectionQueue() {
  try {
    const res = await fetch('/api/quality/queue');
    const queue = await res.json();

    document.getElementById('badge-qc-queue').textContent = queue.length;

    const list = document.getElementById('inspection-queue-list');
    if (!list) return;

    if (queue.length === 0) {
      list.innerHTML = '<div style="color: #94a3b8; font-size: 0.85rem; padding: 1rem;">Không có lốp nào chờ kiểm tra. Vui lòng dỡ lốp chín từ lò lưu hóa.</div>';
      return;
    }

    list.innerHTML = queue.map(tire => `
      <div onclick="selectTireForQC('${tire.tire_serial}')" style="background: #111827; padding: 0.85rem; border-radius: 6px; border: 1px solid var(--border-color); cursor: pointer; transition: all 0.2s;" onmouseover="this.style.borderColor='#38bdf8'" onmouseout="this.style.borderColor='var(--border-color)'">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
          <strong style="color: #38bdf8; font-family: var(--font-mono);">${tire.tire_serial}</strong>
          <span class="status-pill pill-amber" style="font-size: 0.68rem;">CHỜ KCS</span>
        </div>
        <div style="font-size: 0.85rem; color: #fff; font-weight: 600;">${tire.tire_size} - ${tire.pattern_name}</div>
        <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 0.25rem;">
          Lò: <strong>${tire.press_id}-${tire.cavity_side}</strong> &bull; Ra lò: ${tire.cure_end_time.split(' ')[1] || tire.cure_end_time}
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error loading QC queue:', err);
  }
}

async function selectTireForQC(tireSerial) {
  try {
    const res = await fetch('/api/quality/queue');
    const queue = await res.json();
    const tire = queue.find(t => t.tire_serial === tireSerial);
    if (!tire) return;

    state.selectedQcTire = tire;

    // Show form
    document.getElementById('qc-placeholder-msg').style.display = 'none';
    document.getElementById('qc-active-form').style.display = 'block';

    document.getElementById('qc-tire-serial').textContent = tire.tire_serial;
    document.getElementById('qc-tire-desc').textContent = `${tire.tire_size} &bull; ${tire.pattern_name} &bull; ${tire.segment}`;
    document.getElementById('qc-press-origin').textContent = `${tire.press_id} (Hộc ${tire.cavity_side})`;

    // Reset fields to standard pass defaults
    document.querySelector('input[name="qc-visual-radio"][value="PASS"]').checked = true;
    document.querySelector('input[name="qc-xray-radio"][value="PASS"]').checked = true;
    toggleVisualDefectUI();
    toggleXrayDefectUI();

    document.getElementById('qc-belt-align').value = '0.2';
    document.getElementById('qc-rfv').value = '42.5';
    document.getElementById('qc-lfv').value = '18.0';
    document.getElementById('qc-balance').value = '15.0';
  } catch (err) {
    console.error('Error selecting QC tire:', err);
  }
}

function toggleVisualDefectUI() {
  const isFail = document.querySelector('input[name="qc-visual-radio"]:checked').value === 'FAIL';
  document.getElementById('qc-visual-defect-row').style.display = isFail ? 'block' : 'none';
}

function toggleXrayDefectUI() {
  const isFail = document.querySelector('input[name="qc-xray-radio"]:checked').value === 'FAIL';
  document.getElementById('qc-xray-defect-col').style.display = isFail ? 'block' : 'none';
}

async function submitQCInspection() {
  if (!state.selectedQcTire) return;

  const tire_serial = state.selectedQcTire.tire_serial;
  const inspector_id = document.getElementById('qc-inspector-select').value;

  const visual_result = document.querySelector('input[name="qc-visual-radio"]:checked').value;
  const visual_defect_code = visual_result === 'FAIL' ? document.getElementById('qc-visual-defect-select').value : null;
  const defect_location = visual_result === 'FAIL' ? document.getElementById('qc-visual-location').value : null;

  const xray_result = document.querySelector('input[name="qc-xray-radio"]:checked').value;
  const xray_defect_code = xray_result === 'FAIL' ? document.getElementById('qc-xray-defect-select').value : null;
  const belt_alignment_mm = parseFloat(document.getElementById('qc-belt-align').value);

  const uniformity_rfv_n = parseFloat(document.getElementById('qc-rfv').value);
  const uniformity_lfv_n = parseFloat(document.getElementById('qc-lfv').value);
  const dynamic_balance_g = parseFloat(document.getElementById('qc-balance').value);

  try {
    const res = await fetch('/api/quality/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tire_serial,
        inspector_id,
        visual_result,
        visual_defect_code,
        defect_location,
        xray_result,
        xray_defect_code,
        belt_alignment_mm,
        uniformity_rfv_n,
        uniformity_lfv_n,
        dynamic_balance_g
      })
    });

    const data = await res.json();
    if (res.ok) {
      alert(`ĐÁNH GIÁ CHẤT LƯỢNG HOÀN TẤT!\n\nSố Sê-ri: ${data.tire_serial}\nCấp Phân Loại: [${data.final_grade}]\nKết Luận: ${data.disposition_notes}`);

      // Hide form & refresh
      state.selectedQcTire = null;
      document.getElementById('qc-active-form').style.display = 'none';
      document.getElementById('qc-placeholder-msg').style.display = 'block';

      loadInspectionQueue();
      loadDashboard();

      // Automatically switch to Digital Passport to show the finished certificate
      quickLookup(data.tire_serial);
      switchTab('genealogy');
    } else {
      alert(`Lỗi: ${data.detail}`);
    }
  } catch (err) {
    alert('Lỗi: ' + err);
  }
}

// ============================================================================
// TAB 6: 100% DIGITAL TIRE PASSPORT & GENEALOGY
// ============================================================================
function quickLookup(identifier) {
  document.getElementById('passport-search-input').value = identifier;
  lookupPassport();
}

async function lookupPassport() {
  const identifier = document.getElementById('passport-search-input').value.trim();
  if (!identifier) return;

  const viewArea = document.getElementById('passport-view-area');
  viewArea.innerHTML = '<div style="text-align: center; padding: 2rem; color: #38bdf8;">⏳ Đang truy vấn cây phả hệ sản xuất 100% (Genealogy Tree)...</div>';

  try {
    const res = await fetch(`/api/genealogy/passport/${encodeURIComponent(identifier)}`);
    if (!res.ok) {
      viewArea.innerHTML = `<div style="color: #ef4444; padding: 1.5rem; background: rgba(239, 68, 68, 0.1); border-radius: 8px;">Không tìm thấy thông tin sê-ri '${identifier}'!</div>`;
      return;
    }

    const data = await res.json();
    renderPassport(data);
  } catch (err) {
    viewArea.innerHTML = `<div style="color: #ef4444;">Lỗi kết nối tra cứu: ${err}</div>`;
  }
}

function renderPassport(data) {
  const viewArea = document.getElementById('passport-view-area');
  const tire = data.tire;
  const gt = data.green_tire;
  const qc = data.quality_inspection;

  let gradeBadge = 'HẠNG A (OE EXPORT)';
  let gradeColor = '#10b981';

  if (qc) {
    if (qc.final_grade === 'GRADE_B') {
      gradeBadge = 'HẠNG B (AFTERMARKET)';
      gradeColor = '#3b82f6';
    } else if (qc.final_grade === 'REWORK') {
      gradeBadge = 'TÁI CHẾ (REWORK)';
      gradeColor = '#f59e0b';
    } else if (qc.final_grade === 'SCRAP') {
      gradeBadge = 'PHẾ PHẨM (SCRAP)';
      gradeColor = '#ef4444';
    }
  }

  viewArea.innerHTML = `
    <div class="passport-card">
      <div class="passport-watermark">VIETNAM TIRE MES 100% TRACEABLE</div>
      <div class="passport-stamp" style="border-color: ${gradeColor}; color: ${gradeColor};">
        ${gradeBadge}
      </div>

      <!-- Passport Header -->
      <div style="margin-bottom: 1.5rem; max-width: 70%;">
        <div style="font-size: 0.8rem; font-weight: 800; color: #38bdf8; letter-spacing: 0.1em; text-transform: uppercase;">
          CHỨNG CHỈ SẢN PHẨM SỐ &bull; DIGITAL TIRE PASSPORT (ISA-95)
        </div>
        <h2 style="font-size: 1.8rem; font-weight: 900; color: #fff; font-family: var(--font-mono); margin: 0.25rem 0;">
          ${tire ? tire.tire_serial : gt.gt_barcode}
        </h2>
        <div style="font-size: 1rem; color: #e2e8f0; font-weight: 600;">
          ${(tire && tire.tire_size) || (gt && gt.tire_size)} - ${(tire && tire.pattern_name) || (gt && gt.pattern_name)}
        </div>
        <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem;">
          Mã vạch lốp sống: <strong style="color: #38bdf8; font-family: var(--font-mono);">${gt ? gt.gt_barcode : 'N/A'}</strong> &bull; Lệnh sản xuất: <strong>${gt ? gt.wo_id : 'N/A'}</strong>
        </div>
      </div>

      <!-- 5-Stage Complete Timeline Tree -->
      <div class="timeline-tree">

        <!-- Stage 1: Banbury Compounding -->
        <div class="timeline-node passed">
          <div class="timeline-title">
            <span>GIAI ĐOẠN 1: LUYỆN KÍN CAO SU & ĐỘ NHỚT MOONEY (BANBURY MIXING)</span>
          </div>
          <div class="timeline-desc">
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem;">
              <div>Cao su mặt lốp (Tread): <strong>CP-TRD-101</strong> (Mooney 68 ML)</div>
              <div>Cao su hông lốp (Sidewall): <strong>CP-SW-202</strong> (Mooney 54 ML)</div>
              <div>Màng kín khí (Innerliner): <strong>CP-INL-303</strong> (100% Bromobutyl)</div>
              <div>Tráng mành thép (Belt Skim): <strong>CP-SK-404</strong> (Cobalt Adhesion)</div>
            </div>
            <div style="margin-top: 0.35rem; font-size: 0.75rem; color: #34d399;">
              ✓ Đạt thử nghiệm lưu hóa kế Rheometer tc90 & Viscosity ML(1+4) 100&deg;C.
            </div>
          </div>
        </div>

        <!-- Stage 2: Semi-Finished Components -->
        <div class="timeline-node passed">
          <div class="timeline-title">
            <span>GIAI ĐOẠN 2: BÁN THÀNH PHẨM & KIỂM SOÁT HẠN DÙNG (SEMI-FINISHED LOTS)</span>
          </div>
          <div class="timeline-desc">
            <div class="table-responsive">
              <table class="table" style="font-size: 0.78rem;">
                <thead>
                  <tr>
                    <th>Hợp phần</th>
                    <th>Mã Lô Barcode</th>
                    <th>Quy Cách / Mã Cao Su</th>
                    <th>Vị Trí Lưu Kho</th>
                    <th>Kiểm Tra Hạn Dùng</th>
                  </tr>
                </thead>
                <tbody>
                  ${data.components_lineage.map(c => `
                    <tr>
                      <td><strong>${c.component_type}</strong></td>
                      <td><span style="font-family: var(--font-mono); color: #38bdf8;">${c.lot_id}</span></td>
                      <td>${c.spec_code || '--'} (${c.compound_code})</td>
                      <td>${c.storage_location}</td>
                      <td><span class="status-pill pill-green">ĐẠT (VALID)</span></td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Stage 3: Tire Building Machine (TBM) -->
        <div class="timeline-node passed">
          <div class="timeline-title">
            <span>GIAI ĐOẠN 3: THÀNH HÌNH LỐP SỐNG (TBM BUILDING STATION)</span>
          </div>
          <div class="timeline-desc">
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem;">
              <div>Máy đóng lốp: <strong>${gt ? gt.tbm_machine_id : 'TBM-01'}</strong> (${gt ? gt.tbm_machine_name : 'VMI Uni-Stage'})</div>
              <div>Công nhân vận hành: <strong>${gt ? gt.operator_name : 'Nguyễn Văn Hùng'}</strong> (${gt ? gt.operator_id : 'OP-1001'})</div>
              <div>Thời gian đóng: <strong>${gt ? gt.build_timestamp : '--'}</strong></div>
              <div>Trọng lượng thực tế: <strong style="color: #38bdf8;">${gt ? gt.actual_weight_kg : '--'} kg</strong> (Chuẩn: ${(gt && gt.standard_weight_kg) || 9.25} kg)</div>
            </div>
            <div style="margin-top: 0.35rem; font-size: 0.75rem; color: #34d399;">
              ✓ Xác nhận Poka-Yoke: ${gt ? gt.poka_yoke_status : 'VERIFIED_PASS'} &bull; Áp lực con lăn miết đạt chuẩn 4.2 bar.
            </div>
          </div>
        </div>

        <!-- Stage 4: Vulcanization / Curing -->
        <div class="timeline-node ${tire ? (tire.cure_quality_result === 'PASS' ? 'passed' : 'failed') : 'passed'}">
          <div class="timeline-title">
            <span>GIAI ĐOẠN 4: ÉP LƯU HÓA NHIỆT ÁP LỰC (VULCANIZATION & CURING)</span>
          </div>
          <div class="timeline-desc">
            ${tire ? `
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem;">
                <div>Lò lưu hóa: <strong>${tire.press_id} - Hộc ${tire.cavity_side}</strong></div>
                <div>Khuôn mẫu hoa gai: <strong>${tire.mold_id}</strong></div>
                <div>Thời gian nén nhiệt: <strong>${tire.actual_cure_sec} giây</strong> (${Math.round(tire.actual_cure_sec/60)} phút)</div>
                <div>Nhiệt độ khuôn TB: <strong>${tire.avg_mold_temp_c}&deg;C</strong> (Chuẩn: 170.0&deg;C)</div>
                <div>Áp suất bàng bọng TB: <strong>${tire.avg_bladder_press_bar} bar</strong> (Chuẩn: 21.0 bar)</div>
                <div>Thời điểm ra lò: <strong>${tire.cure_end_time}</strong></div>
              </div>
              <div style="margin-top: 0.35rem; font-size: 0.75rem; color: ${tire.cure_quality_result === 'PASS' ? '#34d399' : '#ef4444'};">
                ${tire.cure_quality_result === 'PASS' ? '✓ Biểu đồ nhiệt/áp suất lưu hóa hoàn toàn đạt dung sai tiêu chuẩn (&plusmn;2&deg;C, &plusmn;0.5 bar).' : '❌ CẢNH BÁO: Tụt áp suất bàng lưu hóa trong chu kỳ nén!'}
              </div>
            ` : `
              <div style="color: #f59e0b;">Lốp hiện đang trong vùng đệm hoặc đang chờ lưu hóa.</div>
            `}
          </div>
        </div>

        <!-- Stage 5: Quality Inspection (KCS) -->
        <div class="timeline-node ${qc ? (qc.passed ? 'passed' : 'failed') : 'passed'}">
          <div class="timeline-title">
            <span>GIAI ĐOẠN 5: KIỂM TRA CHẤT LƯỢNG KCS (X-RAY & DYNAMIC BALANCING)</span>
          </div>
          <div class="timeline-desc">
            ${qc ? `
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem;">
                <div>Kiểm nghiệm viên: <strong>${qc.inspector_name || qc.inspector_id}</strong></div>
                <div>Thời điểm KCS: <strong>${qc.inspection_timestamp}</strong></div>
                <div>Ngoại quan (Visual): <strong style="color: ${qc.visual_result === 'PASS' ? '#34d399' : '#ef4444'}">${qc.visual_result}</strong> ${qc.visual_defect_name ? `(${qc.visual_defect_name})` : ''}</div>
                <div>Soi X-Ray cấu trúc: <strong style="color: ${qc.xray_result === 'PASS' ? '#34d399' : '#ef4444'}">${qc.xray_result}</strong> ${qc.xray_defect_name ? `(${qc.xray_defect_name})` : ''}</div>
                <div>Lực đồng đều RFV: <strong>${qc.uniformity_rfv_n} N</strong> (&le; 80 N)</div>
                <div>Mất cân bằng động: <strong>${qc.dynamic_balance_g} g</strong> (&le; 30 g)</div>
              </div>
              <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.05); font-weight: 600; color: #f1f5f9;">
                Kết luận nghiệm thu: <span style="color: ${gradeColor};">[${qc.final_grade}]</span> - ${qc.disposition_notes}
              </div>
            ` : `
              <div style="color: #94a3b8;">Chưa có dữ liệu kiểm tra KCS.</div>
            `}
          </div>
        </div>

      </div>

      <!-- Action Footer -->
      <div style="margin-top: 2rem; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 1rem;">
        <div style="font-size: 0.75rem; color: #94a3b8;">
          Hệ Thống Xác Thực: <strong>${data.cert_issued_by}</strong> &bull; Trạng thái: <strong style="color: #34d399;">${data.traceability_status}</strong>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="window.print()">
          🖨️ In Giấy Chứng Nhận
        </button>
      </div>
    </div>
  `;
}

// ============================================================================
// TAB 7: MASTER DATA & CONFIG
// ============================================================================
async function showMasterSubTab(type) {
  const container = document.getElementById('master-subcontent');
  if (!container) return;

  container.innerHTML = '<div style="padding: 1rem; color: #38bdf8;">Đang tải dữ liệu...</div>';

  try {
    if (type === 'products') {
      const res = await fetch('/api/master/products');
      const prods = await res.json();
      container.innerHTML = `
        <div class="table-responsive">
          <table class="table">
            <thead>
              <tr>
                <th>Mã SKU</th>
                <th>Kích Cỡ</th>
                <th>Hoa Gai</th>
                <th>Phân Khúc</th>
                <th>Chỉ Số Tải/Tốc Độ</th>
                <th>Trọng Lượng Chuẩn</th>
                <th>Chu Kỳ TBM (s)</th>
                <th>Chu Kỳ Lưu Hóa (s)</th>
              </tr>
            </thead>
            <tbody>
              ${prods.map(p => `
                <tr>
                  <td><strong style="color: #38bdf8; font-family: var(--font-mono);">${p.sku}</strong></td>
                  <td><strong>${p.tire_size}</strong></td>
                  <td>${p.pattern_name}</td>
                  <td><span class="status-pill pill-purple">${p.segment}</span></td>
                  <td>${p.load_index} ${p.speed_rating}</td>
                  <td>${p.standard_weight_kg} &plusmn; ${p.weight_tolerance_kg} kg</td>
                  <td>${p.std_tbm_time_sec} s</td>
                  <td>${p.std_cure_time_sec} s (${Math.round(p.std_cure_time_sec/60)}m)</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else if (type === 'equipment') {
      const res = await fetch('/api/master/equipment');
      const eq = await res.json();
      container.innerHTML = `
        <div class="table-responsive">
          <table class="table">
            <thead>
              <tr>
                <th>Mã Máy</th>
                <th>Tên Thiết Bị</th>
                <th>Khu Vực (Area)</th>
                <th>Model</th>
                <th>Số Hộc Khuôn</th>
                <th>Tổng Chu Kỳ</th>
                <th>Mục Tiêu OEE</th>
                <th>Trạng Thái</th>
              </tr>
            </thead>
            <tbody>
              ${eq.map(e => `
                <tr>
                  <td><strong style="color: #38bdf8; font-family: var(--font-mono);">${e.machine_id}</strong></td>
                  <td>${e.machine_name}</td>
                  <td>${e.area_name}</td>
                  <td>${e.model}</td>
                  <td>${e.cavities_count}</td>
                  <td>${e.total_cycles}</td>
                  <td>${e.oee_target}%</td>
                  <td><span class="status-pill ${e.status === 'RUNNING' ? 'pill-green' : 'pill-amber'}">${e.status}</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else if (type === 'defects') {
      const res = await fetch('/api/master/defects');
      const defs = await res.json();
      container.innerHTML = `
        <div class="table-responsive">
          <table class="table">
            <thead>
              <tr>
                <th>Mã Lỗi</th>
                <th>Tên Khuyết Tật (Tiếng Việt)</th>
                <th>Tên Quốc Tế (English)</th>
                <th>Trạm Phát Hiện</th>
                <th>Mức Độ (Severity)</th>
                <th>Xử Lý Mặc Định</th>
                <th>Khu Vực Gốc</th>
              </tr>
            </thead>
            <tbody>
              ${defs.map(d => `
                <tr>
                  <td><strong style="color: #f87171; font-family: var(--font-mono);">${d.defect_code}</strong></td>
                  <td>${d.defect_name_vi}</td>
                  <td>${d.defect_name_en}</td>
                  <td><span class="status-pill pill-blue">${d.inspection_station}</span></td>
                  <td><span class="status-pill ${d.severity === 'CRITICAL' ? 'pill-red' : d.severity === 'MAJOR' ? 'pill-amber' : 'pill-purple'}">${d.severity}</span></td>
                  <td><strong style="color: ${d.default_disposition === 'SCRAP' ? '#ef4444' : '#f59e0b'}">${d.default_disposition}</strong></td>
                  <td>${d.root_cause_area}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else if (type === 'operators') {
      const res = await fetch('/api/master/operators');
      const ops = await res.json();
      container.innerHTML = `
        <div class="table-responsive">
          <table class="table">
            <thead>
              <tr>
                <th>Mã Thẻ (Badge ID)</th>
                <th>Họ Và Tên</th>
                <th>Chức Danh (Role)</th>
                <th>Ca Làm Việc</th>
                <th>Bậc Tay Nghề (Skill)</th>
              </tr>
            </thead>
            <tbody>
              ${ops.map(o => `
                <tr>
                  <td><strong style="color: #38bdf8; font-family: var(--font-mono);">${o.badge_id}</strong></td>
                  <td>${o.full_name}</td>
                  <td><span class="status-pill pill-blue">${o.role}</span></td>
                  <td>${o.current_shift}</td>
                  <td><strong style="color: #34d399;">Bậc ${o.skill_level}/5</strong></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else if (type === 'documents') {
      const res = await fetch('/api/master/documents');
      const docs = await res.json();
      container.innerHTML = `
        <div style="margin-bottom: 1rem; color: #94a3b8; font-size: 0.85rem;">
          MODULE 4: DOCUMENT CONTROL (Quản lý Quy trình Thao tác Chuẩn e-SOP, Bản vẽ Kỹ thuật Mặt cắt Lốp & Hướng dẫn KCS)
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 1rem;">
          ${docs.map(d => `
            <div class="card" style="background: #151d2c; border: 1px solid var(--border-color); margin-bottom: 0;">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                <div>
                  <span class="status-pill ${d.category === 'DRAWING' ? 'pill-purple' : d.category === 'SOP' ? 'pill-blue' : 'pill-amber'}" style="font-size: 0.7rem;">
                    ${d.category}
                  </span>
                  <h4 style="font-size: 0.95rem; color: #fff; margin-top: 0.35rem;">${d.title}</h4>
                </div>
                <span style="font-family: var(--font-mono); font-size: 0.75rem; color: #38bdf8;">${d.revision}</span>
              </div>
              <div style="font-size: 0.78rem; color: #cbd5e1; margin-bottom: 0.75rem; line-height: 1.3;">
                ${d.summary}
              </div>
              <div style="background: #0d131f; padding: 0.65rem; border-radius: 6px; font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.75rem; max-height: 100px; overflow-y: auto;">
                ${d.content_html}
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: #64748b; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 0.5rem;">
                <span>Phê duyệt: <strong style="color: #cbd5e1;">${d.approved_by}</strong></span>
                <span>Ngày hiệu lực: ${d.effective_date}</span>
              </div>
            </div>
          `).join('')}
        </div>
      `;
    }
  } catch (err) {
    container.innerHTML = `<div style="color: #ef4444;">Lỗi tải master data: ${err}</div>`;
  }
}

async function resetDemoData() {
  if (!confirm('Bạn có chắc chắn muốn Tái Thiết Lập toàn bộ cơ sở dữ liệu về trạng thái mẫu ban đầu?')) return;
  try {
    const res = await fetch('/api/master/reset-demo', { method: 'POST' });
    const data = await res.json();
    alert(data.message);
    loadDashboard();
    loadWorkOrders();
    initTbmStation();
    loadCuringPresses();
    loadInspectionQueue();
    quickLookup('VN-T-202610-00101');
    loadGatewayConnectors();
  } catch (err) {
    alert('Lỗi: ' + err);
  }
}

// ============================================================================
// TAB 8: INDUSTRIAL PROTOCOL GATEWAY (OPC-UA, OPC-DA, MODBUS, MQTT, SOCKET)
// ============================================================================
async function loadGatewayConnectors() {
  const grid = document.getElementById('gateway-connectors-grid');
  if (!grid) return;

  grid.innerHTML = '<div style="color: #38bdf8; padding: 1rem;">Đang tải danh sách cổng giao thức công nghiệp...</div>';

  try {
    const res = await fetch('/api/gateway/connectors');
    const connectors = await res.json();

    const protoIcons = {
      'OPC_UA': '🟢',
      'OPC_DA': '🟡',
      'MODBUS_TCP': '🔵',
      'MQTT': '🟣',
      'TCP_SOCKET': '🟠'
    };

    grid.innerHTML = connectors.map(c => {
      return `
        <div class="card" style="margin-bottom: 0; background: #162032; border: 1px solid var(--border-color);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
            <div>
              <div style="font-size: 0.75rem; font-weight: 800; color: #38bdf8; font-family: var(--font-mono);">${c.connector_id}</div>
              <h4 style="font-size: 1rem; color: #fff; font-weight: 700;">${protoIcons[c.protocol_type] || '⚡'} ${c.name}</h4>
              <div style="font-size: 0.78rem; color: #cbd5e1; margin-top: 2px;">Thiết bị đích: <strong>${c.target_equipment}</strong></div>
            </div>
            <div style="text-align: right;">
              <span class="status-pill pill-green" id="pill-${c.connector_id}">${c.status}</span>
              <div style="font-size: 0.72rem; color: #94a3b8; font-family: var(--font-mono); margin-top: 4px;" id="ping-${c.connector_id}">
                Độ trễ: ${c.last_ping_ms}ms
              </div>
            </div>
          </div>

          <!-- Connection parameters -->
          <div style="background: #0f1523; padding: 0.65rem 0.85rem; border-radius: 6px; font-size: 0.78rem; font-family: var(--font-mono); margin-bottom: 0.75rem; border: 1px solid rgba(255, 255, 255, 0.05);">
            <div>Endpoint: <span style="color: #38bdf8;">${c.endpoint_url}</span></div>
            <div>Cổng: <span style="color: #f1f5f9;">${c.port}</span> &bull; Quét: <span style="color: #f1f5f9;">${c.scan_rate_ms}ms</span></div>
          </div>

          <div style="font-size: 0.78rem; color: #94a3b8; margin-bottom: 0.75rem; line-height: 1.3;">
            ${c.description}
          </div>

          <!-- Sample Payload preview -->
          <div style="background: #090d16; padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.72rem; font-family: var(--font-mono); color: #a5f3fc; margin-bottom: 0.85rem; overflow-x: auto; white-space: pre-wrap; max-height: 60px;">
${c.sample_payload}
          </div>

          <!-- Action buttons -->
          <div style="display: flex; gap: 0.5rem;">
            <button class="btn btn-secondary btn-sm" onclick="testConnectorPing('${c.connector_id}')" style="flex: 1;">
              ⚡ Test Handshake (Ping)
            </button>
            <button class="btn btn-primary btn-sm" onclick="simulateConnectorPacket('${c.connector_id}')" style="flex: 1;">
              📡 Gửi Gói Tin Mẫu
            </button>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    grid.innerHTML = `<div style="color: #ef4444;">Lỗi tải cấu hình cổng giao thức: ${err}</div>`;
  }
}

async function testConnectorPing(connector_id) {
  const terminal = document.getElementById('gateway-terminal-logs');
  terminal.textContent += `\n[PING REQUEST] Đang gửi kiểm tra bắt tay (Handshake) tới ${connector_id}...\n`;
  terminal.scrollTop = terminal.scrollHeight;

  try {
    const res = await fetch('/api/gateway/test-ping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ connector_id })
    });
    const data = await res.json();
    if (res.ok) {
      document.getElementById(`ping-${connector_id}`).textContent = `Độ trễ: ${data.latency_ms}ms`;
      data.logs.forEach(log => {
        terminal.textContent += `  ${log}\n`;
      });
      terminal.textContent += `[SUCCESS] ${connector_id} (${data.protocol_type}) phản hồi tốt! Độ trễ đo được: ${data.latency_ms}ms\n--------------------------------------------------\n`;
      terminal.scrollTop = terminal.scrollHeight;
    }
  } catch (err) {
    terminal.textContent += `[ERROR] Lỗi kết nối: ${err}\n`;
  }
}

async function simulateConnectorPacket(connector_id) {
  const terminal = document.getElementById('gateway-terminal-logs');
  terminal.textContent += `\n[PACKET SIM] Đang kích hoạt truyền gói tin cảm biến công nghiệp từ ${connector_id}...\n`;

  try {
    const res = await fetch('/api/gateway/simulate-packet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ connector_id, custom_value: "" })
    });
    const data = await res.json();
    if (res.ok) {
      terminal.textContent += `[DECODED PACKET FROM ${data.protocol_type} AT ${data.timestamp}]\n`;
      terminal.textContent += JSON.stringify(data.decoded_object, null, 2) + '\n';
      terminal.textContent += `[MES INGESTION OK] Dữ liệu đã được nạp thành công vào mô hình ISA-95!\n--------------------------------------------------\n`;
      terminal.scrollTop = terminal.scrollHeight;
    }
  } catch (err) {
    terminal.textContent += `[ERROR] Lỗi giải mã: ${err}\n`;
  }
}

function clearGatewayLogs() {
  document.getElementById('gateway-terminal-logs').textContent = '[SYSTEM] Nhật ký đã được xóa. Sẵn sàng giám sát luồng gói tin mới...';
}

// ============================================================================
// ANTI-SKIP & SEQUENCE INTERLOCK ENGINE (CHỐNG NHẢY CÓC CÔNG ĐOẠN)
// ============================================================================
async function testAntiSkipPreset(presetType) {
  const inputEl = document.getElementById('anti-skip-input-id');
  const stageEl = document.getElementById('anti-skip-target-stage');

  if (presetType === 'CURING_SKIP') {
    // Green tire trying to jump straight to KCS Finishing
    inputEl.value = 'GT-202610-0019';
    stageEl.value = 'FINISHING';
  } else if (presetType === 'QC_SKIP') {
    // Uninspected cured tire trying to enter Warehouse
    inputEl.value = 'VN-T-202610-00119';
    stageEl.value = 'WAREHOUSE';
  } else if (presetType === 'SCRAP_BREACH') {
    // Scrapped tire VN-T-202610-00108 trying to enter Warehouse
    inputEl.value = 'VN-T-202610-00108';
    stageEl.value = 'WAREHOUSE';
  } else if (presetType === 'VALID_DISPATCH') {
    // Grade A tire VN-T-202610-00101 entering Warehouse
    inputEl.value = 'VN-T-202610-00101';
    stageEl.value = 'WAREHOUSE';
  }

  await verifyStageManual();
}

async function verifyStageManual() {
  const identifier = document.getElementById('anti-skip-input-id').value.trim();
  const targetStage = document.getElementById('anti-skip-target-stage').value;
  const resultBox = document.getElementById('anti-skip-result-box');

  if (!identifier) {
    alert('Vui lòng nhập mã Barcode hoặc Sê-ri lốp!');
    return;
  }

  resultBox.style.display = 'block';
  resultBox.innerHTML = '<div style="color: #94a3b8; font-size: 0.85rem;">⏳ Đang đối soát phả hệ CSDL và kiểm tra liên khóa liên công đoạn...</div>';

  try {
    const res = await fetch('/api/routing/verify-transition', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, target_stage: targetStage })
    });
    const data = await res.json();

    if (data.permitted) {
      resultBox.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.12); border: 1.5px solid #10b981; border-radius: 8px; padding: 1rem;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
            <strong style="color: #34d399; font-size: 0.95rem; display: flex; align-items: center; gap: 6px;">
              ✅ CHO PHÉP CHUYỂN TIẾP (PERMITTED)
            </strong>
            <span class="status-pill pill-green">${data.current_stage} &rarr; ${data.target_stage || targetStage}</span>
          </div>
          <div style="color: #e2e8f0; font-size: 0.88rem; line-height: 1.5;">${data.message}</div>
          ${data.final_grade ? `<div style="margin-top: 0.5rem; font-size: 0.8rem; color: #94a3b8;">Cấp hạng KCS nghiệm thu: <strong style="color: #34d399;">${data.final_grade}</strong></div>` : ''}
        </div>
      `;
    } else {
      resultBox.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.15); border: 1.5px solid #ef4444; border-radius: 8px; padding: 1rem;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
            <strong style="color: #f87171; font-size: 0.95rem; display: flex; align-items: center; gap: 6px;">
              🚨 CẢNH BÁO VI PHẠM: CHẶN NHẢY CÓC CÔNG ĐOẠN!
            </strong>
            <span class="status-pill pill-red" style="font-family: var(--font-mono);">${data.error_code || 'INTERLOCK_BLOCKED'}</span>
          </div>
          <div style="color: #fecaca; font-size: 0.88rem; font-weight: 500; line-height: 1.5;">${data.message}</div>
          <div style="margin-top: 0.5rem; font-size: 0.8rem; color: #94a3b8; display: flex; gap: 1rem;">
            <span>Trạng thái hiện tại: <strong style="color: #fca5a5;">${data.current_stage}</strong></span>
            <span>Hành động MES: <strong style="color: #fbbf24;">Khóa PLC / Hú còi Andon / Chặn rào chắn</strong></span>
          </div>
        </div>
      `;
    }
  } catch (err) {
    resultBox.innerHTML = `<div style="color: #ef4444; font-size: 0.85rem;">Lỗi kết nối API: ${err}</div>`;
  }
}

// ============================================================================
// TAB 9: AI ANOMALY DETECTION (ISOLATION FOREST & DEEP AUTOENCODER)
// ============================================================================

let aiCurrentScannedCycles = [];

async function loadAiTab() {
  await loadAiStatus();
  await scanAiCycles();
  await loadAiAnomalyLogs();
}

async function loadAiStatus() {
  try {
    const res = await fetch('/api/ai/status');
    const data = await res.json();
    if (data.models && data.models.deep_autoencoder) {
      const aeThresholdEl = document.getElementById('ai-kpi-ae-threshold');
      if (aeThresholdEl) aeThresholdEl.textContent = Number(data.models.deep_autoencoder.reconstruction_threshold).toFixed(3);
    }
    const samplesEl = document.getElementById('ai-kpi-samples');
    if (samplesEl) samplesEl.textContent = (data.total_baseline_samples || 1200).toLocaleString('vi-VN');
  } catch (err) {
    console.error('Error fetching AI status:', err);
  }
}

async function trainAiModels() {
  const btn = event?.target;
  const originalText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Đang huấn luyện...';
  }

  try {
    const res = await fetch('/api/ai/train', { method: 'POST' });
    const data = await res.json();
    alert(`✅ ${data.message}\nNgưỡng MSE: ${data.ae_threshold}\nSố mẫu Baseline: ${data.baseline_samples}`);
    await loadAiTab();
  } catch (err) {
    alert(`Lỗi tái huấn luyện mô hình: ${err}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }
}

async function scanAiCycles() {
  try {
    const res = await fetch('/api/ai/scan-cycles');
    const data = await res.json();

    aiCurrentScannedCycles = data.all_cycles || [];

    // KPI updates
    const indexEl = document.getElementById('ai-kpi-anomaly-index');
    if (indexEl) indexEl.textContent = data.plant_anomaly_index.toFixed(2);

    const statusTextEl = document.getElementById('ai-kpi-status-text');
    const statusPillEl = document.getElementById('ai-kpi-status-pill');
    if (statusTextEl && statusPillEl) {
      if (data.plant_anomaly_index > 0.6) {
        statusTextEl.textContent = 'Báo Động Cao';
        statusPillEl.className = 'status-pill pill-red';
        statusPillEl.textContent = 'NGUY HIỂM';
      } else if (data.plant_anomaly_index > 0.35) {
        statusTextEl.textContent = 'Có Suy Thoái';
        statusPillEl.className = 'status-pill pill-yellow';
        statusPillEl.textContent = 'CẢNH BÁO';
      } else {
        statusTextEl.textContent = 'Vận Hành Chuẩn';
        statusPillEl.className = 'status-pill pill-green';
        statusPillEl.textContent = 'TỐI ƯU';
      }
    }

    const creepEl = document.getElementById('ai-kpi-takt-creep');
    if (creepEl) creepEl.textContent = `+${data.avg_takt_creep_sec}s`;

    const lossRateEl = document.getElementById('ai-kpi-loss-rate');
    if (lossRateEl) {
      const lossRate = ((data.avg_takt_creep_sec / 45.0) * 100).toFixed(1);
      lossRateEl.textContent = `${lossRate}%`;
    }

    const countEl = document.getElementById('ai-kpi-anomaly-count');
    if (countEl) countEl.textContent = data.total_anomalies_detected;

    const critCount = (data.anomalies || []).filter(a => a.severity === 'CRITICAL').length;
    const warnCount = (data.anomalies || []).filter(a => a.severity === 'WARNING').length;

    const critEl = document.getElementById('ai-kpi-crit-count');
    if (critEl) critEl.textContent = critCount;

    const warnEl = document.getElementById('ai-kpi-warn-count');
    if (warnEl) warnEl.textContent = warnCount;

    // Render Canvas
    renderAiScatterCanvas(aiCurrentScannedCycles);
    await loadAiAnomalyLogs();
  } catch (err) {
    console.error('Error scanning cycles:', err);
  }
}

function renderAiScatterCanvas(cycles) {
  const canvas = document.getElementById('ai-scatter-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  // Clear
  ctx.clearRect(0, 0, w, h);

  // Background
  ctx.fillStyle = '#070a13';
  ctx.fillRect(0, 0, w, h);

  const padding = { top: 30, right: 40, bottom: 40, left: 60 };
  const plotW = w - padding.left - padding.right;
  const plotH = h - padding.top - padding.bottom;

  // Ranges
  const minX = -10, maxX = 70; // Takt deviation (sec)
  const minY = 0, maxY = 320;   // WIP dwell (min)

  const toScreenX = (x) => padding.left + ((x - minX) / (maxX - minX)) * plotW;
  const toScreenY = (y) => padding.top + plotH - ((y - minY) / (maxY - minY)) * plotH;

  // Draw Grid Lines
  ctx.strokeStyle = '#1e293b';
  ctx.lineWidth = 1;

  for (let x = 0; x <= maxX; x += 15) {
    const sx = toScreenX(x);
    ctx.beginPath();
    ctx.moveTo(sx, padding.top);
    ctx.lineTo(sx, padding.top + plotH);
    ctx.stroke();

    ctx.fillStyle = '#64748b';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`${x}s`, sx, padding.top + plotH + 15);
  }

  for (let y = 0; y <= maxY; y += 60) {
    const sy = toScreenY(y);
    ctx.beginPath();
    ctx.moveTo(padding.left, sy);
    ctx.lineTo(padding.left + plotW, sy);
    ctx.stroke();

    ctx.fillStyle = '#64748b';
    ctx.font = '10px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(`${y}m`, padding.left - 8, sy + 3);
  }

  // Draw Warning Threshold Boundaries
  // 1. Takt Creep threshold: X = +15s
  const threshX = toScreenX(15);
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.4)';
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(threshX, padding.top);
  ctx.lineTo(threshX, padding.top + plotH);
  ctx.stroke();

  // 2. WIP Shelf Dwell threshold: Y = 180 min
  const threshY = toScreenY(180);
  ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)';
  ctx.beginPath();
  ctx.moveTo(padding.left, threshY);
  ctx.lineTo(padding.left + plotW, threshY);
  ctx.stroke();
  ctx.setLineDash([]);

  // Axis Labels
  ctx.fillStyle = '#94a3b8';
  ctx.font = '11px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Độ Lệch Chu Kỳ Máy Thực Tế So Với Định Mức: Takt Deviation (giây)', padding.left + plotW / 2, h - 8);

  ctx.save();
  ctx.translate(16, padding.top + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText('Thời Gian Chờ Đệm: WIP Dwell Time (phút)', 0, 0);
  ctx.restore();

  // Draw Threshold Labels
  ctx.fillStyle = '#f59e0b';
  ctx.font = '9px monospace';
  ctx.textAlign = 'left';
  ctx.fillText('Ngưỡng Trôi Takt (+15s)', threshX + 4, padding.top + 12);

  ctx.fillStyle = '#ef4444';
  ctx.textAlign = 'right';
  ctx.fillText('Ngưỡng Lão Hóa WIP (>180m)', padding.left + plotW - 6, threshY - 6);

  // Plot Cycles Points
  if (!cycles || cycles.length === 0) return;

  cycles.forEach(c => {
    const devX = c.metrics ? c.metrics.takt_deviation_sec : 0;
    const dwellY = c.metrics ? c.metrics.wip_queue_dwell_min : 0;
    const score = c.ensemble_anomaly_score || 0;

    const sx = toScreenX(Math.min(maxX, Math.max(minX, devX)));
    const sy = toScreenY(Math.min(maxY, Math.max(minY, dwellY)));

    ctx.beginPath();
    const radius = 4 + score * 8;
    ctx.arc(sx, sy, radius, 0, 2 * Math.PI);

    if (c.severity === 'CRITICAL' || score >= 0.75) {
      ctx.fillStyle = 'rgba(239, 68, 68, 0.85)';
      ctx.strokeStyle = '#f87171';
      ctx.lineWidth = 2;
    } else if (c.severity === 'WARNING' || score >= 0.5) {
      ctx.fillStyle = 'rgba(245, 158, 11, 0.75)';
      ctx.strokeStyle = '#fbbf24';
      ctx.lineWidth = 1.5;
    } else {
      ctx.fillStyle = 'rgba(16, 185, 129, 0.65)';
      ctx.strokeStyle = '#34d399';
      ctx.lineWidth = 1;
    }

    ctx.fill();
    ctx.stroke();

    // Machine label for anomalies
    if (c.is_anomaly || score >= 0.5) {
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 9px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(`${c.machine_id} (${score})`, sx + radius + 4, sy + 3);
    }
  });
}

function setAiPreset(preset) {
  const machineEl = document.getElementById('ai-sim-machine');
  const typeEl = document.getElementById('ai-sim-cycletype');
  const actualEl = document.getElementById('ai-sim-actual-takt');
  const targetEl = document.getElementById('ai-sim-target-takt');
  const wipEl = document.getElementById('ai-sim-wip-dwell');
  const tempEl = document.getElementById('ai-sim-temp-dev');
  const pressEl = document.getElementById('ai-sim-press-dev');

  if (preset === 'NORMAL') {
    machineEl.value = 'TBM-01';
    typeEl.value = 'BUILDING_STAGE1';
    actualEl.value = '45.2';
    targetEl.value = '45.0';
    wipEl.value = '65.0';
    tempEl.value = '0.2';
    pressEl.value = '0.05';
  } else if (preset === 'TAKT_CREEP') {
    machineEl.value = 'TBM-01';
    typeEl.value = 'BUILDING_STAGE1';
    actualEl.value = '68.5';
    targetEl.value = '45.0';
    wipEl.value = '82.0';
    tempEl.value = '0.3';
    pressEl.value = '-0.25';
  } else if (preset === 'QUEUE_CONGESTION') {
    machineEl.value = 'TBM-02';
    typeEl.value = 'BUILDING_STAGE2';
    actualEl.value = '52.0';
    targetEl.value = '50.0';
    wipEl.value = '295.0';
    tempEl.value = '0.1';
    pressEl.value = '0.02';
  } else if (preset === 'CURING_DRIFT') {
    machineEl.value = 'CURING-P01';
    typeEl.value = 'CURING_CYCLE';
    actualEl.value = '865.0';
    targetEl.value = '780.0';
    wipEl.value = '45.0';
    tempEl.value = '-5.4';
    pressEl.value = '-1.85';
  }
}

async function evaluateLiveCycleSim() {
  const resultBox = document.getElementById('ai-sim-result-box');
  resultBox.style.display = 'block';
  resultBox.innerHTML = '<div style="color: #94a3b8; font-size: 0.85rem;">⏳ Đang đưa vector đặc trưng vào mạng Autoencoder & Isolation Forest...</div>';

  const payload = {
    machine_id: document.getElementById('ai-sim-machine').value.trim() || 'TBM-01',
    cycle_type: document.getElementById('ai-sim-cycletype').value,
    sku: 'PCR-205-55R16-91V',
    actual_takt_sec: parseFloat(document.getElementById('ai-sim-actual-takt').value) || 45.0,
    target_takt_sec: parseFloat(document.getElementById('ai-sim-target-takt').value) || 45.0,
    wip_queue_dwell_min: parseFloat(document.getElementById('ai-sim-wip-dwell').value) || 60.0,
    temp_deviation_c: parseFloat(document.getElementById('ai-sim-temp-dev').value) || 0.0,
    pressure_deviation_bar: parseFloat(document.getElementById('ai-sim-press-dev').value) || 0.0
  };

  try {
    const res = await fetch('/api/ai/evaluate-live', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    let borderCol = '#10b981';
    let bgCol = 'rgba(16, 185, 129, 0.12)';
    let pillCol = 'pill-green';
    let icon = '✅';

    if (data.severity === 'CRITICAL') {
      borderCol = '#ef4444';
      bgCol = 'rgba(239, 68, 68, 0.15)';
      pillCol = 'pill-red';
      icon = '🚨';
    } else if (data.severity === 'WARNING') {
      borderCol = '#f59e0b';
      bgCol = 'rgba(245, 158, 11, 0.15)';
      pillCol = 'pill-yellow';
      icon = '⚠️';
    }

    resultBox.innerHTML = `
      <div style="background: ${bgCol}; border: 1.5px solid ${borderCol}; border-radius: 8px; padding: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <div style="font-size: 1rem; font-weight: 600; color: #fff; display: flex; align-items: center; gap: 8px;">
            <span>${icon}</span>
            <span>Kết Quả Giám Định AI Chu Kỳ: ${data.machine_id}</span>
          </div>
          <span class="status-pill ${pillCol}">MỨC ĐỘ: ${data.severity}</span>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 6px; margin-bottom: 0.75rem; font-size: 0.82rem;">
          <div>Điểm Ensemble Score: <strong style="color: #fff; font-size: 0.95rem;">${data.ensemble_anomaly_score}</strong></div>
          <div>iForest Score: <strong style="color: #38bdf8;">${data.isolation_forest_score}</strong></div>
          <div>Autoencoder Loss: <strong style="color: #c084fc;">${data.autoencoder_loss}</strong> (Ngưỡng: ${data.threshold})</div>
          <div>Phán Quyết: <strong style="color: ${borderCol};">${data.is_anomaly ? 'BẤT THƯỜNG / DỊ BIỆT' : 'BÌNH THƯỜNG'}</strong></div>
        </div>

        <div style="font-size: 0.88rem; color: #e2e8f0; margin-bottom: 0.5rem; line-height: 1.5;">
          <strong>Chẩn đoán nguyên nhân gốc rễ (Root Cause):</strong><br>
          <span style="color: #f8fafc;">${data.root_cause_diagnosis}</span>
        </div>

        <div style="font-size: 0.85rem; color: #94a3b8; background: rgba(255,255,255,0.05); padding: 0.6rem 0.8rem; border-radius: 4px; line-height: 1.5;">
          <strong style="color: #fbbf24;">Khuyến nghị khắc phục kỹ thuật (Mitigation):</strong> ${data.mitigation_action}
        </div>
      </div>
    `;

    // Refresh logs in background
    loadAiAnomalyLogs();
  } catch (err) {
    resultBox.innerHTML = `<div style="color: #ef4444; font-size: 0.85rem;">Lỗi kết nối AI Engine: ${err}</div>`;
  }
}

async function loadAiAnomalyLogs() {
  const tbody = document.getElementById('ai-anomalies-table-body');
  if (!tbody) return;

  try {
    const res = await fetch('/api/ai/anomalies-log?limit=30');
    const logs = await res.json();

    if (!logs || logs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; color: #64748b; padding: 1.5rem;">
            Chưa có ghi nhận bất thường nào. Hệ thống vận hành hoàn hảo!
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = logs.map(l => {
      let pillClass = 'pill-green';
      if (l.severity === 'CRITICAL') pillClass = 'pill-red';
      else if (l.severity === 'WARNING') pillClass = 'pill-yellow';

      const isAcked = l.status === 'ACKNOWLEDGED';

      return `
        <tr>
          <td style="font-family: var(--font-mono); font-size: 0.82rem; color: #38bdf8;">${l.entity_id || 'CYC-' + l.id}</td>
          <td><strong style="color: #fff;">${l.entity_type}</strong></td>
          <td style="font-size: 0.8rem; color: #94a3b8;">${l.timestamp ? l.timestamp.replace('T', ' ').substring(0, 19) : '--'}</td>
          <td style="font-family: var(--font-mono);"><strong style="color: #f8fafc;">${Number(l.anomaly_score).toFixed(3)}</strong></td>
          <td><span class="status-pill ${pillClass}">${l.severity}</span></td>
          <td style="max-width: 280px; font-size: 0.82rem; color: #e2e8f0; line-height: 1.4;">${l.root_cause_diagnosis || '--'}</td>
          <td style="max-width: 250px; font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">${l.mitigation_action || '--'}</td>
          <td>
            ${isAcked
              ? '<span style="color: #10b981; font-size: 0.8rem; font-weight: 500;">✓ Đã xác nhận</span>'
              : `<button class="btn btn-secondary btn-sm" onclick="acknowledgeAiAnomaly(${l.id})">Xác nhận</button>`
            }
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading AI anomaly logs:', err);
  }
}

async function acknowledgeAiAnomaly(id) {
  try {
    const res = await fetch(`/api/ai/acknowledge/${id}`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      loadAiAnomalyLogs();
    }
  } catch (err) {
    alert(`Lỗi xác nhận cảnh báo: ${err}`);
  }
}

// ============================================================================
// TAB 10: DYNAMIC BOTTLENECK PREDICTION & AUTOMATED MATERIAL REROUTING
// ============================================================================

let currentBottleneckForecast = null;

async function loadBottleneckTab() {
  await loadBottleneckForecast();
  await loadDynamicRoutingRules();
}

async function loadBottleneckForecast() {
  try {
    const res = await fetch('/api/bottleneck/forecast?horizons=1,2,3,4');
    const data = await res.json();
    currentBottleneckForecast = data;

    const curr = data.current_bottleneck || {};
    const fc2 = data.forecast_2h || {};
    const fc4 = data.forecast_4h || {};

    // Update KPI 1: Current Bottleneck
    const currStEl = document.getElementById('bn-kpi-current-st');
    if (currStEl) currStEl.textContent = curr.station_id || 'TBM-01';

    const currBliEl = document.getElementById('bn-kpi-current-bli');
    if (currBliEl) currBliEl.textContent = curr.current_bli ? curr.current_bli.toFixed(2) : '0.78';

    // Update KPI 2: Predicted Bottleneck (2h-4h)
    const predStEl = document.getElementById('bn-kpi-pred-st');
    if (predStEl) predStEl.textContent = fc2.predicted_bottleneck_station || 'CP-02';

    const shiftProbEl = document.getElementById('bn-kpi-shift-prob');
    if (shiftProbEl) shiftProbEl.textContent = fc2.shift_probability ? `${(fc2.shift_probability * 100).toFixed(1)}%` : '88.5%';

    const shiftPillEl = document.getElementById('bn-kpi-shift-pill');
    if (shiftPillEl) {
      if (fc2.shift_detected) {
        shiftPillEl.className = 'status-pill pill-red';
        shiftPillEl.textContent = 'DỊCH CHUYỂN';
      } else {
        shiftPillEl.className = 'status-pill pill-green';
        shiftPillEl.textContent = 'ỔN ĐỊNH';
      }
    }

    // Update KPI 3: Buffer Fill
    const bufFillEl = document.getElementById('bn-kpi-buffer-fill');
    if (bufFillEl) bufFillEl.textContent = fc2.buffer_fill_pct ? fc2.buffer_fill_pct.toFixed(1) : '68.5';

    const bufStatusEl = document.getElementById('bn-kpi-buffer-status');
    if (bufStatusEl) {
      if (fc2.buffer_fill_pct > 80) {
        bufStatusEl.className = 'status-pill pill-red';
        bufStatusEl.textContent = 'NGUY CƠ KẸT DỘI NGƯỢC';
      } else if (fc2.buffer_fill_pct > 65) {
        bufStatusEl.className = 'status-pill pill-yellow';
        bufStatusEl.textContent = 'CẢNH BÁO TÍCH TỤ';
      } else {
        bufStatusEl.className = 'status-pill pill-green';
        bufStatusEl.textContent = 'THÔNG SUỐT';
      }
    }

    // Update KPI 4: Reroute Status
    const rerouteStatusEl = document.getElementById('bn-kpi-reroute-status');
    const reroutePillEl = document.getElementById('bn-kpi-reroute-pill');
    if (rerouteStatusEl && reroutePillEl) {
      if (data.is_rerouting_active) {
        rerouteStatusEl.textContent = 'ĐANG BẺ GHI 45%';
        reroutePillEl.className = 'status-pill pill-green';
        reroutePillEl.textContent = 'ĐANG KÍCH HOẠT';
      } else if (fc2.reroute_action_needed) {
        rerouteStatusEl.textContent = 'CẦN BẺ GHI GẤP';
        reroutePillEl.className = 'status-pill pill-red';
        reroutePillEl.textContent = 'CẢNH BÁO';
      } else {
        rerouteStatusEl.textContent = 'LUỒNG CHUẨN SOP';
        reroutePillEl.className = 'status-pill pill-cyan';
        reroutePillEl.textContent = 'TIÊU CHUẨN';
      }
    }

    // Update KPI 5: Protected OEE
    const oeeEl = document.getElementById('bn-kpi-protected-oee');
    if (oeeEl) oeeEl.textContent = `+${data.plant_throughput_protected_pct || 14.5}%`;

    // Render Timeline Bar
    renderBottleneckTimeline(data.all_horizons || []);

    // Render Canvas Topology Flow Map
    renderBottleneckTopologyCanvas(data);
  } catch (err) {
    console.error('Error loading bottleneck forecast:', err);
  }
}

function renderBottleneckTimeline(horizons) {
  const container = document.getElementById('bn-timeline-container');
  if (!container) return;

  container.innerHTML = horizons.map(h => {
    const isShift = h.shift_detected;
    const bli = h.station_bli_scores ? (h.station_bli_scores[h.predicted_bottleneck_station] || 0) : 0;
    let pillClass = 'pill-green';
    if (bli >= 0.70) pillClass = 'pill-red';
    else if (bli >= 0.50) pillClass = 'pill-yellow';

    return `
      <div style="background: #090e1a; border: 1px solid ${isShift ? '#ef4444' : '#1e293b'}; border-radius: 8px; padding: 1rem; position: relative;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <strong style="color: #38bdf8; font-size: 0.9rem;">Mốc T+${h.horizon_hours}h (${h.horizon_time})</strong>
          <span class="status-pill ${pillClass}">BLI: ${Number(bli).toFixed(2)}</span>
        </div>
        <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.35rem;">Điểm nghẽn dự báo:</div>
        <div style="font-size: 0.95rem; font-weight: 600; color: #fff; margin-bottom: 0.5rem;">
          ${h.predicted_bottleneck_station}
        </div>
        <div style="font-size: 0.78rem; color: #cbd5e1; margin-bottom: 0.5rem; line-height: 1.4;">
          ${h.predicted_bottleneck_name}
        </div>
        <div style="font-size: 0.75rem; color: #94a3b8; border-top: 1px dashed #1e293b; padding-top: 0.4rem; display: flex; justify-content: space-between;">
          <span>WIP Đệm: <strong>${h.buffer_fill_pct}%</strong></span>
          <span>${isShift ? '<strong style="color: #f87171;">⚠️ Dịch chuyển</strong>' : '<span style="color: #34d399;">✓ Ổn định</span>'}</span>
        </div>
      </div>
    `;
  }).join('');
}

function renderBottleneckTopologyCanvas(forecastData) {
  const canvas = document.getElementById('bn-topology-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  // Background
  ctx.fillStyle = '#070a13';
  ctx.fillRect(0, 0, w, h);

  // Grid dots
  ctx.fillStyle = '#1e293b';
  for (let x = 20; x < w; x += 30) {
    for (let y = 20; y < h; y += 30) {
      ctx.fillRect(x, y, 1.5, 1.5);
    }
  }

  const fc2 = (forecastData && forecastData.forecast_2h) ? forecastData.forecast_2h : {};
  const bliMap = fc2.station_bli_scores || {};
  const isDiverted = forecastData ? forecastData.is_rerouting_active : false;

  // Layout Nodes definition
  const nodes = {
    PREP: { x: 70, y: 170, label: 'BÁN THÀNH PHẨM', sub: 'EXT-01 / CAL-01', bli: 0.35 },
    TBM1: { x: 230, y: 110, label: 'TBM-01 (PCR)', sub: 'VMI MAXX (80u/h)', bli: bliMap['TBM-01'] || 0.45 },
    TBM2: { x: 230, y: 230, label: 'TBM-02 (TBR)', sub: 'HF Tech (60u/h)', bli: bliMap['TBM-02'] || 0.30 },
    BUFFER: { x: 420, y: 170, label: 'GIÀN ĐỆM LỐP SỐNG', sub: `WIP: ${fc2.buffer_fill_pct || 68}% / 120 lốp`, bli: bliMap['BUFFER_GREEN_TIRE'] || 0.78, isBuffer: true },
    CP1: { x: 620, y: 70, label: 'LƯU HÓA CP-01', sub: 'Chính (9.2u/h)', bli: bliMap['CP-01'] || 0.50 },
    CP2: { x: 620, y: 135, label: 'LƯU HÓA CP-02', sub: 'Chính (Van Trễ)', bli: bliMap['CP-02'] || 0.92 },
    CP3: { x: 620, y: 205, label: 'LƯU HÓA CP-03', sub: 'Dự Phòng (Standby)', bli: bliMap['CP-03'] || 0.22, isAlt: true },
    CP4: { x: 620, y: 270, label: 'LƯU HÓA CP-04', sub: 'Dự Phòng (Standby)', bli: bliMap['CP-04'] || 0.20, isAlt: true },
    QC: { x: 800, y: 170, label: 'KCS & HOÀN THIỆN', sub: 'XR-01 & UF-01', bli: bliMap['XR-01'] || 0.38 },
    WH: { x: 910, y: 170, label: 'KHO THÀNH PHẨM', sub: 'WH-01 Đạt Chuẩn', bli: 0.15 }
  };

  // Helper function to draw connections
  function drawConnection(p1, p2, isDivertedPath = false, label = '') {
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);

    if (isDivertedPath) {
      ctx.strokeStyle = '#ec4899';
      ctx.lineWidth = 3;
      ctx.setLineDash([6, 4]);
    } else {
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([]);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw Arrowhead
    const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);
    const midX = (p1.x + p2.x) / 2;
    const midY = (p1.y + p2.y) / 2;

    ctx.save();
    ctx.translate(midX, midY);
    ctx.rotate(angle);
    ctx.fillStyle = isDivertedPath ? '#ec4899' : '#38bdf8';
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(-7, -4);
    ctx.lineTo(-7, 4);
    ctx.closePath();
    ctx.fill();

    if (label) {
      ctx.font = 'bold 9px monospace';
      ctx.fillStyle = isDivertedPath ? '#f472b6' : '#94a3b8';
      ctx.fillText(label, -15, -8);
    }
    ctx.restore();
  }

  // Draw Standard Path Connections
  drawConnection(nodes.PREP, nodes.TBM1);
  drawConnection(nodes.PREP, nodes.TBM2);
  drawConnection(nodes.TBM1, nodes.BUFFER);
  drawConnection(nodes.TBM2, nodes.BUFFER);
  drawConnection(nodes.BUFFER, nodes.CP1);
  drawConnection(nodes.BUFFER, nodes.CP2);
  drawConnection(nodes.CP1, nodes.QC);
  drawConnection(nodes.CP2, nodes.QC);
  drawConnection(nodes.CP3, nodes.QC);
  drawConnection(nodes.CP4, nodes.QC);
  drawConnection(nodes.QC, nodes.WH);

  // If Automated Diverting is Active, highlight Alternate Paths!
  if (isDiverted) {
    drawConnection(nodes.BUFFER, nodes.CP3, true, 'BẺ GHI 45%');
    drawConnection(nodes.BUFFER, nodes.CP4, true, 'BẺ GHI 45%');
    drawConnection(nodes.TBM1, nodes.TBM2, true, 'RE-DISPATCH');
  }

  // Draw Nodes
  Object.keys(nodes).forEach(k => {
    const n = nodes[k];
    const nodeW = n.isBuffer ? 130 : 110;
    const nodeH = 46;
    const rx = n.x - nodeW / 2;
    const ry = n.y - nodeH / 2;

    // Determine colors
    let bgCol = '#0f172a';
    let borderCol = '#334155';
    let textCol = '#38bdf8';

    if (n.bli >= 0.70) {
      bgCol = 'rgba(239, 68, 68, 0.25)';
      borderCol = '#ef4444';
      textCol = '#f87171';
    } else if (n.bli >= 0.50) {
      bgCol = 'rgba(245, 158, 11, 0.2)';
      borderCol = '#f59e0b';
      textCol = '#fbbf24';
    } else if (n.isAlt && isDiverted) {
      bgCol = 'rgba(16, 185, 129, 0.25)';
      borderCol = '#10b981';
      textCol = '#34d399';
    }

    // Node Box
    ctx.fillStyle = bgCol;
    ctx.strokeStyle = borderCol;
    ctx.lineWidth = n.bli >= 0.70 ? 2 : 1;
    ctx.beginPath();
    ctx.roundRect(rx, ry, nodeW, nodeH, 6);
    ctx.fill();
    ctx.stroke();

    // Node Text
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(n.label, n.x, n.y - 6);

    ctx.fillStyle = '#94a3b8';
    ctx.font = '9px monospace';
    ctx.fillText(n.sub, n.x, n.y + 7);

    // BLI Tag
    ctx.fillStyle = textCol;
    ctx.font = 'bold 8.5px monospace';
    ctx.fillText(`BLI: ${(n.bli * 100).toFixed(0)}%`, n.x, n.y + 18);
  });
}

async function simulateBottleneckSurge(scenario) {
  const feedbackEl = document.getElementById('bn-simulation-feedback');
  if (feedbackEl) {
    feedbackEl.style.display = 'block';
    feedbackEl.innerHTML = '<div style="color: #94a3b8; font-size: 0.85rem;">⏳ Đang đưa kịch bản vào mô hình dự báo chuỗi thời gian...</div>';
  }

  try {
    const res = await fetch('/api/bottleneck/simulate-surge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario })
    });
    const data = await res.json();

    if (feedbackEl) {
      feedbackEl.innerHTML = `
        <div style="background: rgba(56, 189, 248, 0.1); border: 1.5px solid #38bdf8; border-radius: 6px; padding: 0.85rem; font-size: 0.85rem; color: #e2e8f0;">
          <strong>⚡ Kết quả mô phỏng:</strong> ${data.message}
        </div>
      `;
    }

    await loadBottleneckForecast();
  } catch (err) {
    alert(`Lỗi kích hoạt mô phỏng: ${err}`);
  }
}

async function applyAiRerouting() {
  try {
    const res = await fetch('/api/bottleneck/apply-reroute', { method: 'POST' });
    const data = await res.json();
    alert(`✅ ${data.message}\nBảo vệ sản lượng: +${data.expected_oee_protection_pct}% OEE!`);
    await loadBottleneckTab();
  } catch (err) {
    alert(`Lỗi kích hoạt điều hướng: ${err}`);
  }
}

async function resetAiRouting() {
  try {
    const res = await fetch('/api/bottleneck/reset-routing', { method: 'POST' });
    const data = await res.json();
    alert(`↺ ${data.message}`);
    await loadBottleneckTab();
  } catch (err) {
    alert(`Lỗi khôi phục luồng chuẩn: ${err}`);
  }
}

async function loadDynamicRoutingRules() {
  const tbody = document.getElementById('bn-rules-table-body');
  if (!tbody) return;

  try {
    const res = await fetch('/api/bottleneck/routing-rules');
    const rules = await res.json();

    if (!rules || rules.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: #64748b; padding: 1.5rem;">Không có quy tắc điều hướng nào.</td></tr>`;
      return;
    }

    tbody.innerHTML = rules.map(r => {
      const isDiv = r.is_diverted === 1;
      const pillClass = isDiv ? 'pill-green' : 'pill-cyan';
      const statusText = isDiv ? 'ĐANG BẺ GHI TỰ ĐỘNG' : 'LUỒNG TIÊU CHUẨN';

      return `
        <tr>
          <td style="font-family: var(--font-mono); font-size: 0.82rem; color: #38bdf8;">${r.rule_id}</td>
          <td><strong style="color: #fff;">${r.source_station}</strong></td>
          <td><span style="color: #cbd5e1;">${r.target_station}</span></td>
          <td><strong style="color: #34d399;">${r.alternate_station}</strong></td>
          <td><span class="status-pill pill-purple">${r.material_type}</span></td>
          <td style="font-family: var(--font-mono); font-weight: 600;">${r.divert_ratio_pct}%</td>
          <td><span class="status-pill ${pillClass}">${statusText}</span></td>
          <td style="color: #38bdf8; font-family: var(--font-mono);">+${r.throughput_gain_forecast_pct}% OEE</td>
          <td>
            ${isDiv
              ? `<button class="btn btn-secondary btn-sm" onclick="resetAiRouting()">Tắt Bẻ Ghi</button>`
              : `<button class="btn btn-primary btn-sm" onclick="applyAiRerouting()">⚡ Bẻ Ghi Ngay</button>`
            }
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading routing rules:', err);
  }
}

// ============================================================================
// TAB 11: MULTIVARIATE FEATURE IMPORTANCE & DECISION TREES / SHAP
// ============================================================================

let currentGlobalShapData = null;
let currentLocalShapData = null;

async function loadShapTab() {
  await loadGlobalShapImportance();
  await loadDecisionTreeRules();
  await loadShapSamplePicker();
  await explainCurrentSample();
}

async function loadGlobalShapImportance() {
  try {
    const res = await fetch('/api/shap/global-importance');
    const data = await res.json();
    currentGlobalShapData = data;

    // KPI 1: Defect rate
    const defectRateEl = document.getElementById('shap-kpi-defect-rate');
    if (defectRateEl) defectRateEl.textContent = `${data.recent_defect_rate_pct}%`;

    const spikePillEl = document.getElementById('shap-kpi-spike-pill');
    if (spikePillEl) {
      if (data.is_spike_active) {
        spikePillEl.className = 'status-pill pill-red';
        spikePillEl.textContent = 'ĐỘT BIẾN LỖI';
      } else {
        spikePillEl.className = 'status-pill pill-green';
        spikePillEl.textContent = 'BÌNH THƯỜNG';
      }
    }

    // KPI 2: Top Root Cause
    const topCause = data.top_root_cause || {};
    const topCauseEl = document.getElementById('shap-kpi-top-cause');
    if (topCauseEl) topCauseEl.textContent = topCause.feature_name || 'Áp Suất Bàng Bọng';

    const topAreaEl = document.getElementById('shap-kpi-top-area');
    if (topAreaEl) topAreaEl.textContent = `${topCause.area || 'CURING'} (${topCause.category || 'Lưu Hóa'})`;

    // KPI 3: Top Share
    const topShareEl = document.getElementById('shap-kpi-top-share');
    if (topShareEl) topShareEl.textContent = `${topCause.importance_share_pct || 0}%`;

    const topValEl = document.getElementById('shap-kpi-top-val');
    if (topValEl) topValEl.textContent = topCause.mean_abs_shap || '0.00';

    // KPI 4: Features count
    const featCountEl = document.getElementById('shap-kpi-features-count');
    if (featCountEl) featCountEl.textContent = data.feature_ranking ? `${data.feature_ranking.length}` : '19';

    // KPI 5: Model accuracy
    const accEl = document.getElementById('shap-kpi-accuracy');
    const f1El = document.getElementById('shap-kpi-f1');
    if (accEl && data.model_metrics) accEl.textContent = Number(data.model_metrics.roc_auc).toFixed(2);
    if (f1El && data.model_metrics) f1El.textContent = Number(data.model_metrics.f1).toFixed(2);

    // Render Canvas
    renderGlobalShapCanvas(data.feature_ranking || []);
  } catch (err) {
    console.error('Error loading global SHAP importance:', err);
  }
}

function renderGlobalShapCanvas(features) {
  const canvas = document.getElementById('shap-global-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);

  // Background
  ctx.fillStyle = '#070a13';
  ctx.fillRect(0, 0, w, h);

  if (!features || features.length === 0) return;

  const top12 = features.slice(0, 12);
  const maxVal = Math.max(...top12.map(f => f.mean_abs_shap), 0.01);

  const padding = { top: 35, right: 90, bottom: 25, left: 240 };
  const chartW = w - padding.left - padding.right;
  const rowH = (h - padding.top - padding.bottom) / top12.length;

  // Grid lines
  ctx.strokeStyle = '#1e293b';
  ctx.lineWidth = 1;
  for (let step = 0; step <= 4; step++) {
    const val = (maxVal / 4) * step;
    const x = padding.left + (val / maxVal) * chartW;
    ctx.beginPath();
    ctx.moveTo(x, padding.top);
    ctx.lineTo(x, h - padding.bottom);
    ctx.stroke();

    ctx.fillStyle = '#64748b';
    ctx.font = '10px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(val.toFixed(3), x, h - padding.bottom + 15);
  }

  // Draw Bars
  top12.forEach((f, idx) => {
    const y = padding.top + idx * rowH;
    const barLen = (f.mean_abs_shap / maxVal) * chartW;
    const barH = rowH * 0.62;

    // Gradient bar color based on rank
    let grad = ctx.createLinearGradient(padding.left, 0, padding.left + barLen, 0);
    if (idx < 2) {
      grad.addColorStop(0, '#f43f5e');
      grad.addColorStop(1, '#ef4444');
    } else if (idx < 5) {
      grad.addColorStop(0, '#f59e0b');
      grad.addColorStop(1, '#fbbf24');
    } else {
      grad.addColorStop(0, '#0284c7');
      grad.addColorStop(1, '#38bdf8');
    }

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.roundRect(padding.left, y + (rowH - barH) / 2, Math.max(4, barLen), barH, 4);
    ctx.fill();

    // Feature Name label on the left
    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(`${idx + 1}. ${f.feature_name}`, padding.left - 12, y + rowH / 2 + 3);

    // Area tag
    ctx.fillStyle = '#94a3b8';
    ctx.font = '9px monospace';
    ctx.fillText(`[${f.area}]`, padding.left - 12, y + rowH / 2 + 13);

    // Value and share text on the right
    ctx.fillStyle = '#cbd5e1';
    ctx.font = 'bold 10px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`${f.importance_share_pct}% (${f.mean_abs_shap.toFixed(3)})`, padding.left + barLen + 8, y + rowH / 2 + 4);
  });
}

async function loadDecisionTreeRules() {
  const container = document.getElementById('shap-rules-container');
  if (!container) return;

  try {
    const res = await fetch('/api/shap/decision-rules');
    const data = await res.json();
    const rules = data.rules || [];

    if (rules.length === 0) {
      container.innerHTML = '<div style="color: #64748b; padding: 1rem;">Không có quy tắc nào vượt ngưỡng. Dây chuyền vận hành chuẩn SOP!</div>';
      return;
    }

    container.innerHTML = rules.map((r, i) => {
      const isCrit = r.defect_probability_pct >= 75.0;
      const borderCol = isCrit ? '#ef4444' : '#f59e0b';
      const pillClass = isCrit ? 'pill-red' : 'pill-yellow';

      return `
        <div style="background: #090e1a; border: 1.5px solid ${borderCol}; border-radius: 8px; padding: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <div style="font-size: 0.95rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px;">
              <span>🌲</span>
              <span>QUY TẮC CÔNG NGHỆ #${i + 1} (${r.rule_id})</span>
            </div>
            <span class="status-pill ${pillClass}">XÁC SUẤT LỖI: ${r.defect_probability_pct}%</span>
          </div>

          <div style="background: #040711; border: 1px solid #1e293b; border-radius: 6px; padding: 0.75rem; margin-bottom: 0.75rem; font-family: var(--font-mono); font-size: 0.82rem; color: #38bdf8; line-height: 1.6;">
            <strong>IF (NẾU):</strong><br>
            ${r.conditions.map(c => `&bull; ${c}`).join('<br>')}<br>
            <strong style="color: #f87171;">THEN (THÌ):</strong> Tỷ lệ phát sinh phế phẩm vọt lên <strong>${r.defect_probability_pct}%</strong> (${r.samples_affected} mẻ vi phạm)!
          </div>

          <div style="font-size: 0.82rem; color: #cbd5e1; line-height: 1.5;">
            <strong style="color: #fbbf24;">Hành động khắc phục IATF 16949:</strong> ${r.action}
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading decision tree rules:', err);
  }
}

async function loadShapSamplePicker() {
  const picker = document.getElementById('shap-sample-picker');
  if (!picker) return;

  try {
    const res = await fetch('/api/shap/samples?limit=25');
    const samples = await res.json();

    picker.innerHTML = samples.map(s => {
      const statusIcon = s.is_defective ? '🚨 [LỖI]' : '✅ [ĐẠT]';
      const desc = s.is_defective ? (s.defect_name || 'Phế phẩm') : 'Chuẩn Grade A';
      return `<option value="${s.tire_serial}">${statusIcon} ${s.tire_serial} (${s.batch_id} - ${desc})</option>`;
    }).join('');
  } catch (err) {
    console.error('Error loading samples picker:', err);
  }
}

async function explainSelectedSample() {
  const picker = document.getElementById('shap-sample-picker');
  const sampleId = picker ? picker.value : null;
  await explainCurrentSample(sampleId);
}

async function explainCurrentSample(sampleId = null) {
  const container = document.getElementById('shap-waterfall-container');
  if (!container) return;

  container.innerHTML = '<div style="color: #94a3b8; font-size: 0.85rem;">⏳ Đang tính toán phân rã lực TreeSHAP cho mẻ lốp này...</div>';

  try {
    const res = await fetch('/api/shap/explain-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sample_id: sampleId })
    });
    const data = await res.json();
    currentLocalShapData = data;

    const meta = data.batch_meta || {};
    const riskPct = (data.predicted_defect_probability * 100).toFixed(1);
    const isHigh = data.is_high_risk;
    const borderCol = isHigh ? '#ef4444' : '#10b981';
    const bgCol = isHigh ? 'rgba(239, 68, 68, 0.12)' : 'rgba(16, 185, 129, 0.1)';
    const pillClass = isHigh ? 'pill-red' : 'pill-green';

    const topPos = (data.waterfall_breakdown || []).filter(f => f.impact_direction === 'PUSH_DEFECT').slice(0, 4);
    const topNeg = (data.waterfall_breakdown || []).filter(f => f.impact_direction === 'MITIGATE').slice(0, 3);
    const rec = data.recommendation || {};

    container.innerHTML = `
      <div style="background: ${bgCol}; border: 1.5px solid ${borderCol}; border-radius: 8px; padding: 1.25rem; margin-bottom: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1rem;">
          <div>
            <div style="font-size: 1.1rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px;">
              <span>${isHigh ? '🚨' : '✅'}</span>
              <span>Giám Định SHAP Chi Tiết: ${meta.tire_serial || 'MẺ SẢN XUẤT'}</span>
            </div>
            <div style="font-size: 0.82rem; color: #94a3b8; margin-top: 3px;">
              Mã Mẻ Luyện: <strong>${meta.batch_id}</strong> &bull; Tình trạng: <strong>${meta.defect_name}</strong>
            </div>
          </div>
          <div style="display: flex; gap: 0.75rem; align-items: center;">
            <div style="text-align: right;">
              <div style="font-size: 0.78rem; color: #94a3b8;">Xác Suất Hỏng Dự Đoán:</div>
              <div style="font-size: 1.3rem; font-weight: 800; color: ${isHigh ? '#f87171' : '#34d399'}; font-family: var(--font-mono);">
                ${riskPct}%
              </div>
            </div>
            <span class="status-pill ${pillClass}">MỨC ĐỘ: ${isHigh ? 'RỦI RO CAO' : 'AN TOÀN'}</span>
          </div>
        </div>

        <!-- Waterfall Force Bars -->
        <div style="background: #090e1a; border: 1px solid #1e293b; border-radius: 6px; padding: 1rem; margin-bottom: 1rem;">
          <div style="font-size: 0.88rem; font-weight: 600; color: #fff; margin-bottom: 0.75rem; display: flex; justify-content: space-between;">
            <span>Biểu Đồ Lực Đóng Góp SHAP (Waterfall Decomposition):</span>
            <span style="font-size: 0.8rem; color: #94a3b8;">Xác suất nền (Base Value): ${(data.base_rate * 100).toFixed(1)}%</span>
          </div>

          <div style="margin-bottom: 0.75rem;">
            <div style="font-size: 0.8rem; font-weight: 600; color: #f87171; margin-bottom: 0.4rem;">
              🔺 Các Yếu Tố Kéo Tăng Nguy Cơ Lỗi (Positive Drivers &bull; Phá hủy chất lượng):
            </div>
            ${topPos.map(p => `
              <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem; padding: 0.35rem 0; border-bottom: 1px dashed #1e293b;">
                <div>
                  <strong style="color: #fff;">${p.feature_name}</strong>: 
                  <span style="color: #f87171; font-family: var(--font-mono);">${p.actual_value} ${p.unit}</span>
                  <span style="color: #64748b; font-size: 0.75rem;">(Chuẩn: ${p.nominal_value} ${p.unit}, Lệch: ${p.deviation > 0 ? '+' : ''}${p.deviation})</span>
                </div>
                <div style="color: #f87171; font-weight: 700; font-family: var(--font-mono);">
                  +${(p.shap_value * 100).toFixed(1)}% rủi ro
                </div>
              </div>
            `).join('')}
          </div>

          <div>
            <div style="font-size: 0.8rem; font-weight: 600; color: #34d399; margin-bottom: 0.4rem;">
              🔻 Các Yếu Tố Triệt Tiêu Nguy Cơ Lỗi (Negative Drivers &bull; Vận hành chuẩn):
            </div>
            ${topNeg.map(n => `
              <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem; padding: 0.35rem 0; border-bottom: 1px dashed #1e293b;">
                <div>
                  <strong style="color: #fff;">${n.feature_name}</strong>: 
                  <span style="color: #34d399; font-family: var(--font-mono);">${n.actual_value} ${n.unit}</span>
                  <span style="color: #64748b; font-size: 0.75rem;">(Chuẩn: ${n.nominal_value} ${n.unit})</span>
                </div>
                <div style="color: #34d399; font-weight: 700; font-family: var(--font-mono);">
                  ${(n.shap_value * 100).toFixed(1)}% rủi ro
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Actionable Engineering Recommendation -->
        <div style="background: rgba(255, 255, 255, 0.04); border-left: 4px solid #38bdf8; padding: 0.85rem 1rem; border-radius: 4px; font-size: 0.84rem; line-height: 1.5;">
          <div style="color: #38bdf8; font-weight: 700; margin-bottom: 0.3rem;">📋 CHẨN ĐOÁN KỸ THUẬT & KHUYẾN NGHỊ KHẮC PHỤC (IATF 16949 / CAPA):</div>
          <div style="color: #e2e8f0; margin-bottom: 0.4rem;"><strong>Chẩn đoán:</strong> ${rec.diagnosis || '--'}</div>
          <div style="color: #fca5a5; margin-bottom: 0.4rem;"><strong>Nguyên nhân gốc rễ:</strong> ${rec.root_cause || '--'}</div>
          <div style="color: #cbd5e1; white-space: pre-line;"><strong style="color: #fbbf24;">Biện pháp xử lý:</strong><br>${rec.corrective_action || '--'}</div>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="color: #ef4444; font-size: 0.85rem;">Lỗi phân tích SHAP: ${err}</div>`;
  }
}

async function simulateShapSpike(scenario) {
  const feedbackEl = document.getElementById('shap-simulation-feedback');
  if (feedbackEl) {
    feedbackEl.style.display = 'block';
    feedbackEl.innerHTML = '<div style="color: #94a3b8; font-size: 0.85rem;">⏳ Đang đưa kịch bản đột biến vào mô hình XAI và tính toán lại ma trận SHAP...</div>';
  }

  try {
    const res = await fetch('/api/shap/simulate-spike', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario })
    });
    const data = await res.json();

    if (feedbackEl) {
      feedbackEl.innerHTML = `
        <div style="background: rgba(6, 182, 212, 0.12); border: 1.5px solid #06b6d4; border-radius: 6px; padding: 0.85rem; font-size: 0.85rem; color: #e2e8f0;">
          <strong>⚡ Đã kích hoạt kịch bản:</strong> Tỷ lệ lỗi xưởng tăng lên <strong>${data.recent_defect_rate_pct}%</strong>! SHAP đã chỉ điểm chính xác căn nguyên hàng đầu: <strong style="color: #f87171;">${data.top_root_cause.feature_name} (${data.top_root_cause.importance_share_pct}%)</strong>.
        </div>
      `;
    }

    await loadShapTab();
  } catch (err) {
    alert(`Lỗi kích hoạt mô phỏng: ${err}`);
  }
}

async function retrainShapModels() {
  try {
    const res = await fetch('/api/shap/retrain', { method: 'POST' });
    const data = await res.json();
    alert(`✅ ${data.message}\nROC-AUC: ${data.metrics.roc_auc}\nF1-Score: ${data.metrics.f1}\nSố mẻ phân tích: ${data.total_samples}`);
    await loadShapTab();
  } catch (err) {
    alert(`Lỗi tái huấn luyện XAI: ${err}`);
  }
}

// ============================================================================
// TAB 12: GRAPH MACHINE LEARNING & TRACEABILITY CONTAGION
// ============================================================================

let currentGraphTopology = null;
let currentGraphSimulation = null;
let graphCanvasInitialized = false;

async function loadGraphTab() {
  try {
    // 1. Fetch Status and KPIs
    const statusRes = await fetch('/api/graph/status');
    if (statusRes.ok) {
      const statusData = await statusRes.json();
      const metrics = statusData.graph_metrics;
      const nodesEl = document.getElementById('kpi-graph-nodes');
      const edgesEl = document.getElementById('kpi-graph-edges');
      const wosEl = document.getElementById('kpi-graph-active-wos');
      if (nodesEl) nodesEl.textContent = metrics.total_nodes;
      if (edgesEl) edgesEl.textContent = metrics.total_edges;
      if (wosEl) wosEl.textContent = metrics.active_work_orders;
    }

    // 2. Fetch Available Lots for Simulation Dropdown
    await loadGraphAvailableLots();

    // 3. Fetch Topology and Render Canvas
    const topoRes = await fetch('/api/graph/topology');
    if (topoRes.ok) {
      currentGraphTopology = await topoRes.json();
      renderGraphTopology(currentGraphTopology);
    }
  } catch (err) {
    console.error('Error loading Graph Tab:', err);
  }
}

async function loadGraphAvailableLots() {
  try {
    const res = await fetch('/api/graph/lots');
    if (!res.ok) return;
    const data = await res.json();
    const selectEl = document.getElementById('graph-sim-lot-select');
    if (!selectEl) return;

    let html = '<optgroup label="Lô Linh Kiện Bán Thành Phẩm">';
    data.component_lots.forEach(lot => {
      html += `<option value="${lot.lot_id}">${lot.lot_id} (${lot.component_type} - ${lot.compound_code}) [Tồn: ${lot.remaining_qty}]</option>`;
    });
    html += '</optgroup>';

    html += '<optgroup label="Mẻ Luyện Kín Banbury Gốc">';
    data.parent_batches.forEach(b => {
      html += `<option value="BATCH:${b.raw_batch_ref}">Mẻ Gốc ${b.raw_batch_ref} (${b.compound_code})</option>`;
    });
    html += '</optgroup>';

    selectEl.innerHTML = html;
  } catch (err) {
    console.error('Error loading lots for graph:', err);
  }
}

function renderGraphTopology(topoData) {
  const canvas = document.getElementById('graph-traceability-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;

  // Clear background
  ctx.fillStyle = '#070d19';
  ctx.fillRect(0, 0, width, height);

  // Draw Column Background Gradients & Labels
  const colNames = [
    'MẺ LUYỆN BANBURY',
    'LÔ VẬT TƯ BTP',
    'TRẠM MÁY & TOOLING',
    'LỐP MỘC & THÀNH PHẨM',
    'LỆNH SẢN XUẤT (WO)'
  ];

  ctx.font = '10px "Inter", sans-serif';
  ctx.textAlign = 'center';

  for (let c = 0; c < 5; c++) {
    const colX = 80 + c * (width - 160) / 4;

    // Subtle vertical column guide line
    ctx.strokeStyle = 'rgba(30, 41, 59, 0.4)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(colX, 25);
    ctx.lineTo(colX, height - 15);
    ctx.stroke();
    ctx.setLineDash([]);

    // Column Header Tag
    ctx.fillStyle = '#64748b';
    ctx.fillText(colNames[c], colX, 18);
  }

  if (!topoData || !topoData.nodes || topoData.nodes.length === 0) return;

  const nodeMap = {};
  topoData.nodes.forEach(n => { nodeMap[n.id] = n; });

  // 1. Draw Edges
  topoData.edges.forEach(edge => {
    const u = nodeMap[edge.source];
    const v = nodeMap[edge.target];
    if (!u || !v) return;

    const isHighRisk = (u.risk_score >= 0.70 || v.risk_score >= 0.70 || u.is_suspect || v.is_suspect);
    const isMediumRisk = (u.risk_score >= 0.45 || v.risk_score >= 0.45);

    ctx.beginPath();
    ctx.moveTo(u.x, u.y);
    ctx.lineTo(v.x, v.y);

    if (isHighRisk) {
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.65)';
      ctx.lineWidth = 2.2;
    } else if (isMediumRisk) {
      ctx.strokeStyle = 'rgba(245, 158, 11, 0.45)';
      ctx.lineWidth = 1.6;
    } else {
      ctx.strokeStyle = 'rgba(100, 116, 139, 0.18)';
      ctx.lineWidth = 0.8;
    }
    ctx.stroke();
  });

  // 2. Draw Nodes
  topoData.nodes.forEach(node => {
    // Outer Pulsing Glow for Suspect or Critical nodes
    if (node.is_suspect) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, 16, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(239, 68, 68, 0.35)';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(node.x, node.y, 22, 0, 2 * Math.PI);
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);
    } else if (node.is_critical) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, 14, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(249, 115, 22, 0.3)';
      ctx.fill();
    }

    // Node Circle
    const radius = node.node_type === 'WORK_ORDER' || node.node_type === 'PARENT_BATCH' ? 9 : 6.5;
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = node.color || '#64748b';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.2;
    ctx.stroke();

    // Node Short Label
    if (node.node_type === 'WORK_ORDER' || node.node_type === 'PARENT_BATCH' || node.is_suspect || node.is_critical) {
      ctx.fillStyle = node.is_suspect ? '#fca5a5' : (node.is_critical ? '#fdba74' : '#e2e8f0');
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      const shortId = node.id.replace(/^(LOT:|BATCH:|MACHINE:|WO:|TIRE:)/, '');
      ctx.fillText(shortId, node.x, node.y - radius - 3);
    }
  });

  // Setup Canvas Interactive Tooltip (only once)
  if (!graphCanvasInitialized) {
    graphCanvasInitialized = true;
    canvas.addEventListener('mousemove', (evt) => {
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const mx = (evt.clientX - rect.left) * scaleX;
      const my = (evt.clientY - rect.top) * scaleY;

      const tooltip = document.getElementById('graph-canvas-tooltip');
      if (!tooltip || !currentGraphTopology) return;

      const hovered = currentGraphTopology.nodes.find(n => {
        const dx = n.x - mx;
        const dy = n.y - my;
        return (dx * dx + dy * dy) <= 120;
      });

      if (hovered) {
        tooltip.style.display = 'block';
        tooltip.style.left = `${evt.clientX - rect.left + 15}px`;
        tooltip.style.top = `${evt.clientY - rect.top + 10}px`;
        tooltip.innerHTML = `
          <div style="font-weight: 700; color: ${hovered.color}; margin-bottom: 2px;">${hovered.label}</div>
          <div style="font-size: 0.72rem; color: #94a3b8;">Loại nút: <strong>${hovered.display_type}</strong></div>
          <div style="font-size: 0.72rem; color: #cbd5e1;">Xác suất rủi ro lây nhiễm: <strong style="color: ${hovered.risk_score >= 0.7 ? '#ef4444' : (hovered.risk_score >= 0.45 ? '#f59e0b' : '#10b981')}">${(hovered.risk_score * 100).toFixed(1)}%</strong></div>
        `;
      } else {
        tooltip.style.display = 'none';
      }
    });

    canvas.addEventListener('mouseleave', () => {
      const tooltip = document.getElementById('graph-canvas-tooltip');
      if (tooltip) tooltip.style.display = 'none';
    });
  }
}

async function runGraphOutbreakSimulation() {
  const lotSelect = document.getElementById('graph-sim-lot-select');
  const defectInput = document.getElementById('graph-sim-defect-desc');
  if (!lotSelect || !lotSelect.value) {
    alert('Vui lòng chọn một lô linh kiện hoặc mẻ Banbury để quét!');
    return;
  }

  const suspectLotId = lotSelect.value.replace('BATCH:', '');
  const defectDesc = defectInput ? defectInput.value : 'Khuyết tật tách lớp mành tanh';

  const tbody = document.getElementById('graph-wo-table-body');
  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" style="text-align: center; color: #38bdf8; padding: 2rem;">
          ⏳ Đang chạy mô hình PyTorch Heterogeneous GNN & Random Walk with Restart Diffusion...
        </td>
      </tr>
    `;
  }

  try {
    const res = await fetch('/api/graph/simulate-outbreak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        suspect_lot_id: suspectLotId,
        defect_description: defectDesc,
        authorized_badge: 'OP-4001'
      })
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || 'Lỗi mô phỏng');
    }

    const data = await res.json();
    currentGraphSimulation = data;
    renderGraphOutbreakResults(data);

    // Refresh canvas with suspect highlight
    const topoRes = await fetch(`/api/graph/topology?suspect_lot_id=${encodeURIComponent(suspectLotId)}`);
    if (topoRes.ok) {
      currentGraphTopology = await topoRes.json();
      renderGraphTopology(currentGraphTopology);
    }
  } catch (err) {
    alert(`Lỗi chạy mô phỏng lây nhiễm: ${err.message}`);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: #ef4444;">${err.message}</td></tr>`;
    }
  }
}

function renderGraphOutbreakResults(data) {
  // 1. Update KPI Cards
  const critKpi = document.getElementById('kpi-graph-critical-wos');
  const critSub = document.getElementById('kpi-graph-critical-sub');
  if (critKpi) {
    critKpi.textContent = data.graph_summary.critical_orders_count;
    critKpi.style.color = data.graph_summary.critical_orders_count > 0 ? '#ef4444' : '#10b981';
  }
  if (critSub) {
    critSub.textContent = `${data.graph_summary.total_tires_at_risk} lốp bị đe dọa (Blast Radius)`;
  }

  // 2. Show Alert Banner
  const alertBanner = document.getElementById('graph-blast-radius-alert');
  const alertHeadline = document.getElementById('graph-alert-headline');
  const alertDirective = document.getElementById('graph-alert-directive');
  if (alertBanner) {
    alertBanner.style.display = 'block';
    if (alertHeadline) alertHeadline.textContent = data.executive_blast_radius_containment.headline;
    if (alertDirective) alertDirective.textContent = data.executive_blast_radius_containment.immediate_action_required;
  }

  // 3. Render Table
  const tbody = document.getElementById('graph-wo-table-body');
  if (!tbody) return;

  const timestampEl = document.getElementById('graph-assessed-timestamp');
  if (timestampEl) timestampEl.textContent = `Phiên: ${data.run_id} (${data.timestamp})`;

  let rowsHtml = '';
  data.work_order_assessments.forEach(wo => {
    let tierBadge = '';
    let barColor = '#10b981';

    if (wo.risk_tier === 'CRITICAL') {
      tierBadge = '<span class="badge" style="background: #ef4444; color: #fff;">CRITICAL (DỪNG MÁY)</span>';
      barColor = '#ef4444';
    } else if (wo.risk_tier === 'HIGH_RISK') {
      tierBadge = '<span class="badge" style="background: #f97316; color: #fff;">HIGH (SIẾT CHẶT NDT)</span>';
      barColor = '#f97316';
    } else if (wo.risk_tier === 'MEDIUM_RISK') {
      tierBadge = '<span class="badge" style="background: #eab308; color: #1e293b;">MEDIUM (TĂNG MẪU)</span>';
      barColor = '#eab308';
    } else {
      tierBadge = '<span class="badge" style="background: #64748b; color: #fff;">LOW (GIÁM SÁT)</span>';
      barColor = '#64748b';
    }

    let vectorText = wo.primary_transmission_vector;
    if (vectorText === 'DIRECT_BOM_MATERIAL_CONSUMPTION') vectorText = 'Trực Tiếp (Vật tư BOM)';
    else if (vectorText === 'SHARED_MACHINE_RESIDUE') vectorText = 'Dư Lượng Máy Chạy Kế (TBM)';
    else if (vectorText === 'SHARED_PARENT_BANBURY_BATCH') vectorText = 'Chung Mẻ Luyện Gốc (Banbury)';
    else if (vectorText === 'ISOLATED_INDEPENDENT_LINE') vectorText = 'Chuyền Độc Lập An Toàn';

    rowsHtml += `
      <tr style="${wo.risk_tier === 'CRITICAL' ? 'background: rgba(239, 68, 68, 0.08);' : ''}">
        <td><strong style="color: #fff; font-family: var(--font-mono);">${wo.wo_id}</strong></td>
        <td>${wo.sku}</td>
        <td><span class="badge" style="background: #1e293b; color: #cbd5e1;">${wo.assigned_machine || '--'}</span></td>
        <td><span class="badge" style="background: #0284c7; color: #fff;">${wo.status}</span></td>
        <td>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <div style="flex: 1; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden;">
              <div style="width: ${wo.risk_score_pct}%; height: 100%; background: ${barColor};"></div>
            </div>
            <strong style="color: ${barColor}; font-family: var(--font-mono); font-size: 0.8rem; width: 44px; text-align: right;">${wo.risk_score_pct}%</strong>
          </div>
        </td>
        <td>${tierBadge}</td>
        <td><span style="font-size: 0.78rem; color: #cbd5e1;">${vectorText}</span></td>
        <td><strong style="color: ${wo.tires_at_risk > 0 ? '#fca5a5' : '#94a3b8'}; font-family: var(--font-mono);">${wo.tires_at_risk} lốp</strong></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="showTrajectoryForWO('${wo.wo_id}')" style="font-size: 0.75rem; padding: 0.2rem 0.5rem;">
            🔍 Xem Chuỗi Lây Nhiễm
          </button>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = rowsHtml;

  // 4. Default show trajectory of top critical work order
  if (data.work_order_assessments.length > 0) {
    showTrajectoryForWO(data.work_order_assessments[0].wo_id);
  }
}

function showTrajectoryForWO(woId) {
  if (!currentGraphSimulation) return;
  const wo = currentGraphSimulation.work_order_assessments.find(w => w.wo_id === woId);
  if (!wo) return;

  const card = document.getElementById('graph-path-explainer-card');
  const flowContainer = document.getElementById('graph-trajectory-flow');
  if (!card || !flowContainer) return;

  card.style.display = 'block';

  if (!wo.shortest_infection_path_steps || wo.shortest_infection_path_steps.length === 0) {
    flowContainer.innerHTML = '<div style="color: #64748b; font-size: 0.84rem;">Không phát hiện đường truyền bệnh trực tiếp (Dây chuyền độc lập cách ly).</div>';
    return;
  }

  let html = '';
  wo.shortest_infection_path_steps.forEach((step, idx) => {
    let badgeColor = '#3b82f6';
    if (step.node_type === 'LOT') badgeColor = '#f59e0b';
    if (step.node_type === 'MACHINE') badgeColor = '#8b5cf6';
    if (step.node_type === 'WORK_ORDER') badgeColor = wo.risk_tier === 'CRITICAL' ? '#ef4444' : '#10b981';
    if (step.node_type === 'PARENT_BATCH') badgeColor = '#ec4899';

    html += `
      <div style="background: rgba(30, 41, 59, 0.8); border: 1px solid ${badgeColor}; padding: 0.5rem 0.75rem; border-radius: 6px; font-size: 0.8rem;">
        <div style="color: ${badgeColor}; font-size: 0.7rem; font-weight: 700; text-transform: uppercase;">${step.node_type}</div>
        <div style="color: #fff; font-weight: 600;">${step.label}</div>
      </div>
    `;

    if (idx < wo.shortest_infection_path_steps.length - 1) {
      let rel = step.outgoing_relation || 'FLOWS_TO';
      let w = step.transmission_weight || 0.5;
      html += `
        <div style="color: #f59e0b; font-size: 0.75rem; display: flex; flex-direction: column; align-items: center; padding: 0 0.25rem;">
          <span style="font-family: var(--font-mono); font-size: 0.7rem; color: #94a3b8;">${rel} (${w})</span>
          <span>➔</span>
        </div>
      `;
    }
  });

  flowContainer.innerHTML = html;
}

async function executeGraphQuarantineAction() {
  if (!currentGraphSimulation || !currentGraphSimulation.run_id) {
    alert('Vui lòng chạy mô phỏng lây nhiễm trước khi phát lệnh cách ly!');
    return;
  }

  const runId = currentGraphSimulation.run_id;
  const confirmMsg = `XÁC NHẬN LỆNH KHẨN CẤP IATF 16949:\nBạn có chắc chắn muốn phát lệnh khóa Poka-Yoke dừng máy và cách ly toàn bộ lốp thuộc diện CRITICAL trong đợt '${runId}' không?`;
  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch('/api/graph/execute-quarantine', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        run_id: runId,
        authorized_badge: 'OP-4001'
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lỗi cách ly');
    }

    const data = await res.json();
    alert(`🛡️ ${data.containment_directive}\nCấp bởi: ${data.authorized_by}`);

    // Reload floor data
    await loadWorkOrders();
    await loadDashboard(true);
    await loadGraphTab();
  } catch (err) {
    alert(`Lỗi thực thi lệnh cách ly: ${err.message}`);
  }
}





