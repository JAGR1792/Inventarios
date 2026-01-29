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
    exportGoogleSheets: () => httpJson('POST', '/api/exportGoogleSheets', {}),
    importGoogleSheets: () => httpJson('POST', '/api/importGoogleSheets', {}),
    syncGoogleSheets: () => httpJson('POST', '/api/syncGoogleSheets', {}),
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
  document.getElementById('imSetStock').value = String(stock)
  document.getElementById('imHint').textContent = 'Ajusta el stock al valor correcto.'

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
  toast('Categoría actualizada')
}

async function doSaveAllChanges() {
  const key = state.currentKey
  if (!key) return

  // Recopilar todos los cambios
  const name = String(document.getElementById('imNameEdit')?.value || '').trim()
  const desc = String(document.getElementById('imDescEdit')?.value || '').trim()
  const cat = String(document.getElementById('imCategory')?.value || '').trim()
  const priceRaw = String(document.getElementById('imPriceEdit')?.value || '').trim()
  const stockRaw = String(document.getElementById('imSetStock')?.value || '').trim()
  const price = priceRaw ? Number(priceRaw) : 0
  const stock = Math.max(0, Number(stockRaw || 0))

  const err = document.getElementById('imError')
  if (err) { err.hidden = true; err.textContent = '' }

  // Validaciones
  if (!name) {
    if (err) { err.hidden = false; err.textContent = 'Nombre requerido' }
    return
  }
  if (!Number.isFinite(price) || price < 0) {
    if (err) { err.hidden = false; err.textContent = 'Precio inválido' }
    return
  }

  // Deshabilitar botón durante guardado
  const saveBtn = document.getElementById('imSaveBtn')
  if (saveBtn) {
    saveBtn.disabled = true
    saveBtn.textContent = 'Guardando...'
  }

  try {
    // Ejecutar cambios en paralelo donde sea posible
    const promises = []

    // Si nombre o descripción cambiaron
    const origProduct = state.products.find((x) => String(x.key ?? '').trim() === String(key ?? '').trim())
    if (origProduct && (name !== origProduct.producto || desc !== origProduct.descripcion)) {
      promises.push(
        state.backend.setProductInfo(key, name, desc).then(res => {
          if (res?.ok && origProduct) {
            origProduct.producto = name
            origProduct.descripcion = desc
            document.getElementById('imTitle').textContent = name || 'Producto'
            document.getElementById('imDesc').textContent = desc || ''
          }
          return res
        })
      )
    }

    // Si precio cambió
    if (origProduct && price !== origProduct.precio_final) {
      promises.push(
        state.backend.setProductPrice(key, price).then(res => {
          if (res?.ok && origProduct) {
            origProduct.precio_final = Number(res.precio_final ?? price)
            document.getElementById('imPrice').textContent = `$${fmtMoney(Number(res.precio_final ?? price))}`
          }
          return res
        })
      )
    }

    // Si categoría cambió
    if (origProduct && cat !== origProduct.category) {
      promises.push(
        state.backend.setProductCategory(key, cat).then(res => {
          if (res?.ok && origProduct) {
            origProduct.category = cat
          }
          return res
        })
      )
    }

    // Si stock cambió
    if (origProduct && stock !== origProduct.unidades) {
      const notes = 'ajuste desde edición'
      promises.push(
        state.backend.setProductStock(key, stock, notes).then(res => {
          if (res?.ok && origProduct) {
            origProduct.unidades = Number(res.unidades || 0)
            const newStock = Number(res.unidades || 0)
            const stockClass = newStock <= 0 ? 'stockBad' : (newStock <= 2 ? 'stockLow' : 'stockOk')
            const stockEl = document.getElementById('imStock')
            if (stockEl) {
              stockEl.textContent = String(newStock)
              stockEl.className = `stock ${stockClass}`
            }
            document.getElementById('imSetStock').value = String(newStock)
          }
          return res
        })
      )
    }

    // Si no hay cambios, mostrar mensaje
    if (promises.length === 0) {
      toast('Sin cambios para guardar')
      if (saveBtn) {
        saveBtn.disabled = false
        saveBtn.textContent = 'Guardar cambios'
      }
      return
    }

    // Esperar a que todos se completen
    const results = await Promise.all(promises)

    // Verificar si hay errores
    const hasError = results.some(res => !res || !res.ok)
    if (hasError) {
      const firstError = results.find(res => !res || !res.ok)
      if (err) {
        err.hidden = false
        err.textContent = firstError?.error || 'Error al guardar algunos cambios'
      }
      if (saveBtn) {
        saveBtn.disabled = false
        saveBtn.textContent = 'Guardar cambios'
      }
      return
    }

    // Éxito
    await loadCategories()
    renderGrid()
    toast('✅ Cambios guardados exitosamente')

  } catch (e) {
    if (err) {
      err.hidden = false
      err.textContent = 'Error: ' + (e?.message || e)
    }
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false
      saveBtn.textContent = 'Guardar cambios'
    }
  }
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
  
  // Actualizar display sin re-abrir modal
  document.getElementById('imPrice').textContent = `$${fmtMoney(Number(res.precio_final ?? price))}`
  
  renderGrid()
  toast('Precio actualizado')
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
  
  // Actualizar display sin re-abrir modal
  document.getElementById('imTitle').textContent = name || 'Producto'
  document.getElementById('imDesc').textContent = desc || ''
  
  renderGrid()
  toast('Información del producto actualizada')
}

async function doExportGoogleSheets() {
  if (!state.backend) return

  toast('Exportando a Google Sheets...')
  
  try {
    const res = await state.backend.exportGoogleSheets()
    if (res && res.ok) {
      const count = res.exported || res.written || 0
      alert(`Exportado exitosamente\n\n${count} productos guardados en Google Sheets`)
      return
    }
    alert('Error al exportar: ' + (res?.error || 'Error desconocido'))
  } catch (e) {
    alert('Error al exportar: ' + (e?.message || e))
  }
}

async function doImportGoogleSheets() {
  if (!state.backend || !state.backend.importGoogleSheets) {
    alert('Función no disponible')
    return
  }

  const confirmed = confirm('¿Importar productos desde Google Sheets?\n\nEsto actualizará tu inventario local.')
  if (!confirmed) return

  toast('Importando desde Google Sheets...')
  
  try {
    const res = await state.backend.importGoogleSheets()
    if (res && res.ok) {
      alert(`Importación exitosa\n\n${res.imported || 0} productos importados desde ${res.source || 'Google Sheets'}`)
      await searchProducts()
    } else {
      alert('Error al importar: ' + (res?.error || 'Error desconocido'))
    }
  } catch (e) {
    alert('Error al importar: ' + (e?.message || e))
  }
}

async function doSyncSheets() {
  if (!state.backend) return

  const confirmed = confirm('Sincronizar con Google Sheets\n\n1. Importará productos desde la nube\n2. Exportará tu inventario actual\n\n¿Continuar?')
  if (!confirmed) return

  toast('Sincronizando con Google Sheets...')

  try {
    // Usar endpoint de sincronización si existe
    if (state.backend.syncGoogleSheets) {
      const res = await state.backend.syncGoogleSheets()
      if (res && res.ok) {
        alert(`Sincronización exitosa\n\nImportados: ${res.imported || 0} productos\nExportados: ${res.exported || 0} productos`)
        await searchProducts()
        return
      }
      alert('Error en sincronización: ' + (res?.error || 'Error desconocido'))
      return
    }

    // Fallback: importar y exportar por separado
    const importRes = await state.backend.importGoogleSheets()
    if (!importRes || !importRes.ok) {
      alert('Error al importar: ' + (importRes?.error || 'Error desconocido'))
      return
    }
    
    await searchProducts()
    
    const exportRes = await state.backend.exportGoogleSheets()
    if (exportRes && exportRes.ok) {
      alert(`Sincronización exitosa\n\nImportados: ${importRes.imported || 0} productos\nExportados: ${exportRes.exported || 0} productos`)
    } else {
      alert('Importación exitosa, pero hubo error al exportar: ' + (exportRes?.error || 'Error desconocido'))
    }
  } catch (e) {
    alert('Error en sincronización: ' + (e?.message || e))
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
  if (m) {
    m.hidden = true
    m.style.display = 'none'
  }
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

  // Mostrar toast ANTES de cerrar para que sea visible
  toast('✅ Producto creado exitosamente')
  
  // Cerrar modal inmediatamente
  closeNewProductModal()
  
  // Actualizar listas en background
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
    alert('Función no disponible')
    return
  }

  toast('Eliminando duplicados...')
  
  try {
    const res = await state.backend.deleteDuplicates(true)
    if (!res || !res.ok) {
      alert('Error al eliminar duplicados: ' + (res?.error || 'Error desconocido'))
      return
    }

    alert(`Eliminados ${res.deleted} productos duplicados`)
    await searchProducts()
  } catch (e) {
    alert('Error al eliminar duplicados: ' + (e?.message || e))
  }
}

async function doCleanDuplicates() {
  if (!state.backend) return
  
  // Primero buscar cuántos duplicados hay
  toast('Buscando duplicados...')
  
  try {
    let res
    if (state.backend.findDuplicates) {
      res = await state.backend.findDuplicates()
    } else {
      // Fallback: usar el endpoint directo
      res = await fetch('/api/findDuplicates').then(r => r.json())
    }
    
    if (!res || !res.ok) {
      alert('Error al buscar duplicados: ' + (res?.error || 'Error desconocido'))
      return
    }
    
    const total = res.total || 0
    if (total === 0) {
      alert('No se encontraron productos duplicados')
      return
    }
    
    const confirmed = confirm(
      `Se encontraron ${total} grupos de productos duplicados.\n\n` +
      `Se conservará el primero de cada grupo y se eliminarán los demás.\n\n` +
      `¿Deseas continuar?`
    )
    
    if (!confirmed) return
    
    toast('Eliminando duplicados...')
    await deleteDuplicates()
    
  } catch (e) {
    alert('Error: ' + (e?.message || e))
  }
}

async function doDeleteProduct() {
  const key = state.currentKey
  if (!key) return
  if (!state.backend?.deleteProduct) {
    alert('Función de eliminar no disponible')
    return
  }

  const name = String(document.getElementById('imTitle')?.textContent || 'Producto')
  const confirmText = prompt(
    `Eliminar "${name}" del inventario.\n\nEscribe ELIMINAR para confirmar:`,
    ''
  )
  if (!confirmText) return

  // Mostrar que está procesando
  toast('Eliminando producto...')
  
  try {
    const res = await state.backend.deleteProduct(key, confirmText)
    if (!res || !res.ok) {
      alert('Error: ' + (res?.error || 'No se pudo eliminar el producto'))
      return
    }

    closeModal()
    await loadCategories()
    await searchProducts()
    alert(`Producto "${name}" eliminado correctamente`)
  } catch (e) {
    alert('Error al eliminar: ' + (e?.message || e))
  }
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

  const btnSyncSheets = document.getElementById('btnSyncSheets')
  if (btnSyncSheets) btnSyncSheets.addEventListener('click', doSyncSheets)

  const btnImportSheets = document.getElementById('btnImportSheets')
  if (btnImportSheets) btnImportSheets.addEventListener('click', doImportGoogleSheets)

  const btnExportSheets = document.getElementById('btnExportSheets')
  if (btnExportSheets) btnExportSheets.addEventListener('click', doExportGoogleSheets)

  const btnCleanDuplicates = document.getElementById('btnCleanDuplicates')
  if (btnCleanDuplicates) btnCleanDuplicates.addEventListener('click', doCleanDuplicates)

  const grid = document.getElementById('invGrid')
  if (grid) grid.addEventListener('click', (e) => {
    const btn = e.target?.closest?.('button[data-open]')
    if (btn) { e.stopPropagation(); openModal(btn.getAttribute('data-open')); return }
    const card = e.target?.closest?.('.cardP')
    if (card && card.dataset.key) openModal(card.dataset.key)
  })

  document.getElementById('imClose').addEventListener('click', closeModal)
  document.getElementById('imSaveBtn').addEventListener('click', doSaveAllChanges)
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
