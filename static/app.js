function toggleCat(id){
 const el=document.getElementById("cat-body-"+id);
 if(!el) return;
 el.style.display = el.style.display==="block"?"none":"block";
}
