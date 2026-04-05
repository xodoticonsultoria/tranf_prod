// =========================
// CSRF
// =========================
function getCSRFToken() {
  const token = document.querySelector('[name=csrfmiddlewaretoken]');
  return token ? token.value : "";
}

// =========================
// ADD PRODUCT
// =========================
function addProductWithQty(btn, productId) {

  if (!btn) return;

  const container = btn.closest(".x-prod");
  if (!container) return;

  const qtyInput = container.querySelector("input");
  let qty = parseInt(qtyInput?.value);

  if (isNaN(qty) || qty <= 0) qty = 1;

  // 🔥 trava botão (evita spam)
  btn.disabled = true;

  fetch("/q/add-product/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken()
    },
    body: JSON.stringify({
      product_id: productId,
      qty: qty
    })
  })
  .then(res => res.json())
  .then(data => {

    if (data.success) {

      // reset qty
      if (qtyInput) qtyInput.value = 1;

      // feedback visual
      btn.innerText = "✔";
      setTimeout(() => {
        btn.innerText = "SALVAR";
        btn.disabled = false;
      }, 800);

      // atualiza badge
      const badge = document.getElementById("cart-count");
      if (badge) {
        badge.style.display = "inline-block";
        badge.innerText = data.cart_total_items ?? 0;
      }

    } else {
      alert(data.error || "Erro ao adicionar produto");
      btn.disabled = false;
    }

  })
  .catch(err => {
    console.error(err);
    alert("Erro de conexão");
    btn.disabled = false;
  });
}

// =========================
// UPDATE ITEM
// =========================
function updateItem(input, itemId) {

  if (!input) return;

  let qty = parseInt(input.value);

  if (isNaN(qty) || qty < 0) qty = 0;

  fetch("/q/update-item/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken()
    },
    body: JSON.stringify({
      item_id: itemId,
      qty: qty
    })
  })
  .then(res => res.json())
  .then(data => {

    if (data.deleted) {
      const el = input.closest(".cart-item");
      if (el) el.remove();
    }

  })
  .catch(err => {
    console.error(err);
    alert("Erro ao atualizar item");
  });
}

// =========================
// REMOVE ITEM
// =========================
function removeItem(btn, itemId) {

  if (!btn) return;

  fetch("/q/remove-item/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken()
    },
    body: JSON.stringify({
      item_id: itemId
    })
  })
  .then(res => res.json())
  .then(data => {

    if (data.success) {
      const el = btn.closest(".cart-item");
      if (el) el.remove();
    } else {
      alert(data.error || "Erro ao remover item");
    }

  })
  .catch(err => {
    console.error(err);
    alert("Erro de conexão");
  });
}