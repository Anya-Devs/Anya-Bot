// =========================
// 🌐 Bot Config
// =========================
const botConfig = {
  botName: "Anya Bot",
  botId: "1234247716243112100",
  description: "A Discord bot that helps manage your server and provides fun features.",
  inviteLink: "https://discord.com/oauth2/authorize?client_id=1234247716243112100&scope=bot&permissions=8",
  supportServer: "https://discord.com/oauth2/authorize?client_id=1234247716243112100&permissions=1689934541355072&integration_type=0&scope=bot",
  redirectUri: "http://127.0.0.1:5500/auth/callback",
  features: [
    "Quest system",
    "Fun commands",
    "Poketwo Helper",
    "Music playback",
    "Moderation tools",
    "Minigames",
  ],
};

// =========================
// Site Config
// =========================
class AppConfig {
  constructor() {
    this.siteTitle = botConfig.botName;
    this.navLinks = [
      { name: "Home", script: "scripts/homepage.js" },
      { name: "Dashboard", script: "scripts/dashboard.js" },
      { name: "Commands", script: null }, // handled inline
    ];
    this.hero = {
      title: "👋",
      subtitle: "Anya ventures into your server with multiple tools and quests to engage members, bringing communities closer together.",
      buttonText: "Get Started",
      inviteText: "Invite Bot"
    };
    this.features = [
      { title: "Poketwo Helper", desc: "Automatically names Poketwo Pokémon and provides Dex information." },
      { title: "User Engagement", desc: "Quests that get members chatting, using emojis, and making friends while earning rewards." },
      { title: "Moderation", desc: "Kick, ban, warn, and manage your server with ease.", comingSoon: true },
      { title: "Fun Commands", desc: "Roll dice, hug members, gamble, and more." },
      { title: "Music", desc: "Play music from YouTube and other sources.", comingSoon: true },
    ];
    this.footer = "© 2025 Anya Bot. All rights reserved.";
  }
}

// =========================
// Layout Elements
// =========================
class LayoutElements {
  static createHeader(config) {
    const header = document.createElement("header");
    header.className = "header";

    const logoContainer = document.createElement("div");
    logoContainer.className = "logo-container";

    const logo = document.createElement("h1");
    logo.className = "logo";
    logo.textContent = config.siteTitle;

    const botAvatar = document.createElement("img");
    botAvatar.className = "bot-avatar";
    botAvatar.alt = `${config.siteTitle} Avatar`;
    botAvatar.src = "https://cdn.discordapp.com/embed/avatars/0.png";

    // --- FAVICON SETUP ---
    const favicon =
      document.querySelector("link[rel*='icon']") || document.createElement("link");
    favicon.rel = "icon";
    favicon.type = "image/png";
    favicon.href = "https://cdn.discordapp.com/embed/avatars/0.png";
    if (!document.querySelector("link[rel*='icon']")) {
      document.head.appendChild(favicon);
    }
    // --- /FAVICON SETUP ---

    fetch(`https://discord.com/api/v10/applications/${botConfig.botId}/rpc`)
      .then(r => (r.ok ? r.json() : null))
      .then(botData => {
        if (botData && botData.icon) {
          const url = `https://cdn.discordapp.com/app-icons/${botConfig.botId}/${botData.icon}.png?size=256`;
          botAvatar.src = url;
          favicon.href = url; // update tab icon too
        }
      })
      .catch(err => console.warn("[Debug] Failed to fetch bot avatar / favicon:", err));

    logoContainer.append(botAvatar, logo);

    const nav = document.createElement("nav");
    nav.className = "nav";

    config.navLinks.forEach(link => {
      const a = document.createElement("a");
      a.href = "javascript:void(0)";
      a.textContent = link.name;
      a.addEventListener("click", async e => {
        e.preventDefault();
        const zone = document.getElementById("dynamic-zone");
        zone.replaceChildren();

        if (link.name === "Commands") {
          await CommandsPage.render("dynamic-zone");
        } else if (link.script) {
          await PageLoader.loadPage(link.script, "dynamic-zone");
        }
      });
      nav.appendChild(a);
    });

    header.append(logoContainer, nav);
    return header;
  }

  static createHero(config) {
    const hero = document.createElement("section");
    hero.className = "hero";
    hero.innerHTML = `
      <h2>${config.hero.title}</h2>
      <p>${config.hero.subtitle}</p>
      <div class="hero-buttons">
        <button class="cta">${config.hero.buttonText}</button>
        <a href="${botConfig.inviteLink}" target="_blank" class="cta">${config.hero.inviteText}</a>
      </div>
    `;
    return hero;
  }

  static createFeatures(config) {
    const features = document.createElement("section");
    features.className = "features";
    config.features.forEach(f => {
      const div = document.createElement("div");
      div.className = "feature";
      div.innerHTML = `
        <h3>${f.title}</h3>
        <p>${f.desc} ${f.comingSoon ? '<span class="coming-soon">Coming Soon</span>' : ""}</p>
      `;
      features.appendChild(div);
    });
    return features;
  }

  static createFooter(config) {
    const footer = document.createElement("footer");
    footer.className = "footer";
    footer.innerHTML = `<p>${config.footer}</p>`;
    return footer;
  }
}

// =========================
// Page Loader
// =========================
class PageLoader {
  static async loadPage(scriptPath, containerId = "dynamic-zone") {
    const container = document.getElementById(containerId);
    if (!container) return;

    const existing = document.querySelector(`script[data-dynamic="true"]`);
    if (existing) existing.remove();

    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = scriptPath;
      script.dataset.dynamic = "true";
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = err => reject(err);
      document.body.appendChild(script);
    });
  }

  static loadCSS(cssPath) {
    if (!cssPath) return;
    const existing = document.querySelector(`link[data-dynamic="true"]`);
    if (existing) existing.remove();
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = cssPath;
    link.dataset.dynamic = "true";
    document.head.appendChild(link);
  }
}

// =========================
// Commands Page (Inline)
// =========================
class CommandsPage {
  static async loadCommands(jsonPath = "html/data/pages/commands.json") {
    try {
      const res = await fetch(jsonPath);
      if (!res.ok) throw new Error("Failed to fetch commands JSON");
      const data = await res.json();
      return data.cogs || {};
    } catch {
      return {};
    }
  }

  static createSidebar(cogs) {
    const sidebar = document.createElement("aside");
    sidebar.className = "sidebar";
    Object.keys(cogs).forEach(cogName => {
      const cogLink = document.createElement("a");
      cogLink.href = `#${cogName}`;
      cogLink.textContent = cogName;
      sidebar.appendChild(cogLink);
    });
    return sidebar;
  }

  static createCommandSection(cogName, commands) {
    const section = document.createElement("section");
    section.className = "cog-section";
    section.id = cogName;

    const title = document.createElement("h2");
    title.textContent = cogName;
    section.appendChild(title);

    commands.forEach(cmd => {
      const cmdDiv = document.createElement("div");
      cmdDiv.className = "command";

      const args = cmd.args ? ` ${cmd.args}` : "";
      const cmdTitle = document.createElement("h3");
      cmdTitle.textContent = cmd.name + args;
      cmdDiv.appendChild(cmdTitle);

      const desc = document.createElement("p");
      desc.textContent = cmd.description;
      cmdDiv.appendChild(desc);

      if (cmd.examples?.length) {
        const examples = document.createElement("ul");
        examples.className = "examples";
        cmd.examples.forEach(ex => {
          const li = document.createElement("li");
          li.textContent = `${ex.usage} → ${ex.description}`;
          examples.appendChild(li);
        });
        cmdDiv.appendChild(examples);
      }

      section.appendChild(cmdDiv);
    });

    return section;
  }

  static async render(containerId = "dynamic-zone") {
    const zone = document.getElementById(containerId);
    if (!zone) return;

    const cogs = await CommandsPage.loadCommands();
    if (!Object.keys(cogs).length) return;

    const wrapper = document.createElement("div");
    wrapper.className = "commands-wrapper dynamic-section";

    const sidebar = CommandsPage.createSidebar(cogs);
    wrapper.appendChild(sidebar);

    const content = document.createElement("div");
    content.className = "commands-content";

    Object.entries(cogs).forEach(([cogName, commands]) => {
      const section = CommandsPage.createCommandSection(cogName, commands);
      content.appendChild(section);
    });

    wrapper.appendChild(content);
    zone.appendChild(wrapper);
  }
}

// =========================
// Initialize Page
// =========================
window.addEventListener("DOMContentLoaded", async () => {
  // 1. Ensure container
  let container = document.getElementById("app");
  if (!container) {
    container = document.createElement("div");
    container.id = "app";
    document.body.appendChild(container);
  }

  // 2. One-time layout injection
  if (!container.hasAttribute("data-layout-mounted")) {
    const cfg = new AppConfig();
    container.append(
      LayoutElements.createHeader(cfg),
      LayoutElements.createHero(cfg),
      LayoutElements.createFeatures(cfg)
    );

    // create the **only** dynamic zone
    const dynamic = document.createElement("main");
    dynamic.id = "dynamic-zone";
    container.append(dynamic, LayoutElements.createFooter(cfg));

    container.setAttribute("data-layout-mounted", "true");
  }

  // 3. Load commands immediately
  const zone = document.getElementById("dynamic-zone");
  await CommandsPage.render(zone.id);
});

// =========================
// Safe Global Assignment
// =========================
if (typeof window !== "undefined") {
  window.botConfig = botConfig;
  window.AppConfig = AppConfig;
  window.LayoutElements = LayoutElements;
  window.PageLoader = PageLoader;
  window.CommandsPage = CommandsPage;
}