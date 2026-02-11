function toggleCat(id){
  const el = document.getElementById("cat-"+id);
  el.style.display = el.style.display==="none" ? "block" : "none";
}

function inc(btn){
  const i = btn.parentNode.querySelector("input");
  i.value = parseInt(i.value||1)+1;
}

function dec(btn){
  const i = btn.parentNode.querySelector("input");
  i.value = Math.max(1, parseInt(i.value||1)-1);
}
