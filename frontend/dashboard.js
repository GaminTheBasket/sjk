const serviceGrid = document.getElementById('service-grid');
const metricsSummary = document.getElementById('metrics-summary');
const metricsDetails = document.getElementById('metrics-details');
const logSummary = document.getElementById('log-summary');
const logList = document.getElementById('log-list');
const updatedAt = document.getElementById('updated-at');
const refreshButton = document.getElementById('refresh-button');

const apiBase = `${window.location.protocol}//${window.location.hostname}:8020`;

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

function renderLogList(logs) {
  if (!logs || logs.length === 0) {
    return `
      <div class="panel">
        <h3>Giao dịch gần đây</h3>
        <p>Không có bản ghi.</p>
      </div>
    `;
  }

  const rowsHtml = logs
    .slice(0, 10)
    .map(
      (log) => `
        <tr>
          <td>${new Date(log.timestamp).toLocaleString('vi-VN')}</td>
          <td>${log.gateId}</td>
          <td>${log.direction}</td>
          <td>${log.status}</td>
          <td>${log.cardId}</td>
        </tr>
      `,
    )
    .join('');

  return `
    <div class="panel">
      <h3>Giao dịch gần đây</h3>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr><th>Thời gian</th><th>Cổng</th><th>Chiều</th><th>Trạng thái</th><th>Thẻ</th></tr>
          </thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>
    </div>
  `;
}

function renderLogSummary(items) {
  const total = items.length;
  const allowed = items.filter((item) => item.status === 'ALLOWED').length;
  const denied = items.filter((item) => item.status === 'DENIED').length;
  const byGate = items.reduce((acc, item) => {
    acc[item.gateId] = (acc[item.gateId] || 0) + 1;
    return acc;
  }, {});

  logSummary.innerHTML = `
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

  logList.innerHTML = renderLogList(items);
}

async function loadDashboard() {
  updatedAt.textContent = 'Đang tải...';

  let coreHealth = null;
  let metricsLatest = null;
  let accessLogs = null;
  let metricsError = null;

  try {
    coreHealth = await fetchJson(`${apiBase}/health`);
  } catch (error) {
    console.error('Core health fetch failed', error);
  }

  try {
    metricsLatest = await fetchJson(`${apiBase}/analytics/metrics/latest`);
  } catch (error) {
    metricsError = error;
    console.warn('Metrics fetch failed', error);
  }

  try {
    accessLogs = await fetchJson(`${apiBase}/collections/access_logs_recent.json`);
  } catch (error) {
    console.error('Access logs fetch failed', error);
  }

  renderServiceCards([
    {
      name: 'Core Business',
      url: `${apiBase}/health`,
      status: coreHealth?.status === 'ok' ? 'ok' : 'error',
      label: coreHealth?.status?.toUpperCase() || 'UNAVAILABLE',
    },
    {
      name: 'Analytics Metrics',
      url: `${apiBase}/analytics/metrics/latest`,
      status: metricsLatest ? 'ok' : 'warning',
      label: metricsLatest ? 'OK' : 'NO DATA',
    },
  ]);

  if (metricsLatest) {
    renderSummary(metricsLatest.report || metricsLatest);
    metricsDetails.innerHTML = `
      ${renderDetailTable('Nhiệt độ trung bình theo phòng', metricsLatest.report?.avg_temperature_by_room || {})}
      ${renderDetailTable('Độ ẩm trung bình theo phòng', metricsLatest.report?.avg_humidity_by_room || {})}
      ${renderDetailTable('Số sự kiện theo nguồn dịch vụ', metricsLatest.report?.events_by_source || {})}
      ${renderDetailTable('Số sự kiện theo mức độ', metricsLatest.report?.events_by_severity || {})}
      ${renderDetailTable('Số sự kiện theo khu vực', metricsLatest.report?.events_by_area || {})}
    `;
  } else {
    metricsSummary.innerHTML = `
      <div class="panel">
        <h3>Chưa có dữ liệu metrics</h3>
        <p>${metricsError?.message || 'Đang chờ analytics gửi dữ liệu.'}</p>
      </div>
    `;
    metricsDetails.innerHTML = '';
  }

  renderLogSummary(accessLogs?.items || []);

  updatedAt.textContent = `Cập nhật ${new Date().toLocaleString('vi-VN')}`;
}

refreshButton.addEventListener('click', loadDashboard);
loadDashboard();

const REFRESH_INTERVAL = 5000;

setInterval(async () => {
    try {
        await loadDashboard();
    } catch (err) {
        console.error(err);
    }
}, REFRESH_INTERVAL);
