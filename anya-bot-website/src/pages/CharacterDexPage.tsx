import { useState, useEffect } from 'react';
import { Book, Search, Filter, RefreshCw } from 'lucide-react';
import { Character } from '../types/character';
import { getCharacters, searchCharacters, filterByRarity, filterBySeries } from '../services/characterService';
import { subscribeToCharacters } from '../services/characterDatabase';
import CharacterCard from '../components/CharacterCard';
import { RARITY_CONFIG } from '../config/bot';

const CharacterDexPage = () => {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [filteredCharacters, setFilteredCharacters] = useState<Character[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRarity, setSelectedRarity] = useState('all');
  const [selectedSeries, setSelectedSeries] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Get unique series
  const allSeries = Array.from(new Set(characters.map(c => c.series))).sort();

  useEffect(() => {
    loadCharacters();
    
    // Subscribe to real-time updates
    const unsubscribe = subscribeToCharacters((updatedCharacters) => {
      setCharacters(updatedCharacters);
    });
    
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [characters, searchQuery, selectedRarity, selectedSeries]);

  async function loadCharacters() {
    setLoading(true);
    const data = await getCharacters();
    setCharacters(data);
    setFilteredCharacters(data);
    setLoading(false);
  }
  
  async function refreshCharacters() {
    setRefreshing(true);
    await loadCharacters();
    setRefreshing(false);
  }

  async function applyFilters() {
    let result = [...characters];

    // Search filter
    if (searchQuery) {
      result = await searchCharacters(searchQuery, result);
    }

    // Rarity filter
    result = filterByRarity(result, selectedRarity);

    // Series filter
    result = filterBySeries(result, selectedSeries);

    setFilteredCharacters(result);
  }

  return (
    <div className="pt-24 pb-20 min-h-screen bg-dark">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-12 animate-slide-up">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-primary rounded-2xl mb-4 shadow-lg">
            <Book className="w-8 h-8 text-white" />
          </div>
          <div className="flex items-center justify-center gap-4 mb-4">
            <h1 className="text-4xl md:text-5xl font-display font-bold text-gradient">
              📚 Character Dex
            </h1>
            <button
              onClick={refreshCharacters}
              disabled={refreshing}
              className="p-2 bg-dark-800 hover:bg-dark-700 border border-primary/30 rounded-lg transition-colors disabled:opacity-50"
              title="Refresh characters"
            >
              <RefreshCw className={`w-5 h-5 text-primary ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto font-medium">
            Browse ALL anime characters from AniList, Jikan, and Kitsu with artwork from 100+ sources
          </p>
          <p className="text-sm text-gray-500 mt-2">
            🔍 Search dynamically fetches from APIs • 🎨 Images from Danbooru, Gelbooru, Konachan, Yande.re & more
          </p>
        </div>

        {/* Filters */}
        <div className="mb-8 space-y-4">
          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search characters, series, or tags... (searches API if not found locally)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-dark-800 border border-dark-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-primary transition-colors"
            />
          </div>

          {/* Filter Buttons */}
          <div className="flex flex-wrap gap-4">
            {/* Rarity Filter */}
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-400" />
              <select
                value={selectedRarity}
                onChange={(e) => setSelectedRarity(e.target.value)}
                className="px-4 py-2 bg-dark-800 border border-dark-600 rounded-lg text-white focus:outline-none focus:border-primary transition-colors"
              >
                <option value="all">All Rarities</option>
                {Object.entries(RARITY_CONFIG).map(([key, config]) => (
                  <option key={key} value={key}>
                    {config.emoji} {config.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Series Filter */}
            <select
              value={selectedSeries}
              onChange={(e) => setSelectedSeries(e.target.value)}
              className="px-4 py-2 bg-dark-800 border border-dark-600 rounded-lg text-white focus:outline-none focus:border-primary transition-colors"
            >
              <option value="all">All Series</option>
              {allSeries.map(series => (
                <option key={series} value={series}>{series}</option>
              ))}
            </select>
          </div>

          {/* Results Count */}
          <div className="text-gray-400 text-sm">
            Showing {filteredCharacters.length} of {characters.length} characters
          </div>
        </div>

        {/* Character Grid */}
        {loading ? (
          <div className="text-center py-20">
            <div className="inline-block w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
            <p className="text-gray-400 mt-4 text-lg font-semibold">Loading ALL anime characters...</p>
            <p className="text-gray-500 mt-2 text-sm">Fetching from AniList, Jikan, and Kitsu APIs</p>
            <p className="text-gray-500 mt-1 text-sm">🎨 Getting artwork from 100+ sources (Danbooru, Gelbooru, Konachan, Yande.re, etc.)</p>
            <p className="text-gray-600 mt-2 text-xs">Characters load progressively - you'll see them appear as they're fetched!</p>
          </div>
        ) : filteredCharacters.length === 0 ? (
          <div className="card p-12 text-center">
            <div className="text-6xl mb-4">🔍</div>
            <h2 className="text-2xl font-bold text-white mb-2">No characters found</h2>
            <p className="text-gray-400">
              Try adjusting your search or filters
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredCharacters.map(character => (
              <CharacterCard key={character.id} character={character} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CharacterDexPage;
