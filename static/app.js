const sectorsElement = document.querySelector('#sectors');
const form = document.querySelector('#search-form');
const button = document.querySelector('#submit-button');
const spinner = document.querySelector('#loading-spinner');
const buttonLabel = document.querySelector('#button-label');
const alerts = document.querySelector('#alert-container');
const historyKey = 'iddfs-irrigation-search-log';
const tariffGrid = document.querySelector('#tariff-grid');
const defaultTariff = [365, 365, 365, 365, 365, 365, 365, 365, 365, 450, 450, 450, 450, 450, 450, 800, 800, 800, 800, 800, 390, 390, 390, 390];

const defaultSectors = [
  { area: 5000, min: .08, max: .12, initial: .10, flow: 85, power: 20 },
  { area: 10000, min: .09, max: .13, initial: .12, flow: 100, power: 30 },
  { area: 10000, min: .09, max: .13, initial: .11, flow: 120, power: 35 }
];

function sectorTemplate(sector, index) {
  return `<article class="sector-card" data-sector>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <span class="sector-name">Sector ${index + 1}</span>
      <button type="button" class="btn btn-link p-0 remove-sector" aria-label="Eliminar sector">Eliminar</button>
    </div>
    <div class="row g-2">
      <div class="col-6 col-md-3"><label class="form-label">Área (m²)</label><input class="form-control" data-field="area" type="number" min="1" step="1" value="${sector.area}" required></div>
      <div class="col-6 col-md-3"><label class="form-label">L mín (m)</label><input class="form-control" data-field="min" type="number" min="0" step="any" value="${sector.min}" required></div>
      <div class="col-6 col-md-3"><label class="form-label">L inicial (m)</label><input class="form-control" data-field="initial" type="number" min="0" step="any" value="${sector.initial}" required></div>
      <div class="col-6 col-md-3"><label class="form-label">L máx (m)</label><input class="form-control" data-field="max" type="number" min=".001" step="any" value="${sector.max}" required></div>
      <div class="col-6"><label class="form-label">Caudal (m³/h)</label><input class="form-control" data-field="flow" type="number" min=".01" step=".01" value="${sector.flow}" required></div>
      <div class="col-6"><label class="form-label">Potencia (kW)</label><input class="form-control" data-field="power" type="number" min=".01" step=".01" value="${sector.power}" required></div>
    </div>
  </article>`;
}

function validateSector(card) {
  const value = (field) => Number(card.querySelector(`[data-field="${field}"]`).value);
  const minInput = card.querySelector('[data-field="min"]');
  const initialInput = card.querySelector('[data-field="initial"]');
  const maxInput = card.querySelector('[data-field="max"]');
  const min = value('min');
  const initial = value('initial');
  const max = value('max');
  const valid = [min, initial, max].every(Number.isFinite) && min <= initial && initial <= max;
  maxInput.setCustomValidity(valid ? '' : 'Lmax debe ser mayor o igual que Linicial y Lmin');
  initialInput.setCustomValidity(valid ? '' : 'Linicial debe estar entre Lmin y Lmax');
  minInput.setCustomValidity(valid ? '' : 'Lmin debe ser menor o igual que Linicial');
}

function validateSectors() {
  sectorsElement.querySelectorAll('[data-sector]').forEach(validateSector);
}

function renderSectors() {
  [...sectorsElement.querySelectorAll('[data-sector]')].forEach((card, index) => {
    card.querySelector('.sector-name').textContent = `Sector ${index + 1}`;
    card.querySelector('.remove-sector').disabled = sectorsElement.children.length === 1;
    card.querySelectorAll('[data-field="min"], [data-field="initial"], [data-field="max"]').forEach((input) => {
      input.addEventListener('input', () => validateSector(card));
    });
  });
}

function addSector(sector = { area: 5000, min: .08, max: .12, initial: .10, flow: 85, power: 20 }) {
  sectorsElement.insertAdjacentHTML('beforeend', sectorTemplate(sector, sectorsElement.children.length));
  renderSectors();
  validateSectors();
}

function renderTariffInputs() {
  tariffGrid.innerHTML = defaultTariff.map((value, hour) => `<div class="col-6 col-md-3"><label class="form-label" for="tariff-${hour}">Hora ${hour}</label><div class="input-group input-group-sm"><input class="form-control tariff-input" id="tariff-${hour}" type="number" min="0.01" step="any" value="${value}" required><span class="input-group-text">Gs</span></div></div>`).join('');
}

function readTariff() {
  return [...tariffGrid.querySelectorAll('.tariff-input')].map((input) => Number(input.value));
}

defaultSectors.forEach(addSector);
renderTariffInputs();
document.querySelector('#add-sector').addEventListener('click', () => addSector());
sectorsElement.addEventListener('click', (event) => {
  if (event.target.matches('.remove-sector') && sectorsElement.children.length > 1) {
    event.target.closest('[data-sector]').remove();
    renderSectors();
  }
});

function number(selector) { return Number(document.querySelector(selector).value); }
function readSectors() {
  return [...sectorsElement.querySelectorAll('[data-sector]')].map((card) => {
    const value = (field) => Number(card.querySelector(`[data-field="${field}"]`).value);
    return {
      area_m2: value('area'), l_min: value('min'), l_max: value('max'),
      obj_level_m: value('initial'),
      pump: { caudal_m3h: value('flow'), power_kw: value('power') }
    };
  });
}
function payload() {
  const sectors = readSectors();
  return {
    horizon_t: number('#horizon'), strategy: document.querySelector('#strategy').value,
    system: {
      sectors, p_max_kw: number('#max-power'), max_energy_cost: number('#budget'),
      water_loss_m: number('#water-loss'), start_reservoir_v: number('#reservoir'), tariff_table: readTariff()
    },
    initial_state: { t: 0, water_levels_m: sectors.map((sector) => sector.obj_level_m), reservoir_v: number('#reservoir'), accumulated_cost: 0 }
  };
}
function showAlert(message, type = 'danger') {
  alerts.innerHTML = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar"></button></div>`;
}
function format(value, digits = 2) { return Number(value).toLocaleString('es-PY', { maximumFractionDigits: digits }); }
function resultRow(step) {
  const pumps = step.pumps_active.map((active, index) => `<span class="pump-badge ${active ? 'on' : ''}">B${index + 1}</span>`).join('');
  const levels = step.resulting_water_levels.map((level, index) => `S${index + 1}: ${format(level * 1000, 1)} mm`).join('<br>');
  return `<tr><td><strong>t=${step.interval}</strong></td><td>${pumps}</td><td>${format(step.power_kw, 1)} kW</td><td>${format(step.water_pumped_m3, 1)} m³</td><td class="levels">${levels}</td><td>${format(step.remaining_reservoir_v, 1)} m³</td><td>${format(step.accumulated_cost)} Gs</td></tr>`;
}
function savedSearches() {
  try { return JSON.parse(localStorage.getItem(historyKey) || '[]'); }
  catch { return []; }
}
function updateHistoryCount() {
  const count = savedSearches().length;
  document.querySelector('#history-count').textContent = count;
  document.querySelector('#clear-log').disabled = count === 0;
}
function saveSearch(request, result) {
  const searches = savedSearches();
  searches.unshift({ id: Date.now(), createdAt: new Date().toISOString(), request, result });
  localStorage.setItem(historyKey, JSON.stringify(searches.slice(0, 20)));
  updateHistoryCount();
}
function stateSummary(step) {
  if (!step) return '<span class="text-muted">Sin datos</span>';
  const levels = step.resulting_water_levels.map((level, index) => `<span>S${index + 1}: ${format(level * 1000, 1)} mm</span>`).join('');
  return `<div class="state-title">t=${step.interval}</div><div class="state-levels">${levels}</div><div class="state-detail">Reserva <strong>${format(step.remaining_reservoir_v, 1)} m³</strong><br>Costo <strong>${format(step.accumulated_cost)} Gs</strong></div>`;
}
function renderLog() {
  const searches = savedSearches();
  const list = document.querySelector('#log-list');
  document.querySelector('#empty-log').classList.toggle('d-none', searches.length > 0);
  list.innerHTML = searches.map((entry) => {
    const sequence = entry.result.sequence || [];
    const first = sequence[0];
    const final = sequence[sequence.length - 1];
    const date = new Date(entry.createdAt).toLocaleString('es-PY');
    return `<article class="history-card"><div class="history-head"><div><span class="history-date">${date}</span><h3 class="h6 mb-0">${entry.request.strategy} · ${entry.request.horizon_t} horas</h3></div><span class="history-cost">${format(entry.result.total_cost)} Gs</span></div><div class="history-config">${entry.request.system.sectors.length} sectores · ${format(entry.request.system.p_max_kw, 1)} kW máximo · ${format(entry.request.system.start_reservoir_v, 1)} m³ reserva</div><div class="state-compare"><div class="state-box"><span class="state-label">Estado inicial</span>${stateSummary(first)}</div><div class="state-arrow">→</div><div class="state-box final"><span class="state-label">Estado final</span>${stateSummary(final)}</div></div></article>`;
  }).join('');
  updateHistoryCount();
}
function renderResults(result) {
  document.querySelector('#empty-state').classList.add('d-none');
  document.querySelector('#results-content').classList.remove('d-none');
  document.querySelector('#result-meta').classList.remove('d-none');
  document.querySelector('#result-meta').textContent = `${format(result.execution_time_seconds, 3)} s`;
  document.querySelector('#metrics').innerHTML = `<div class="metric"><div class="metric-label">Costo total</div><div class="metric-value">${format(result.total_cost)} Gs</div></div><div class="metric"><div class="metric-label">Profundidad final</div><div class="metric-value">${result.final_depth} h</div></div><div class="metric"><div class="metric-label">Pasos ejecutados</div><div class="metric-value">${result.sequence.length}</div></div>`;
  const rows = result.sequence.map(resultRow).join('');
  document.querySelector('#sequence-body').innerHTML = rows;
  document.querySelector('#modal-sequence-body').innerHTML = rows;
}
document.querySelector('#show-log').addEventListener('click', renderLog);
const confirmClearModalEl = document.querySelector('#confirm-clear-modal');
const confirmClearModal = new bootstrap.Modal(confirmClearModalEl);
document.querySelector('#clear-log').addEventListener('click', () => {
  if (savedSearches().length) confirmClearModal.show();
});
document.querySelector('#confirm-clear-log').addEventListener('click', () => {
  localStorage.removeItem(historyKey);
  renderLog();
  confirmClearModal.hide();
  showAlert('Historial de búsquedas eliminado.', 'success');
});
updateHistoryCount();
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  validateSectors();
  if (!form.checkValidity()) { form.classList.add('was-validated'); showAlert('Revisa los campos obligatorios y los límites de cada sector.', 'warning'); return; }
  button.disabled = true; spinner.classList.remove('d-none'); buttonLabel.textContent = 'Calculando...'; alerts.innerHTML = '';
  try {
    const response = await fetch('/api/v1/irrigation/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload()) });
    const data = await response.json();
    if (response.ok) { const request = payload(); renderResults(data); saveSearch(request, data); showAlert('Secuencia válida encontrada dentro de las restricciones.', 'success'); }
    else { showAlert(data.detail || 'No existe una secuencia viable para este escenario.', 'danger'); }
  } catch (error) { showAlert('No se pudo contactar al motor de búsqueda. Verifica que el servidor esté activo.', 'danger'); }
  finally { button.disabled = false; spinner.classList.add('d-none'); buttonLabel.textContent = 'Buscar secuencia'; }
});
