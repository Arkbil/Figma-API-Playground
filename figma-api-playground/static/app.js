const state = {
  fileKey: '',
  fileName: '',
  sessionId: '',
  token: '',
  pages: [],
  currentPageId: '',
  orderedFrames: [],
  imageUrls: {},
  pageImageUrls: {},
  sectionImageUrls: {},
  framePreviewImageUrls: {},
  showPagePreview: false,
  flowAnalysis: null,
  flowImageUrls: {},
  showAllFrames: false,
  showAllCleanEdges: false,
  showAllNoisyEdges: false,
  openMergedFlows: {},
  openJourneys: {},
  savedProjects: [],
  username: '',
  snapshotImported: false,
};

const $ = (selector) => document.querySelector(selector);
const FRAME_PREVIEW_LIMIT = 8;
const CLEAN_EDGE_LIMIT = 8;
const NOISY_EDGE_LIMIT = 20;

function toast(message, error = false) {
  if (error) {
    showAlert('Request Failed', message || 'Something went wrong.', 'error');
    return;
  }
  const el = $('#toast');
  el.textContent = message;
  el.classList.toggle('error', error);
  el.hidden = false;
  clearTimeout(el.timer);
  el.timer = setTimeout(() => { el.hidden = true; }, 3600);
}

function showAlert(title, message, type = 'error', detail = '') {
  const overlay = $('#alertOverlay');
  const icon = $('#alertIcon');
  $('#alertTitle').textContent = title || 'Notice';
  $('#alertMessage').textContent = message || 'No detail available.';
  icon.textContent = type === 'success' ? 'OK' : '!';
  icon.className = `alert-icon ${type}`;
  const detailEl = $('#alertDetail');
  if (detail) {
    detailEl.textContent = detail;
    detailEl.hidden = false;
  } else {
    detailEl.textContent = '';
    detailEl.hidden = true;
  }
  overlay.hidden = false;
  $('#alertClose').focus();
}

function closeAlert() {
  $('#alertOverlay').hidden = true;
}

function showLogin() {
  $('#loginView').hidden = false;
  $('#appView').hidden = true;
}

function showApp(username) {
  state.username = username || 'admin';
  $('#activeUser').textContent = state.username;
  $('#loginView').hidden = true;
  $('#appView').hidden = false;
}

function resetActiveFile(message = 'Session cleared. Load a Figma file again.') {
  state.sessionId = '';
  state.token = '';
  state.fileKey = '';
  state.fileName = '';
  state.pages = [];
  state.orderedFrames = [];
  state.pageImageUrls = {};
  state.flowAnalysis = null;
  state.flowImageUrls = {};
  state.openMergedFlows = {};
  state.openJourneys = {};
  $('#fileSummary').hidden = true;
  $('#pageSelect').innerHTML = '';
  $('#pageSelect').disabled = true;
  setExportButtons(true);
  $('#renderSections').disabled = true;
  $('#renderFrames').disabled = true;
  $('#frameList').className = 'frame-list empty';
  $('#frameList').textContent = 'Load a Figma file first.';
  resetRenderPreviews();
}

function setExportButtons(disabled) {
  $('#exportCurrentPage').disabled = disabled;
  $('#exportCheckedFrames').disabled = disabled;
  $('#exportAllPages').disabled = disabled;
}
function renderSavedProjects(projects = state.savedProjects) {
  state.savedProjects = projects || [];
  const select = $('#savedProjectSelect');
  select.innerHTML = '';
  if (!state.savedProjects.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No saved Figma yet';
    select.appendChild(option);
    $('#loadSavedProject').disabled = true;
    $('#deleteSavedProject').disabled = true;
    return;
  }
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = 'Select saved Figma...';
  select.appendChild(empty);
  state.savedProjects.forEach((project) => {
    const option = document.createElement('option');
    option.value = project.id;
    const fileLabel = project.file_name || project.file_key || 'unknown file';
    option.textContent = `${project.title || fileLabel} | ${fileLabel} | ${project.token_mask || 'saved token'}`;
    select.appendChild(option);
  });
  $('#loadSavedProject').disabled = !select.value;
  $('#deleteSavedProject').disabled = !select.value;
}

function applyLoadedFile(data, token = '') {
  state.token = token;
  state.sessionId = data.session_id;
  state.fileKey = data.file_key;
  state.fileName = data.file_name;
  state.pages = data.pages || [];
  state.snapshotImported = Boolean(data.snapshot_imported);
  state.flowAnalysis = null;
  state.flowImageUrls = {};
  state.showAllCleanEdges = false;
  state.showAllNoisyEdges = false;
  state.openMergedFlows = {};
  state.openJourneys = {};
  if (data.saved_projects) renderSavedProjects(data.saved_projects);
  $('#fileSummary').hidden = false;
  $('#fileSummary').textContent = `${data.figma_title || data.file_name || '(untitled file)'} | ${data.frame_count} top-level frames | ${data.pages?.length || 0} pages | file key ${data.file_key} | ${data.load_mode || 'full'} | last modified ${data.last_modified || '-'}`;
  renderPageOptions();
  setFramesFromPage();
  resetRenderPreviews();
  $('#renderSections').disabled = state.snapshotImported && !state.token;
  $('#renderFrames').disabled = state.snapshotImported && !state.token;
  $('#downloadSnapshot').disabled = false;
}

async function refreshSavedProjects() {
  const data = await postJson('/api/saved-figma-list', {});
  renderSavedProjects(data.projects || []);
}

async function checkAuth() {
  try {
    const response = await fetch('/api/me');
    const data = await response.json();
    if (data.authenticated) {
      showApp(data.username);
      renderSavedProjects(data.projects || []);
    } else {
      showLogin();
    }
  } catch {
    showLogin();
  }
}

async function postJson(url, payload = {}, timeoutMs = 90000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('Request timeout. File Figma kemungkinan besar atau koneksi/API sedang lambat.');
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
  const contentType = response.headers.get('content-type') || '';
  const raw = await response.text();
  let parsed = null;
  if (contentType.includes('application/json') && raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new Error(`Server mengirim JSON tidak valid: ${raw.slice(0, 240)}`);
    }
  }
  if (!response.ok) {
    const message = parsed?.error || raw || `HTTP ${response.status}`;
    throw new Error(message);
  }
  if (contentType.includes('application/json')) return parsed || {};
  return new Response(raw, {status: response.status, headers: response.headers});
}

async function postDownload(url, payload = {}, timeoutMs = 90000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!response.ok) {
      const raw = await response.text();
      let message = raw || `HTTP ${response.status}`;
      if ((response.headers.get('content-type') || '').includes('application/json')) {
        try {
          message = JSON.parse(raw).error || message;
        } catch {
          // Keep raw message.
        }
      }
      throw new Error(message);
    }
    return response;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Export timeout.');
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function selectedPage() {
  return state.pages.find((page) => page.id === state.currentPageId) || state.pages[0];
}

function renderPageOptions() {
  const select = $('#pageSelect');
  select.innerHTML = '';
  state.pages.forEach((page) => {
    const option = document.createElement('option');
    option.value = page.id;
    option.textContent = `${page.name} (${page.frames.length} frames)`;
    select.appendChild(option);
  });
  select.disabled = state.pages.length === 0;
  state.currentPageId = select.value || state.pages[0]?.id || '';
}

function setFramesFromPage() {
  const page = selectedPage();
  state.orderedFrames = page ? [...page.frames] : [];
  state.showAllFrames = false;
  state.pageImageUrls = {};
  state.sectionImageUrls = {};
  state.framePreviewImageUrls = {};
  state.showPagePreview = false;
  renderFrameList();
  resetRenderPreviews();
}

function resetRenderPreviews() {
  const sectionGrid = $('#sectionPreviewGrid');
  const frameGrid = $('#framePreviewGrid');
  if (sectionGrid) {
    sectionGrid.className = 'page-preview empty';
    sectionGrid.textContent = 'Load a file, then render sections from the selected page.';
  }
  if (frameGrid) {
    frameGrid.className = 'page-preview empty';
    frameGrid.textContent = 'Load a file, then render frames from the selected page.';
  }
}
function renderFrameList() {
  const list = $('#frameList');
  if (!state.orderedFrames.length) {
    list.className = 'frame-list empty';
    list.textContent = 'No top-level frames found on this page.';
    setExportButtons(true);
    $('#renderSections').disabled = true;
    $('#renderFrames').disabled = true;
    return;
  }
  const visibleFrames = state.showAllFrames ? state.orderedFrames : state.orderedFrames.slice(0, FRAME_PREVIEW_LIMIT);
  list.className = 'frame-list';
  list.innerHTML = '';
  visibleFrames.forEach((frame) => {
    const actualIndex = state.orderedFrames.indexOf(frame);
    const row = document.createElement('article');
    row.className = 'frame-row selected';
    row.innerHTML = `
      <div class="frame-main">
        <input type="checkbox" checked data-id="${frame.id}">
        <div class="frame-title">
          <strong>${actualIndex + 1}. ${escapeHtml(frame.name || '(unnamed frame)')}</strong>
          <small>${frame.type}${frame.section_name ? ` | section: ${escapeHtml(frame.section_name)}` : ''} | ${frame.id} | ${Math.round(frame.width)}x${Math.round(frame.height)} | x ${Math.round(frame.x)}, y ${Math.round(frame.y)}</small>
        </div>
      </div>
      <div class="frame-actions">
        <button class="mini-btn" type="button" data-action="up" data-index="${actualIndex}">Up</button>
        <button class="mini-btn" type="button" data-action="down" data-index="${actualIndex}">Down</button>
      </div>`;
    list.appendChild(row);
  });
  if (state.orderedFrames.length > FRAME_PREVIEW_LIMIT) {
    list.appendChild(moreButton(state.showAllFrames ? 'Show fewer frames' : `More frames (${state.orderedFrames.length - FRAME_PREVIEW_LIMIT})`, 'toggle-frames'));
  }
  setExportButtons(false);
  $('#renderSections').disabled = state.snapshotImported && !state.token;
  $('#renderFrames').disabled = state.snapshotImported && !state.token;
}

function previewGroupElement(title, items, description) {
  const section = document.createElement('section');
  section.className = 'page-preview-group';
  section.innerHTML = `
    <header>
      <div>
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(description)}</p>
      </div>
      <span>${items.length} items</span>
    </header>`;

  const body = document.createElement('div');
  body.className = 'page-preview-items';
  if (!items.length) {
    body.className = 'page-preview-items empty';
    body.textContent = `No ${title.toLowerCase()} found on this page.`;
    section.appendChild(body);
    return section;
  }

  items.forEach((frame, index) => {
    const url = state.pageImageUrls[frame.id];
    const card = document.createElement('a');
    card.dataset.frameId = frame.id;
    card.dataset.frameName = frame.name || frame.id;
    card.className = 'page-preview-card';
    card.href = url || '#';
    if (url) {
      card.target = '_blank';
      card.rel = 'noopener';
    }
    card.innerHTML = `
      <span>${index + 1}. ${escapeHtml(frame.type || 'FRAME')}</span>
      ${url ? `<img src="${url}" alt="${escapeHtml(frame.name || frame.id)}">` : '<div class="preview-missing">No preview</div>'}
      <strong>${escapeHtml(frame.name || frame.id)}</strong>
      ${frame.section_name ? `<small>Section: ${escapeHtml(frame.section_name)}</small>` : ''}`;
    body.appendChild(card);
  });

  section.appendChild(body);
  return section;
}
function selectedFrameIds() {
  return Array.from(document.querySelectorAll('#frameList input[type="checkbox"]:checked')).map((input) => input.dataset.id).filter(Boolean);
}

function selectedFramesInOrder() {
  const ids = new Set(selectedFrameIds());
  if (!ids.size || !state.showAllFrames) return state.orderedFrames;
  return state.orderedFrames.filter((frame) => ids.has(frame.id));
}

function moveFrame(index, direction) {
  const target = index + direction;
  if (target < 0 || target >= state.orderedFrames.length) return;
  const next = [...state.orderedFrames];
  const [item] = next.splice(index, 1);
  next.splice(target, 0, item);
  state.orderedFrames = next;
  renderFrameList();
}

function renderPrototypeAnalysis(data) {
  state.flowAnalysis = data;
  const result = $('#prototypeResult');
  const flowEdges = data.flow_edges || [];
  const noisyEdges = data.noisy_edges || [];
  const stats = data.stats || {};
  result.className = 'flow-analysis';
  result.innerHTML = `
    <div class="flow-stats">
      ${statCard('Official flows', stats.official_flows || 0)}
      ${statCard('Journeys', stats.journeys || 0)}
      ${statCard('Merged flows', stats.merged_flows || 0)}
      ${statCard('Raw edges', stats.raw_edges || 0)}
      ${statCard('Screen flow', stats.screen_flow_edges || 0)}
      ${statCard('Ignored', stats.ignored_edges || 0)}
      ${statCard('Frames', stats.top_level_frames || 0)}
    </div>
    <div class="flow-section">
      <h3>Screen Flow Candidates</h3>
      <p>${flowEdges.length ? 'Cleaned frame-to-frame navigation candidates. Similar paths are merged in the preview below.' : 'No clean screen-to-screen flow found. Use canvas order/manual ordering as fallback.'}</p>
      <div class="edge-list" id="cleanFlowEdges"></div>
    </div>
    <details class="flow-section">
      <summary>Ignored / Noisy Interactions (${noisyEdges.length})</summary>
      <p>Usually hover states, component internals, missing destinations, or interactions inside the same screen.</p>
      <div class="edge-list" id="noisyFlowEdges"></div>
    </details>`;
  renderCleanEdges();
  renderNoisyEdges();
}

function renderCleanEdges() {
  const clean = $('#cleanFlowEdges');
  if (!clean || !state.flowAnalysis) return;
  const flowEdges = state.flowAnalysis.flow_edges || [];
  if (!flowEdges.length) {
    clean.className = 'edge-list empty';
    clean.textContent = 'No clean screen flow edges after filtering.';
    return;
  }
  const visible = state.showAllCleanEdges ? flowEdges : flowEdges.slice(0, CLEAN_EDGE_LIMIT);
  clean.className = 'edge-list';
  clean.innerHTML = '';
  visible.forEach((edge, index) => clean.appendChild(flowEdgeElement(edge, index + 1, false)));
  if (flowEdges.length > CLEAN_EDGE_LIMIT) clean.appendChild(moreButton(state.showAllCleanEdges ? 'Show fewer flow edges' : `More flow edges (${flowEdges.length - CLEAN_EDGE_LIMIT})`, 'toggle-clean-edges'));
}

function renderNoisyEdges() {
  const noisy = $('#noisyFlowEdges');
  if (!noisy || !state.flowAnalysis) return;
  const noisyEdges = state.flowAnalysis.noisy_edges || [];
  if (!noisyEdges.length) {
    noisy.className = 'edge-list empty';
    noisy.textContent = 'No ignored interactions.';
    return;
  }
  const visible = state.showAllNoisyEdges ? noisyEdges : noisyEdges.slice(0, NOISY_EDGE_LIMIT);
  noisy.className = 'edge-list';
  noisy.innerHTML = '';
  visible.forEach((edge, index) => noisy.appendChild(flowEdgeElement(edge, index + 1, true)));
  if (noisyEdges.length > NOISY_EDGE_LIMIT) noisy.appendChild(moreButton(state.showAllNoisyEdges ? 'Show fewer ignored interactions' : `More ignored interactions (${noisyEdges.length - NOISY_EDGE_LIMIT})`, 'toggle-noisy-edges'));
}


function mergedGroupElement(group) {
  return `
    <section class="merged-flow-section">
      <div class="merged-flow-title">
        <strong>${escapeHtml(group.name || `Flow ${group.index}`)}: starts at ${escapeHtml(group.root_name || group.root_id)}</strong>
        <span>${group.path_count || 0} paths merged · ${group.branch_count || 0} branch points</span>
      </div>
      <div class="merged-tree">${treeNodeElement(group.tree, 0)}</div>
    </section>
  `;
}

function exportJourney(journeyKey) {
  const journey = (state.flowAnalysis?.journey_groups || []).find((item) => item.key === journeyKey);
  if (!journey) {
    toast('Journey not found.', true);
    return;
  }
  const groups = (state.flowAnalysis?.merged_flow_groups || []).filter((group) => (journey.flow_indexes || []).includes(group.index));
  const frameIds = [];
  groups.forEach((group) => collectTreeIds(group.tree, frameIds));
  const payload = {
    export_type: 'journey',
    file_key: state.fileKey,
    file_name: state.fileName,
    journey,
    merged_flow_groups: groups,
    frame_ids: frameIds,
    generated_at: new Date().toISOString(),
  };
  downloadJson(payload, `figma-journey-${slugify(journey.label || journey.key)}.json`);
}

function downloadJson(payload, filename) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function slugify(value) {
  return String(value || 'export').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'export';
}
function treeNodeElement(node, depth) {
  if (!node) return '';
  const children = node.children || [];
  const branchClass = children.length > 1 ? ' branch-node' : '';
  return `
    <div class="tree-level depth-${Math.min(depth, 6)}">
      <div class="tree-node${branchClass}">
        ${flowShot(node.id, node.name, depth === 0 ? 'Start' : `Step ${depth + 1}`)}
        ${children.length > 1 ? `<div class="branch-label">${children.length} branches</div>` : ''}
      </div>
      ${children.length ? `<div class="tree-children">${children.map((child) => treeNodeElement(child, depth + 1)).join('')}</div>` : ''}
    </div>`;
}

function flowShot(frameId, frameName, label) {
  const url = state.flowImageUrls[frameId];
  if (!url) return `<div class="flow-shot missing"><span>${label}</span><strong>${escapeHtml(frameName || frameId)}</strong><small>No preview</small></div>`;
  return `<a class="flow-shot" href="${url}" target="_blank" rel="noopener"><span>${label}</span><img src="${url}" alt="${escapeHtml(frameName || frameId)}"><strong>${escapeHtml(frameName || frameId)}</strong></a>`;
}

function statCard(label, value) {
  return `<div><strong>${value}</strong><span>${escapeHtml(label)}</span></div>`;
}

function flowEdgeElement(edge, index, noisy) {
  const row = document.createElement('article');
  row.className = noisy ? 'edge edge-noisy' : 'edge';
  const confidence = Math.round((Number(edge.confidence || 0)) * 100);
  const badge = noisy ? escapeHtml(edge.category || 'IGNORED') : `${confidence}% confidence`;
  row.innerHTML = `<div><strong>${index}. ${escapeHtml(edge.source_frame_name || edge.source_name || edge.source_id)}</strong><span>${escapeHtml(edge.source_frame_type || edge.source_type || '')}</span></div><div><strong>-></strong><br><span>${escapeHtml(edge.trigger || edge.action_type || 'interaction')}</span><em>${badge}</em></div><div><strong>${escapeHtml(edge.destination_frame_name || edge.destination_name || edge.destination_id)}</strong><span>${escapeHtml(edge.destination_frame_type || edge.destination_type || '')}</span></div><p>${escapeHtml(edge.reason || '')}${edge.raw_count ? ` Raw duplicates: ${edge.raw_count}.` : ''}</p>`;
  return row;
}

function moreButton(label, action, value = '') {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'more-button';
  button.dataset.action = action;
  if (value !== '') button.dataset.value = String(value);
  button.textContent = label;
  return button;
}

function escapeHtml(value) {
  return String(value || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
}

$('#loginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = 'Logging in...';
  try {
    const payload = Object.fromEntries(new FormData(form).entries());
    const data = await postJson('/api/login', payload);
    showApp(data.username);
    renderSavedProjects(data.projects || []);
    toast('Logged in.');
  } catch (error) {
    showAlert('Login Failed', error.message || 'Login failed.', 'error');
  } finally {
    button.disabled = false;
    button.textContent = 'Login';
  }
});

$('#loadForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  button.textContent = 'Loading...';
  try {
    const payload = Object.fromEntries(new FormData(form).entries());
    if (!String(payload.figma_title || '').trim()) throw new Error('Judul Figma wajib diisi.');
    if (!String(payload.token || '').trim()) throw new Error('Figma Personal Access Token wajib diisi.');
    if (!String(payload.figma_url || '').trim()) throw new Error('Figma File URL atau file key wajib diisi.');
    const data = await postJson('/api/load-file', payload, 45000);
    applyLoadedFile(data, payload.token);
    toast(data.message || 'Figma file loaded and saved.');
  } catch (error) {
    showAlert(
      'Load File Failed',
      error.message || 'Failed to load Figma file.',
      'error',
      'Cek token, akses file, URL/file key, dan rate limit Figma API. Entry baru hanya disimpan setelah load berhasil.'
    );
  } finally {
    button.disabled = false;
    button.textContent = 'Load & Save File';
  }
});

$('#savedProjectSelect').addEventListener('change', (event) => {
  const hasValue = Boolean(event.target.value);
  $('#loadSavedProject').disabled = !hasValue;
  $('#deleteSavedProject').disabled = !hasValue;
});

$('#loadSavedProject').addEventListener('click', async () => {
  const savedId = $('#savedProjectSelect').value;
  if (!savedId) return;
  $('#loadSavedProject').disabled = true;
  $('#loadSavedProject').textContent = 'Loading...';
  try {
    const data = await postJson('/api/load-file', {saved_project_id: savedId}, 45000);
    applyLoadedFile(data, '');
    toast('Saved Figma loaded without re-entering token.');
  } catch (error) {
    showAlert('Load Saved Failed', error.message || 'Failed to load saved Figma.', 'error');
  } finally {
    $('#loadSavedProject').disabled = !$('#savedProjectSelect').value;
    $('#loadSavedProject').textContent = 'Load Saved';
  }
});

$('#deleteSavedProject').addEventListener('click', async () => {
  const savedId = $('#savedProjectSelect').value;
  if (!savedId) return;
  try {
    const data = await postJson('/api/delete-saved-figma', {id: savedId});
    renderSavedProjects(data.projects || []);
    toast('Saved Figma deleted.');
  } catch (error) {
    showAlert('Delete Saved Failed', error.message || 'Failed to delete saved Figma.', 'error');
  }
});
$('#pageSelect').addEventListener('change', (event) => { state.currentPageId = event.target.value; setFramesFromPage(); });


$('#frameList').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  if (button.dataset.action === 'toggle-frames') { state.showAllFrames = !state.showAllFrames; renderFrameList(); return; }
  moveFrame(Number(button.dataset.index), button.dataset.action === 'up' ? -1 : 1);
});

$('#frameList').addEventListener('change', (event) => {
  const checkbox = event.target.closest('input[type="checkbox"]');
  if (checkbox) checkbox.closest('.frame-row')?.classList.toggle('selected', checkbox.checked);
});


async function renderNodePreview(kind) {
  const isSection = kind === 'section';
  const grid = isSection ? $('#sectionPreviewGrid') : $('#framePreviewGrid');
  const button = isSection ? $('#renderSections') : $('#renderFrames');
  const typeLabel = isSection ? 'sections' : 'frames';
  if (state.snapshotImported && !state.token) {
    showAlert('Render Unavailable', 'Snapshot lokal tidak menyimpan token. Struktur tetap bisa dibaca, tapi render image perlu Figma API/token.', 'error');
    return;
  }
  const items = state.orderedFrames.filter((item) => isSection ? item.type === 'SECTION' : item.type !== 'SECTION');
  if (!items.length) {
    grid.className = 'page-preview empty';
    grid.textContent = `No ${typeLabel} found on this page.`;
    return;
  }
  const ids = items.map((item) => item.id).filter(Boolean).slice(0, 50);
  button.disabled = true;
  button.textContent = 'Rendering...';
  grid.className = 'page-preview empty';
  grid.textContent = `Rendering ${ids.length} ${typeLabel}...`;
  try {
    const data = await postJson('/api/render-frames', {session_id: state.sessionId, token: state.token, file_key: state.fileKey, ids, format: 'png', scale: '0.5'}, 90000);
    if (isSection) state.sectionImageUrls = data.images || {};
    else state.framePreviewImageUrls = data.images || {};
    renderPreviewItems(grid, items.slice(0, 50), isSection ? state.sectionImageUrls : state.framePreviewImageUrls, isSection ? 'Sections' : 'Frames / Screens');
    toast(`${ids.length} ${typeLabel} rendered.`);
  } catch (error) {
    showAlert(`Render ${isSection ? 'Sections' : 'Frames'} Failed`, error.message || 'Failed to render preview.', 'error', 'Render memakai Figma Images API. Jika kena rate limit, tunggu sebentar atau gunakan snapshot untuk membaca struktur tanpa render image.');
  } finally {
    button.disabled = state.snapshotImported && !state.token;
    button.textContent = isSection ? 'Render Sections' : 'Render Frames';
  }
}

function renderPreviewItems(grid, items, images, title) {
  grid.className = 'page-preview';
  grid.innerHTML = '';
  state.pageImageUrls = images;
  grid.appendChild(previewGroupElement(title, items, title === 'Sections' ? 'Rendered Figma section containers from the selected page.' : 'Rendered frames/screens from the selected page.'));
  if (items.length >= 50) {
    const note = document.createElement('div');
    note.className = 'preview-note';
    note.textContent = 'Showing first 50 items to avoid heavy Figma image requests.';
    grid.appendChild(note);
  }
  const cards = grid.querySelectorAll('.page-preview-card');
  cards.forEach((card) => {
    const frameId = card.dataset.frameId;
    const url = images[frameId];
    if (url) {
      card.href = url;
      card.target = '_blank';
      card.rel = 'noopener';
      const placeholder = card.querySelector('.preview-missing');
      if (placeholder) placeholder.outerHTML = `<img src="${url}" alt="${escapeHtml(card.dataset.frameName || frameId)}">`;
    }
  });
}

$('#renderSections').addEventListener('click', () => renderNodePreview('section'));
$('#renderFrames').addEventListener('click', () => renderNodePreview('frame'));
$('#downloadSnapshot').addEventListener('click', async () => {
  if (!state.sessionId) {
    showAlert('Snapshot Unavailable', 'Load atau import file terlebih dahulu sebelum download snapshot.', 'error');
    return;
  }
  $('#downloadSnapshot').disabled = true;
  $('#downloadSnapshot').textContent = 'Downloading...';
  try {
    const response = await postDownload('/api/export-snapshot', {session_id: state.sessionId, file_key: state.fileKey, file_name: state.fileName}, 90000);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `figma-snapshot-${slugify(state.fileName || state.fileKey || 'export')}.json`;
    link.click();
    URL.revokeObjectURL(url);
    toast('Snapshot downloaded.');
  } catch (error) {
    showAlert('Download Snapshot Failed', error.message || 'Failed to download snapshot.', 'error');
  } finally {
    $('#downloadSnapshot').disabled = !state.sessionId;
    $('#downloadSnapshot').textContent = 'Download Snapshot';
  }
});

$('#importSnapshot').addEventListener('click', () => {
  $('#snapshotFile').value = '';
  $('#snapshotFile').click();
});

$('#snapshotFile').addEventListener('change', async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    const snapshot = JSON.parse(text);
    const data = await postJson('/api/import-snapshot', {snapshot}, 90000);
    applyLoadedFile(data, '');
    toast(data.message || 'Snapshot imported.');
  } catch (error) {
    showAlert(
      'Import Snapshot Failed',
      error.message || 'Snapshot JSON tidak bisa dibaca.',
      'error',
      'Pastikan file yang diupload adalah JSON hasil Download Snapshot dari Figma API Playground.'
    );
  }
});
async function downloadFrameOrderExport(exportType, payload, filenamePrefix) {
  try {
    const response = await postDownload('/api/export-order', payload);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filenamePrefix}-${state.fileKey || 'export'}.json`;
    link.click();
    URL.revokeObjectURL(url);
    toast(`${exportType} exported.`);
  } catch (error) {
    toast(error.message || `Failed to export ${exportType}.`, true);
  }
}

$('#exportCurrentPage').addEventListener('click', async () => {
  const page = selectedPage();
  const frames = state.orderedFrames.map(frameExportRow);
  await downloadFrameOrderExport('Current page frames', {
    export_type: 'current_page_frames',
    file_key: state.fileKey,
    file_name: state.fileName,
    page_id: page?.id || '',
    page_name: page?.name || '',
    frames,
  }, 'figma-current-page-frames');
});

$('#exportCheckedFrames').addEventListener('click', async () => {
  const page = selectedPage();
  const frames = checkedFramesInOrder().map(frameExportRow);
  if (!frames.length) {
    showAlert('No Checked Frames', 'Pilih minimal satu checkbox frame sebelum export checked frames.', 'error');
    return;
  }
  await downloadFrameOrderExport('Checked frames', {
    export_type: 'checked_frames',
    file_key: state.fileKey,
    file_name: state.fileName,
    page_id: page?.id || '',
    page_name: page?.name || '',
    frames,
  }, 'figma-checked-frames');
});

$('#exportAllPages').addEventListener('click', async () => {
  const pages = state.pages.map((page) => ({
    id: page.id,
    name: page.name,
    frame_count: (page.frames || []).length,
    frames: (page.frames || []).map((frame, index) => ({
      order: index + 1,
      id: frame.id,
      name: frame.name,
      type: frame.type,
      section_name: frame.section_name || '',
      x: frame.x,
      y: frame.y,
      width: frame.width,
      height: frame.height,
    })),
  }));
  await downloadFrameOrderExport('All pages frames', {
    export_type: 'all_pages_frames',
    file_key: state.fileKey,
    file_name: state.fileName,
    pages,
  }, 'figma-all-pages-frames');
});
$('#clearToken').addEventListener('click', async () => {
  try {
    await postJson('/api/clear-session', {session_id: state.sessionId});
    resetActiveFile('Active file cleared. Saved Figma entries are still available.');
    toast('Active file cleared.');
  } catch (error) {
    toast(error.message || 'Failed to clear active file.', true);
  }
});

$('#logoutButton').addEventListener('click', async () => {
  try {
    await postJson('/api/logout', {});
  } catch {
    // Continue local logout even if the server session is already gone.
  }
  resetActiveFile('Logged out. Login again to load saved Figma entries.');
  renderSavedProjects([]);
  showLogin();
  toast('Logged out.');
});
$('#alertClose').addEventListener('click', closeAlert);
$('#alertOverlay').addEventListener('click', (event) => {
  if (event.target.id === 'alertOverlay') closeAlert();
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !$('#alertOverlay').hidden) closeAlert();
});
window.addEventListener('error', (event) => {
  showAlert('Browser Script Error', event.message || 'Unexpected browser error.', 'error', `${event.filename || ''}:${event.lineno || 0}`);
});
window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason?.message || String(event.reason || 'Unhandled promise rejection.');
  showAlert('Unhandled Request Error', reason, 'error');
});

resetRenderPreviews();
checkAuth();

