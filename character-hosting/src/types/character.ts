export interface Character {
  id: string;
  name: string;
  series: string;
  aliases: string[];
  tags: string[];
  voiceActors: {
    english?: string;
    japanese?: string;
  };
  rarity: 'C' | 'R' | 'SR' | 'SSR';
  images: string[];
  imageCount: number;
  description: string;
  affiliation: string[];
  role: string[];
  appearance?: string[];
  createdAt: string;
  updatedAt: string;
  scrapedAt?: string;
}

export interface Series {
  id: string;
  name: string;
  characters: string[];
  characterCount: number;
  createdAt: string;
  updatedAt: string;
}
