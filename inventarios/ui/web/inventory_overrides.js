(() => {
  'use strict'

  let lastOpenedKey = ''

  function getEl(id) {
    return document.getElementById(id)
  }

  function hardHideModal(id) {
    const m = getEl(id)
    if (!m) return
    m.hidden = true
    try { m.setAttribute('hidden', '') } catch (e) { /* ignore */ }
    // Ensure no lingering inline display overrides keep it visible
    try { m.style.removeProperty('display') } catch (e) { /* ignore */ }
  }

  function hardShowModal(id) {
    const m = getEl(id)
    if (!m) return
    m.hidden = false
    try { m.removeAttribute('hidden') } catch (e) { /* ignore */ }
    try { m.style.removeProperty('display') } catch (e) { /* ignore */ }
  }

  function safeToast(msg) {
    try {
      if (typeof window.toast === 'function') window.toast(msg)
    } catch (e) { /* ignore */ }
  }

  function safeAlert(msg) {
    try { window.alert(msg) } catch (e) { /* ignore */ }
  }

  async function httpJson(method, path, body) {
    const opt = { method, headers: {} }
    if (body !== undefined && body !== null) {
      opt.headers['Content-Type'] = 'application/json'
      opt.body = JSON.stringify(body)
    }
    const res = await fetch(path, opt)
    const txt = await res.text()
    let data
    try { data = txt ? JSON.parse(txt) : null } catch (e) { data = null }
    if (!res.ok) {
      const msg = (data && data.error) ? data.error : (`HTTP ${res.status}`)
      throw new Error(msg)
    }
    return data
  }

  function stopAll(e) {
    e.preventDefault()
    e.stopPropagation()
    // stopImmediatePropagation exists on Event
    if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation()
  }

  async function refreshInventoryQuiet() {
    // Preferimos usar el refresco nativo (mantiene state.products correcto)
    try {
      const btn = getEl('btnRefreshInv')
      if (btn) btn.click()
    } catch (e) { /* ignore */ }
  }

  async function handleCreateProduct() {
    const name = String(getEl('npName')?.value || '').trim()
    const desc = String(getEl('npDesc')?.value || '').trim()
    const cat = String(getEl('npCategory')?.value || '').trim()
    const priceRaw = String(getEl('npPrice')?.value || '').trim()
    const stockRaw = String(getEl('npStock')?.value || '').trim()

    const err = getEl('npError')
    if (err) { err.hidden = true; err.textContent = '' }

    if (!name) {
      if (err) { err.hidden = false; err.textContent = 'Nombre requerido' }
      return
    }

    const precio = priceRaw ? Number(priceRaw) : 0
    const unidades = stockRaw ? Number(stockRaw) : 0

    if (!Number.isFinite(precio) || precio < 0) {
      if (err) { err.hidden = false; err.textContent = 'Precio inválido' }
      return
    }
    if (!Number.isFinite(unidades) || unidades < 0) {
      if (err) { err.hidden = false; err.textContent = 'Stock inválido' }
      return
    }

    // Igual que eliminar: toast de proceso + cerrar modal SI O SI + alert final
    safeToast('Procesando...')

    try {
      await httpJson('POST', '/api/createProduct', {
        producto: name,
        descripcion: desc,
        precio_final: precio,
        unidades: Math.round(unidades),
        category: cat,
      })

      hardHideModal('newProdModal')
      await refreshInventoryQuiet()
      safeAlert(`Producto "${name}" creado correctamente`)
    } catch (e) {
      safeAlert('Error al crear: ' + (e?.message || e))
    }
  }

  async function handleSaveProduct() {
    const key = String(lastOpenedKey || '').trim()
    if (!key) return

    const name = String(getEl('imNameEdit')?.value || '').trim()
    const desc = String(getEl('imDescEdit')?.value || '').trim()
    const cat = String(getEl('imCategory')?.value || '').trim()
    const priceRaw = String(getEl('imPriceEdit')?.value || '').trim()
    const stockRaw = String(getEl('imSetStock')?.value || '').trim()

    const err = getEl('imError')
    if (err) { err.hidden = true; err.textContent = '' }

    if (!name) {
      if (err) { err.hidden = false; err.textContent = 'Nombre requerido' }
      return
    }

    const precio = priceRaw ? Number(priceRaw) : 0
    const unidades = stockRaw ? Number(stockRaw) : 0

    if (!Number.isFinite(precio) || precio < 0) {
      if (err) { err.hidden = false; err.textContent = 'Precio inválido' }
      return
    }
    if (!Number.isFinite(unidades) || unidades < 0) {
      if (err) { err.hidden = false; err.textContent = 'Stock inválido' }
      return
    }

    safeToast('Procesando...')

    try {
      // Guardamos TODO (sin complicaciones ni dependencias con state/products)
      await Promise.all([
        httpJson('POST', '/api/setProductInfo', { key, producto: name, descripcion: desc }),
        httpJson('POST', '/api/setProductPrice', { key, precio_final: precio }),
        httpJson('POST', '/api/setProductCategory', { key, category: cat }),
        httpJson('POST', '/api/setProductStock', { key, stock: Math.round(unidades), notes: '' }),
      ])

      // Cerrar el modal SI O SI como en eliminar
      try {
        if (typeof window.closeModal === 'function') window.closeModal()
        else hardHideModal('invModal')
      } catch (e) {
        hardHideModal('invModal')
      }

      await refreshInventoryQuiet()
      safeAlert(`Producto "${name}" actualizado correctamente`)
    } catch (e) {
      safeAlert('Error al guardar: ' + (e?.message || e))
    }
  }

  function wire() {
    // Evita el problema de "display:none" persistente si alguien lo dejó así.
    hardShowModal('newProdModal')
    hardHideModal('newProdModal')

    // Capturar el key del producto que se está abriendo (sin depender de state.currentKey)
    const grid = getEl('invGrid')
    if (grid) {
      grid.addEventListener('click', (e) => {
        try {
          const btn = e.target?.closest?.('button[data-open]')
          if (btn) {
            lastOpenedKey = String(btn.getAttribute('data-open') || '').trim()
            return
          }
          const card = e.target?.closest?.('.cardP')
          if (card && card.dataset && card.dataset.key) {
            lastOpenedKey = String(card.dataset.key || '').trim()
          }
        } catch (err) { /* ignore */ }
      }, true)
    }

    const createBtn = getEl('npCreate')
    if (createBtn) {
      createBtn.addEventListener('click', (e) => {
        stopAll(e)
        handleCreateProduct()
      }, true)
    }

    // Enter = crear (sin tener que tocar el botón)
    for (const id of ['npName', 'npDesc', 'npPrice', 'npStock', 'npCategory']) {
      const el = getEl(id)
      if (!el) continue
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          stopAll(e)
          handleCreateProduct()
        }
      }, true)
    }

    const saveBtn = getEl('imSaveBtn')
    if (saveBtn) {
      saveBtn.addEventListener('click', (e) => {
        stopAll(e)
        handleSaveProduct()
      }, true)
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    // Se engancha al final para no romper el renderizado de productos.
    try { wire() } catch (e) { /* ignore */ }
  })
})()
