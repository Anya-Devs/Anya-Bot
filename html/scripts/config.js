// scripts/configs.js
;// --- Bot Config ---
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

// --- Site Config ---
class AppConfig {
  constructor() {
    this.siteTitle = botConfig.botName;
    this.navLinks = [
      { name: "Home", href: "/homepage", activate: "scripts/homepage.js" },
      { name: "Dashboard", href: "/dashboard", activate: "scripts/dashboard.js" },
      { name: "Commands", href: "/commands", activate: "scripts/commands.js" },
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

// --- Layout Builder ---
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
    botAvatar.src = "https://cdn.discordapp.com/embed/avatars/0.png"; // default

    // Fetch avatar async, update when ready
    fetch(`https://discord.com/api/v10/applications/${botConfig.botId}/rpc`, {
      headers: { "Content-Type": "application/json" }
    })
      .then(r => r.ok ? r.json() : null)
      .then(botData => {
        if (botData && botData.icon) {
          botAvatar.src = `https://cdn.discordapp.com/app-icons/${botConfig.botId}/${botData.icon}.png?size=256`;
        }
      })
      .catch(err => console.error("Failed to fetch bot avatar:", err));

    logoContainer.append(botAvatar, logo);

    const nav = document.createElement("nav");
    nav.className = "nav";

    config.navLinks.forEach((link) => {
      const a = document.createElement("a");
      a.href = link.href;
      a.textContent = link.name;
      a.addEventListener("click", (e) => {
        e.preventDefault();
        LayoutElements.loadScript(link.activate);
      });
      nav.appendChild(a);
    });

    header.append(logoContainer, nav);
    return header;
  }

  static loadScript(src) {
    const existing = document.querySelector(`script[data-dynamic="true"]`);
    if (existing) existing.remove();

    const script = document.createElement("script");
    script.src = src;
    script.dataset.dynamic = "true";
    script.defer = true;
    document.body.appendChild(script);
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
    config.features.forEach((f) => {
      const div = document.createElement("div");
      div.className = "feature";
      div.innerHTML = `
        <h3>${f.title}</h3>
        <p>${f.desc} ${f.comingSoon ? '<span class="coming-soon">Coming Soon</span>' : ''}</p>
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

// --- Safe global assignment ---
if (typeof window !== "undefined") {
  window.botConfig = botConfig;
  window.AppConfig = AppConfig;
  window.LayoutElements = LayoutElements;
}
