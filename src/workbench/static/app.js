'use strict';

const byId = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="workbench-token"]').content;
const terminal = new Set(['completed', 'failed', 'cancelled', 'interrupted', 'stopped']);
const labels = {queued: '等待启动', running: '运行中', waiting: '待你确认', completed: '已完成', failed: '失败', cancelled: '已取消', interrupted: '已中断', stopped: '已停止生成'};
const state = {job: null, activeId: null, after: 0, logs: '', articleOffset: 0, articleTotal: 0, historyOffset: 0, historyTotal: 0, polling: false, reviewId: null, historyRequest: 0, articleRequest: 0, providers: []};
let toastTimer;

function notify(message) {
  byId('toast').textContent = message;
  byId('toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { byId('toast').hidden = true; }, 6000);
}

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type': 'application/json', 'X-Workbench-Token': token, ...options.headers}});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '请求失败');
  return data;
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function dateLabel(value) {
  return value ? new Date(value).toLocaleString('zh-CN', {hour12: false}) : '';
}

function debounce(callback, delay = 250) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => callback(...args), delay); };
}

function providerProfile(id) { return state.providers.find((item) => item.id === id) || state.providers.find((item) => item.id === 'openai_proxy'); }

function setProtocolOptions(profile, selected) {
  const select = byId('setting-protocol');
  const options = profile?.api_type === 'gemini' ? [['gemini', 'Google Gemini 原生接口']]
    : profile?.api_type === 'anthropic' ? [['anthropic', 'Anthropic Messages API']]
    : [['openai', 'OpenAI Chat Completions'], ...(profile?.supports_responses ? [['openai_responses', 'OpenAI Responses']] : [])];
  select.replaceChildren(...options.map(([value, label]) => { const option = document.createElement('option'); option.value = value; option.textContent = label; return option; }));
  select.value = options.some(([value]) => value === selected) ? selected : options[0][0];
}

function applyProviderProfile(id, {preserveModel = false, preserveBase = true, selectedProtocol = ''} = {}) {
  const profile = providerProfile(id);
  if (!profile) return;
  byId('setting-provider').value = profile.id;
  if (profile.base_url && (!preserveBase || !byId('setting-base-url').value.trim())) byId('setting-base-url').value = profile.base_url;
  if (!preserveModel || !byId('setting-model').value.trim()) byId('setting-model').value = profile.default_model || '';
  setProtocolOptions(profile, selectedProtocol || profile.api_type);
  byId('provider-hint').textContent = profile.description + (profile.requires_api_key ? ' · 需要 API Key' : ' · 本地服务无需 API Key');
  byId('base-url-hint').textContent = profile.api_type === 'gemini' ? 'Gemini 使用原生 v1beta 接口。' : profile.api_type === 'anthropic' ? 'Claude 使用原生 Messages API，模型名称需手动填写。' : `推荐地址：${profile.base_url || '请填写服务商提供的完整地址'}`;
}

function populateProviders(providers) {
  state.providers = Array.isArray(providers) ? providers : [];
  const select = byId('setting-provider');
  if (!select || !state.providers.length) return;
  select.replaceChildren(...state.providers.map((profile) => { const option = document.createElement('option'); option.value = profile.id; option.textContent = profile.label; return option; }));
}

function switchView(name) {
  document.querySelectorAll('.view').forEach((view) => { view.hidden = view.id !== `view-${name}`; });
  document.querySelectorAll('[data-view]').forEach((button) => { button.classList.toggle('active', button.dataset.view === name); });
  byId('breadcrumb').textContent = {system: '系统状态', workspace: '研究工作台', history: '历史检索', settings: '配置'}[name];
  if (name === 'history') loadHistory().catch((error) => notify(error.message));
  if (name === 'settings' || name === 'system') loadSystemStatus().catch((error) => notify(error.message));
}

async function loadSystemStatus() {
  const data = await api('/api/system/status');
  const dl = byId('system-status'); dl.replaceChildren();
  const actions = byId('system-actions'); actions.replaceChildren();
  for (const [key, value] of [['Python', data.python], ['解释器', data.executable], ['虚拟环境', data.virtualenv ? '已启用' : '未启用'], ['依赖', Object.entries(data.dependencies).filter(([,ok]) => ok).map(([name]) => name).join('、')], ['Pandoc', data.pandoc || '未检测到'], ['数据目录', data.data_directory ? '存在' : '缺少'], ['提示词文件', data.prompts ? '存在' : '缺少']]) dl.append(element('dt', key), element('dd', String(value)));
  const journals = await api('/api/journals/status'); dl.append(element('dt', '期刊数据'), element('dd', Object.values(journals.files).every((item) => item.exists) ? 'ShowJCR 最新数据已存在' : '缺少 ShowJCR 最新数据'));
  if (!data.pandoc) { const button=element('button','安装 Pandoc','button'); button.onclick=()=>installPandoc(button,'pandoc'); actions.append(button); }
  else { const button=element('button','更新 Pandoc','button'); button.onclick=()=>installPandoc(button,'pandoc_update'); actions.append(button); }
  if (Object.values(data.dependencies).some((ok)=>!ok)) { const button=element('button','安装缺失依赖','button'); button.onclick=async()=>{button.disabled=true;try{await api('/api/system/install',{method:'POST',body:JSON.stringify({component:'dependencies'})});await loadSystemStatus();}catch(e){notify(e.message);button.disabled=false;}}; actions.append(button); }
  const prompt = await api('/api/prompts');
  for (const [module, id] of [['intent_analysis','prompt-intent'],['outline_generation','prompt-outline'],['review_generation','prompt-review']]) byId(id).value = prompt.modules?.[module] || '';
}
async function installPandoc(button, component) { button.disabled=true; button.textContent=component==='pandoc_update'?'正在更新 Pandoc…':'正在下载安装 Pandoc…'; notify('正在处理 Pandoc，请勿重复点击。'); try { await api('/api/system/install',{method:'POST',body:JSON.stringify({component})}); notify(component==='pandoc_update'?'Pandoc 更新并验证成功':'Pandoc 安装并验证成功'); await loadSystemStatus(); } catch (error) { notify(error.message); button.disabled=false; button.textContent=component==='pandoc_update'?'重试更新 Pandoc':'重试安装 Pandoc'; } }

function readOptions() {
  const filters = {year_start:byId('year-start').value ? Number(byId('year-start').value) : null, year_end:byId('year-end').value ? Number(byId('year-end').value) : null, min_if:byId('if-min').value ? Number(byId('if-min').value) : null, jcr:Number(byId('jcr-range').value), cas:Number(byId('cas-range').value), new_rui_2026:Number(byId('new-rui-2026').value)};
  return {target: Number(byId('target').value),
    search_filters: filters, topic_details: '', topic_outcomes: '',
    confirm_steps: true, cache: true, interactive_ai: false,
    ai_provider: byId('setting-provider').value,
    ai_protocol: byId('setting-protocol').value,
    model: byId('setting-model').value,
    intent_model: byId('setting-intent-model').value, outline_model: byId('setting-outline-model').value, review_model: byId('setting-review-model').value,
    intent_reasoning: byId('setting-intent-reasoning').value, outline_reasoning: byId('setting-outline-reasoning').value, review_reasoning: byId('setting-review-reasoning').value,
    temperature: null,
    max_tokens: byId('setting-max-tokens').value ? Number(byId('setting-max-tokens').value) : null,
    review_format: byId('setting-format').value};
}

function fillOptions(options) {
  const filters = {...options.search_filters};
  if (Number.isInteger(filters.years)) {
    const year = Number(byId('year-start').max);
    filters.year_start = filters.years ? year - filters.years + 1 : null;
    filters.year_end = filters.years ? year : null;
  }
  for (const [key, id] of [['year_start','year-start'],['year_end','year-end'],['min_if','if-min'],['jcr','jcr-range'],['cas','cas-range'],['new_rui_2026','new-rui-2026']]) {
    byId(id).value = filters[key] ?? ((key === 'jcr' || key === 'cas' || key === 'new_rui_2026') ? 0 : '');
    byId(id).dispatchEvent(new Event('input'));
  }
  if (options.ai_provider) applyProviderProfile(options.ai_provider, {preserveModel: true, selectedProtocol: options.ai_protocol});
  else if (options.ai_protocol) setProtocolOptions(providerProfile(byId('setting-provider').value), options.ai_protocol);
  for (const [key, id] of Object.entries({target: 'target'})) {
    if (options[key] !== undefined) byId(id).value = options[key];
  }
  if (options.model !== undefined) byId('setting-model').value = options.model;
  for (const key of ['intent_model','outline_model','review_model','intent_reasoning','outline_reasoning','review_reasoning']) if (options[key] !== undefined) byId(`setting-${key.replaceAll('_','-')}`).value = options[key];
  if (byId('setting-max-tokens') && options.max_tokens !== undefined) byId('setting-max-tokens').value = options.max_tokens ?? '';
  if (byId('setting-format') && options.review_format !== undefined) byId('setting-format').value = options.review_format;
}

async function bootstrap(initial = false) {
  const data = await api('/api/bootstrap');
  if (initial) {
    const config = await api('/api/configuration');
    populateProviders(config.providers);
    const preferences = {...data.preferences};
    if (!preferences.ai_provider) preferences.ai_provider = config.provider;
    if (!preferences.ai_protocol) preferences.ai_protocol = config.api_type;
    if (!preferences.model) preferences.model = config.model;
    applyProviderProfile(preferences.ai_provider, {preserveModel: true, selectedProtocol: preferences.ai_protocol});
    byId('setting-base-url').value = config.base_url || '';
    byId('setting-api-key').placeholder = config.requires_api_key ? (config.api_key_configured ? '已配置；留空保留' : '请输入 AI API Key') : '本地服务无需 API Key';
    byId('pubmed-key-status').textContent = `${config.pubmed_key_configured ? '已配置 Key' : '未配置 Key'} · 限制 ${config.pubmed_requests_per_second} 次/秒`;
    fillOptions(preferences);
  }
  state.activeId = data.active_id;
  byId('stat-tasks').textContent = data.stats.tasks;
  byId('stat-completed').textContent = data.stats.completed;
  byId('stat-articles').textContent = data.stats.articles;
  byId('history-count').textContent = data.stats.tasks;
  byId('start-button').disabled = Boolean(state.activeId);
  byId('start-button').textContent = state.activeId ? '已有任务运行中' : '开始检索 →';
  if (initial && state.activeId) await selectJob(state.activeId);
}

async function selectJob(id) {
  state.job = {id};
  state.after = 0;
  state.logs = '';
  state.articleOffset = 0;
  state.articleTotal = 0;
  state.reviewId = null;
  byId('article-search').value = '';
  byId('outline-content').textContent = '大纲生成后可在这里查看。';
  byId('review-content').textContent = '正文生成后可在这里查看。DOCX 文件请在成果文件中下载。';
  byId('log-content').textContent = '正在载入运行日志…';
  byId('article-list').replaceChildren(element('p', '正在载入文献…', 'empty-state'));
  switchView('workspace');
  await refreshJob(true);
}

async function refreshJob(forceArticles = false) {
  if (!state.job) return;
  const id = state.job.id;
  const [job, events] = await Promise.all([api(`/api/jobs/${id}`), api(`/api/jobs/${id}/events?after=${state.after}`)]);
  if (!state.job || state.job.id !== id) return;
  const previousCount = state.job.article_count;
  const previousStatus = state.job.status;
  state.job = job;
  byId('job-summary').hidden = false;
  byId('job-query').textContent = job.query;
  byId('job-meta').textContent = `${dateLabel(job.created_at)} · 任务 ${job.id.slice(0, 8)} · ${labels[job.status] || job.status}`;
  byId('job-badge').textContent = labels[job.status] || job.status;
  byId('article-count').textContent = job.article_count;
  byId('cancel-button').hidden = terminal.has(job.status);
  byId('job-error').hidden = !job.error;
  byId('job-error').textContent = job.error || '';
  const stages = ['intent', 'search', 'outline', 'review'];
  const currentIndex = stages.indexOf(job.stage);
  document.querySelectorAll('[data-stage]').forEach((node, index) => {
    node.classList.toggle('current', index === currentIndex && !terminal.has(job.status));
    node.classList.toggle('done', job.status === 'completed' || index < currentIndex);
  });
  const oldPrompt = byId('prompt-panel').dataset.prompt;
  byId('prompt-panel').hidden = !job.prompt || job.status !== 'waiting';
  if (job.prompt) {
    const isReviewGate = job.prompt.purpose === 'start_review' || (job.stage === 'search' && Number(job.article_count || 0) > 0);
    byId('start-review').hidden = !isReviewGate;
    byId('adjust-search').hidden = !isReviewGate;
    byId('prompt-form').hidden = isReviewGate;
    byId('result-count-confirm').textContent = isReviewGate ? `目标 ${job.options.target} 篇，实际 ${job.article_count || 0} 篇。请确认是否开始综述。` : '';
    byId('prompt-panel').dataset.prompt = job.prompt.id;
    byId('prompt-text').textContent = job.prompt.text;
    byId('prompt-value').type = job.prompt.sensitive ? 'password' : 'text';
    if (oldPrompt !== job.prompt.id) byId('prompt-value').value = '';
  }
  if (job.outline) byId('outline-content').textContent = job.outline.content;
  for (const event of events.items) {
    state.after = Math.max(state.after, event.id);
    if (event.kind === 'log') state.logs += event.payload.text + '\n';
  }
  state.logs = state.logs.slice(-60000);
  const log = byId('log-content');
  const atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 30;
  log.textContent = state.logs || '尚无运行日志。';
  if (atBottom) log.scrollTop = log.scrollHeight;
  renderArtifacts(job.artifacts);
  if (forceArticles || previousCount !== job.article_count) await loadArticles();
  if (previousStatus !== job.status) await bootstrap();
}

function renderArtifacts(artifacts) {
  artifacts = artifacts.filter((artifact) => artifact.name.includes('文献列表-') || artifact.name.includes('最终纳入综述文献') || artifact.name.includes('综述文章'));
  byId('artifact-count').textContent = artifacts.length;
  const list = byId('artifact-list');
  list.replaceChildren();
  if (!artifacts.length) list.append(element('p', '任务产生的 CSV、Markdown、DOCX 等文件会出现在这里。', 'muted'));
  for (const artifact of artifacts) {
    const link = element('a', undefined, 'artifact-link');
    link.href = `/api/artifacts/${artifact.id}`;
    const name = artifact.name.split(/[\\/]/).pop();
    const label = element('span', name);
    label.append(element('small', `${(artifact.size / 1024).toFixed(1)} KB · 下载`));
    link.append(element('span', name.split('.').pop().toUpperCase(), 'file-type'), label);
    list.append(link);
  }
  const review = artifacts.find((artifact) => artifact.name.includes('综述文章') && artifact.name.endsWith('.md'));
  if (review && state.reviewId !== review.id) {
    state.reviewId = review.id;
    const jobId = state.job.id;
    api(`/api/artifacts/${review.id}?preview=1`).then((data) => {
      if (state.job.id === jobId) byId('review-content').textContent = data.content + (data.truncated ? '\n\n[预览已截断，请下载完整文件]' : '');
    }).catch((error) => { state.reviewId = null; notify(error.message); });
  }
}

async function loadArticles() {
  if (!state.job) return;
  const id = state.job.id;
  const requestNumber = ++state.articleRequest;
  const data = await api(`/api/jobs/${id}/articles?offset=${state.articleOffset}&q=${encodeURIComponent(byId('article-search').value)}`);
  if (state.job.id !== id || requestNumber !== state.articleRequest) return;
  state.articleTotal = data.total;
  byId('article-toolbar').hidden = false;
  byId('article-total').textContent = `${data.total} 篇文献`;
  const list = byId('article-list');
  list.replaceChildren();
  if (!data.items.length) {
    list.append(element('p', byId('article-search').value ? '没有匹配的文献，试试其他关键词。' : '暂无已保存文献。运行中可查看日志；失败或取消任务只保留实际产生的结果。', 'empty-state'));
  }
  data.items.forEach((article, index) => {
    const row = element('div', undefined, 'article-row');
    const body = element('div', undefined, 'article-body');
    const title = element('button', article.title || '未提供标题', 'article-title');
    title.addEventListener('click', () => showArticle(article));
    const meta = element('div', undefined, 'article-meta');
    meta.append(element('span', article.journal || '期刊信息缺失'), element('span', article.year || article.pub_date || article.publication_date || ''));
    if (/^\d+$/.test(String(article.pmid))) {
      const pubmed = element('a', `PMID ${article.pmid} ↗`);
      pubmed.href = `https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`;
      pubmed.target = '_blank';
      pubmed.rel = 'noopener noreferrer';
      meta.append(pubmed);
    }
    body.append(title, meta);
    row.append(element('span', String(state.articleOffset + index + 1).padStart(2, '0'), 'article-index'), body);
    list.append(row);
  });
  byId('article-pagination').hidden = data.total <= 50;
  byId('articles-page').textContent = `${Math.floor(state.articleOffset / 50) + 1} / ${Math.max(1, Math.ceil(data.total / 50))}`;
  byId('articles-prev').disabled = state.articleOffset === 0;
  byId('articles-next').disabled = state.articleOffset + 50 >= data.total;
}

function showArticle(article) {
  byId('detail-title').textContent = article.title || '未提供标题';
  byId('detail-meta').textContent = `${article.journal || ''} · PMID ${article.pmid || '未提供'}`;
  const abstract = article.abstract;
  byId('detail-abstract').textContent = typeof abstract === 'string' ? abstract || '该记录未提供摘要。' : abstract ? JSON.stringify(abstract, null, 2) : '该记录未提供摘要。';
  byId('detail-json').textContent = JSON.stringify(article, null, 2);
  byId('article-dialog').showModal();
}

async function loadHistory() {
  const requestNumber = ++state.historyRequest;
  const data = await api(`/api/jobs?q=${encodeURIComponent(byId('history-search').value)}&status=${byId('history-status').value}&offset=${state.historyOffset}`);
  if (requestNumber !== state.historyRequest) return;
  state.historyTotal = data.total;
  const list = byId('history-list');
  list.replaceChildren();
  if (!data.items.length) list.append(element('p', '暂无匹配的历史记录。新建检索后，任务会自动保存在这里。', 'empty-state'));
  for (const job of data.items) {
    const row = element('div', undefined, 'history-row');
    const check = document.createElement('input'); check.type = 'checkbox'; check.className = 'history-select'; check.dataset.jobId = job.id; check.addEventListener('change', updateHistorySelection); row.append(check);
    const information = element('div');
    const meta = element('p');
    meta.append(element('span', labels[job.status] || job.status, 'status-label'), document.createTextNode(dateLabel(job.created_at)));
    information.append(element('h3', job.query), meta);
    const button = element('button', '查看结果 ↗', 'button secondary small');
    button.addEventListener('click', () => selectJob(job.id).catch((error) => notify(error.message)));
    const remove = element('button', '清理', 'button danger small');
    remove.addEventListener('click', async () => { if (!window.confirm('确定清理这条历史检索及其结果吗？')) return; try { await api(`/api/jobs/${job.id}`, {method:'DELETE'}); notify('历史记录已清理'); await loadHistory(); } catch (error) { notify(error.message); } });
    row.append(information, button);
    list.append(row);
  }
  byId('history-page').textContent = `共 ${data.total} 项 · ${Math.floor(state.historyOffset / 30) + 1} / ${Math.max(1, Math.ceil(data.total / 30))}`;
  byId('history-prev').disabled = state.historyOffset === 0;
  byId('history-next').disabled = state.historyOffset + 30 >= data.total;
}

function updateHistorySelection() { const selected = document.querySelectorAll('.history-select:checked'); byId('clear-selected-history').disabled = !selected.length; }
byId('select-all-history').addEventListener('click', () => { const items = [...document.querySelectorAll('.history-select')]; const select = items.some((item) => !item.checked); items.forEach((item) => { item.checked = select; }); updateHistorySelection(); byId('select-all-history').textContent = select ? '取消全选' : '全选'; });
byId('clear-selected-history').addEventListener('click', async () => { const ids = [...document.querySelectorAll('.history-select:checked')].map((item) => item.dataset.jobId); if (!ids.length || !window.confirm('确定清理所选历史记录及其结果吗？')) return; try { for (const id of ids) await api(`/api/jobs/${id}`, {method:'DELETE'}); notify('历史记录已清理'); await loadHistory(); } catch (error) { notify(error.message); } });

document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => switchView(button.dataset.view)));
byId('show-history').addEventListener('click', () => switchView('history'));
byId('new-search').addEventListener('click', () => { switchView('workspace'); byId('query').focus(); });
document.querySelectorAll('[data-tab]').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('[data-tab]').forEach((item) => { item.classList.toggle('active', item === button); item.setAttribute('aria-selected', String(item === button)); });
    document.querySelectorAll('.tab-panel').forEach((panel) => { panel.hidden = panel.id !== `tab-${button.dataset.tab}`; });
  });
});
byId('search-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  byId('start-button').disabled = true;
  try {
    const options = readOptions(); const query = byId('query').value;
    const job = await api('/api/jobs', {method: 'POST', body: JSON.stringify({query, ...options})});
    await selectJob(job.id);
    notify('任务已创建。你可以留在这里查看进度，也可以稍后从历史中打开。');
  } catch (error) { notify(error.message); }
  finally { await bootstrap().catch((error) => notify(error.message)); }
});
byId('prompt-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!state.job?.prompt) return;
  try {
    await api(`/api/jobs/${state.job.id}/respond`, {method: 'POST', body: JSON.stringify({prompt_id: state.job.prompt.id, value: byId('prompt-value').value})});
    byId('prompt-value').value = '';
    await refreshJob();
  } catch (error) { notify(error.message); }
});
byId('start-review').addEventListener('click', async () => {
  if (!state.job?.prompt) return;
  try { await api(`/api/jobs/${state.job.id}/respond`, {method:'POST', body: JSON.stringify({prompt_id: state.job.prompt.id, value: 'start_review'})}); await refreshJob(); } catch (error) { notify(error.message); }
});
for (const [id, output, format] of [['jcr-range','jcr-range-value',(v) => v > 0 ? `Q${v}及以上` : '不限'],['cas-range','cas-range-value',(v) => v > 0 ? `${v}区及以上` : '不限'],['new-rui-2026','new-rui-2026-value',(v) => v > 0 ? `${v}区及以上` : '不限']]) {
  const input = byId(id);
  const update = () => byId(output).value = format(Number(input.value));
  input.addEventListener('input', update);
  update();
}
byId('adjust-search').addEventListener('click', async () => {
  if (!state.job?.prompt) return;
  try {
    const job = state.job;
    await api(`/api/jobs/${job.id}/respond`, {method:'POST', body:JSON.stringify({prompt_id:job.prompt.id,value:'adjust_search'})});
    byId('query').value = job.query;
    fillOptions(job.options);
    await refreshJob();
    byId('search-form').scrollIntoView({behavior:'smooth'});
    byId('query').focus();
    notify('请修改条件，待当前任务结束后点击开始检索。已有结果会保留。');
  } catch (error) { notify(error.message); }
});
byId('cancel-button').addEventListener('click', async () => {
  if (!state.job || !window.confirm('取消当前任务？已产生的文献与成果会保留；正在进行的远程请求可能已计费。')) return;
  try { await api(`/api/jobs/${state.job.id}/cancel`, {method: 'POST', body: '{}'}); await refreshJob(); }
  catch (error) { notify(error.message); }
});
byId('rerun-button').addEventListener('click', () => {
  if (!state.job) return;
  byId('query').value = state.job.query;
  fillOptions(state.job.options);
  byId('query').focus();
  byId('search-form').scrollIntoView({behavior: 'smooth', block: 'center'});
  notify('条件已填入。点击“开始检索”会创建新任务，不会覆盖原记录。');
});
byId('setting-provider').addEventListener('change', () => applyProviderProfile(byId('setting-provider').value, {preserveBase: false}));
byId('save-preferences').addEventListener('click', async () => {
  try { const options = readOptions(); await api('/api/preferences', {method: 'PUT', body: JSON.stringify(options)}); await api('/api/configuration', {method: 'PUT', body: JSON.stringify({service: options.ai_provider, api_type: options.ai_protocol, base_url: byId('setting-base-url').value, api_key: byId('setting-api-key').value, model: options.model, pubmed_api_key: byId('setting-pubmed-key').value})}); notify('默认运行选项和配置已保存。'); }
  catch (error) { notify(error.message); }
});
byId('fetch-models').addEventListener('click', async () => {
  byId('model-status').textContent = '获取中…';
  try { const data = await api('/api/models', {method: 'POST', body: '{}'}); byId('model-list').replaceChildren(...data.models.map((id) => { const option = document.createElement('option'); option.value = id; return option; })); if (!byId('setting-model').value.trim() && data.models.length) { const preferred = providerProfile(byId('setting-provider').value)?.default_model; byId('setting-model').value = data.models.includes(preferred) ? preferred : data.models[0]; } byId('model-status').textContent = `已获取 ${data.models.length} 个模型${data.models.length ? '，已自动选择可用模型' : ''}`; }
  catch (error) { byId('model-status').textContent = error.message; }
});
byId('refresh-system-status').addEventListener('click', () => loadSystemStatus().catch((error) => notify(error.message)));
byId('save-prompts').addEventListener('click', async () => { try { await api('/api/prompts', {method:'PUT', body: JSON.stringify({modules:{intent_analysis: byId('prompt-intent').value, outline_generation: byId('prompt-outline').value, review_generation: byId('prompt-review').value}})}); byId('prompt-status').textContent='已保存'; } catch (error) { byId('prompt-status').textContent=error.message; } });
byId('article-search').addEventListener('input', debounce(() => { state.articleOffset = 0; loadArticles().catch((error) => notify(error.message)); }));
for (const id of ['history-search', 'history-status']) byId(id).addEventListener(id === 'history-search' ? 'input' : 'change', debounce(() => { state.historyOffset = 0; loadHistory().catch((error) => notify(error.message)); }));
for (const [id, offset] of [['articles-prev', -50], ['articles-next', 50]]) byId(id).addEventListener('click', () => { state.articleOffset = Math.max(0, state.articleOffset + offset); loadArticles().catch((error) => notify(error.message)); });
for (const [id, offset] of [['history-prev', -30], ['history-next', 30]]) byId(id).addEventListener('click', () => { state.historyOffset = Math.max(0, state.historyOffset + offset); loadHistory().catch((error) => notify(error.message)); });
byId('close-article').addEventListener('click', () => byId('article-dialog').close());

async function poll() {
  try {
    if (!document.hidden) {
      if (state.job) await refreshJob();
      await bootstrap();
    }
  } catch (error) { notify(`连接暂时中断：${error.message}。将自动重试。`); }
  finally { setTimeout(poll, state.job && !terminal.has(state.job.status) ? 1200 : 5000); }
}

switchView('system'); bootstrap(true).catch((error) => notify(error.message)).finally(() => { setTimeout(poll, 1200); });


