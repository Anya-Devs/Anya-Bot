import { useState, useEffect } from 'react';
import { X, Heart, Image as ImageIcon, Film, Sparkles } from 'lucide-react';
import { Character } from '../types/character';
import { fetchCharacterMedia, type CharacterMedia } from '../services/characterMediaAPI';
import { RARITY_CONFIG } from '../config/bot';

interface CharacterDetailModalProps {
  character: Character;
  onClose: () => void;
}

const CharacterDetailModal = ({ character, onClose }: CharacterDetailModalProps) => {
  const [media, setMedia] = useState<CharacterMedia | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'info' | 'portraits' | 'fullBody' | 'banners' | 'gifs' | 'screenshots' | 'fanart' | 'official'>('info');
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  
  const rarityConfig = RARITY_CONFIG[character.rarity];

  useEffect(() => {
    loadMedia();
  }, [character]);

  async function loadMedia() {
    setLoading(true);
    try {
      const mediaData = await fetchCharacterMedia(character.name, character.series);
      setMedia(mediaData);
    } catch (error) {
      console.error('Failed to load media:', error);
    }
    setLoading(false);
  }

  const totalImages = media ? Object.values(media).reduce((sum, arr) => sum + arr.length, 0) : 0;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/80 backdrop-blur-sm" onClick={onClose}>
      <div className="min-h-screen px-4 py-8">
        <div 
          className="max-w-7xl mx-auto bg-dark-800 rounded-2xl shadow-2xl border border-primary/20"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="relative">
            {/* Banner Background */}
            {media?.banners[0] && (
              <div className="absolute inset-0 h-64 overflow-hidden rounded-t-2xl">
                <img 
                  src={media.banners[0]} 
                  alt="Banner"
                  className="w-full h-full object-cover opacity-30 blur-sm"
                />
                <div className="absolute inset-0 bg-gradient-to-b from-transparent to-dark-800"></div>
              </div>
            )}
            
            {/* Header Content */}
            <div className="relative p-6 md:p-8">
              <button
                onClick={onClose}
                className="absolute top-4 right-4 p-2 bg-dark-700 hover:bg-dark-600 rounded-full transition-colors"
              >
                <X className="w-6 h-6 text-white" />
              </button>

              <div className="flex flex-col md:flex-row gap-6 items-start">
                {/* Character Image */}
                <div className="flex-shrink-0">
                  <div className="w-48 h-48 rounded-2xl overflow-hidden border-4 shadow-xl" style={{ borderColor: rarityConfig.color }}>
                    <img 
                      src={character.images[0] || `https://placehold.co/200x200/1a1a2e/ff6b9d?text=${encodeURIComponent(character.name)}`}
                      alt={character.name}
                      className="w-full h-full object-cover"
                    />
                  </div>
                </div>

                {/* Character Info */}
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h1 className="text-3xl md:text-4xl font-bold text-white">
                      {character.name}
                    </h1>
                    <span 
                      className="px-3 py-1 rounded-full text-sm font-bold"
                      style={{ 
                        backgroundColor: `${rarityConfig.color}20`,
                        color: rarityConfig.color,
                        border: `2px solid ${rarityConfig.color}`
                      }}
                    >
                      {rarityConfig.emoji} {rarityConfig.name}
                    </span>
                  </div>
                  
                  <p className="text-xl text-primary mb-4">{character.series}</p>
                  
                  {/* Quick Stats */}
                  <div className="flex flex-wrap gap-4 mb-4">
                    <div className="flex items-center gap-2 text-gray-400">
                      <ImageIcon className="w-5 h-5" />
                      <span>{totalImages} Images</span>
                    </div>
                    {media?.gifs && media.gifs.length > 0 && (
                      <div className="flex items-center gap-2 text-gray-400">
                        <Film className="w-5 h-5" />
                        <span>{media.gifs.length} GIFs</span>
                      </div>
                    )}
                    <button className="flex items-center gap-2 text-primary hover:text-primary/80 transition-colors">
                      <Heart className="w-5 h-5" />
                      <span>Add to Favorites</span>
                    </button>
                  </div>

                  {/* Aliases */}
                  {character.aliases && character.aliases.length > 0 && (
                    <div className="mb-4">
                      <h3 className="text-sm font-semibold text-gray-400 mb-2">Also Known As:</h3>
                      <div className="flex flex-wrap gap-2">
                        {character.aliases.slice(0, 6).map((alias, idx) => (
                          <span key={idx} className="px-3 py-1 bg-dark-700 text-gray-300 text-sm rounded-full">
                            {alias}
                          </span>
                        ))}
                        {character.aliases.length > 6 && (
                          <span className="px-3 py-1 bg-dark-700 text-gray-400 text-sm rounded-full">
                            +{character.aliases.length - 6} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Content Tabs */}
          <div className="border-t border-dark-600">
            <div className="flex overflow-x-auto px-6">
              <button
                onClick={() => setActiveTab('info')}
                className={`px-4 py-3 font-semibold border-b-2 transition-colors ${
                  activeTab === 'info'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-400 hover:text-white'
                }`}
              >
                Information
              </button>
              <button
                onClick={() => setActiveTab('portraits')}
                className={`px-4 py-3 font-semibold border-b-2 transition-colors ${
                  activeTab === 'portraits'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-400 hover:text-white'
                }`}
              >
                Portraits ({media?.portraits.length || 0})
              </button>
              <button
                onClick={() => setActiveTab('fullBody')}
                className={`px-4 py-3 font-semibold border-b-2 transition-colors ${
                  activeTab === 'fullBody'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-400 hover:text-white'
                }`}
              >
                Full Body ({media?.fullBody.length || 0})
              </button>
              <button
                onClick={() => setActiveTab('gifs')}
                className={`px-4 py-3 font-semibold border-b-2 transition-colors ${
                  activeTab === 'gifs'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-400 hover:text-white'
                }`}
              >
                GIFs ({media?.gifs.length || 0})
              </button>
              <button
                onClick={() => setActiveTab('fanart')}
                className={`px-4 py-3 font-semibold border-b-2 transition-colors ${
                  activeTab === 'fanart'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-400 hover:text-white'
                }`}
              >
                Fanart ({media?.fanart.length || 0})
              </button>
              <button
                onClick={() => setActiveTab('official')}
                className={`px-4 py-3 font-semibold border-b-2 transition-colors ${
                  activeTab === 'official'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-400 hover:text-white'
                }`}
              >
                Official ({media?.official.length || 0})
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="p-6 md:p-8">
            {loading ? (
              <div className="text-center py-20">
                <div className="inline-block w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
                <p className="text-gray-400">Loading media...</p>
              </div>
            ) : activeTab === 'info' ? (
              <div>
                {/* Character Information */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  {/* Left Column - Details */}
                  <div className="lg:col-span-2 space-y-6">
                    {/* Description */}
                    {character.description && (
                      <div>
                        <h3 className="text-xl font-bold text-white mb-3">About</h3>
                        <p className="text-gray-300 leading-relaxed">{character.description}</p>
                      </div>
                    )}

                    {/* Voice Actors */}
                    {character.voiceActors && (Object.keys(character.voiceActors).length > 0) && (
                      <div>
                        <h3 className="text-xl font-bold text-white mb-3">Voice Actors</h3>
                        <div className="space-y-2">
                          {character.voiceActors.japanese && (
                            <div className="flex items-center gap-3 p-3 bg-dark-700 rounded-lg">
                              <span className="text-2xl">🇯🇵</span>
                              <div>
                                <p className="text-sm text-gray-400">Japanese</p>
                                <p className="text-white font-semibold">{character.voiceActors.japanese}</p>
                              </div>
                            </div>
                          )}
                          {character.voiceActors.english && (
                            <div className="flex items-center gap-3 p-3 bg-dark-700 rounded-lg">
                              <span className="text-2xl">🇺🇸</span>
                              <div>
                                <p className="text-sm text-gray-400">English</p>
                                <p className="text-white font-semibold">{character.voiceActors.english}</p>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Right Column - Tags & Info */}
                  <div className="space-y-6">
                    {/* Role */}
                    {character.role && character.role.length > 0 && (
                      <div>
                        <h3 className="text-lg font-bold text-white mb-3">Role</h3>
                        <div className="flex flex-wrap gap-2">
                          {character.role.map((role, idx) => (
                            <span key={idx} className="px-3 py-1 bg-primary/20 text-primary rounded-lg text-sm font-semibold">
                              {role}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Affiliation */}
                    {character.affiliation && character.affiliation.length > 0 && (
                      <div>
                        <h3 className="text-lg font-bold text-white mb-3">Affiliation</h3>
                        <div className="space-y-2">
                          {character.affiliation.map((aff, idx) => (
                            <div key={idx} className="px-3 py-2 bg-dark-700 rounded-lg text-gray-300">
                              {aff}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Tags */}
                    {character.tags && character.tags.length > 0 && (
                      <div>
                        <h3 className="text-lg font-bold text-white mb-3">Tags</h3>
                        <div className="flex flex-wrap gap-2">
                          {character.tags.map((tag, idx) => (
                            <span key={idx} className="px-2 py-1 bg-dark-700 text-gray-400 text-xs rounded">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              /* Image Gallery */
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {media && media[activeTab]?.map((url, idx) => (
                  <div
                    key={idx}
                    className="relative aspect-square rounded-lg overflow-hidden cursor-pointer group"
                    onClick={() => setSelectedImage(url)}
                  >
                    <img
                      src={url}
                      alt={`${character.name} ${activeTab} ${idx + 1}`}
                      className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                      loading="lazy"
                    />
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <Sparkles className="w-8 h-8 text-white" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Image Lightbox */}
      {selectedImage && (
        <div 
          className="fixed inset-0 z-60 bg-black/95 flex items-center justify-center p-4"
          onClick={() => setSelectedImage(null)}
        >
          <button
            onClick={() => setSelectedImage(null)}
            className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 rounded-full"
          >
            <X className="w-6 h-6 text-white" />
          </button>
          <img
            src={selectedImage}
            alt="Full size"
            className="max-w-full max-h-full object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
};

export default CharacterDetailModal;
