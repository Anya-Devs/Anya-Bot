import { useState } from 'react';
import { Character } from '../types/character';
import { RARITY_CONFIG } from '../config/bot';
import CharacterDetailModal from './CharacterDetailModal';

interface CharacterCardProps {
  character: Character;
  onClick?: () => void;
}

const CharacterCard = ({ character, onClick }: CharacterCardProps) => {
  const [showModal, setShowModal] = useState(false);
  
  const handleClick = () => {
    if (onClick) {
      onClick();
    } else {
      setShowModal(true);
    }
  };
  const rarityConfig = RARITY_CONFIG[character.rarity];
  const imageUrl = character.images && character.images.length > 0 
    ? character.images[0] 
    : `https://placehold.co/400x400/1a1a2e/ff6b9d?text=${encodeURIComponent(character.name)}&font=roboto`;
  
  return (
    <>
      <div 
        onClick={handleClick}
        className="card-hover p-0 cursor-pointer group overflow-hidden"
      >
      {/* Character Image */}
      <div className="relative h-48 overflow-hidden bg-dark-700">
        <img 
          src={imageUrl}
          alt={character.name}
          className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
          onError={(e) => {
            // Fallback if image fails to load
            e.currentTarget.src = `https://placehold.co/400x400/1a1a2e/ff6b9d?text=${encodeURIComponent(character.name)}&font=roboto`;
          }}
        />
        {/* Rarity Badge Overlay */}
        <div className="absolute top-2 right-2">
          <span 
            className="px-3 py-1 rounded-full text-xs font-bold backdrop-blur-sm"
            style={{ 
              backgroundColor: `${rarityConfig.color}40`,
              color: 'white',
              border: `1px solid ${rarityConfig.color}`
            }}
          >
            {rarityConfig.emoji} {rarityConfig.name}
          </span>
        </div>
      </div>

      {/* Card Content */}
      <div className="p-4">

      {/* Character Name */}
      <h3 className="text-lg font-bold text-white mb-1 group-hover:text-primary transition-colors">
        {character.name}
      </h3>

      {/* Series */}
      <p className="text-sm text-gray-400 mb-3">
        {character.series}
      </p>

      {/* Description */}
      {character.description && (
        <p className="text-sm text-gray-500 line-clamp-2 mb-3">
          {character.description}
        </p>
      )}

      {/* Tags */}
      <div className="flex flex-wrap gap-1 mb-3">
        {character.tags.slice(0, 3).map((tag, idx) => (
          <span 
            key={idx}
            className="px-2 py-1 bg-dark-700 text-gray-400 text-xs rounded"
          >
            {tag}
          </span>
        ))}
        {character.tags.length > 3 && (
          <span className="px-2 py-1 bg-dark-700 text-gray-400 text-xs rounded">
            +{character.tags.length - 3}
          </span>
        )}
      </div>

      {/* Voice Actors */}
      {character.voiceActors && (
        <div className="text-xs text-gray-500 space-y-1">
          {character.voiceActors.japanese && (
            <div>🇯🇵 {character.voiceActors.japanese}</div>
          )}
          {character.voiceActors.english && (
            <div>🇺🇸 {character.voiceActors.english}</div>
          )}
        </div>
      )}
      </div>
    </div>
    
    {/* Character Detail Modal */}
    {showModal && (
      <CharacterDetailModal
        character={character}
        onClose={() => setShowModal(false)}
      />
    )}
    </>
  );
};

export default CharacterCard;
