document.addEventListener("DOMContentLoaded", function(){

  // restore categories
  document.querySelectorAll(".cat-body").forEach(el=>{
    const id = el.id.replace("cat-body-","");
    if(localStorage.getItem("cat_open_"+id)){
      el.style.display = "block";
    }
  });

});
