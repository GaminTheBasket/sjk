const serviceGrid = document.getElementById('service-grid');
const metricsSummary = document.getElementById('metrics-summary');
const metricsDetails = document.getElementById('metrics-details');
const activitySummary = document.getElementById('activity-summary');
const activityPager = document.getElementById('activity-pager');
const activityList = document.getElementById('activity-list');
const dataSourceEl = document.getElementById('data-source');
const updatedAt = document.getElementById('updated-at');
const refreshButton = document.getElementById('refresh-button');

const coreBase = window.location.origin;

function formatNumber(value) {
  return new Intl.NumberFormat('vi-VN').format(value);
}

function renderServiceCards(statuses) {
  serviceGrid.innerHTML = statuses
    .map((service) => `
      <div class="card">
        <h3>${service.name}</h3>
        <p>URL: ${service.url}</p>
        <span class="badge ${service.status === 'ok' ? 'ok' : service.status === 'warning' ? 'warn' : 'bad'}">
          ${service.label}
        </span>
      </div>
    `)
    .join('');
}

function renderSummary(metrics) {
  const items = [
    { label: 'Tổng lượt vào', value: metrics.total_access_in },
    { label: 'Từ chối truy cập', value: metrics.denied_access_count },
    { label: 'Số thiết bị pin yếu', value: metrics.low_battery_device_count },
    { label: 'Cảnh báo nguy hiểm', value: metrics.danger_event_count },
    { label: 'Cảnh báo cảnh báo', value: metrics.warning_event_count },
    { label: 'Giờ cao điểm', value: metrics.peak_access_hour || 'Không có' },
  ];

  metricsSummary.innerHTML = items
    .map(
      (item) => `
      <div class="summary-item">
        <span>${item.label}</span>
        <strong>${item.value}</strong>
      </div>
    `,
    )
    .join('');
}

function renderDetailTable(title, rows) {
  if (!rows || Object.keys(rows).length === 0) {
    return `
      <div class="panel">
        <h3>${title}</h3>
        <p>Không có dữ liệu.</p>
      </div>
    `;
  }

  const rowsHtml = Object.entries(rows)
    .map(
      ([key, value]) => `
        <tr>
          <td>${key}</td>
          <td>${formatNumber(value)}</td>
        </tr>
      `,
    )
    .join('');

  return `
    <div class="panel">
      <h3>${title}</h3>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr><th>Phân loại</th><th>Giá trị</th></tr>
          </thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>
    </div>
  `;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

let _activityItems = [];
let _activityPage = 1;
const ACTIVITY_PAGE_SIZE = 10;

function renderDataSource(sourceLabel, sourceUrl) {
  dataSourceEl.innerHTML = `
    <div class="summary-item">
      <span>Nguồn dữ liệu</span>
      <strong>${sourceLabel}</strong>
    </div>
    <div class="summary-item">
      <span>Metrics API</span>
      <strong>${sourceUrl}</strong>
    </div>
  `;
}

function renderActivitySummary(items) {
  _activityItems = items || [];
  _activityPage = 1;
  const total = _activityItems.length;
  const allowed = _activityItems.filter((item) => item.status === 'ALLOWED').length;
  const denied = _activityItems.filter((item) => item.status === 'DENIED').length;
  activitySummary.innerHTML = `
    <div class="summary-item">
      <span>Tổng bản ghi</span>
      <strong>${formatNumber(total)}</strong>
    </div>
    <div class="summary-item">
      <span>Cho phép</span>
      <strong>${formatNumber(allowed)}</strong>
    </div>
    <div class="summary-item">
      <span>Từ chối</span>
      <strong>${formatNumber(denied)}</strong>
    </div>
  `;

  renderActivityPage(_activityPage);
  renderActivityPagination();
}

function renderActivityPage(page) {
  const start = (page - 1) * ACTIVITY_PAGE_SIZE;
  const rows = _activityItems.slice(start, start + ACTIVITY_PAGE_SIZE);
  if (!rows || rows.length === 0) {
    activityList.innerHTML = `
      <div class="panel">
        <h3>Giao dịch gần đây</h3>
        <p>Không có bản ghi.</p>
      </div>
    `;
    return;
  }

  activityList.innerHTML = `
    <div class="panel">
      <h3>Giao dịch gần đây</h3>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr><th>Thời gian</th><th>Cổng</th><th>Chiều</th><th>Trạng thái</th><th>Thẻ</th></tr>
          </thead>
          <tbody>
            ${rows.map((item) => `
              <tr>
                <td>${new Date(item.timestamp).toLocaleString('vi-VN')}</td>
                <td>${item.gateId}</td>
                <td>${item.direction}</td>
                <td>${item.status}</td>
                <td>${item.cardId}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderActivityPagination() {
  const total = _activityItems.length;
  const pages = Math.max(1, Math.ceil(total / ACTIVITY_PAGE_SIZE));
  if (pages <= 1) {
    activityPager.innerHTML = '';
    return;
  }

  let html = '';
  html += `<button class="pager-btn" data-page="${Math.max(1, _activityPage - 1)}">‹ Prev</button>`;
  for (let p = 1; p <= pages; p++) {
    html += `<button class="pager-btn ${p === _activityPage ? 'active' : ''}" data-page="${p}">${p}</button>`;
  }
  html += `<button class="pager-btn" data-page="${Math.min(pages, _activityPage + 1)}">Next ›</button>`;

  activityPager.innerHTML = html;
  activityPager.querySelectorAll('.pager-btn').forEach((btn) => {
    btn.addEventListener('click', (ev) => {
      const pg = Number(ev.currentTarget.getAttribute('data-page')) || 1;
      _activityPage = pg;
      renderActivityPage(_activityPage);
      renderActivityPagination();
    });
  });
}

async function loadDashboard() {
  updatedAt.textContent = 'Đang tải...';

  try {
    const [coreHealth, metricsLatest, accessLogs] = await Promise.all([
      fetchJson(`${coreBase}/health`),
      fetchJson(`${coreBase}/analytics/metrics/latest`),
      fetchJson(`${coreBase}/collections/access_logs_recent.json`),
    ]);

    renderServiceCards([
      { name: 'Core Business', url: `${coreBase}/health`, status: coreHealth?.status === 'ok' ? 'ok' : 'bad', label: coreHealth?.status?.toUpperCase() || 'UNAVAILABLE' },
      { name: 'Metrics API', url: `${coreBase}/analytics/metrics/latest`, status: metricsLatest ? 'ok' : 'warning', label: metricsLatest ? 'OK' : 'NO DATA' },
    ]);

    renderDataSource('Metrics lấy từ Core Business; dữ liệu gốc từ IoT broker', `${coreBase}/analytics/metrics/latest`);

    renderSummary(metricsLatest.report || metricsLatest);

    metricsDetails.innerHTML = `
      ${renderDetailTable('Nhiệt độ trung bình theo phòng', metricsLatest.report?.avg_temperature_by_room || {})}
      ${renderDetailTable('Độ ẩm trung bình theo phòng', metricsLatest.report?.avg_humidity_by_room || {})}
      ${renderDetailTable('Số sự kiện theo mức độ', metricsLatest.report?.events_by_severity || {})}
      ${renderDetailTable('Số sự kiện theo khu vực', metricsLatest.report?.events_by_area || {})}
      ${renderDetailTable('Số sự kiện theo nguồn', metricsLatest.report?.events_by_source || {})}
    `;

    renderActivitySummary(accessLogs?.items || []);

    updatedAt.textContent = `Cập nhật ${new Date().toLocaleString('vi-VN')}`;
  } catch (error) {
    serviceGrid.innerHTML = `
      <div class="card">
        <h3>Lỗi tải dashboard</h3>
        <p>${error.message}</p>
      </div>
    `;
    metricsSummary.innerHTML = '';
    metricsDetails.innerHTML = '';
    activitySummary.innerHTML = '';
    activityList.innerHTML = '';
    updatedAt.textContent = 'Lỗi tải dữ liệu';
  }
}

refreshButton.addEventListener('click', loadDashboard);
loadDashboard();
