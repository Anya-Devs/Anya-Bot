import { botConfig } from './config.js';

/**
 * Layout elements creator
 */
export class LayoutElements {
  static createHeader(config) {
    const header = document.createElement('header');
    header.className = 'header';
    
    // Logo container
    const logoContainer = document.createElement('div');
    logoContainer.className = 'logo-container';
    
    const botAvatar = document.createElement('img');
    botAvatar.className = 'bot-avatar';
    botAvatar.alt = 'Bot Avatar';
    
    const logo = document.createElement('h1');
    logo.className = 'logo';
    logo.textContent = config.siteTitle;
    
    // Fetch bot avatar
    const favicon = document.getElementById('favicon');
    fetch(`https://discord.com/api/v10/applications/${botConfig.botId}/rpc`)
      .then(r => (r.ok ? r.json() : null))
      .then(botData => {
        if (botData && botData.icon) {
          const url = `https://cdn.discordapp.com/app-icons/${botConfig.botId}/${botData.icon}.png?size=256`;
          botAvatar.src = url;
          if (favicon) favicon.href = url;
        }
      })
      .catch(err => console.warn('[Debug] Failed to fetch bot avatar:', err));
    
    logoContainer.append(botAvatar, logo);
    
    // Navigation
    const nav = document.createElement('nav');
    nav.className = 'nav';
    
    config.navLinks.forEach(link => {
      const a = document.createElement('a');
      a.href = `#${link.id}`;
      a.textContent = link.name;
      a.setAttribute('data-page-id', link.id);
      a.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('.nav a').forEach(el => el.classList.remove('active'));
        a.classList.add('active');
        window.dispatchEvent(new CustomEvent('navigate', { detail: link.id }));
      });
      nav.appendChild(a);
    });
    
    header.append(logoContainer, nav);
    return header;
  }

  static createHero(config) {
    const hero = document.createElement('section');
    hero.className = 'hero';
    hero.id = 'home';
    
    const content = document.createElement('div');
    content.className = 'hero-content';
    
    const title = document.createElement('h1');
    title.className = 'hero-title';
    title.textContent = config.hero.title;
    
    const subtitle = document.createElement('p');
    subtitle.className = 'hero-subtitle';
    subtitle.textContent = config.hero.subtitle;
    
    const buttons = document.createElement('div');
    buttons.className = 'hero-buttons';
    
    const inviteBtn = document.createElement('a');
    inviteBtn.href = botConfig.inviteLink;
    inviteBtn.className = 'cta';
    inviteBtn.textContent = config.hero.inviteText;
    inviteBtn.target = '_blank';
    
    const supportBtn = document.createElement('a');
    supportBtn.href = botConfig.supportServer;
    supportBtn.className = 'cta secondary';
    supportBtn.textContent = 'Support Server';
    supportBtn.target = '_blank';
    
    buttons.append(inviteBtn, supportBtn);
    
    const tagline = document.createElement('p');
    tagline.className = 'hero-tagline';
    tagline.textContent = config.hero.tagline;
    
    content.append(title, subtitle, buttons, tagline);
    hero.appendChild(content);
    
    // Add gradient effect on mouse move
    inviteBtn.addEventListener('mousemove', (e) => {
      const rect = inviteBtn.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const px = (x / rect.width) * 100;
      const py = (y / rect.height) * 100;
      inviteBtn.style.setProperty('--px', `${px}%`);
      inviteBtn.style.setProperty('--py', `${py}%`);
    });
    
    inviteBtn.addEventListener('mouseleave', () => {
      inviteBtn.style.setProperty('--px', '50%');
      inviteBtn.style.setProperty('--py', '50%');
    });
    
    return hero;
  }

  static createFeatures(config) {
    const section = document.createElement('section');
    section.className = 'features';
    
    const title = document.createElement('h2');
    title.textContent = 'Features';
    title.style.textAlign = 'center';
    title.style.marginBottom = '2rem';
    section.appendChild(title);
    
    const grid = document.createElement('div');
    grid.className = 'features-grid';
    
    config.features.forEach(feature => {
      const card = document.createElement('div');
      card.className = 'feature-card';
      
      const icon = document.createElement('div');
      icon.className = 'feature-icon';
      icon.textContent = feature.icon;
      
      const featureTitle = document.createElement('h3');
      featureTitle.textContent = feature.title;
      
      const desc = document.createElement('p');
      desc.textContent = feature.description;
      
      card.append(icon, featureTitle, desc);
      grid.appendChild(card);
    });
    
    section.appendChild(grid);
    return section;
  }

  static createFooter(config) {
    const footer = document.createElement('footer');
    footer.className = 'footer';
    footer.textContent = config.footer;
    return footer;
  }
}

export default LayoutElements;
