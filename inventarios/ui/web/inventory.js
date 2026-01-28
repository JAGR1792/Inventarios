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
  // Tablet/kiosk is always lite. Desktop can still use ?lite=1 if needed.
  state.ui.lite = state.ui.tablet ? true : (liteParam === null ? false : Boolean(liteParam))
  try {
    if (state.ui.lite) document.documentElement.dataset.lite = '1'
    else delete document.documentElement.dataset.lite
  } catch (e) { /* ignore */ }

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

// Theme support removed: use Dark-only.
function applyDarkOnlyTheme() {
  try {
    document.documentElement.dataset.theme = 'dark'
  } catch (e) { /* ignore */ }
  try {
    localStorage.removeItem('inventarios_theme')
  } catch (e) { /* ignore */ }
}

// Apply lite-mode and dark theme as early as possible (does not require backend)
initUiModes()
applyDarkOnlyTheme()

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
    restockProduct: (key, delta, notes) => httpJson('POST', '/api/restockProduct', { key, delta, notes }),
    setProductStock: (key, stock, notes) => httpJson('POST', '/api/setProductStock', { key, stock, notes }),
    deleteProduct: (key, confirm_text) => httpJson('POST', '/api/deleteProduct', { key, confirm_text }),
    findDuplicates: () => httpJson('GET', '/api/findDuplicates'),
    deleteDuplicates: (keep_first) => httpJson('POST', '/api/deleteDuplicates', { keep_first }),
    setProductInfo: (key, producto, descripcion) => httpJson('POST', '/api/setProductInfo', { key, producto, descripcion }),
    setProductCategory: (key, category) => httpJson('POST', '/api/setProductCategory', { key, category }),
    setProductPrice: (key, precio_final) => httpJson('POST', '/api/setProductPrice', { key, precio_final }),
    clearProductImage: (key) => httpJson('POST', '/api/clearProductImage', { key }),
    openImagesFolder: () => httpJson('POST', '/api/openImagesFolder', {}),
    exportExcelSelect: () => httpJson('POST', '/api/exportExcelSelect', {}),
    exportExcelToLast: () => httpJson('POST', '/api/exportExcelToLast', {}),
    createProduct: (producto, descripcion, precio_final, unidades, category) => httpJson('POST', '/api/createProduct', { producto, descripcion, precio_final, unidades, category }),
    uploadProductImage: async (key, file) => {
      const fd = new FormData()
      fd.append('key', String(key || ''))
      fd.append('file', file)
      return httpUpload('/api/uploadProductImage', fd)
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

      const img = p.image_url ? `<img src="${escapeHtmlAttr(p.image_url)}" alt="" loading="lazy" decoding="async" />` : '📦'

      const stock = Number(p.unidades || 0)
      const stockClass = stock <= 0 ? 'stockBad' : (stock <= 2 ? 'stockLow' : 'stockOk')

      // Same store technique: reduce DOM on tablets.
      if (tablet) {
        el.innerHTML = `
          <div class="cardTop">
            <div class="thumb">${img}</div>
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
            <div class="thumb">${img}</div>
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

  const nameEl = document.getElementById('imNameEdit')
  if (nameEl) nameEl.value = String(p.producto || '')
  const descEl = document.getElementById('imDescEdit')
  if (descEl) descEl.value = String(p.descripcion || '')

  const stock = Number(p.unidades || 0)
  const stockClass = stock <= 0 ? 'stockBad' : (stock <= 2 ? 'stockLow' : 'stockOk')
  const stockEl = document.getElementById('imStock')
  stockEl.textContent = String(stock)
  stockEl.className = `stock ${stockClass}`

  document.getElementById('imPrice').textContent = `$${fmtMoney(p.precio_final || 0)}`
  const catEl = document.getElementById('imCategory')
  if (catEl) catEl.value = String(p.category || '')
  const priceEl = document.getElementById('imPriceEdit')
  if (priceEl) priceEl.value = String(Number(p.precio_final || 0))
  document.getElementById('imRestockQty').value = '1'
  document.getElementById('imSetStock').value = String(stock)
  document.getElementById('imHint').textContent = 'Usa Rellenar para sumar. Ajustar stock para corregir.'

  const delBtn = document.getElementById('imDeleteProduct')
  if (delBtn) delBtn.hidden = !state.backend?.deleteProduct

  const thumb = document.getElementById('imThumb')
  if (p.image_url) thumb.innerHTML = `<img src="${escapeHtmlAttr(p.image_url)}" alt="" />`
  else thumb.textContent = '📦'

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
  const qty = Number(document.getElementById('imRestockQty').value || 0)
  if (!Number.isFinite(qty) || qty <= 0) {
    const err = document.getElementById('imError')
    err.hidden = false
    err.textContent = 'Cantidad inválida (usa 1 o más para Rellenar)'
    return
  }
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

async function doSaveCategory() {
  const key = state.currentKey
  if (!key) return
  const cat = String(document.getElementById('imCategory')?.value || '').trim()
  const res = await state.backend.setProductCategory(key, cat)
  if (!res || !res.ok) {
    const err = document.getElementById('imError')
    err.hidden = false
    err.textContent = res?.error || 'No se pudo guardar la categoría'
    return
  }
  const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
  if (p) p.category = cat
  await loadCategories()
  renderGrid()
  alert('Categoría actualizada')
}

async function doSavePrice() {
  const key = state.currentKey
  if (!key) return
  const raw = String(document.getElementById('imPriceEdit')?.value || '').trim()
  const price = Number(raw)
  if (!Number.isFinite(price) || price < 0) {
    const err = document.getElementById('imError')
    err.hidden = false
    err.textContent = 'Precio inválido'
    return
  }
  const res = await state.backend.setProductPrice(key, price)
  if (!res || !res.ok) {
    const err = document.getElementById('imError')
    err.hidden = false
    err.textContent = res?.error || 'No se pudo guardar el precio'
    return
  }
  const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
  if (p) p.precio_final = Number(res.precio_final ?? price)
  openModal(key)
  renderGrid()
  alert('Precio actualizado correctamente')
}

async function doSaveInfo() {
  const key = state.currentKey
  if (!key) return
  const name = String(document.getElementById('imNameEdit')?.value || '').trim()
  const desc = String(document.getElementById('imDescEdit')?.value || '').trim()

  const err = document.getElementById('imError')
  if (err) { err.hidden = true; err.textContent = '' }

  if (!name) {
    if (err) { err.hidden = false; err.textContent = 'Nombre requerido' }
    return
  }

  if (!state.backend?.setProductInfo) {
    if (err) { err.hidden = false; err.textContent = 'Acción no disponible' }
    return
  }

  const res = await state.backend.setProductInfo(key, name, desc)
  if (!res || !res.ok) {
    if (err) { err.hidden = false; err.textContent = res?.error || 'No se pudo guardar' }
    return
  }

  const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
  if (p) { p.producto = name; p.descripcion = desc }
  openModal(key)
  renderGrid()
  alert('Información del producto actualizada')
}

async function doExportExcel() {
  if (!state.backend) return

  // Tablet-friendly: export to the last configured file.
  if (state.backend.exportExcelToLast) {
    const res = await state.backend.exportExcelToLast()
    if (res && res.ok) {
      const msg = res.target === 'Google Sheets' 
        ? `Exportado a Google Sheets (${res.exported || 0} productos)`
        : `Excel actualizado (${res.written || 0} filas)`
      return toast(msg)
    }
    return toast(res?.error || 'Export falló')
  }

  return toast('Export no disponible')
}

async function doImportExcel() {
  if (!state.backend || !state.backend.importExcel) return

  const confirmed = confirm('¿Importar productos desde Google Sheets?\n\nEsto actualizará tu inventario local.')
  if (!confirmed) return

  toast('Importando...')
  
  const res = await state.backend.importExcel()
  if (res && res.ok) {
    toast(`Importados ${res.imported || 0} productos desde ${res.source || 'Google Sheets'}`)
    // Recargar inventario
    await init()
  } else {
    toast(res?.error || 'Error al importar')
  }
}

async function doSyncSheets() {
  if (!state.backend) return

  const confirmed = confirm('Sincronizar con Google Sheets\n\n1. Importará productos desde la nube\n2. Exportará tu inventario actual\n\n¿Continuar?')
  if (!confirmed) return

  toast('Sincronizando...')

  // 1. Importar primero
  if (state.backend.importExcel) {
    const importRes = await state.backend.importExcel()
    if (importRes && importRes.ok) {
      toast(`Importados ${importRes.imported || 0} productos`)
      await init() // Recargar inventario
    } else {
      toast('Error al importar: ' + (importRes?.error || 'desconocido'))
      return
    }
  }

  // 2. Exportar después
  if (state.backend.exportExcelToLast) {
    const exportRes = await state.backend.exportExcelToLast()
    if (exportRes && exportRes.ok) {
      toast(`Sincronizado: ${exportRes.exported || 0} productos exportados`)
    } else {
      toast('Error al exportar: ' + (exportRes?.error || 'desconocido'))
    }
  }
}

async function doPickImage() {
  const key = state.currentKey
  if (!key) return

  // Web mode (tablet): upload file
  if (state.backend?.uploadProductImage) {
    const file = await pickFile('image/*')
    if (!file) return
    const res = await state.backend.uploadProductImage(key, file)
    if (!res || !res.ok) {
      const err = document.getElementById('imError')
      err.hidden = false
      err.textContent = res?.error || 'No se pudo cargar imagen'
      return
    }
    const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
    if (p) p.image_url = res.image_url || p.image_url
    openModal(key)
    renderGrid()
    toast('Imagen actualizada')
    return
  }

  // Desktop mode (pywebview): open OS file picker
  const res = await state.backend.pickProductImage(key)
  if (!res || !res.ok) {
    const err = document.getElementById('imError')
    err.hidden = false
    err.textContent = res?.error || 'No se pudo cargar imagen'
    return
  }
  const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
  if (p) p.image_url = res.image_url || p.image_url
  openModal(key)
  renderGrid()
  toast('Imagen actualizada')
}

async function doClearImage() {
  const key = state.currentKey
  if (!key) return
  const res = await state.backend.clearProductImage(key)
  if (!res || !res.ok) {
    const err = document.getElementById('imError')
    err.hidden = false
    err.textContent = res?.error || 'No se pudo quitar imagen'
    return
  }
  const p = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
  if (p) p.image_url = null
  openModal(key)
  renderGrid()
  toast('Imagen removida')
}

function openNewProductModal() {
  const m = document.getElementById('newProdModal')
  if (!m) return
  const err = document.getElementById('npError')
  if (err) { err.hidden = true; err.textContent = '' }
  document.getElementById('npName').value = ''
  document.getElementById('npDesc').value = ''
  document.getElementById('npPrice').value = ''
  document.getElementById('npStock').value = '0'
  document.getElementById('npCategory').value = ''
  m.hidden = false
  setTimeout(() => {
    const el = document.getElementById('npName')
    if (el) el.focus()
  }, 0)
}

function closeNewProductModal() {
  const m = document.getElementById('newProdModal')
  if (m) m.hidden = true
}

async function doCreateProduct() {
  const name = String(document.getElementById('npName')?.value || '').trim()
  const desc = String(document.getElementById('npDesc')?.value || '').trim()
  const cat = String(document.getElementById('npCategory')?.value || '').trim()
  const priceRaw = String(document.getElementById('npPrice')?.value || '').trim()
  const stockRaw = String(document.getElementById('npStock')?.value || '').trim()
  const price = priceRaw ? Number(priceRaw) : 0
  const stock = stockRaw ? Number(stockRaw) : 0

  const err = document.getElementById('npError')
  if (err) { err.hidden = true; err.textContent = '' }

  if (!name) {
    if (err) { err.hidden = false; err.textContent = 'Nombre requerido' }
    return
  }
  if (!Number.isFinite(price) || price < 0) {
    if (err) { err.hidden = false; err.textContent = 'Precio inválido' }
    return
  }
  if (!Number.isFinite(stock) || stock < 0) {
    if (err) { err.hidden = false; err.textContent = 'Stock inválido' }
    return
  }

  // Deshabilitar botón para evitar clicks múltiples
  const createBtn = document.getElementById('npCreate')
  if (createBtn) {
    createBtn.disabled = true
    createBtn.textContent = 'Creando...'
  }

  const res = await state.backend.createProduct(name, desc, price, Math.round(stock), cat)
  
  // Rehabilitar botón
  if (createBtn) {
    createBtn.disabled = false
    createBtn.textContent = 'Crear'
  }

  if (!res || !res.ok) {
    if (err) { err.hidden = false; err.textContent = res?.error || 'No se pudo crear producto' }
    return
  }

  // Cerrar modal INMEDIATAMENTE
  closeNewProductModal()
  
  // Mostrar confirmación clara
  alert('✅ Producto creado exitosamente')
  
  // Actualizar listas
  await loadCategories()
  await searchProducts()
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
  if (p) p.unidades = Number(res.unidades || 0)
  
  // Actualizar UI inmediatamente con el nuevo stock
  const stockEl = document.getElementById('imStock')
  const newStock = Number(res.unidades || 0)
  const stockClass = newStock <= 0 ? 'stockBad' : (newStock <= 2 ? 'stockLow' : 'stockOk')
  if (stockEl) {
    stockEl.textContent = String(newStock)
    stockEl.className = `stock ${stockClass}`
  }
  document.getElementById('imSetStock').value = String(newStock)
  
  renderGrid()
  toast('Stock actualizado')
}

async function findDuplicates() {
  if (!state.backend?.findDuplicates) {
    toast('Función no disponible en modo escritorio')
    return
  }

  const res = await state.backend.findDuplicates()
  if (!res || !res.ok) {
    toast('Error al buscar duplicados')
    return
  }

  if (!res.duplicates || res.duplicates.length === 0) {
    alert('✅ No se encontraron productos duplicados')
    return
  }

  const count = res.duplicates.reduce((sum, d) => sum + (d.count - 1), 0)
  const msg = `Se encontraron ${res.total} grupos de duplicados (${count} productos duplicados).\n\n¿Deseas eliminar los duplicados? Se mantendrá el primero de cada grupo.`
  
  if (confirm(msg)) {
    await deleteDuplicates()
  }
}

async function deleteDuplicates() {
  if (!state.backend?.deleteDuplicates) {
    toast('Función no disponible')
    return
  }

  const res = await state.backend.deleteDuplicates(true)
  if (!res || !res.ok) {
    toast('Error al eliminar duplicados')
    return
  }

  alert(`Eliminados ${res.deleted} productos duplicados`)
  await searchProducts()
}

async function doDeleteProduct() {
  const key = state.currentKey
  if (!key) return
  if (!state.backend?.deleteProduct) {
    const err = document.getElementById('imError')
    err.hidden = false
    err.textContent = 'Acción no disponible'
    return
  }

  const name = String(document.getElementById('imTitle')?.textContent || 'Producto')
  const confirmText = prompt(
    `Eliminar ${name} del inventario.\n\nEscribe ELIMINAR para confirmar:`,
    ''
  )
  if (!confirmText) return

  const res = await state.backend.deleteProduct(key, confirmText)
  if (!res || !res.ok) {
    const err = document.getElementById('imError')
    err.hidden = false
    err.textContent = res?.error || 'No se pudo eliminar'
    return
  }

  closeModal()
  await loadCategories()
  await searchProducts()
  alert('Producto eliminado correctamente')
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

  const btnOpenImages = document.getElementById('btnOpenImages')
  if (btnOpenImages) {
    btnOpenImages.addEventListener('click', async () => {
      if (!state.backend?.openImagesFolder) return
      const res = await state.backend.openImagesFolder()
      if (!res || !res.ok) toast(res?.error || 'No se pudo abrir carpeta de imágenes')
    })
  }

  const btnNewProduct = document.getElementById('btnNewProduct')
  if (btnNewProduct) btnNewProduct.addEventListener('click', openNewProductModal)

  const btnCleanDuplicates = document.getElementById('cleanDuplicatesBtn')
  if (btnCleanDuplicates) btnCleanDuplicates.addEventListener('click', findDuplicates)

  const btnSyncSheets = document.getElementById('btnSyncSheets')
  if (btnSyncSheets) btnSyncSheets.addEventListener('click', doSyncSheets)

  const btnImportExcel = document.getElementById('btnImportExcel')
  if (btnImportExcel) btnImportExcel.addEventListener('click', doImportExcel)

  const btnExportExcel = document.getElementById('btnExportExcel')
  if (btnExportExcel) btnExportExcel.addEventListener('click', doExportExcel)

  const grid = document.getElementById('invGrid')
  if (grid) grid.addEventListener('click', (e) => {
    const btn = e.target?.closest?.('button[data-open]')
    if (btn) { e.stopPropagation(); openModal(btn.getAttribute('data-open')); return }
    const card = e.target?.closest?.('.cardP')
    if (card && card.dataset.key) openModal(card.dataset.key)
  })

  document.getElementById('imClose').addEventListener('click', closeModal)
  document.getElementById('imSaveInfoBtn').addEventListener('click', doSaveInfo)
  document.getElementById('imRestockBtn').addEventListener('click', doRestock)
  document.getElementById('imSetStockBtn').addEventListener('click', doSetStock)
  document.getElementById('imSaveCatBtn').addEventListener('click', doSaveCategory)
  document.getElementById('imSavePriceBtn').addEventListener('click', doSavePrice)
  document.getElementById('imPickImg').addEventListener('click', doPickImage)
  document.getElementById('imClearImg').addEventListener('click', doClearImage)

  const del = document.getElementById('imDeleteProduct')
  if (del) del.addEventListener('click', doDeleteProduct)

  document.getElementById('npCancel').addEventListener('click', closeNewProductModal)
  document.getElementById('npCreate').addEventListener('click', doCreateProduct)
}

window.addEventListener('DOMContentLoaded', () => {
  init().catch((e) => {
    // eslint-disable-next-line no-console
    console.error(e)
    toast(String(e?.message || e || 'Error'))
  })
})
