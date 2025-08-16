// scripts/homepage.js
/// Test: alert("Homepage script loaded");


document.addEventListener("DOMContentLoaded", () => {
  const appConfig = new AppConfig();
  const header = LayoutElements.createHeader(appConfig);
  const hero = LayoutElements.createHero(appConfig);
  const features = LayoutElements.createFeatures(appConfig);
  const footer = LayoutElements.createFooter(appConfig);

  const root = document.getElementById("root") || document.body;
  root.append(header, hero, features, footer);

  const ctaBtn = hero.querySelector(".cta");
  if (ctaBtn) {
    ctaBtn.addEventListener("click", () => {
      window.location.href = "/dashboard";
    });
  }
});
