/**
 * Generate placeholder images for characters
 * Uses placeholder services until real images are scraped
 */

export function getCharacterPlaceholder(character: {
  name: string;
  series: string;
  rarity?: string;
}): string {
  // Use character name as seed for consistent colors
  // Remove unused variable
  // const seed = character.name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  
  // Generate color based on rarity
  const rarityColors: Record<string, string> = {
    'SSR': 'FFD700', // Gold
    'SR': 'A855F7',  // Purple
    'R': '3B82F6',   // Blue
    'C': '9CA3AF'    // Gray
  };
  
  const color = rarityColors[character.rarity || 'R'] || '9CA3AF';
  
  // Use DiceBear API for anime-style avatars
  return `https://api.dicebear.com/7.x/bottts/svg?seed=${encodeURIComponent(character.name)}&backgroundColor=${color}`;
}

export function getCharacterPlaceholders(character: {
  name: string;
  series: string;
  rarity?: string;
}, count: number = 3): string[] {
  const placeholders: string[] = [];
  
  for (let i = 0; i < count; i++) {
    placeholders.push(getCharacterPlaceholder({
      ...character,
      name: `${character.name}-${i}`
    }));
  }
  
  return placeholders;
}
