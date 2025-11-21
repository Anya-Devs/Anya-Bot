import { collection, getDocs, query, where, orderBy, limit } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js';
import { RARITY_CONFIG } from './config.js';

/**
 * Character Dex Page
 */
export class DexPage {
  constructor() {
    this.characters = [];
    this.filteredCharacters = [];
    this.currentPage = 1;
    this.pageSize = 24;
    this.filters = {
      series: null,
      rarity: null,
      tags: [],
      search: ''
    };
  }

  /**
   * Render the dex page
   */
  async render(containerId = 'dynamic-zone') {
    const zone = document.getElementById(containerId);
    if (!zone) return;

    zone.innerHTML = '<div class="loading">Loading character dex...</div>';

    const wrapper = document.createElement('div');
    wrapper.className = 'dex-wrapper dynamic-section';

    // Header
    const header = this.createHeader();
    wrapper.appendChild(header);

    // Filters
    const filters = await this.createFilters();
    wrapper.appendChild(filters);

    // Load characters
    await this.loadCharacters();

    // Character grid
    const grid = this.createCharacterGrid();
    wrapper.appendChild(grid);

    // Pagination
    const pagination = this.createPagination();
    wrapper.appendChild(pagination);

    zone.replaceChildren(wrapper);
  }

  /**
   * Create page header
   */
  createHeader() {
    const header = document.createElement('div');
    header.className = 'dex-header';

    const title = document.createElement('h2');
    title.textContent = '📚 Character Dex';

    const subtitle = document.createElement('p');
    subtitle.textContent = 'Browse our collection of anime, manga, game, and cartoon characters';

    header.append(title, subtitle);
    return header;
  }

  /**
   * Create filter controls
   */
  async createFilters() {
    const filterContainer = document.createElement('div');
    filterContainer.className = 'dex-filters';

    // Search bar
    const searchWrapper = document.createElement('div');
    searchWrapper.className = 'search-wrapper';

    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = '🔍 Search characters...';
    searchInput.className = 'search-input';
    searchInput.addEventListener('input', (e) => {
      this.filters.search = e.target.value;
      this.applyFilters();
    });

    searchWrapper.appendChild(searchInput);

    // Rarity filter
    const rarityFilter = document.createElement('select');
    rarityFilter.className = 'filter-select';
    rarityFilter.innerHTML = '<option value="">All Rarities</option>';
    
    Object.entries(RARITY_CONFIG).forEach(([key, config]) => {
      const option = document.createElement('option');
      option.value = key;
      option.textContent = `${config.emoji} ${config.name}`;
      rarityFilter.appendChild(option);
    });

    rarityFilter.addEventListener('change', (e) => {
      this.filters.rarity = e.target.value || null;
      this.applyFilters();
    });

    // Series filter
    const seriesFilter = document.createElement('select');
    seriesFilter.className = 'filter-select';
    seriesFilter.innerHTML = '<option value="">All Series</option>';

    // Load series from database
    try {
      const seriesSnapshot = await getDocs(collection(window.firebaseDb, 'series'));
      seriesSnapshot.forEach(doc => {
        const series = doc.data();
        const option = document.createElement('option');
        option.value = series.name;
        option.textContent = `${series.name} (${series.characterCount})`;
        seriesFilter.appendChild(option);
      });
    } catch (error) {
      console.error('Failed to load series:', error);
    }

    seriesFilter.addEventListener('change', (e) => {
      this.filters.series = e.target.value || null;
      this.applyFilters();
    });

    // Sort options
    const sortSelect = document.createElement('select');
    sortSelect.className = 'filter-select';
    sortSelect.innerHTML = `
      <option value="name">Name (A-Z)</option>
      <option value="rarity">Rarity</option>
      <option value="recent">Recently Added</option>
    `;

    sortSelect.addEventListener('change', (e) => {
      this.sortCharacters(e.target.value);
    });

    filterContainer.append(searchWrapper, rarityFilter, seriesFilter, sortSelect);
    return filterContainer;
  }

  /**
   * Load characters from database
   */
  async loadCharacters() {
    try {
      const charactersRef = collection(window.firebaseDb, 'characters');
      const snapshot = await getDocs(charactersRef);
      
      this.characters = snapshot.docs.map(doc => doc.data());
      this.filteredCharacters = [...this.characters];
      
      console.log(`Loaded ${this.characters.length} characters`);
    } catch (error) {
      console.error('Failed to load characters:', error);
      this.characters = [];
      this.filteredCharacters = [];
    }
  }

  /**
   * Apply filters to character list
   */
  applyFilters() {
    this.filteredCharacters = this.characters.filter(char => {
      // Search filter
      if (this.filters.search) {
        const searchLower = this.filters.search.toLowerCase();
        const matchesName = char.name.toLowerCase().includes(searchLower);
        const matchesSeries = char.series.toLowerCase().includes(searchLower);
        const matchesAlias = char.aliases?.some(alias => 
          alias.toLowerCase().includes(searchLower)
        );
        
        if (!matchesName && !matchesSeries && !matchesAlias) {
          return false;
        }
      }

      // Rarity filter
      if (this.filters.rarity && char.rarity !== this.filters.rarity) {
        return false;
      }

      // Series filter
      if (this.filters.series && char.series !== this.filters.series) {
        return false;
      }

      return true;
    });

    this.currentPage = 1;
    this.updateCharacterGrid();
    this.updatePagination();
  }

  /**
   * Sort characters
   */
  sortCharacters(sortBy) {
    switch (sortBy) {
      case 'name':
        this.filteredCharacters.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'rarity':
        const rarityOrder = { 'SSR': 0, 'SR': 1, 'R': 2, 'C': 3 };
        this.filteredCharacters.sort((a, b) => 
          (rarityOrder[a.rarity] || 99) - (rarityOrder[b.rarity] || 99)
        );
        break;
      case 'recent':
        this.filteredCharacters.sort((a, b) => 
          new Date(b.createdAt) - new Date(a.createdAt)
        );
        break;
    }

    this.updateCharacterGrid();
  }

  /**
   * Create character grid
   */
  createCharacterGrid() {
    const container = document.createElement('div');
    container.className = 'character-grid-container';
    container.id = 'character-grid';

    const grid = document.createElement('div');
    grid.className = 'character-grid';

    const start = (this.currentPage - 1) * this.pageSize;
    const end = start + this.pageSize;
    const pageCharacters = this.filteredCharacters.slice(start, end);

    if (pageCharacters.length === 0) {
      const noResults = document.createElement('div');
      noResults.className = 'no-results';
      noResults.textContent = '😢 No characters found';
      container.appendChild(noResults);
      return container;
    }

    pageCharacters.forEach(char => {
      const card = this.createCharacterCard(char);
      grid.appendChild(card);
    });

    container.appendChild(grid);
    return container;
  }

  /**
   * Create character card
   */
  createCharacterCard(character) {
    const card = document.createElement('div');
    card.className = 'character-card';
    card.setAttribute('data-rarity', character.rarity);

    // Image
    const imageContainer = document.createElement('div');
    imageContainer.className = 'character-image';

    const img = document.createElement('img');
    img.src = character.images?.[0]?.thumbnail || character.images?.[0]?.url || '/images/placeholder.png';
    img.alt = character.name;
    img.loading = 'lazy';

    imageContainer.appendChild(img);

    // Info
    const info = document.createElement('div');
    info.className = 'character-info';

    const name = document.createElement('h3');
    name.textContent = character.name;

    const series = document.createElement('p');
    series.className = 'character-series';
    series.textContent = character.series;

    const rarity = document.createElement('span');
    rarity.className = 'character-rarity';
    const rarityConfig = RARITY_CONFIG[character.rarity] || RARITY_CONFIG['C'];
    rarity.textContent = `${rarityConfig.emoji} ${rarityConfig.name}`;
    rarity.style.color = rarityConfig.color;

    info.append(name, series, rarity);

    card.append(imageContainer, info);

    // Click to view details
    card.addEventListener('click', () => {
      this.showCharacterDetails(character);
    });

    return card;
  }

  /**
   * Show character details modal
   */
  showCharacterDetails(character) {
    const modal = document.createElement('div');
    modal.className = 'modal';

    const content = document.createElement('div');
    content.className = 'modal-content character-details';

    // Close button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'modal-close';
    closeBtn.textContent = '✕';
    closeBtn.addEventListener('click', () => modal.remove());

    // Character info
    const header = document.createElement('div');
    header.className = 'character-details-header';

    const name = document.createElement('h2');
    name.textContent = character.name;

    const rarityConfig = RARITY_CONFIG[character.rarity] || RARITY_CONFIG['C'];
    const rarity = document.createElement('span');
    rarity.className = 'character-rarity-badge';
    rarity.textContent = `${rarityConfig.emoji} ${rarityConfig.name}`;
    rarity.style.backgroundColor = rarityConfig.color;

    header.append(name, rarity);

    // Series and aliases
    const meta = document.createElement('div');
    meta.className = 'character-meta';
    meta.innerHTML = `
      <p><strong>Series:</strong> ${character.series}</p>
      ${character.aliases?.length ? `<p><strong>Aliases:</strong> ${character.aliases.join(', ')}</p>` : ''}
      ${character.voiceActors?.japanese ? `<p><strong>Voice Actor (JP):</strong> ${character.voiceActors.japanese}</p>` : ''}
      ${character.voiceActors?.english ? `<p><strong>Voice Actor (EN):</strong> ${character.voiceActors.english}</p>` : ''}
    `;

    // Tags
    if (character.tags?.length) {
      const tagsContainer = document.createElement('div');
      tagsContainer.className = 'character-tags';

      const tagsTitle = document.createElement('strong');
      tagsTitle.textContent = 'Tags: ';
      tagsContainer.appendChild(tagsTitle);

      character.tags.forEach(tag => {
        const tagSpan = document.createElement('span');
        tagSpan.className = 'tag';
        tagSpan.textContent = tag;
        tagsContainer.appendChild(tagSpan);
      });

      meta.appendChild(tagsContainer);
    }

    // Image gallery
    const gallery = document.createElement('div');
    gallery.className = 'character-gallery';

    const galleryTitle = document.createElement('h3');
    galleryTitle.textContent = `Images (${character.imageCount || 0})`;
    gallery.appendChild(galleryTitle);

    const imageGrid = document.createElement('div');
    imageGrid.className = 'gallery-grid';

    character.images?.slice(0, 12).forEach(img => {
      const imgEl = document.createElement('img');
      imgEl.src = img.thumbnail || img.url;
      imgEl.alt = character.name;
      imgEl.loading = 'lazy';
      imgEl.addEventListener('click', () => {
        window.open(img.url, '_blank');
      });
      imageGrid.appendChild(imgEl);
    });

    gallery.appendChild(imageGrid);

    content.append(closeBtn, header, meta, gallery);
    modal.appendChild(content);

    // Close on background click
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    document.body.appendChild(modal);
  }

  /**
   * Update character grid
   */
  updateCharacterGrid() {
    const container = document.getElementById('character-grid');
    if (!container) return;

    const newGrid = this.createCharacterGrid();
    container.replaceWith(newGrid);
  }

  /**
   * Create pagination
   */
  createPagination() {
    const pagination = document.createElement('div');
    pagination.className = 'pagination';
    pagination.id = 'pagination';

    this.updatePaginationContent(pagination);
    return pagination;
  }

  /**
   * Update pagination
   */
  updatePagination() {
    const pagination = document.getElementById('pagination');
    if (pagination) {
      this.updatePaginationContent(pagination);
    }
  }

  /**
   * Update pagination content
   */
  updatePaginationContent(pagination) {
    pagination.innerHTML = '';

    const totalPages = Math.ceil(this.filteredCharacters.length / this.pageSize);

    if (totalPages <= 1) return;

    // Previous button
    const prev = document.createElement('button');
    prev.textContent = '← Previous';
    prev.disabled = this.currentPage === 1;
    prev.addEventListener('click', () => {
      if (this.currentPage > 1) {
        this.currentPage--;
        this.updateCharacterGrid();
        this.updatePagination();
      }
    });

    // Page info
    const pageInfo = document.createElement('span');
    pageInfo.textContent = `Page ${this.currentPage} of ${totalPages}`;

    // Next button
    const next = document.createElement('button');
    next.textContent = 'Next →';
    next.disabled = this.currentPage === totalPages;
    next.addEventListener('click', () => {
      if (this.currentPage < totalPages) {
        this.currentPage++;
        this.updateCharacterGrid();
        this.updatePagination();
      }
    });

    pagination.append(prev, pageInfo, next);
  }
}

export default DexPage;
