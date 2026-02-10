function toggleCat(id){
const el=document.getElementById("cat-body-"+id)
if(!el) return
el.style.display = el.style.display==="block"?"none":"block"
}

/* badge realtime Austin */

function checkBadge(){
fetch("/austin/api/badge/")
.then(r=>r.json())
.then(d=>{
const b=document.getElementById("badgeAustin")
if(b) b.innerText=d.count
})
}

setInterval(checkBadge,8000)
