// static/js/main.js
document.addEventListener("DOMContentLoaded", function(){
  // small button ripple for vote buttons
  document.querySelectorAll(".btn-esc, .ripple").forEach(btn=>{
    btn.addEventListener("click", function(e){
      let circle = document.createElement("span");
      circle.classList.add("ripple-circle");
      const rect = this.getBoundingClientRect();
      circle.style.left = (e.clientX - rect.left) + "px";
      circle.style.top = (e.clientY - rect.top) + "px";
      this.appendChild(circle);
      setTimeout(()=> circle.remove(), 600);
    });
  });
});
