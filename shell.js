function keepCurrentNavigationVisible() {
  const navigation = document.querySelector(".nav-list");
  const current = navigation?.querySelector(".is-active");
  if (!navigation || !current || window.innerWidth > 700) return;
  const centeredLeft = current.offsetLeft - (navigation.clientWidth - current.offsetWidth) / 2;
  navigation.scrollTo({ left: Math.max(0, centeredLeft), behavior: "auto" });
}

window.addEventListener("DOMContentLoaded", keepCurrentNavigationVisible);
window.addEventListener("resize", keepCurrentNavigationVisible);
