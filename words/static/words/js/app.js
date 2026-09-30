const logoutForm = document.getElementById("logout-form");
logoutForm?.addEventListener("submit", () => {
  try {
    for (const key of Object.keys(sessionStorage)) {
      if (key.startsWith("voca-quiz:")) sessionStorage.removeItem(key);
    }
  } catch {
    /* Storage is optional. */
  }
});
window.addEventListener("pageshow", (event) => {
  if (event.persisted) window.location.reload();
});
const bars = [...document.querySelectorAll("[data-chart-value]")];
const maximum = Math.max(
  1,
  ...bars.map((bar) => Number(bar.dataset.chartValue)),
);
for (const bar of bars)
  bar.style.height = `${(Number(bar.dataset.chartValue) / maximum) * 100}%`;
