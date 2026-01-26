/* global */

const state = {
  backend: null,
  products: [],
  cart: new Map(), // key -> { key, producto, precio_final, qty }
  activeTab: 'store',
  lastSearchQuery: '',
  categories: ['Todas'],
  currentProductKey: null,
  ui: {
    tablet: false,
    lite: false,
    gridLimit: 0,
    gridLimitMax: 0,
  },
}

let _storeGridRenderSeq = 0

function detectTabletMode() {
  try {
    const coarse = window.matchMedia && window.matchMedia('(pointer: coarse)').matches
    const small = window.matchMedia && window.matchMedia('(max-width: 900px)').matches
    return Boolean(coarse || small)
  } catch (e) {
    return false
  }
}

function isTabletMode() {
  return Boolean(state.ui && state.ui.tablet)
}

function isTouchStorePage() {
  return isTabletMode() && (document.body?.dataset?.page || '') === 'store'
}

function setSheetOpen(open) {
  try {
    if (open) document.documentElement.dataset.sheet = 'open'
    else delete document.documentElement.dataset.sheet
  } catch (e) {
    // ignore
  }
}

function isSheetOpen() {
  return String(document.documentElement?.dataset?.sheet || '') === 'open'
}

async function refreshTicketToday() {
  if (!state.backend || !isTouchStorePage()) return
  const el = document.getElementById('ticketToday')
  if (!el) return
  try {
    const res = await state.backend.getCashPanel(todayIso())
    if (!res || !res.ok) return
    const gross = Number(res.gross_total || 0)
    el.hidden = false
    el.textContent = `Hoy: $${fmtMoney(gross)}`
  } catch (e) {
    // ignore
  }
}

function setupTouchTicketSheet() {
  if (!isTouchStorePage()) return
  const cashier = document.getElementById('cashier')
  const card = cashier?.querySelector?.('.sidebarCard')
  const header = card?.querySelector?.('.cartHeader')
  if (!cashier || !card || !header) return

  const getSheetHeights = () => {
    const cs = getComputedStyle(document.documentElement)
    const rawCollapsed = (cs.getPropertyValue('--sheetCollapsed') || '170px').trim()
    const rawExpanded = (cs.getPropertyValue('--sheetExpanded') || '72vh').trim()

    const parsePx = (v) => {
      const n = Number(String(v).replace('px', '').trim())
      return Number.isFinite(n) ? n : 0
    }
    const parseVh = (v) => {
      const n = Number(String(v).replace('vh', '').trim())
      return Number.isFinite(n) ? (window.innerHeight * n / 100) : 0
    }

    const collapsedPx = rawCollapsed.endsWith('vh') ? parseVh(rawCollapsed) : parsePx(rawCollapsed)
    const expandedPx = rawExpanded.endsWith('vh') ? parseVh(rawExpanded) : parsePx(rawExpanded)
    return {
      collapsedPx: Math.max(120, collapsedPx || 170),
      expandedPx: Math.max(260, expandedPx || Math.round(window.innerHeight * 0.72)),
    }
  }

  const SHEET_H_KEY = 'inventarios_sheet_h'
  const readSavedHeight = () => {
    try {
      const raw = String(localStorage.getItem(SHEET_H_KEY) || '').trim()
      if (!raw) return null
      const n = Number(raw)
      return Number.isFinite(n) ? n : null
    } catch (e) {
      return null
    }
  }
  const saveHeight = (px) => {
    try { localStorage.setItem(SHEET_H_KEY, String(Math.round(px))) } catch (e) { /* ignore */ }
  }
  const clearSavedHeight = () => {
    try { localStorage.removeItem(SHEET_H_KEY) } catch (e) { /* ignore */ }
  }

  const applyCollapsed = () => {
    card.style.height = ''
    setSheetOpen(false)
    updateSheetBtnIcon()
  }
  const applyOpen = () => {
    setSheetOpen(true)
    // If there is a saved custom height, keep it via inline height.
    const { collapsedPx, expandedPx } = getSheetHeights()
    const saved = readSavedHeight()
    if (saved != null) {
      const clamped = Math.min(expandedPx, Math.max(collapsedPx, saved))
      card.style.height = `${Math.round(clamped)}px`
    } else {
      card.style.height = ''
    }
    updateSheetBtnIcon()
  }

  const btnSheet = header.querySelector('#btnSheet')
  const updateSheetBtnIcon = () => {
    if (!btnSheet) return
    // Collapsed shows "up" to indicate expand; open shows "down" to indicate collapse.
    btnSheet.textContent = isSheetOpen() ? '▾' : '▴'
  }

  // Insert handle once
  if (!card.querySelector('.sheetHandle')) {
    const h = document.createElement('div')
    h.className = 'sheetHandle'
    card.insertBefore(h, header)
  }

  // Insert KPI once
  if (!header.querySelector('#ticketToday')) {
    const kpi = document.createElement('div')
    kpi.id = 'ticketToday'
    kpi.className = 'sub'
    kpi.hidden = true
    // Put it under the title area (left column)
    const title = header.querySelector('.cartTitle')
    if (title && title.parentElement) title.parentElement.appendChild(kpi)
    else header.appendChild(kpi)
  }

  // Ensure icon is correct at startup
  updateSheetBtnIcon()

  // Default collapsed
  applyCollapsed()

  // Restore last chosen height if present (open by default)
  {
    const { collapsedPx, expandedPx } = getSheetHeights()
    const saved = readSavedHeight()
    if (saved != null) {
      const clamped = Math.min(expandedPx, Math.max(collapsedPx, saved))
      setSheetOpen(true)
      card.style.height = `${Math.round(clamped)}px`
      updateSheetBtnIcon()
    }
  }

  let _ignoreHeaderClickUntil = 0

  // Toggle on tapping header (but not when tapping buttons inside it)
  header.addEventListener('click', (e) => {
    if (Date.now() < _ignoreHeaderClickUntil) return
    const btn = e.target?.closest?.('button')
    if (btn) return
    if (isSheetOpen()) applyCollapsed()
    else applyOpen()
  })

  // Explicit expand/collapse button (max height <-> collapsed)
  if (btnSheet && !btnSheet._wired) {
    btnSheet._wired = true
    btnSheet.addEventListener('click', (e) => {
      e.preventDefault()
      e.stopPropagation()
      if (isSheetOpen()) {
        clearSavedHeight()
        card.style.height = ''
        setSheetOpen(false)
        updateSheetBtnIcon()
        return
      }
      // Expand to nearly full screen
      const fullH = Math.max(400, window.innerHeight - 60)
      setSheetOpen(true)
      card.style.height = `${Math.round(fullH)}px`
      saveHeight(fullH)
      updateSheetBtnIcon()
    })
  }

  // Drag to open/close (prefer drag over tap on tablets)
  const handle = card.querySelector('.sheetHandle')
  let dragging = false
  let startY = 0
  let startH = 0
  let lastH = 0
  let moved = 0
  let startT = 0
  const cartItems = card.querySelector('.cartItems')
  let prevItemsOverflow = ''
  let rafId = 0
  let pendingHeight = null

  const setDraggingFlag = (on) => {
    try {
      if (on) document.documentElement.dataset.sheetdrag = '1'
      else delete document.documentElement.dataset.sheetdrag
    } catch (e) {
      // ignore
    }
  }

  const flushHeight = () => {
    rafId = 0
    if (pendingHeight == null) return
    card.style.height = `${pendingHeight}px`
    pendingHeight = null
  }

  const beginDrag = (clientY, sourceEl, preventDefaultFn) => {
    const btn = sourceEl?.closest?.('button')
    if (btn) return
    const { collapsedPx, expandedPx } = getSheetHeights()
    dragging = true
    moved = 0
    startT = performance.now()
    startY = clientY
    setDraggingFlag(true)
    // Prefer current inline height; fallback to open/collapsed defaults.
    const currentInline = Number(String(card.style.height || '').replace('px', '').trim())
    const hasInline = Number.isFinite(currentInline) && currentInline > 0
    startH = hasInline ? currentInline : (isSheetOpen() ? expandedPx : collapsedPx)
    lastH = startH
    card.classList.add('dragging')
    if (cartItems) {
      prevItemsOverflow = cartItems.style.overflow || ''
      cartItems.style.overflow = 'hidden'
    }
    pendingHeight = Math.round(startH)
    if (!rafId) rafId = requestAnimationFrame(flushHeight)
    if (preventDefaultFn) preventDefaultFn()
  }

  const moveDrag = (clientY, preventDefaultFn) => {
    if (!dragging) return
    const { collapsedPx, expandedPx } = getSheetHeights()
    const dy = startY - clientY
    moved = Math.max(moved, Math.abs(dy))
    const next = Math.min(expandedPx, Math.max(collapsedPx, startH + dy))
    lastH = next
    pendingHeight = Math.round(next)
    if (!rafId) rafId = requestAnimationFrame(flushHeight)
    if (preventDefaultFn) preventDefaultFn()
  }

  const endDrag = (preventDefaultFn) => {
    if (!dragging) return
    dragging = false
    card.classList.remove('dragging')
    setDraggingFlag(false)
    if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = 0
    }
    flushHeight()
    if (cartItems) cartItems.style.overflow = prevItemsOverflow

    // If there was basically no movement, keep click behavior.
    if (moved < 10) return

    const { collapsedPx, expandedPx } = getSheetHeights()
    const mid = (collapsedPx + expandedPx) / 2
    const dt = Math.max(1, performance.now() - startT)
    const dy = lastH - startH
    const v = dy / dt // px/ms

    // Natural snap: if user flicks up/down, respect it.
    const open = (v > 0.35) ? true : (v < -0.35) ? false : (lastH >= mid)

    // If user drags near the minimum, collapse and clear the custom height.
    const nearMin = lastH <= (collapsedPx + 18)
    if (!open || nearMin) {
      clearSavedHeight()
      applyCollapsed()
    } else {
      setSheetOpen(true)
      const finalH = Math.min(expandedPx, Math.max(collapsedPx, lastH))
      card.style.height = `${Math.round(finalH)}px`
      saveHeight(finalH)
    }

    // Prevent the synthetic click that some WebViews fire after drag.
    _ignoreHeaderClickUntil = Date.now() + 450
    if (preventDefaultFn) preventDefaultFn()
  }

  const onDown = (ev) => {
    if (ev.pointerType === 'mouse') return
    try { ev.currentTarget?.setPointerCapture?.(ev.pointerId) } catch (e) { /* ignore */ }
    beginDrag(ev.clientY, ev.target, () => ev.preventDefault())
  }

  const onMove = (ev) => {
    moveDrag(ev.clientY, () => ev.preventDefault())
  }

  const onUp = (ev) => {
    endDrag(() => ev.preventDefault())
  }

  ;[handle, header].filter(Boolean).forEach((el) => {
    el.addEventListener('pointerdown', onDown, { passive: false })
    el.addEventListener('pointermove', onMove, { passive: false })
    el.addEventListener('pointerup', onUp, { passive: false })
    el.addEventListener('pointercancel', onUp, { passive: false })
  })

  // Touch fallback for older Android WebViews that don't deliver pointer events reliably.
  ;[handle, header].filter(Boolean).forEach((el) => {
    el.addEventListener('touchstart', (e) => {
      if (!e.touches || e.touches.length !== 1) return
      const t = e.touches[0]
      if (!t) return
      beginDrag(t.clientY, e.target, () => e.preventDefault())
    }, { passive: false })
    el.addEventListener('touchmove', (e) => {
      if (!e.touches || e.touches.length !== 1) return
      const t = e.touches[0]
      if (!t) return
      moveDrag(t.clientY, () => e.preventDefault())
    }, { passive: false })
    el.addEventListener('touchend', (e) => {
      endDrag(() => e.preventDefault())
    }, { passive: false })
    el.addEventListener('touchcancel', (e) => {
      endDrag(() => e.preventDefault())
    }, { passive: false })
  })

  refreshTicketToday().catch(() => { /* ignore */ })
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

const THEME_KEY = 'inventarios_theme'

// Cache formatter (Intl is expensive if recreated per call)
const _moneyFmt = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function getSavedTheme() {
  try {
    const v = String(localStorage.getItem(THEME_KEY) || '').trim()
    if (v === 'dark' || v === 'light' || v === 'system') return v
  } catch (e) {
    // ignore
  }
  return 'system'
}

function updateThemeButton(theme) {
  const btn = document.getElementById('btnTheme')
  if (!btn) return
  const label = theme === 'system' ? 'System' : (theme === 'dark' ? 'Dark' : 'Light')
  btn.textContent = `Tema: ${label}`
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

// Apply theme as early as possible (does not require backend)
applyTheme(getSavedTheme())

function fmtMoney(value) {
  const n = Number(value || 0)
  return _moneyFmt.format(n)
}

function toast(msg) {
  const el = document.getElementById('toast')
  if (!el) return
  el.textContent = msg
  el.hidden = false
  clearTimeout(el._t)
  el._t = setTimeout(() => { el.hidden = true }, 2400)
}

function setTab(name) {
  state.activeTab = name
  for (const id of ['store', 'summary']) {
    const view = document.getElementById(`view${id[0].toUpperCase()}${id.slice(1)}`)
    if (view) view.hidden = id !== name
  }

  for (const btn of document.querySelectorAll('.tab')) {
    btn.classList.toggle('active', btn.dataset.tab === name)
  }

  if (name === 'summary') {
    // Let the UI paint the tab first; then fetch.
    setTimeout(() => {
      refreshSummary()
      refreshCashCloses()
    }, 0)
  }

  focusSearch()
}

function focusSearch() {
  // On touch devices, auto-focusing the search box pops the software keyboard
  // and feels janky. Let the user tap the search box explicitly.
  if (isTabletMode() && isHttpBrowser()) return
  const el = document.getElementById('storeSearch')
  if (!el) return
  el.focus()
  el.select()
}

function cartTotal() {
  let total = 0
  for (const item of state.cart.values()) {
    total += Number(item.precio_final) * Number(item.qty)
  }
  return total
}

function renderCart() {
  const list = document.getElementById('cartItems')
  if (!list) return
  const frag = document.createDocumentFragment()
  list.innerHTML = ''

  for (const item of state.cart.values()) {
    const row = document.createElement('div')
    row.className = 'cartItem'
    row.innerHTML = `
      <div>
        <div class="name">${escapeHtml(item.producto)}</div>
        <div class="sub">$${fmtMoney(item.precio_final)} c/u</div>
      </div>
      <div>
        <div class="price">$${fmtMoney(Number(item.precio_final) * Number(item.qty))}</div>
        <div class="qty">
          <button data-act="dec" data-key="${escapeHtmlAttr(item.key)}">-</button>
          <div>${item.qty}</div>
          <button data-act="inc" data-key="${escapeHtmlAttr(item.key)}">+</button>
          <button data-act="rm" data-key="${escapeHtmlAttr(item.key)}">x</button>
        </div>
      </div>
    `
    frag.appendChild(row)
  }
  list.appendChild(frag)

  const totalEl = document.getElementById('cartTotal')
  if (totalEl) totalEl.textContent = `$${fmtMoney(cartTotal())}`
  if (document.getElementById('errorBox')) hideError('errorBox')
}

function hideError(id) {
  const box = document.getElementById(id)
  box.hidden = true
  box.textContent = ''
}

function showError(id, msg) {
  const box = document.getElementById(id)
  box.hidden = false
  box.textContent = msg
}

function addToCartByKey(key, deltaQty) {
  const k = String(key ?? '').trim()
  if (!k) return

  const item = state.cart.get(k)
  if (!item) {
    const p = state.products.find((x) => String(x.key ?? '').trim() === k)
    if (!p) return
    if (deltaQty <= 0) return
    state.cart.set(k, { key: k, producto: p.producto, precio_final: p.precio_final, qty: deltaQty })
  } else {
    const next = Number(item.qty) + Number(deltaQty)
    if (next <= 0) state.cart.delete(k)
    else item.qty = next
  }
  rerenderAll()

  // Keep the workflow keyboard/scanner-first
  focusSearch()
}

function clearCart() {
  state.cart.clear()
  rerenderAll()
}

function rerenderAll() {
  renderCart()
}

function escapeHtml(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function escapeHtmlAttr(s) {
  return escapeHtml(s).replaceAll('`', '')
}

async function searchProducts(query, mode) {
  state.lastSearchQuery = query
  if (!state.backend) return

  // On low-end tablets, reduce payload + rendering pressure.
  const limit = isTabletMode() ? (state.ui.lite ? 70 : 90) : 180
  const results = await state.backend.searchProducts(query, limit)
  if (state.lastSearchQuery !== query) return
  state.products = Array.isArray(results) ? results : []

  // Reset pagination on new results
  if (state.ui.tablet) {
    const start = state.ui.lite ? 24 : 60
    state.ui.gridLimit = start
    state.ui.gridLimitMax = state.ui.lite ? 96 : 999999
  } else {
    state.ui.gridLimit = 999999
    state.ui.gridLimitMax = 999999
  }

  if (document.getElementById('storeGrid')) renderStoreGrid()
}

function selectedCategory() {
  const id = 'storeCategory'
  const el = document.getElementById(id)
  if (!el) return 'Todas'
  const v = (el?.value || 'Todas').trim()
  return v || 'Todas'
}

function filteredProducts() {
  const cat = selectedCategory()
  if (!cat || cat === 'Todas') return state.products
  return state.products.filter((p) => String(p.category || '').trim() === cat)
}

function renderStoreGrid() {
  const grid = document.getElementById('storeGrid')
  if (!grid) return

  const seq = (_storeGridRenderSeq += 1)
  grid.innerHTML = ''

  const all = filteredProducts()
  const tablet = isTabletMode()
  const lite = Boolean(state.ui.lite)
  const limitRaw = Math.max(0, Number(state.ui.gridLimit || 0))
  const maxRaw = Math.max(0, Number(state.ui.gridLimitMax || 0))
  const maxLimit = (tablet && maxRaw > 0) ? maxRaw : 999999
  const limit = Math.min(limitRaw || maxLimit, maxLimit)
  const items = tablet ? all.slice(0, Math.min(all.length, limit)) : all
  const chunkSize = tablet ? 24 : 80
  let i = 0

  const renderChunk = () => {
    if (_storeGridRenderSeq !== seq) return
    const frag = document.createDocumentFragment()
    const end = Math.min(items.length, i + chunkSize)

    for (; i < end; i += 1) {
      const p = items[i]
      const el = document.createElement('div')
      el.className = 'cardP'
      el.dataset.key = String(p.key ?? '').trim()

      const img = p.image_url ? `<img src="${escapeHtmlAttr(p.image_url)}" alt="" loading="lazy" decoding="async" />` : '📦'

      const stock = Number(p.unidades || 0)
      const stockClass = stock <= 0 ? 'stockBad' : (stock <= 2 ? 'stockLow' : 'stockOk')

      // On tablet, reduce DOM a bit (less text + fewer buttons)
      if (tablet) {
        el.innerHTML = `
          <div class="cardTop">
            <div class="thumb">${img}</div>
            <div style="flex:1">
              <div class="pName">${escapeHtml(p.producto)}</div>
            </div>
          </div>
          <div class="pMeta">
            <div>Stock: <span class="stock ${stockClass}">${escapeHtml(p.unidades)}</span></div>
            <div class="pPrice">$${fmtMoney(p.precio_final)}</div>
          </div>
          <div class="rowBtns">
            <button class="btn" data-add="${escapeHtmlAttr(p.key)}">Agregar</button>
          </div>
        `
      } else {
        el.innerHTML = `
          <div class="cardTop">
            <div class="thumb">${img}</div>
            <div style="flex:1">
              <div class="pName">${escapeHtml(p.producto)}</div>
              <div class="pDesc">${escapeHtml(p.descripcion || '')}</div>
            </div>
          </div>
          <div class="pMeta">
            <div>Stock: <span class="stock ${stockClass}">${escapeHtml(p.unidades)}</span></div>
            <div class="pPrice">$${fmtMoney(p.precio_final)}</div>
          </div>
          <div class="rowBtns">
            <button class="btn" data-add="${escapeHtmlAttr(p.key)}">Agregar</button>
            <button class="btn ghost" data-add2="${escapeHtmlAttr(p.key)}">+2</button>
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

  // Tablet pagination: never render hundreds of cards at once.
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

    more.innerHTML = `<button class="btn ${lite ? '' : 'ghost'}" id="btnLoadMore">Cargar más (${items.length}/${all.length})</button>`
    grid.appendChild(more)
    const btn = document.getElementById('btnLoadMore')
    if (btn) {
      btn.addEventListener('click', () => {
        const step = lite ? 24 : 60
        const next = Number(state.ui.gridLimit || 0) + step
        state.ui.gridLimit = Math.min(next, maxLimit)
        renderStoreGrid()
      }, { once: true })
    }
  }
}

function addFirstResult() {
  if (state.products.length === 0) return
  addToCartByKey(String(state.products[0].key ?? '').trim(), 1)

  const ss = document.getElementById('storeSearch')
  if (ss) ss.value = ''
}

function openPayModal() {
  const payModal = document.getElementById('payModal')
  if (!payModal) return

  if (document.getElementById('errorBox')) hideError('errorBox')

  if (state.cart.size === 0) {
    if (document.getElementById('errorBox')) showError('errorBox', 'Carrito vacío')
    return
  }

  const payError = document.getElementById('payError')
  const payTotal = document.getElementById('payTotal')
  const payChange = document.getElementById('payChange')
  const cashReceived = document.getElementById('cashReceived')
  const cashBox = document.getElementById('cashBox')
  if (payError) payError.hidden = true
  if (payTotal) payTotal.textContent = `$${fmtMoney(cartTotal())}`
  if (payChange) payChange.textContent = '$0,00'
  if (cashReceived) cashReceived.value = ''
  document.querySelectorAll('input[name="payMethod"]').forEach((r) => { r.checked = r.value === 'cash' })
  if (cashBox) cashBox.hidden = false
  payModal.hidden = false

  setTimeout(() => {
    const el = document.getElementById('cashReceived')
    if (el) el.focus()
  }, 0)
}

function closePayModal() {
  const pm = document.getElementById('payModal')
  if (pm) pm.hidden = true
  focusSearch()
}

function openCashCloseModal() {
  const modal = document.getElementById('cashCloseModal')
  if (!modal) return

  const err = document.getElementById('cashError')
  const ok = document.getElementById('cashOk')
  const errClose = document.getElementById('cashCloseError')
  const okClose = document.getElementById('cashCloseOk')
  if (err) err.hidden = true
  if (ok) ok.hidden = true
  if (errClose) errClose.hidden = true
  if (okClose) okClose.hidden = true

  modal.hidden = false
  setTimeout(() => {
    const expectedText = document.getElementById('cashExpected')?.textContent || ''
    const carry = document.getElementById('carryNext')
    if (carry && !(carry.value || '').trim()) {
      // Try to parse $ formatted number; fallback to backend default anyway.
      const n = Number(String(expectedText).replace(/[^0-9.,-]/g, '').replace(/\./g, '').replace(',', '.'))
      if (Number.isFinite(n) && n > 0) carry.value = String(n)
    }
    const el = document.getElementById('carryNext') || document.getElementById('cashCounted')
    if (el) el.focus()
  }, 0)
}

function closeCashCloseModal() {
  const modal = document.getElementById('cashCloseModal')
  if (!modal) return
  modal.hidden = true
}

function currentPayMethod() {
  const el = document.querySelector('input[name="payMethod"]:checked')
  return (el?.value || 'cash').trim()
}

function recomputePayChange() {
  const method = currentPayMethod()
  const cashBox = document.getElementById('cashBox')
  if (cashBox) cashBox.hidden = method !== 'cash'

  if (method !== 'cash') {
    const pc = document.getElementById('payChange')
    if (pc) pc.textContent = '$0,00'
    return
  }

  const total = cartTotal()
  const received = Number(document.getElementById('cashReceived')?.value || 0)
  const change = Math.max(0, received - total)
  const pc = document.getElementById('payChange')
  if (pc) pc.textContent = `$${fmtMoney(change)}`
}

async function confirmPay() {
  if (document.getElementById('errorBox')) hideError('errorBox')

  const lines = []
  for (const item of state.cart.values()) {
    lines.push({ key: item.key, qty: item.qty })
  }

  const method = currentPayMethod()
  const payment = { method }
  if (method === 'cash') {
    const v = (document.getElementById('cashReceived').value || '').trim()
    if (v) payment.cash_received = Number(v)
  }

  const res = await state.backend.checkout(lines, payment)
  if (!res || !res.ok) {
    const msg = res?.error || 'No se pudo cobrar'
    if (res?.details && Array.isArray(res.details) && res.details.length) {
      const d = res.details[0]
      if (document.getElementById('errorBox')) {
        showError('errorBox', `${msg}: ${d.producto} disponible=${d.available} solicitado=${d.requested}`)
      }
    } else {
      if (document.getElementById('errorBox')) showError('errorBox', msg)
    }
    document.getElementById('payError').hidden = false
    document.getElementById('payError').textContent = msg
    return
  }

  closePayModal()
  const pm = String(res.payment_method || method)
  const change = res.change_given != null ? ` • Cambio $${fmtMoney(res.change_given)}` : ''
  toast(`Venta #${res.sale_id} • ${pm.toUpperCase()} • Total $${fmtMoney(res.total)}${change}`)

  // Keep the touch ticket KPI up to date
  refreshTicketToday().catch(() => { /* ignore */ })
  clearCart()

  if (document.getElementById('cashDay')) refreshCashPanel()

  // refresh the results so stock is updated
  const ss = document.getElementById('storeSearch')
  searchProducts(ss ? (ss.value || '') : '', 'store')
}

async function checkout() {
  if (!document.getElementById('payModal')) return
  openPayModal()
}

async function refreshSummary() {
  if (!document.getElementById('kpiTotal')) return
  let s
  try {
    s = await state.backend.getSummary(25)
  } catch (e) {
    // If backend fails, keep UI responsive.
    return
  }
  if (!s) return

  document.getElementById('kpiTotal').textContent = `$${fmtMoney(s.total_vendido || 0)}`

  const tbody = document.getElementById('salesRows')
  tbody.innerHTML = ''
  for (const row of (s.ultimas_ventas || [])) {
    const method = String(row.payment_method || 'cash')
    const tr = document.createElement('tr')
    tr.innerHTML = `
      <td>${escapeHtml(row.created_at || '')}</td>
      <td>${escapeHtml(method)}</td>
      <td class="right"><b>$${fmtMoney(row.total || 0)}</b></td>
      <td class="right">${escapeHtml(row.items || 0)}</td>
    `
    tbody.appendChild(tr)
  }
}

async function refreshCashCloses() {
  const tbody = document.getElementById('closesRows')
  if (!tbody) return
  let rows
  try {
    rows = await state.backend.listCashCloses(30)
  } catch (e) {
    return
  }
  tbody.innerHTML = ''
  for (const r of (rows || [])) {
    const tr = document.createElement('tr')
    tr.innerHTML = `
      <td>${escapeHtml(r.created_at || '')}</td>
      <td>${escapeHtml(r.day || '')}</td>
      <td class="right">$${fmtMoney(r.opening_cash || 0)}</td>
      <td class="right">$${fmtMoney(r.withdrawals_total || 0)}</td>
      <td class="right">$${fmtMoney(r.expected_cash_end || 0)}</td>
      <td class="right"><b>$${fmtMoney(r.carry_to_next_day || 0)}</b></td>
    `
    tbody.appendChild(tr)
  }
}

function todayIso() {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

async function refreshCashPanel() {
  const dayEl = document.getElementById('cashDay')
  if (!dayEl) return
  const day = todayIso()
  dayEl.value = day
  dayEl.disabled = true

  const err = document.getElementById('cashError')
  const ok = document.getElementById('cashOk')
  if (err) err.hidden = true
  if (ok) ok.hidden = true

  let res
  try {
    res = await state.backend.getCashPanel(day)
  } catch (e) {
    return
  }
  if (!res || !res.ok) {
    if (err) {
      err.hidden = false
      err.textContent = res?.error || 'No se pudo consultar caja'
    }
    return
  }

  const openingInput = document.getElementById('openingCash')
  const openingHint = document.getElementById('openingHint')
  const openingSuggestedEl = document.getElementById('cashOpeningSuggested')
  const btnSetInitial = document.getElementById('btnSetInitialOpening')

  const openingCash = Number(res.opening_cash || 0)
  const openingSource = String(res.opening_source || '')
  const needsInitial = Boolean(res.needs_initial_opening)

  if (openingInput) openingInput.value = String(openingCash)
  if (btnSetInitial) btnSetInitial.hidden = !needsInitial
  if (openingSuggestedEl) {
    const note = needsInitial
      ? 'Primera vez: ingresa monto inicial.'
      : (openingSource === 'prev_close' ? 'Automático (de ayer)' : 'Inicial')
    openingSuggestedEl.textContent = note
  }
  if (openingHint) {
    openingHint.textContent = needsInitial
      ? 'Primera vez: pulsa “Ingresar monto inicial”. Luego el sistema arrastra la apertura automáticamente.'
      : 'La apertura se toma automáticamente del cierre anterior.'
  }

  document.getElementById('cashGross').textContent = `$${fmtMoney(res.gross_total || 0)}`
  document.getElementById('cashCash').textContent = `$${fmtMoney(res.cash_total || 0)}`
  document.getElementById('cashCard').textContent = `$${fmtMoney(res.card_total || 0)}`
  document.getElementById('cashNequi').textContent = `$${fmtMoney(res.nequi_total || 0)}`
  document.getElementById('cashVirtual').textContent = `$${fmtMoney(res.virtual_total || 0)}`
  document.getElementById('cashCount').textContent = String(res.sales_count || 0)
  document.getElementById('cashWithdrawals').textContent = `$${fmtMoney(res.withdrawals_total || 0)}`
  document.getElementById('cashExpected').textContent = `$${fmtMoney(res.expected_cash_end || 0)}`

  const lc = document.getElementById('cashLastClose')
  if (lc) {
    lc.textContent = res.last_close?.created_at ? String(res.last_close.created_at) : '—'
  }

  const forceBtn = document.getElementById('btnCloseDayForce')
  if (forceBtn) forceBtn.hidden = true

  const list = document.getElementById('withdrawList')
  if (list) {
    list.innerHTML = ''
    for (const w of (res.withdrawals || [])) {
      const row = document.createElement('div')
      row.className = 'miniRow'
      row.dataset.id = String(w.id)
      row.innerHTML = `
        <div>
          <div><b>$${fmtMoney(w.amount || 0)}</b> <span class="sub">${escapeHtml(w.created_at || '')}</span></div>
          <div class="sub">${escapeHtml(w.notes || '')}</div>
        </div>
        <div><button data-del="${escapeHtmlAttr(w.id)}">Quitar</button></div>
      `
      list.appendChild(row)
    }
  }

  if (res.last_close && ok) {
    const diff = res.last_close.cash_diff != null ? ` • Dif $${fmtMoney(res.last_close.cash_diff)}` : ''
    ok.hidden = false
    ok.textContent = `Último cierre: ${res.last_close.created_at}${diff}`
  }
}

async function setInitialOpeningCash() {
  const day = todayIso()
  const v = prompt('Monto inicial en caja (solo la primera vez):', '0')
  const err = document.getElementById('cashError')
  const ok = document.getElementById('cashOk')
  if (err) err.hidden = true
  if (ok) ok.hidden = true

  if (v == null) return
  const vv = String(v || '').trim()
  if (!vv) return

  const res = await state.backend.setOpeningCash(day, Number(vv))
  if (!res || !res.ok) {
    if (err) { err.hidden = false; err.textContent = res?.error || 'No se pudo guardar apertura' }
    return
  }
  if (ok) { ok.hidden = false; ok.textContent = 'Monto inicial guardado' }
  toast('Monto inicial guardado')
  refreshCashPanel()
}

async function addWithdrawal() {
  const day = document.getElementById('cashDay').value || todayIso()
  const amt = (document.getElementById('withdrawAmount').value || '').trim()
  const notes = (document.getElementById('withdrawNotes').value || '').trim()
  const err = document.getElementById('cashError')
  const ok = document.getElementById('cashOk')
  if (err) err.hidden = true
  if (ok) ok.hidden = true

  const res = await state.backend.addCashWithdrawal(day, amt ? Number(amt) : 0, notes)
  if (!res || !res.ok) {
    if (err) { err.hidden = false; err.textContent = res?.error || 'No se pudo agregar retiro' }
    return
  }
  document.getElementById('withdrawAmount').value = ''
  document.getElementById('withdrawNotes').value = ''
  toast('Retiro agregado')
  refreshCashPanel()
}

async function deleteWithdrawal(id) {
  const res = await state.backend.deleteCashMove(Number(id))
  if (!res || !res.ok) {
    toast(res?.error || 'No se pudo quitar')
    return
  }
  refreshCashPanel()
}

async function closeCashDay(force = false) {
  const day = document.getElementById('cashDay').value || todayIso()
  const counted = (document.getElementById('cashCounted').value || '').trim()
  const notes = (document.getElementById('cashNotes').value || '').trim()
  const err = document.getElementById('cashCloseError') || document.getElementById('cashError')
  const ok = document.getElementById('cashCloseOk') || document.getElementById('cashOk')
  if (err) err.hidden = true
  if (ok) ok.hidden = true

  const res = await state.backend.closeCashDay(day, counted ? Number(counted) : null, notes, Boolean(force))
  if (!res || !res.ok) {
    // Mismatch flow: show warning and enable force button.
    const forceBtn = document.getElementById('btnCloseDayForce')
    if (res?.needs_force && forceBtn) {
      forceBtn.hidden = false
      forceBtn.onclick = () => closeCashDay(true)
    }
    if (err) { err.hidden = false; err.textContent = res?.error || 'No se pudo guardar cierre' }
    return
  }

  if (ok) {
    ok.hidden = false
    ok.textContent = (res.message ? String(res.message) + ' ' : '') + `Cierre guardado (${res.created_at || ''})` + (res.cash_diff != null ? ` • Dif $${fmtMoney(res.cash_diff)}` : '')
  }
  toast('Cierre guardado')
  refreshCashPanel()
  refreshCashCloses()
  closeCashCloseModal()
}

function openProductModal(key) {
  const k = String(key || '').trim()
  if (!k) return
  const p = state.products.find((x) => String(x.key ?? '').trim() === k)
  if (!p) return

  state.currentProductKey = k
  document.getElementById('pmError').hidden = true

  document.getElementById('pmTitle').textContent = p.producto || 'Producto'
  document.getElementById('pmDesc').textContent = p.descripcion || ''

  const stock = Number(p.unidades || 0)
  const stockClass = stock <= 0 ? 'stockBad' : (stock <= 2 ? 'stockLow' : 'stockOk')
  const stockEl = document.getElementById('pmStock')
  stockEl.textContent = String(stock)
  stockEl.className = `stock ${stockClass}`

  document.getElementById('pmPrice').textContent = `$${fmtMoney(p.precio_final || 0)}`
  const catEl = document.getElementById('pmCategory')
  if (catEl) catEl.value = String(p.category || '')
  document.getElementById('pmQty').value = '1'

  const thumb = document.getElementById('pmThumb')
  if (p.image_url) {
    thumb.innerHTML = `<img src="${escapeHtmlAttr(p.image_url)}" alt="" />`
  } else {
    thumb.textContent = '📦'
  }

  document.getElementById('productModal').hidden = false
  setTimeout(() => {
    document.getElementById('pmQty').focus()
    document.getElementById('pmQty').select()
  }, 0)
}

function closeProductModal() {
  document.getElementById('productModal').hidden = true
  state.currentProductKey = null
  focusSearch()
}

async function saveProductCategory() {
  const key = state.currentProductKey
  if (!key) return
  const cat = (document.getElementById('pmCategory').value || '').trim()
  const res = await state.backend.setProductCategory(key, cat)
  if (!res || !res.ok) {
    document.getElementById('pmError').hidden = false
    document.getElementById('pmError').textContent = 'No se pudo guardar la categoría'
    return
  }
  const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
  if (p) p.category = cat
  await loadCategories()
  rerenderAll()
  toast('Categoría guardada')
}

async function pickProductImage() {
  const key = state.currentProductKey
  if (!key) return

  // Web mode (tablet): upload file
  if (state.backend?.uploadProductImage) {
    const file = await pickFile('image/*')
    if (!file) return
    const res = await state.backend.uploadProductImage(key, file)
    if (!res || !res.ok) {
      document.getElementById('pmError').hidden = false
      document.getElementById('pmError').textContent = res?.error || 'No se pudo cargar imagen'
      return
    }
    const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
    if (p) p.image_url = res.image_url || p.image_url
    const thumb = document.getElementById('pmThumb')
    if (res.image_url) thumb.innerHTML = `<img src="${escapeHtmlAttr(res.image_url)}" alt="" />`
    renderStoreGrid()
    toast('Imagen actualizada')
    return
  }

  // Desktop mode (pywebview): open OS file picker
  const res = await state.backend.pickProductImage(key)
  if (!res || !res.ok) {
    document.getElementById('pmError').hidden = false
    document.getElementById('pmError').textContent = res?.error || 'No se pudo cargar imagen'
    return
  }
  const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
  if (p) p.image_url = res.image_url || p.image_url
  const thumb = document.getElementById('pmThumb')
  if (res.image_url) thumb.innerHTML = `<img src="${escapeHtmlAttr(res.image_url)}" alt="" />`
  renderStoreGrid()
  toast('Imagen actualizada')
}

async function clearProductImage() {
  const key = state.currentProductKey
  if (!key) return
  const res = await state.backend.clearProductImage(key)
  if (!res || !res.ok) {
    document.getElementById('pmError').hidden = false
    document.getElementById('pmError').textContent = res?.error || 'No se pudo quitar imagen'
    return
  }
  const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
  if (p) p.image_url = null
  document.getElementById('pmThumb').textContent = '📦'
  renderStoreGrid()
  toast('Imagen removida')
}

function addFromProductModal() {
  const key = state.currentProductKey
  if (!key) return
  const qty = Math.max(1, Number(document.getElementById('pmQty').value || 1))
  addToCartByKey(key, qty)
  closeProductModal()
}

async function loadCategories() {
  const cats = await state.backend.getCategories()
  state.categories = Array.isArray(cats) && cats.length ? cats : ['Todas']

  const storeSel = document.getElementById('storeCategory')
  const prevStore = storeSel.value || 'Todas'

  storeSel.innerHTML = ''
  for (const c of state.categories) {
    const opt = document.createElement('option')
    opt.value = c
    opt.textContent = c
    storeSel.appendChild(opt)
  }

  storeSel.value = state.categories.includes(prevStore) ? prevStore : 'Todas'
}

function openResetModal() {
  document.getElementById('confirmText').value = ''
  document.getElementById('modalError').hidden = true
  document.getElementById('modal').hidden = false
  document.getElementById('confirmText').focus()
}

function closeResetModal() {
  document.getElementById('modal').hidden = true
}

async function confirmReset() {
  const txt = (document.getElementById('confirmText').value || '').trim()
  const err = document.getElementById('modalError')
  err.hidden = true

  const res = await state.backend.resetDatabase(txt)
  if (!res || !res.ok) {
    err.hidden = false
    err.textContent = res?.error || 'No se pudo reiniciar'
    return
  }

  closeResetModal()
  toast('Base de datos reiniciada')
  clearCart()
  await searchProducts('', 'store')
  await refreshSummary()
  refreshCashPanel()
}

async function doImport() {
  if (!state.backend) return

  // Web mode (tablet): upload xlsx
  if (state.backend.importExcelUpload) {
    const file = await pickFile('.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    if (!file) return
    const res = await state.backend.importExcelUpload(file)
    if (!res || !res.ok) {
      toast(res?.error || 'Import falló')
      return
    }
    toast(`Importado ${res.imported} • Actualizados ${res.upserted}`)
    if (document.getElementById('storeCategory')) await loadCategories()
    if (document.getElementById('storeGrid')) {
      const ss = document.getElementById('storeSearch')
      await searchProducts(ss ? (ss.value || '') : '', 'store')
    }
    if (document.getElementById('cashDay')) refreshCashPanel()
    return
  }

  const res = await state.backend.importExcel()
  if (!res || !res.ok) {
    toast(res?.error || 'Import falló')
    return
  }
  toast(`Importado ${res.imported} • Actualizados ${res.upserted}`)
  if (document.getElementById('storeCategory')) await loadCategories()
  if (document.getElementById('storeGrid')) {
    const ss = document.getElementById('storeSearch')
    await searchProducts(ss ? (ss.value || '') : '', 'store')
  }
  if (document.getElementById('cashDay')) refreshCashPanel()
}

function setupHandlers() {
  // If tabs are buttons (legacy single-page index.html), we switch views in-place.
  const tabStore = document.getElementById('tabStore')
  const tabSummary = document.getElementById('tabSummary')
  if (tabStore && tabStore.tagName === 'BUTTON') tabStore.addEventListener('click', () => setTab('store'))
  if (tabSummary && tabSummary.tagName === 'BUTTON') tabSummary.addEventListener('click', () => setTab('summary'))

  const storeSearch = document.getElementById('storeSearch')

  const debounce = (fn, ms) => {
    let t
    return (...args) => {
      clearTimeout(t)
      t = setTimeout(() => fn(...args), ms)
    }
  }

  const debounceMs = isTabletMode() ? (state.ui.lite ? 380 : 260) : 120
  if (storeSearch) storeSearch.addEventListener('input', debounce(() => searchProducts(storeSearch.value, 'store'), debounceMs))

  const storeCategory = document.getElementById('storeCategory')
  if (storeCategory) storeCategory.addEventListener('change', () => renderStoreGrid())

  if (storeSearch) {
    storeSearch.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); addFirstResult() }
    })
  }

  const btnCheckout = document.getElementById('btnCheckout')
  const btnClear = document.getElementById('btnClear')
  if (btnCheckout) btnCheckout.addEventListener('click', () => checkout())
  if (btnClear) btnClear.addEventListener('click', clearCart)

  // Bottom-sheet toggle button (tablet): expand to full screen or collapse
  const btnSheet = document.getElementById('btnSheet')
  if (btnSheet && !btnSheet._globalWired) {
    btnSheet._globalWired = true
    const card = document.querySelector('#cashier .sidebarCard')
    btnSheet.addEventListener('click', (e) => {
      e.preventDefault()
      e.stopPropagation()
      const open = isSheetOpen()
      if (open) {
        // Collapse
        if (card) card.style.height = ''
        setSheetOpen(false)
        btnSheet.textContent = '▴'
      } else {
        // Expand to nearly full screen
        const fullH = Math.max(400, window.innerHeight - 60)
        if (card) card.style.height = `${Math.round(fullH)}px`
        setSheetOpen(true)
        btnSheet.textContent = '▾'
      }
    })
  }

  const btnReset = document.getElementById('btnReset')
  const btnCancel = document.getElementById('btnCancel')
  const btnConfirm = document.getElementById('btnConfirm')
  if (btnReset) btnReset.addEventListener('click', openResetModal)
  if (btnCancel) btnCancel.addEventListener('click', closeResetModal)
  if (btnConfirm) btnConfirm.addEventListener('click', confirmReset)

  const btnImport = document.getElementById('btnImport')
  if (btnImport) btnImport.addEventListener('click', doImport)

  const btnOpenImages = document.getElementById('btnOpenImages')
  if (btnOpenImages) {
    btnOpenImages.addEventListener('click', async () => {
      if (!state.backend?.openImagesFolder) return
      const res = await state.backend.openImagesFolder()
      if (!res || !res.ok) {
        toast(res?.error || 'No se pudo abrir carpeta de imágenes')
      }
    })
  }

  const btnTheme = document.getElementById('btnTheme')
  if (btnTheme) {
    updateThemeButton(getSavedTheme())
    btnTheme.addEventListener('click', () => cycleTheme())
  }
  // Product modal
  const pmCancel = document.getElementById('pmCancel')
  const pmSaveCat = document.getElementById('pmSaveCat')
  const pmPickImg = document.getElementById('pmPickImg')
  const pmClearImg = document.getElementById('pmClearImg')
  const pmAdd = document.getElementById('pmAdd')
  const pmInc = document.getElementById('pmInc')
  const pmDec = document.getElementById('pmDec')
  if (pmCancel) pmCancel.addEventListener('click', closeProductModal)
  if (pmSaveCat) pmSaveCat.addEventListener('click', saveProductCategory)
  if (pmPickImg) pmPickImg.addEventListener('click', pickProductImage)
  if (pmClearImg) pmClearImg.addEventListener('click', clearProductImage)
  if (pmAdd) pmAdd.addEventListener('click', addFromProductModal)
  if (pmInc) pmInc.addEventListener('click', () => {
    const el = document.getElementById('pmQty'); el.value = String(Math.max(1, Number(el.value || 1) + 1))
  })
  if (pmDec) pmDec.addEventListener('click', () => {
    const el = document.getElementById('pmQty'); el.value = String(Math.max(1, Number(el.value || 1) - 1))
  })

  // Payment modal
  const payCancel = document.getElementById('payCancel')
  const payConfirm = document.getElementById('payConfirm')
  const cashReceived = document.getElementById('cashReceived')
  if (payCancel) payCancel.addEventListener('click', closePayModal)
  if (payConfirm) payConfirm.addEventListener('click', confirmPay)
  if (cashReceived) cashReceived.addEventListener('input', recomputePayChange)
  document.querySelectorAll('input[name="payMethod"]').forEach((r) => {
    r.addEventListener('change', recomputePayChange)
  })

  // Cash close modal (Caja page)
  const btnOpenCloseModal = document.getElementById('btnOpenCloseModal')
  const btnCloseModalCancel = document.getElementById('btnCloseModalCancel')
  if (btnOpenCloseModal) btnOpenCloseModal.addEventListener('click', openCashCloseModal)
  if (btnCloseModalCancel) btnCloseModalCancel.addEventListener('click', closeCashCloseModal)

  // Cart buttons (event delegation)
  const cartItems = document.getElementById('cartItems')
  if (cartItems) cartItems.addEventListener('click', (e) => {
    const btn = e.target?.closest?.('button[data-act]')
    if (!btn) return
    const key = btn.getAttribute('data-key')
    const act = btn.getAttribute('data-act')
    if (act === 'inc') addToCartByKey(key, 1)
    if (act === 'dec') addToCartByKey(key, -1)
    if (act === 'rm') { state.cart.delete(key); rerenderAll() }
  })

  // Store grid (event delegation)
  const storeGrid = document.getElementById('storeGrid')
  if (storeGrid) storeGrid.addEventListener('click', (e) => {
    const add1 = e.target?.closest?.('button[data-add]')
    if (add1) { e.stopPropagation(); addToCartByKey(add1.getAttribute('data-add'), 1); return }
    const add2 = e.target?.closest?.('button[data-add2]')
    if (add2) { e.stopPropagation(); addToCartByKey(add2.getAttribute('data-add2'), 2); return }
    const card = e.target?.closest?.('.cardP')
    if (card && card.dataset.key) openProductModal(card.dataset.key)
  })

  // Cash drawer (apertura/retiros/cierre)
  const cashDay = document.getElementById('cashDay')
  if (cashDay) {
    cashDay.addEventListener('change', () => {
      refreshCashPanel()
    })
  }
  const btnRefreshCash = document.getElementById('btnRefreshCash')
  const btnSetInitialOpening = document.getElementById('btnSetInitialOpening')
  const btnAddWithdraw = document.getElementById('btnAddWithdraw')
  const btnCloseDay = document.getElementById('btnCloseDay')
  const btnCloseDayForce = document.getElementById('btnCloseDayForce')
  if (btnRefreshCash) btnRefreshCash.addEventListener('click', refreshCashPanel)
  if (btnSetInitialOpening) btnSetInitialOpening.addEventListener('click', setInitialOpeningCash)
  if (btnAddWithdraw) btnAddWithdraw.addEventListener('click', addWithdrawal)
  if (btnCloseDay) btnCloseDay.addEventListener('click', () => closeCashDay(false))
  if (btnCloseDayForce) btnCloseDayForce.addEventListener('click', () => closeCashDay(true))
  const withdrawList = document.getElementById('withdrawList')
  if (withdrawList) withdrawList.addEventListener('click', (e) => {
    const btn = e.target?.closest?.('button[data-del]')
    if (!btn) return
    deleteWithdrawal(btn.getAttribute('data-del'))
  })

  document.addEventListener('keydown', (e) => {
    if (e.key === 'F2') {
      e.preventDefault()
      focusSearch()
    }
    if (e.key === 'F4') {
      e.preventDefault()
      checkout()
    }
    if (e.key === 'Escape') {
      const resetModal = document.getElementById('modal')
      const payModal = document.getElementById('payModal')
      const prodModal = document.getElementById('productModal')
      const cashCloseModal = document.getElementById('cashCloseModal')
      if (cashCloseModal && !cashCloseModal.hidden) { closeCashCloseModal(); return }
      if (resetModal && !resetModal.hidden) closeResetModal()
      else if (payModal && !payModal.hidden) closePayModal()
      else if (prodModal && !prodModal.hidden) closeProductModal()
    }

    if (e.key === 'Enter') {
      const payModal = document.getElementById('payModal')
      const prodModal = document.getElementById('productModal')
      if (payModal && !payModal.hidden) {
        e.preventDefault()
        confirmPay()
      } else if (prodModal && !prodModal.hidden) {
        // If typing in category, allow Enter to save category; otherwise add.
        const active = document.activeElement
        if (active && active.id === 'pmCategory') {
          e.preventDefault()
          saveProductCategory()
        } else {
          e.preventDefault()
          addFromProductModal()
        }
      }
    }
  })
}

let _backendInited = false

function setBridgeStatus(msg, isError) {
  const id = 'bridgeStatus'
  const existing = document.getElementById(id)

  if (!msg) {
    if (existing) existing.remove()
    return
  }

  const el = existing || document.createElement('div')
  el.id = id
  el.style.position = 'fixed'
  el.style.left = '12px'
  el.style.bottom = '12px'
  el.style.zIndex = '99999'
  el.style.padding = '10px 12px'
  el.style.borderRadius = '10px'
  el.style.fontFamily = 'system-ui, -apple-system, Segoe UI, Roboto, Arial'
  el.style.fontSize = '13px'
  el.style.background = isError ? 'rgba(140, 25, 25, 0.92)' : 'rgba(20, 20, 20, 0.75)'
  el.style.color = '#fff'
  el.style.backdropFilter = 'blur(6px)'
  el.textContent = String(msg)

  if (!existing) document.body.appendChild(el)
}

function isHttpBrowser() {
  const p = String(window.location?.protocol || '')
  return p === 'http:' || p === 'https:'
}

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

  async function httpUpload(path, formData) {
    const url = base + path
    const res = await fetch(url, { method: 'POST', body: formData })
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
    checkout: (lines, payment) => httpJson('POST', '/api/checkout', { lines, payment }),

    getSummary: (limit) => httpJson('GET', `/api/getSummary?limit=${encodeURIComponent(String(limit ?? 25))}`),
    listCashCloses: (limit) => httpJson('GET', `/api/listCashCloses?limit=${encodeURIComponent(String(limit ?? 30))}`),
    getCashPanel: (day) => httpJson('GET', `/api/getCashPanel?day=${encodeURIComponent(String(day || ''))}`),

    useSuggestedOpeningCash: (day) => httpJson('POST', '/api/useSuggestedOpeningCash', { day }),
    setOpeningCash: (day, opening_cash) => httpJson('POST', '/api/setOpeningCash', { day, opening_cash }),
    addCashWithdrawal: (day, amount, notes) => httpJson('POST', '/api/addCashWithdrawal', { day, amount, notes }),
    deleteCashMove: (id) => httpJson('POST', '/api/deleteCashMove', { id }),
    closeCashDay: (day, cash_counted, notes, force) => httpJson('POST', '/api/closeCashDay', { day, cash_counted, notes, force }),

    setProductCategory: (key, category) => httpJson('POST', '/api/setProductCategory', { key, category }),
    clearProductImage: (key) => httpJson('POST', '/api/clearProductImage', { key }),
    restockProduct: (key, delta, notes) => httpJson('POST', '/api/restockProduct', { key, delta, notes }),
    setProductStock: (key, stock, notes) => httpJson('POST', '/api/setProductStock', { key, stock, notes }),
    resetDatabase: (confirm_text) => httpJson('POST', '/api/resetDatabase', { confirm_text }),
    openImagesFolder: () => httpJson('POST', '/api/openImagesFolder'),

    uploadProductImage: async (key, file) => {
      const fd = new FormData()
      fd.append('key', String(key || ''))
      fd.append('file', file)
      return httpUpload('/api/uploadProductImage', fd)
    },

    importExcelUpload: async (file) => {
      const fd = new FormData()
      fd.append('file', file)
      return httpUpload('/api/importExcelUpload', fd)
    },
  }
}

function pickFile(accept) {
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    if (accept) input.accept = accept
    input.style.position = 'fixed'
    input.style.left = '-10000px'
    input.style.top = '-10000px'
    document.body.appendChild(input)

    input.addEventListener('change', () => {
      const file = input.files && input.files[0] ? input.files[0] : null
      input.remove()
      resolve(file)
    }, { once: true })

    input.click()
  })
}

function initBackendCommon() {
  if (_backendInited) return
  if (!state.backend) return
  _backendInited = true

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

  setBridgeStatus(null)

  state.backend.getAppInfo().then((info) => {
    const appName = document.getElementById('appName')
    if (appName) appName.textContent = info.app_name || 'Inventarios POS'
    if (info.db_file) {
      const appSub = document.getElementById('appSub')
      if (appSub) appSub.textContent = `DB: ${info.db_file}`
    }
    // eslint-disable-next-line no-console
    console.log('Inventarios POS DB:', info.db_url || info.db_file || '')
  }).catch((e) => {
    // eslint-disable-next-line no-console
    console.error('getAppInfo error:', e)
  })

  setupHandlers()
  const page = (document.body?.dataset?.page || 'store').trim()

  // Only use legacy in-page tab switching if tabs are buttons.
  const legacyTabs = document.getElementById('tabStore')?.tagName === 'BUTTON'
  if (legacyTabs) {
    setTab(page === 'summary' ? 'summary' : 'store')
  } else {
    state.activeTab = page
    if (page === 'summary') {
      setTimeout(() => {
        refreshSummary()
        refreshCashCloses()
      }, 0)
    }
  }

  const cashDay = document.getElementById('cashDay')
  if (cashDay) {
    cashDay.value = todayIso()
    refreshCashPanel()
  }

  if (document.getElementById('cashCloseModal') && window.location.hash === '#close') {
    setTimeout(() => openCashCloseModal(), 0)
  }

  const catSel = document.getElementById('storeCategory')
  if (catSel) {
    loadCategories()
      .catch(() => { /* ignore */ })
      .finally(() => {
        if (document.getElementById('storeGrid')) searchProducts('', 'store')
      })
  }
}

function initPyWebview() {
  // pywebview injects window.pywebview + window.pywebview.api.
  if (!window.pywebview || !window.pywebview.api) return
  state.backend = window.pywebview.api
  initBackendCommon()
}

function initHttpBackend() {
  state.backend = createHttpBackend('')
  initBackendCommon()
}

window.addEventListener('DOMContentLoaded', () => {
  // pywebview path: may not be ready yet at DOMContentLoaded
  if (window.pywebview && window.pywebview.api) {
    initPyWebview()
    rerenderAll()
    return
  }

  // Browser path: served by the Flask server.
  if (isHttpBrowser()) {
    setBridgeStatus('Conectando…', false)
    initHttpBackend()
    rerenderAll()
    return
  }

  // Bridge not available yet. This is normal for pywebview: wait for 'pywebviewready'.
  setBridgeStatus('Cargando…', false)

  // As a fallback, poll briefly in case the event doesn't fire for some reason.
  let tries = 0
  const t = setInterval(() => {
    tries += 1
    if (window.pywebview && window.pywebview.api) {
      clearInterval(t)
      initPyWebview()
      rerenderAll()
      return
    }
    if (tries >= 40) {
      clearInterval(t)
      setBridgeStatus('Error: backend bridge no disponible (pywebview)', true)
    }
  }, 100)
})

// pywebview emits this event when the bridge is ready.
window.addEventListener('pywebviewready', () => {
  initPyWebview()
  rerenderAll()
})
