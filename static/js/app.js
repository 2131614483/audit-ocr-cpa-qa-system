/* ============================================================
   app.js — 统一前端共享工具
   依赖: 无 (marked 可选，页面按需加载)
   ============================================================ */
'use strict';

/* ---------- fetch 封装 ---------- */
async function api(path, opts = {}) {
  const { method = 'GET', body, query, toastError = true } = opts;
  let url = path;
  if (query) {
    const qs = new URLSearchParams(query).toString();
    url += (url.includes('?') ? '&' : '?') + qs;
  }
  const init = { method, headers: {} };
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, init);
  } catch (e) {
    if (toastError) showToast('网络请求失败: ' + e.message, 'error');
    throw e;
  }
  let data = null;
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) data = await res.json();
  if (!res.ok) {
    const msg = (data && (data.error || data.message)) || ('HTTP ' + res.status);
    if (toastError) showToast(msg, 'error');
    throw Object.assign(new Error(msg), { status: res.status, data });
  }
  return data;
}

/* ---------- Toast ---------- */
function showToast(msg, type = 'info', duration = 2600) {
  let wrap = document.querySelector('.toast-wrap');
  if (!wrap) {
    wrap = document.createElement('div');
    wrap.className = 'toast-wrap';
    document.body.appendChild(wrap);
  }
  const t = document.createElement('div');
  t.className = 'toast ' + (type || 'info');
  t.textContent = msg;
  wrap.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(() => t.remove(), 320); }, duration);
}

/* ---------- 模态框 ---------- */
function openModal({ title = '', body = '', foot = '', size = '', onOpen } = {}) {
  closeModal();
  const mask = document.createElement('div');
  mask.className = 'modal-mask';
  mask.innerHTML = `<div class="modal-box ${size}">
    <div class="modal-head"><span>${escapeHtml(title)}</span>
      <button class="modal-close" onclick="closeModal()">&times;</button></div>
    <div class="modal-body">${body}</div>
    ${foot ? `<div class="modal-foot">${foot}</div>` : ''}
  </div>`;
  mask.addEventListener('click', (e) => { if (e.target === mask) closeModal(); });
  document.body.appendChild(mask);
  if (onOpen) onOpen(mask);
  return mask;
}
function closeModal() {
  document.querySelectorAll('.modal-mask').forEach((m) => m.remove());
}
function modalFoot(html) {
  const box = document.querySelector('.modal-box');
  if (!box) return;
  let f = box.querySelector('.modal-foot');
  if (!f) { f = document.createElement('div'); f.className = 'modal-foot'; box.appendChild(f); }
  f.innerHTML = html;
}
function modalBody(html) {
  const b = document.querySelector('.modal-box .modal-body');
  if (b) b.innerHTML = html;
}

/* ---------- 分页 ---------- */
function renderPagination(el, { page, totalPages, total, pageSize, onPage }) {
  if (!el) return;
  if (!totalPages || totalPages <= 1) { el.innerHTML = ''; return; }
  const pages = [];
  const start = Math.max(1, page - 2), end = Math.min(totalPages, page + 2);
  if (start > 1) pages.push(1);
  if (start > 2) pages.push('...');
  for (let i = start; i <= end; i++) pages.push(i);
  if (end < totalPages - 1) pages.push('...');
  if (end < totalPages) pages.push(totalPages);
  const btns = pages.map((p) => p === '...'
    ? '<span class="page-btn" style="border:none;background:none;cursor:default">…</span>'
    : `<button class="page-btn ${p === page ? 'active' : ''}" data-p="${p}">${p}</button>`).join('');
  el.innerHTML = `<div class="pagination">${btns}
    <span class="page-info">共 ${total} 条 / ${totalPages} 页</span></div>`;
  el.querySelectorAll('.page-btn[data-p]').forEach((b) => {
    b.addEventListener('click', () => onPage && onPage(parseInt(b.dataset.p, 10)));
  });
}

/* ---------- 工具函数 ---------- */
function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}
function fmtTime(s) {
  if (!s) return '';
  const d = new Date(s);
  if (isNaN(d)) return String(s);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function debounce(fn, wait = 300) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); };
}
function empty(el) { if (el) el.innerHTML = ''; }
function isStr(x) { return typeof x === 'string'; }
/* Markdown 渲染：若有 marked 则用，否则转义后保留换行 */
function mdRender(text) {
  if (typeof marked !== 'undefined') return marked.parse(text || '');
  return escapeHtml(text).replace(/\n/g, '<br>');
}
function riskBadge(level) {
  const map = { '高风险': 'high', '中风险': 'mid', '低风险': 'low' };
  const cls = map[level] || 'gray';
  return `<span class="badge badge-${cls}">${escapeHtml(level || '未知')}</span>`;
}

/* 侧边栏移动端切换 */
function toggleSidebar() {
  document.querySelector('.sidebar').classList.toggle('open');
  document.querySelector('.sidebar-mask').classList.toggle('open');
}
