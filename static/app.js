function toggleCat(id){
  const el=document.getElementById("cat-body-"+id);
  if(!el) return;

  const open = el.style.display==="block";
  el.style.display = open?"none":"block";

  if(!open){
    localStorage.setItem("cat_open_"+id,"1");
  } else {
    localStorage.removeItem("cat_open_"+id);
  }
}

function inc(btn){
  const input = btn.parentNode.querySelector("input");
  input.value = parseInt(input.value||0)+1;
}

function dec(btn){
  const input = btn.parentNode.querySelector("input");
  input.value = Math.max(1,parseInt(input.value||1)-1);
}

document.addEventListener("DOMContentLoaded",()=>{
  document.querySelectorAll(".x-cat-body").forEach(el=>{
    const id = el.id.replace("cat-body-","");
    if(localStorage.getItem("cat_open_"+id)){
      el.style.display="block";
    }
  });
});
