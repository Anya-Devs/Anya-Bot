import { collection, getDocs, query, orderBy, limit } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js';

/**
 * Leaderboard Page
 */
export class LeaderboardPage {
  constructor() {
    this.leaderboardData = [];
    this.currentCategory = 'total';
  }

  /**
   * Render the leaderboard page
   */
  async render(containerId = 'dynamic-zone') {
    const zone = document.getElementById(containerId);
    if (!zone) return;

    zone.innerHTML = '<div class="loading">Loading leaderboard...</div>';

    const wrapper = document.createElement('div');
    wrapper.className = 'leaderboard-wrapper dynamic-section';

    // Header
    const header = this.createHeader();
    wrapper.appendChild(header);

    // Category tabs
    const tabs = this.createCategoryTabs();
    wrapper.appendChild(tabs);

    // Load leaderboard data
    await this.loadLeaderboard();

    // Leaderboard table
    const table = this.createLeaderboardTable();
    wrapper.appendChild(table);

    zone.replaceChildren(wrapper);
  }

  /**
   * Create page header
   */
  createHeader() {
    const header = document.createElement('div');
    header.className = 'leaderboard-header';

    const title = document.createElement('h2');
    title.textContent = '🏆 Leaderboard';

    const subtitle = document.createElement('p');
    subtitle.textContent = 'Top collectors in the community';

    header.append(title, subtitle);
    return header;
  }

  /**
   * Create category tabs
   */
  createCategoryTabs() {
    const tabsContainer = document.createElement('div');
    tabsContainer.className = 'leaderboard-tabs';

    const categories = [
      { id: 'total', name: '📊 Total Characters', icon: '📊' },
      { id: 'rare', name: '⭐ Rare Collection', icon: '⭐' },
      { id: 'complete', name: '✅ Series Complete', icon: '✅' },
      { id: 'recent', name: '🔥 Most Active', icon: '🔥' }
    ];

    categories.forEach(cat => {
      const tab = document.createElement('button');
      tab.className = 'tab-button';
      tab.textContent = cat.name;
      
      if (cat.id === this.currentCategory) {
        tab.classList.add('active');
      }

      tab.addEventListener('click', () => {
        this.currentCategory = cat.id;
        document.querySelectorAll('.tab-button').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.updateLeaderboardTable();
      });

      tabsContainer.appendChild(tab);
    });

    return tabsContainer;
  }

  /**
   * Load leaderboard data
   */
  async loadLeaderboard() {
    try {
      const leaderboardRef = collection(window.firebaseDb, 'leaderboard');
      const q = query(leaderboardRef, orderBy('totalCharacters', 'desc'), limit(100));
      const snapshot = await getDocs(q);
      
      this.leaderboardData = snapshot.docs.map((doc, index) => ({
        rank: index + 1,
        ...doc.data()
      }));
      
      console.log(`Loaded ${this.leaderboardData.length} leaderboard entries`);
    } catch (error) {
      console.error('Failed to load leaderboard:', error);
      this.leaderboardData = this.generateMockData();
    }
  }

  /**
   * Generate mock leaderboard data for testing
   */
  generateMockData() {
    const mockUsers = [
      { username: 'CharacterMaster', avatar: '👑' },
      { username: 'AnimeCollector', avatar: '🎴' },
      { username: 'GachaKing', avatar: '🎰' },
      { username: 'WaifuHunter', avatar: '💖' },
      { username: 'OtakuLegend', avatar: '⭐' },
      { username: 'CardCollector', avatar: '🃏' },
      { username: 'MangaFan', avatar: '📚' },
      { username: 'AnimeLover', avatar: '❤️' },
      { username: 'GachaAddict', avatar: '🎲' },
      { username: 'CollectorPro', avatar: '🏅' }
    ];

    return mockUsers.map((user, index) => ({
      rank: index + 1,
      userId: `user_${index}`,
      username: user.username,
      avatar: user.avatar,
      totalCharacters: Math.floor(Math.random() * 500) + 100,
      rareCharacters: Math.floor(Math.random() * 50) + 10,
      seriesCompleted: Math.floor(Math.random() * 20) + 1,
      lastActive: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString()
    }));
  }

  /**
   * Create leaderboard table
   */
  createLeaderboardTable() {
    const container = document.createElement('div');
    container.className = 'leaderboard-table-container';
    container.id = 'leaderboard-table';

    const table = document.createElement('table');
    table.className = 'leaderboard-table';

    // Table header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    
    const headers = this.getTableHeaders();
    headers.forEach(header => {
      const th = document.createElement('th');
      th.textContent = header;
      headerRow.appendChild(th);
    });

    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Table body
    const tbody = document.createElement('tbody');
    
    const sortedData = this.getSortedData();
    sortedData.forEach((entry, index) => {
      const row = this.createLeaderboardRow(entry, index);
      tbody.appendChild(row);
    });

    table.appendChild(tbody);
    container.appendChild(table);

    return container;
  }

  /**
   * Get table headers based on category
   */
  getTableHeaders() {
    const baseHeaders = ['Rank', 'User'];
    
    switch (this.currentCategory) {
      case 'total':
        return [...baseHeaders, 'Total Characters', 'Rare Characters', 'Series Completed'];
      case 'rare':
        return [...baseHeaders, 'Rare Characters', 'Total Characters', 'Completion %'];
      case 'complete':
        return [...baseHeaders, 'Series Completed', 'Total Characters', 'Avg per Series'];
      case 'recent':
        return [...baseHeaders, 'Total Characters', 'Last Active', 'Activity Score'];
      default:
        return [...baseHeaders, 'Total Characters'];
    }
  }

  /**
   * Get sorted data based on category
   */
  getSortedData() {
    const data = [...this.leaderboardData];
    
    switch (this.currentCategory) {
      case 'total':
        return data.sort((a, b) => b.totalCharacters - a.totalCharacters);
      case 'rare':
        return data.sort((a, b) => b.rareCharacters - a.rareCharacters);
      case 'complete':
        return data.sort((a, b) => b.seriesCompleted - a.seriesCompleted);
      case 'recent':
        return data.sort((a, b) => new Date(b.lastActive) - new Date(a.lastActive));
      default:
        return data;
    }
  }

  /**
   * Create leaderboard row
   */
  createLeaderboardRow(entry, index) {
    const row = document.createElement('tr');
    
    if (index < 3) {
      row.classList.add(`rank-${index + 1}`);
    }

    // Rank
    const rankCell = document.createElement('td');
    rankCell.className = 'rank-cell';
    
    const rankBadge = document.createElement('span');
    rankBadge.className = 'rank-badge';
    
    if (index === 0) rankBadge.textContent = '🥇';
    else if (index === 1) rankBadge.textContent = '🥈';
    else if (index === 2) rankBadge.textContent = '🥉';
    else rankBadge.textContent = `#${index + 1}`;
    
    rankCell.appendChild(rankBadge);

    // User
    const userCell = document.createElement('td');
    userCell.className = 'user-cell';
    
    const userAvatar = document.createElement('span');
    userAvatar.className = 'user-avatar';
    userAvatar.textContent = entry.avatar || '👤';
    
    const username = document.createElement('span');
    username.className = 'username';
    username.textContent = entry.username || 'Unknown User';
    
    userCell.append(userAvatar, username);

    // Stats based on category
    const statCells = this.getStatCells(entry);

    row.append(rankCell, userCell, ...statCells);
    return row;
  }

  /**
   * Get stat cells based on category
   */
  getStatCells(entry) {
    const cells = [];

    switch (this.currentCategory) {
      case 'total':
        cells.push(
          this.createStatCell(entry.totalCharacters || 0, 'primary'),
          this.createStatCell(entry.rareCharacters || 0, 'secondary'),
          this.createStatCell(entry.seriesCompleted || 0, 'secondary')
        );
        break;
      
      case 'rare':
        const completion = entry.totalCharacters ? 
          Math.round((entry.rareCharacters / entry.totalCharacters) * 100) : 0;
        cells.push(
          this.createStatCell(entry.rareCharacters || 0, 'primary'),
          this.createStatCell(entry.totalCharacters || 0, 'secondary'),
          this.createStatCell(`${completion}%`, 'secondary')
        );
        break;
      
      case 'complete':
        const avgPerSeries = entry.seriesCompleted ? 
          Math.round(entry.totalCharacters / entry.seriesCompleted) : 0;
        cells.push(
          this.createStatCell(entry.seriesCompleted || 0, 'primary'),
          this.createStatCell(entry.totalCharacters || 0, 'secondary'),
          this.createStatCell(avgPerSeries, 'secondary')
        );
        break;
      
      case 'recent':
        const lastActive = entry.lastActive ? 
          this.formatRelativeTime(entry.lastActive) : 'Never';
        const activityScore = Math.floor(Math.random() * 1000); // Mock score
        cells.push(
          this.createStatCell(entry.totalCharacters || 0, 'secondary'),
          this.createStatCell(lastActive, 'secondary'),
          this.createStatCell(activityScore, 'primary')
        );
        break;
    }

    return cells;
  }

  /**
   * Create stat cell
   */
  createStatCell(value, type = 'primary') {
    const cell = document.createElement('td');
    cell.className = `stat-cell stat-${type}`;
    cell.textContent = value;
    return cell;
  }

  /**
   * Format relative time
   */
  formatRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  }

  /**
   * Update leaderboard table
   */
  updateLeaderboardTable() {
    const container = document.getElementById('leaderboard-table');
    if (!container) return;

    const newTable = this.createLeaderboardTable();
    container.replaceWith(newTable);
  }
}

export default LeaderboardPage;
