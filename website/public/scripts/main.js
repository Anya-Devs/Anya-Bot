import AppConfig from './config.js';
import LayoutElements from './layout.js';
import DexPage from './dex.js';
import LeaderboardPage from './leaderboard.js';

/**
 * Main application controller
 */
class App {
  constructor() {
    this.config = new AppConfig();
    this.currentPage = 'home';
    this.pages = {
      dex: new DexPage(),
      leaderboard: new LeaderboardPage()
    };
  }

  /**
   * Initialize the application
   */
  init() {
    this.setupLayout();
    this.setupNavigation();
    this.setupRouting();
  }

  /**
   * Setup page layout
   */
  setupLayout() {
    let container = document.getElementById('app');
    if (!container) {
      container = document.createElement('div');
      container.id = 'app';
      document.body.appendChild(container);
    }

    if (!container.hasAttribute('data-layout-mounted')) {
      container.append(
        LayoutElements.createHeader(this.config),
        LayoutElements.createHero(this.config),
        LayoutElements.createFeatures(this.config)
      );

      const dynamic = document.createElement('main');
      dynamic.id = 'dynamic-zone';
      container.append(dynamic, LayoutElements.createFooter(this.config));
      container.setAttribute('data-layout-mounted', 'true');

      // Set home as active
      document.querySelector('.nav a[data-page-id="home"]')?.classList.add('active');
    }
  }

  /**
   * Setup navigation listeners
   */
  setupNavigation() {
    window.addEventListener('navigate', (e) => {
      this.navigateTo(e.detail);
    });
  }

  /**
   * Setup URL routing
   */
  setupRouting() {
    // Handle initial hash
    const hash = window.location.hash.slice(1);
    if (hash && hash !== 'home') {
      this.navigateTo(hash);
    }

    // Handle hash changes
    window.addEventListener('hashchange', () => {
      const newHash = window.location.hash.slice(1);
      if (newHash) {
        this.navigateTo(newHash);
      }
    });
  }

  /**
   * Navigate to a page
   */
  async navigateTo(pageId) {
    this.currentPage = pageId;
    const dynamicZone = document.getElementById('dynamic-zone');

    if (!dynamicZone) return;

    // Show/hide sections based on page
    const hero = document.querySelector('.hero');
    const features = document.querySelector('.features');

    switch (pageId) {
      case 'home':
        if (hero) hero.style.display = 'block';
        if (features) features.style.display = 'block';
        dynamicZone.innerHTML = '';
        break;

      case 'dex':
        if (hero) hero.style.display = 'none';
        if (features) features.style.display = 'none';
        await this.pages.dex.render('dynamic-zone');
        break;

      case 'leaderboard':
        if (hero) hero.style.display = 'none';
        if (features) features.style.display = 'none';
        await this.pages.leaderboard.render('dynamic-zone');
        break;

      case 'commands':
        if (hero) hero.style.display = 'none';
        if (features) features.style.display = 'none';
        this.renderCommandsPage();
        break;

      default:
        if (hero) hero.style.display = 'block';
        if (features) features.style.display = 'block';
        dynamicZone.innerHTML = '';
    }

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /**
   * Render commands page
   */
  renderCommandsPage() {
    const zone = document.getElementById('dynamic-zone');
    if (!zone) return;

    zone.innerHTML = `
      <div class="commands-wrapper dynamic-section">
        <div class="commands-header">
          <h2>🎮 Bot Commands</h2>
          <p>All commands for the character gacha system</p>
        </div>
        
        <div class="command-section">
          <h3>Gacha Commands</h3>
          <div class="command-list">
            <div class="command-item">
              <code>/roll</code>
              <p>Roll for a random character</p>
            </div>
            <div class="command-item">
              <code>/roll [rarity]</code>
              <p>Roll for a character of specific rarity (C, R, SR, SSR)</p>
            </div>
            <div class="command-item">
              <code>/daily</code>
              <p>Claim your daily free roll</p>
            </div>
            <div class="command-item">
              <code>/multi</code>
              <p>Roll 10 characters at once</p>
            </div>
          </div>
        </div>

        <div class="command-section">
          <h3>Collection Commands</h3>
          <div class="command-list">
            <div class="command-item">
              <code>/collection</code>
              <p>View your character collection</p>
            </div>
            <div class="command-item">
              <code>/dex [character]</code>
              <p>View detailed information about a character</p>
            </div>
            <div class="command-item">
              <code>/search [query]</code>
              <p>Search for characters by name, series, or tags</p>
            </div>
            <div class="command-item">
              <code>/favorite [character]</code>
              <p>Set a character as your favorite</p>
            </div>
          </div>
        </div>

        <div class="command-section">
          <h3>Trading Commands</h3>
          <div class="command-list">
            <div class="command-item">
              <code>/trade @user</code>
              <p>Start a trade with another user</p>
            </div>
            <div class="command-item">
              <code>/gift @user [character]</code>
              <p>Gift a character to another user</p>
            </div>
            <div class="command-item">
              <code>/market</code>
              <p>View the character marketplace</p>
            </div>
          </div>
        </div>

        <div class="command-section">
          <h3>Stats Commands</h3>
          <div class="command-list">
            <div class="command-item">
              <code>/stats</code>
              <p>View your collection statistics</p>
            </div>
            <div class="command-item">
              <code>/leaderboard</code>
              <p>View the global leaderboard</p>
            </div>
            <div class="command-item">
              <code>/compare @user</code>
              <p>Compare your collection with another user</p>
            </div>
          </div>
        </div>
      </div>
    `;
  }
}

// Initialize app when DOM is ready
window.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init();
  
  console.log('✅ Anya Bot Character Collection initialized!');
});
