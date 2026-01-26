/* global */

const state = {
  backend: null,
  products: [],
  categories: ['Todas'],
  currentKey: null,
  ui: {
    tablet: false,
    lite: false,
    gridLimit: 0,
    gridLimitMax: 0,
  },
}

let _invGridRenderSeq = 0

const _moneyFmt = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const THEME_KEY = 'inventarios_theme'

function fmtMoney(value) {
  const n = Number(value || 0)
  return _moneyFmt.format(n)
}

function detectTabletMode() {
  try {
    const coarse = window.matchMedia && window.matchMedia('(pointer: coarse)').matches
    const small = window.matchMedia && window.matchMedia('(max-width: 900px)').matches
    return Boolean(coarse || small)
  } catch (e) {
    return false
  }
}

function detectLiteMode() {
  try {
    const u = new URL(window.location.href)
    const raw = u.searchParams.get('lite')
    if (raw == null) return null
    const v = String(raw).trim().toLowerCase()
    if (v === '0' || v === 'false') return false
    return v === '1' || v === 'true'
  } catch (e) {
    return null
  }
}

function isHttpBrowser() {
  const p = String(window.location?.protocol || '')
  return p === 'http:' || p === 'https:'
}

function initUiModes() {
  state.ui.tablet = detectTabletMode()

  const liteParam = detectLiteMode()
  // Auto-lite for tablets in browser mode unless explicitly disabled (?lite=0)
  state.ui.lite = (liteParam === null) ? Boolean(state.ui.tablet && isHttpBrowser()) : Boolean(liteParam)
  if (state.ui.lite) {
    try { document.documentElement.dataset.lite = '1' } catch (e) { /* ignore */ }
  }

  // Avoid huge DOM on low-end tablets.
  state.ui.gridLimit = state.ui.tablet ? (state.ui.lite ? 24 : 60) : 999999
  state.ui.gridLimitMax = state.ui.tablet ? (state.ui.lite ? 96 : 999999) : 999999
}

function toast(msg) {
  const el = document.getElementById('toast')
  if (!el) return
  el.textContent = msg
  el.hidden = false
  clearTimeout(el._t)
  el._t = setTimeout(() => { el.hidden = true }, 2400)
}

function getSavedTheme() {
  try { return localStorage.getItem(THEME_KEY) || 'system' } catch (e) { return 'system' }
}

function updateThemeButton(theme) {
  const btn = document.getElementById('btnTheme')
  if (!btn) return
  const t = theme || 'system'
  btn.textContent = (t === 'system') ? 'Tema' : (t === 'dark' ? 'Tema: Oscuro' : 'Tema: Claro')
}

function applyTheme(theme) {
  const root = document.documentElement
  if (theme === 'dark' || theme === 'light') {
    root.dataset.theme = theme
  } else {
    delete root.dataset.theme
    theme = 'system'
  }
  try { localStorage.setItem(THEME_KEY, theme) } catch (e) { /* ignore */ }
  updateThemeButton(theme)
}

function cycleTheme() {
  const cur = getSavedTheme()
  const next = cur === 'system' ? 'dark' : (cur === 'dark' ? 'light' : 'system')
  applyTheme(next)
}

// Apply lite-mode and theme as early as possible (does not require backend)
initUiModes()
applyTheme(getSavedTheme())

function createHttpBackend(baseUrl) {
  const base = String(baseUrl || '')
  async function httpJson(method, path, body) {
    const url = base + path
    const opt = { method, headers: {} }
    if (body !== undefined && body !== null) {
      opt.headers['Content-Type'] = 'application/json'
      opt.body = JSON.stringify(body)
    }
    const res = await fetch(url, opt)
    const txt = await res.text()
    let data
    try { data = txt ? JSON.parse(txt) : null } catch (e) { data = null }
    if (!res.ok) {
      const msg = (data && data.error) ? data.error : (`HTTP ${res.status}`)
      throw new Error(msg)
    }
    return data
  }

  return {
    getAppInfo: () => httpJson('GET', '/api/getAppInfo'),
    searchProducts: (q, limit) => httpJson('POST', '/api/searchProducts', { q, limit }),
    getCategories: () => httpJson('GET', '/api/getCategories'),
    restockProduct: (key, delta, notes) => httpJson('POST', '/api/restockProduct', { key, delta, notes }),
    setProductStock: (key, stock, notes) => httpJson('POST', '/api/setProductStock', { key, stock, notes }),
  }
}

function selectedCategory() {
  const sel = document.getElementById('invCategory')
  return (sel && sel.value) ? String(sel.value) : 'Todas'
}

function filteredProducts() {
  const cat = selectedCategory()
  if (!cat || cat === 'Todas') return state.products
  return state.products.filter((p) => String(p.category || '') === cat)
}

function renderGrid() {
  const grid = document.getElementById('invGrid')
  if (!grid) return
  const seq = (_invGridRenderSeq += 1)
  grid.innerHTML = ''

  const all = filteredProducts()
  const tablet = Boolean(state.ui.tablet)
  const lite = Boolean(state.ui.lite)
  const limitRaw = Math.max(0, Number(state.ui.gridLimit || 0))
  const maxRaw = Math.max(0, Number(state.ui.gridLimitMax || 0))
  const maxLimit = (tablet && maxRaw > 0) ? maxRaw : 999999
  const limit = Math.min(limitRaw || maxLimit, maxLimit)
  const items = tablet ? all.slice(0, Math.min(all.length, limit)) : all
  const chunkSize = tablet ? 24 : 80
  let i = 0

  const renderChunk = () => {
    if (_invGridRenderSeq !== seq) return
    const frag = document.createDocumentFragment()
    const end = Math.min(items.length, i + chunkSize)

    for (; i < end; i += 1) {
      const p = items[i]
      const el = document.createElement('div')
      el.className = 'cardP'
      el.dataset.key = String(p.key ?? '').trim()

      const stock = Number(p.unidades || 0)
      const stockClass = stock <= 0 ? 'stockBad' : (stock <= 2 ? 'stockLow' : 'stockOk')

      // Same store technique: reduce DOM on tablets.
      if (tablet) {
        el.innerHTML = `
          <div class="cardTop">
            <div class="thumb">📦</div>
            <div style="flex:1">
              <div class="pName">${escapeHtml(p.producto || '')}</div>
            </div>
          </div>
          <div class="pMeta">
            <div>Stock: <span class="stock ${stockClass}">${escapeHtml(String(p.unidades ?? 0))}</span></div>
            <div class="pPrice">$${fmtMoney(p.precio_final || 0)}</div>
          </div>
        `
      } else {
        el.innerHTML = `
          <div class="cardTop">
            <div class="thumb">📦</div>
            <div style="flex:1">
              <div class="pName">${escapeHtml(p.producto || '')}</div>
              <div class="pDesc">${escapeHtml(p.descripcion || '')}</div>
            </div>
          </div>
          <div class="pMeta">
            <div>Stock: <span class="stock ${stockClass}">${escapeHtml(String(p.unidades ?? 0))}</span></div>
            <div class="pPrice">$${fmtMoney(p.precio_final || 0)}</div>
          </div>
          <div class="rowBtns">
            <button class="btn" data-open="${escapeHtmlAttr(String(p.key ?? ''))}">Abrir</button>
          </div>
        `
      }

      frag.appendChild(el)
    }

    grid.appendChild(frag)
    if (i < items.length) {
      // Yield to keep scrolling/taps responsive on low-end devices.
      setTimeout(renderChunk, 0)
    }
  }

  renderChunk()

  // Same store technique: tablet pagination / load-more.
  if (tablet && all.length > items.length) {
    const more = document.createElement('div')
    more.style.gridColumn = '1 / -1'
    more.style.display = 'flex'
    more.style.justifyContent = 'center'
    more.style.padding = '8px 0 14px'

    const atMax = items.length >= maxLimit
    if (atMax) {
      more.innerHTML = `<div class="hint" style="text-align:center">Mostrando ${items.length} de ${all.length}. Para ver otros productos, escribe más letras en la búsqueda.</div>`
      grid.appendChild(more)
      return
    }

    more.innerHTML = `<button class="btn ${lite ? '' : 'ghost'}" id="btnLoadMoreInv">Cargar más (${items.length}/${all.length})</button>`
    grid.appendChild(more)
    const btn = document.getElementById('btnLoadMoreInv')
    if (btn) {
      btn.addEventListener('click', () => {
        const step = lite ? 24 : 60
        const next = Number(state.ui.gridLimit || 0) + step
        state.ui.gridLimit = Math.min(next, maxLimit)
        renderGrid()
      }, { once: true })
    }
  }
}

function escapeHtml(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function escapeHtmlAttr(s) {
  return escapeHtml(s).replace(/'/g, '&#39;')
}

async function loadCategories() {
  const cats = await state.backend.getCategories()
  state.categories = Array.isArray(cats) && cats.length ? cats : ['Todas']

  const sel = document.getElementById('invCategory')
  if (!sel) return
  const prev = sel.value || 'Todas'
  sel.innerHTML = ''
  for (const c of state.categories) {
    const opt = document.createElement('option')
    opt.value = c
    opt.textContent = c
    sel.appendChild(opt)
  }
  sel.value = state.categories.includes(prev) ? prev : 'Todas'
}

async function searchProducts() {
  const q = String(document.getElementById('invSearch')?.value || '').trim()
  // Same store technique: reduce payload + rendering pressure on tablets.
  const limit = state.ui.tablet ? (state.ui.lite ? 70 : 90) : 180
  const rows = await state.backend.searchProducts(q, limit)
  state.products = Array.isArray(rows) ? rows : []

  // Same store technique: reset pagination on new results.
  if (state.ui.tablet) {
    const start = state.ui.lite ? 24 : 60
    state.ui.gridLimit = start
    state.ui.gridLimitMax = state.ui.lite ? 96 : 999999
  } else {
    state.ui.gridLimit = 999999
    state.ui.gridLimitMax = 999999
  }

  renderGrid()
}

function openModal(key) {
  const k = String(key || '').trim()
  if (!k) return
  const p = state.products.find((x) => String(x.key ?? '').trim() === k)
  if (!p) return

  state.currentKey = k

  document.getElementById('imError').hidden = true
  document.getElementById('imTitle').textContent = p.producto || 'Producto'
  document.getElementById('imDesc').textContent = p.descripcion || ''

  const stock = Number(p.unidades || 0)
  const stockClass = stock <= 0 ? 'stockBad' : (stock <= 2 ? 'stockLow' : 'stockOk')
  const stockEl = document.getElementById('imStock')
  stockEl.textContent = String(stock)
  stockEl.className = `stock ${stockClass}`

  document.getElementById('imPrice').textContent = `$${fmtMoney(p.precio_final || 0)}`
  document.getElementById('imRestockQty').value = '1'
  document.getElementById('imSetStock').value = String(stock)
  document.getElementById('imHint').textContent = 'Usa Rellenar para sumar. Ajustar stock para corregir.'

  document.getElementById('invModal').hidden = false
  setTimeout(() => {
    document.getElementById('imRestockQty').focus()
    document.getElementById('imRestockQty').select()
  }, 0)
}

function closeModal() {
  document.getElementById('invModal').hidden = true
  state.currentKey = null
}

async function doRestock() {
  const key = state.currentKey
  if (!key) return
  const qty = Math.max(1, Number(document.getElementById('imRestockQty').value || 0))
  const notes = prompt('Notas (opcional):', 'relleno')

  const res = await state.backend.restockProduct(key, qty, notes || '')
  if (!res || !res.ok) {
    const err = document.getElementById('imError')
    err.hidden = false
    err.textContent = res?.error || 'No se pudo rellenar'
    return
  }

  const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
  if (p) p.unidades = Number(res.unidades || p.unidades || 0)
  openModal(key)
  renderGrid()
  toast('Stock actualizado')
}

async function doSetStock() {
  const key = state.currentKey
  if (!key) return
  const stock = Math.max(0, Number(document.getElementById('imSetStock').value || 0))
  const notes = prompt('Notas (opcional):', 'ajuste')

  const res = await state.backend.setProductStock(key, stock, notes || '')
  if (!res || !res.ok) {
    const err = document.getElementById('imError')
    err.hidden = false
    err.textContent = res?.error || 'No se pudo guardar stock'
    return
  }

  const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
  if (p) p.unidades = Number(res.unidades || p.unidades || 0)
  openModal(key)
  renderGrid()
  toast('Stock actualizado')
}

async function init() {
  // Backend selection: pywebview (desktop) or HTTP (tablet)
  if (window.pywebview && window.pywebview.api) {
    state.backend = window.pywebview.api
  } else {
    state.backend = createHttpBackend('')
  }

  const info = await state.backend.getAppInfo()
  const appName = document.getElementById('appName')
  if (appName) appName.textContent = info.app_name || 'Inventarios POS'

  await loadCategories()
  await searchProducts()

  const btnTheme = document.getElementById('btnTheme')
  if (btnTheme) {
    updateThemeButton(getSavedTheme())
    btnTheme.addEventListener('click', () => cycleTheme())
  }

  const sel = document.getElementById('invCategory')
  if (sel) sel.addEventListener('change', () => renderGrid())

  const search = document.getElementById('invSearch')
  if (search) {
    const debounce = (fn, ms) => {
      let t
      return () => { clearTimeout(t); t = setTimeout(fn, ms) }
    }
    search.addEventListener('input', debounce(() => searchProducts(), 200))
    search.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); searchProducts() }
    })
  }

  const refresh = document.getElementById('btnRefreshInv')
  if (refresh) refresh.addEventListener('click', async () => { await loadCategories(); await searchProducts() })

  const grid = document.getElementById('invGrid')
  if (grid) grid.addEventListener('click', (e) => {
    const btn = e.target?.closest?.('button[data-open]')
    if (btn) { e.stopPropagation(); openModal(btn.getAttribute('data-open')); return }
    const card = e.target?.closest?.('.cardP')
    if (card && card.dataset.key) openModal(card.dataset.key)
  })

  document.getElementById('imClose').addEventListener('click', closeModal)
  document.getElementById('imRestockBtn').addEventListener('click', doRestock)
  document.getElementById('imSetStockBtn').addEventListener('click', doSetStock)
}

window.addEventListener('DOMContentLoaded', () => {
  init().catch((e) => {
    // eslint-disable-next-line no-console
    console.error(e)
    toast(String(e?.message || e || 'Error'))
  })
})
