// Emoji mapping to match the Python implementation
export const flagMapping = {
  "en": "🇬🇧", "fr": "🇫🇷", "es": "🇪🇸", "de": "🇩🇪", "it": "🇮🇹", "ja": "🇯🇵",
  "ko": "🇰🇷", "zh-Hans": "🇨🇳", "ru": "🇷🇺", "es-MX": "🇲🇽", "pt": "🇵🇹",
  "nl": "🇳🇱", "tr": "🇹🇷", "ar": "🇸🇦", "th": "🇹🇭", "vi": "🇻🇳", "pl": "🇵🇱",
  "sv": "🇸🇪", "da": "🇩🇰", "no": "🇳🇴", "fi": "🇫🇮", "el": "🇬🇷", "id": "🇮🇩",
  "ms": "🇲🇾", "fil": "🇵🇭", "hu": "🇭🇺", "cs": "🇨🇿", "sk": "🇸🇰", "ro": "🇷🇴",
  "uk": "🇺🇦", "hr": "🇭🇷", "bg": "🇧🇬", "et": "🇪🇪", "lv": "🇱🇻", "lt": "🇱🇹",
  "sl": "🇸🇮", "mt": "🇲🇹", "sq": "🇦🇱", "mk": "🇲🇰", "bs": "🇧🇦", "sr": "🇷🇸",
  "cy": "🇨🇾", "ga": "🇮🇪", "gd": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "kw": "🇰🇾", "br": "🇧🇷", "af": "🇿🇦",
  "xh": "🇿🇦", "zu": "🇿🇦", "tn": "🇿🇦", "st": "🇿🇦", "ss": "🇿🇦", "nr": "🇿🇦",
  "nso": "🇿🇦", "ts": "🇿🇦", "ve": "🇿🇦", "xog": "🇺🇬", "lg": "🇺🇬", "ak": "🇬🇭",
  "tw": "🇬🇭", "bm": "🇧🇫", "my": "🇲🇲", "km": "🇰🇭", "lo": "🇱🇦", "am": "🇪🇹",
  "ti": "🇪🇹", "om": "🇪🇹", "so": "🇸🇴", "sw": "🇰🇪", "rw": "🇷🇼", "yo": "🇳🇬",
  "ig": "🇳🇬", "ha": "🇳🇬", "bn": "🇧🇩", "pa": "🇮🇳", "gu": "🇮🇳", "or": "🇮🇳",
  "ta": "🇮🇳", "te": "🇮🇳", "kn": "🇮🇳", "ml": "🇮🇳", "si": "🇱🇰", "ne": "🇳🇵",
  "dz": "🇧🇹", "be": "🇧🇾", "kk": "🇰🇿", "uz": "🇺🇿", "ky": "🇰🇬"
};


export const regionMappings = {
  "Paldea": "<:Paldea:1212335178714980403>",
  "Sinnoh": "<:Sinnoh:1212335180459544607>",
  "Alola": "<:Alola:1212335185228472411>",
  "Kalos": "<:Kalos:1212335190656024608>",
  "Galar": "<:Galar:1212335192740470876>",
  "Pasio": "<:848495108667867139:1212335194628034560>",
  "Hoenn": "<:Hoenn:1212335197304004678>",
  "Unova": "<:Unova:1212335199095095306>",
  "Kanto": "<:Kanto:1212335202341363713>",
  "Johto": "<:Kanto:1212335202341363713>"
};


// Format emoji URL for Discord CDN
export const formatEmojiUrl = (emojiId: string, format: 'webp' | 'png' | 'gif' = 'webp', size: number = 24) => {
  return `https://cdn.discordapp.com/emojis/${emojiId}.${format}?quality=lossless&size=${size}`;
};


// Get emoji URL from Discord emoji format <:name:id>
export const getEmojiUrl = (emojiString: string, size: number = 24): string => {
  const match = emojiString.match(/<a?:\w+:(\d+)>/);
  if (match && match[1]) {
    const format = emojiString.startsWith('<a:') ? 'gif' : 'webp';
    return formatEmojiUrl(match[1], format, size);
  }
  return '';
};


// Get region emoji (returns the emoji string for Discord embeds)
export const getRegionEmoji = (region: string): string => {
  const emojiString = regionMappings[region as keyof typeof regionMappings];
  if (!emojiString) return '';
  return emojiString; // Return the emoji string like <:Kanto:1212335202341363713>
};


// Format alternate names with flags
export const formatAlternateNames = (names: {name: string, language: string}[] = []): string => {
  return names
    .filter(({name, language}) => name && language && flagMapping[language as keyof typeof flagMapping])
    .map(({name, language}) => {
      const flag = flagMapping[language as keyof typeof flagMapping];
      return `${flag} ${name}`;
    })
    .join(' ');
};
