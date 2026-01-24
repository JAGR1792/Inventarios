/* global QWebChannel */

const state = {
  backend: null,
  products: [],
  cart: new Map(), // key -> { key, producto, precio_final, qty }
  activeTab: 'store',
  lastSearchQuery: '',
  categories: ['Todas'],
  currentProductKey: null,
}

const THEME_KEY = 'inventarios_theme'

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
  return n.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
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
  const item = state.cart.get(key)
  if (!item) {
    const p = state.products.find((x) => x.key === key)
    if (!p) return
    if (deltaQty <= 0) return
    state.cart.set(key, { key: p.key, producto: p.producto, precio_final: p.precio_final, qty: deltaQty })
  } else {
    const next = Number(item.qty) + Number(deltaQty)
    if (next <= 0) state.cart.delete(key)
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
  const results = await state.backend.searchProducts(query, 180)
  if (state.lastSearchQuery !== query) return
  state.products = Array.isArray(results) ? results : []

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
  grid.innerHTML = ''

  const frag = document.createDocumentFragment()

  for (const p of filteredProducts()) {
    const el = document.createElement('div')
    el.className = 'cardP'
    el.dataset.key = p.key

    const img = p.image_url ? `<img src="${escapeHtmlAttr(p.image_url)}" alt="" loading="lazy" decoding="async" />` : '📦'

    const stock = Number(p.unidades || 0)
    const stockClass = stock <= 0 ? 'stockBad' : (stock <= 2 ? 'stockLow' : 'stockOk')

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

    frag.appendChild(el)
  }

  grid.appendChild(frag)
}

function addFirstResult() {
  if (state.products.length === 0) return
  addToCartByKey(state.products[0].key, 1)

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
  const btnUseSuggested = document.getElementById('btnUseSuggested')

  const openingCash = Number(res.opening_cash || 0)
  const suggested = Number(res.suggested_opening_cash || 0)
  const isManual = Number(res.opening_cash_manual || 0) === 1

  if (openingSuggestedEl) openingSuggestedEl.textContent = `$${fmtMoney(suggested)}`
  if (openingInput) {
    if (isManual) {
      openingInput.value = String(openingCash)
      openingInput.placeholder = ''
    } else {
      openingInput.value = ''
      openingInput.placeholder = suggested ? String(suggested) : 'Sugerido'
    }
  }
  if (btnUseSuggested) btnUseSuggested.disabled = !isManual
  if (openingHint) {
    if (!isManual && suggested === 0) {
      openingHint.textContent = 'Primera vez: escribe cuánto efectivo hay en caja para iniciar.'
    } else if (!isManual) {
      openingHint.textContent = 'Inicio automático (de ayer). Si necesitas corregir, guarda apertura.'
    } else {
      openingHint.textContent = 'Inicio manual (ajustado por ti). Puedes volver a sugerido.'
    }
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

  const carryEl = document.getElementById('carryNext')
  if (carryEl && (carryEl.value || '').trim() === '') {
    carryEl.value = String(res.expected_cash_end || 0)
  }

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

async function useSuggestedOpeningCash() {
  const dayEl = document.getElementById('cashDay')
  if (!dayEl) return
  const day = todayIso()
  try {
    const res = await state.backend.useSuggestedOpeningCash(day)
    if (!res || !res.ok) {
      toast(res?.error || 'No se pudo usar sugerido')
      return
    }
  } catch (e) {
    return
  }
  refreshCashPanel()
}

async function saveOpeningCash() {
  const day = todayIso()
  const v = (document.getElementById('openingCash')?.value || '').trim()
  const err = document.getElementById('cashError')
  const ok = document.getElementById('cashOk')
  if (err) err.hidden = true
  if (ok) ok.hidden = true

  if (!v) {
    if (err) { err.hidden = false; err.textContent = 'Escribe el efectivo inicial para guardar (solo si vas a ajustar).' }
    return
  }

  const res = await state.backend.setOpeningCash(day, v ? Number(v) : 0)
  if (!res || !res.ok) {
    if (err) { err.hidden = false; err.textContent = res?.error || 'No se pudo guardar apertura' }
    return
  }
  if (ok) { ok.hidden = false; ok.textContent = 'Apertura guardada' }
  toast('Apertura guardada')
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

async function closeCashDay() {
  const day = document.getElementById('cashDay').value || todayIso()
  const counted = (document.getElementById('cashCounted').value || '').trim()
  const carry = (document.getElementById('carryNext').value || '').trim()
  const notes = (document.getElementById('cashNotes').value || '').trim()
  const err = document.getElementById('cashCloseError') || document.getElementById('cashError')
  const ok = document.getElementById('cashCloseOk') || document.getElementById('cashOk')
  if (err) err.hidden = true
  if (ok) ok.hidden = true

  const res = await state.backend.closeCashDay(day, counted ? Number(counted) : null, carry ? Number(carry) : null, notes)
  if (!res || !res.ok) {
    if (err) { err.hidden = false; err.textContent = res?.error || 'No se pudo guardar cierre' }
    return
  }

  if (ok) {
    ok.hidden = false
    ok.textContent = `Cierre guardado (${res.created_at || ''})` + (res.cash_diff != null ? ` • Dif $${fmtMoney(res.cash_diff)}` : '')
  }
  toast('Cierre guardado')
  refreshCashPanel()
  refreshCashCloses()
  closeCashCloseModal()
}

function openProductModal(key) {
  const k = String(key || '').trim()
  if (!k) return
  const p = state.products.find((x) => x.key === k)
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
  document.getElementById('pmCategory').value = String(p.category || '')
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
  const p = state.products.find((x) => x.key === key)
  if (p) p.category = cat
  await loadCategories()
  rerenderAll()
  toast('Categoría guardada')
}

async function pickProductImage() {
  const key = state.currentProductKey
  if (!key) return
  const res = await state.backend.pickProductImage(key)
  if (!res || !res.ok) {
    document.getElementById('pmError').hidden = false
    document.getElementById('pmError').textContent = res?.error || 'No se pudo cargar imagen'
    return
  }
  const p = state.products.find((x) => x.key === key)
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
  const p = state.products.find((x) => x.key === key)
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

  if (storeSearch) storeSearch.addEventListener('input', debounce(() => searchProducts(storeSearch.value, 'store'), 120))

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
  const btnSaveOpening = document.getElementById('btnSaveOpening')
  const btnUseSuggested = document.getElementById('btnUseSuggested')
  const btnAddWithdraw = document.getElementById('btnAddWithdraw')
  const btnCloseDay = document.getElementById('btnCloseDay')
  if (btnRefreshCash) btnRefreshCash.addEventListener('click', refreshCashPanel)
  if (btnSaveOpening) btnSaveOpening.addEventListener('click', saveOpeningCash)
  if (btnUseSuggested) btnUseSuggested.addEventListener('click', useSuggestedOpeningCash)
  if (btnAddWithdraw) btnAddWithdraw.addEventListener('click', addWithdrawal)
  if (btnCloseDay) btnCloseDay.addEventListener('click', closeCashDay)
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

function initWebChannel() {
  new QWebChannel(qt.webChannelTransport, (channel) => {
    state.backend = channel.objects.backend

    initBackendCommon()
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

function initBackendCommon() {
  if (_backendInited) return
  if (!state.backend) return
  _backendInited = true

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

window.addEventListener('DOMContentLoaded', () => {
  if (typeof qt !== 'undefined') {
    // Qt WebEngine path
    initWebChannel()
    rerenderAll()
    return
  }

  // pywebview path: may not be ready yet at DOMContentLoaded
  if (window.pywebview && window.pywebview.api) {
    initPyWebview()
    rerenderAll()
    return
  }

  // Neither bridge is available yet. This is normal for pywebview: wait for 'pywebviewready'.
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
      setBridgeStatus('Error: backend bridge no disponible (Qt WebChannel / pywebview)', true)
    }
  }, 100)
})

// pywebview emits this event when the bridge is ready.
window.addEventListener('pywebviewready', () => {
  initPyWebview()
  rerenderAll()
})
