function toggleCat(id){
 const el=document.getElementById("cat-body-"+id);
 if(!el) return;
 const open = el.style.display==="block";
 el.style.display = open?"none":"block";
 if(!open){localStorage.setItem("cat_open_"+id,"1")}
 else{localStorage.removeItem("cat_open_"+id)}
}

document.addEventListener("DOMContentLoaded", ()=>{
 document.querySelectorAll(".cat-body").forEach(el=>{
   const id = el.id.replace("cat-body-","");
   if(localStorage.getItem("cat_open_"+id)){
     el.style.display="block";
   }
 });
});

function inc(btn){
 const i=btn.parentNode.querySelector("input");
 i.value=parseInt(i.value||0)+1;
}

function dec(btn){
 const i=btn.parentNode.querySelector("input");
 i.value=Math.max(1,parseInt(i.value||1)-1);
}
