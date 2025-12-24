import React, { useState, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import DiscordChannel from './DiscordChannel';
import DiscordMessage from './DiscordMessage';
import BotAvatar from './BotAvatar';
import { BOT_CONFIG } from '../config/bot';
import { pokemonPredictor } from '../utils/pokemon/pokemon_predictor';
import { SAMPLE_SPAWN_IMAGE_URL } from '../utils/pokemon/model_config';
import { getRegionEmoji } from '../utils/emojiUtils';

// ---------------------------------------------------------------------------
// Types (unchanged – kept for context)
// ---------------------------------------------------------------------------
interface ImageUrls {
  jpg?: {
    large_image_url?: string;
    medium_image_url?: string;
    small_image_url?: string;
  };
  webp?: {
    large_image_url?: string;
    medium_image_url?: string;
    small_image_url?: string;
  };
}
interface Genre { name: string; }
interface Trailer { url: string; }

interface AnimeData {
  title: string;
  synopsis?: string;
  images?: ImageUrls;
  episodes?: number;
  status?: string;
  genres?: Genre[];
  score?: number;
  trailer?: Trailer;
}
interface ActionData {
  phrases: {
    self: Record<string, string>;
    everyone: Record<string, string>;
    other: Record<string, string>;
  };
}
interface PokemonSpecies {
  id: number;
  name: string;
  url?: string;
  genera?: Array<{ genus: string; language: { name: string } }>;
  flavor_text_entries?: Array<{ flavor_text: string; language: { name: string } }>;
  habitat?: { name: string };
  is_legendary?: boolean;
  is_mythical?: boolean;
  gender_rate?: number;
  names?: Array<{ name: string; language: { name: string } }>;
}
interface PokemonData {
  id: number;
  name: string;
  height: number;
  weight: number;
  sprites: {
    other: {
      'official-artwork': { front_default: string };
    };
    versions?: {
      'generation-v': {
        'black-white': {
          animated: {
            front_default: string;
          }
        }
      }
    };
  };
  types: Array<{ type: { name: string } }>;
  species: PokemonSpecies;
}
interface ActionButton {
  label: string;
  style?: 'primary' | 'secondary' | 'success' | 'danger' | 'link';
  url?: string;
}
interface EmbedField {
  name: string;
  value: string;
  inline?: boolean;
}
interface FeatureDemo {
  id: string;
  title: string;
  description: string;
  command: string;
  embed: {
    title?: string;
    description?: string;
    color?: string;
    image?: string;
    thumbnail?: string;
    fields?: EmbedField[];
    footer?: string;
    buttons?: ActionButton[];
  };
}

// ---------------------------------------------------------------------------
// Feature data
// ---------------------------------------------------------------------------
const featureDemos: FeatureDemo[] = [
  {
    id: 'pokedex',
    title: 'Pokedex Lookup',
    description: 'Search for any Pokémon and get detailed information, stats, and images.',
    command: '.pokedex pikachu',
    embed: { title: 'Loading Pokémon...', description: 'Fetching data...', color: '#FF6B9D' },
  },
  {
    id: 'spawn-detect',
    title: 'Pokemon Spawn Events',
    description: 'Automatically detect wild Pokémon spawns and get instant notifications.',
    command: '',
    embed: {
      title: 'A wild pokémon has appeared!',
      description: 'Guess the pokémon and type `@Pokétwo#8236 catch <pokémon>` to catch it!',
      color: '#FF6B9D',
      image: SAMPLE_SPAWN_IMAGE_URL,
      buttons: [
        { label: 'View Spawn', style: 'link', url: '#' },
        { label: 'Catch', style: 'primary' }
      ]
    },
  },
  {
    id: 'anime-search',
    title: 'Anime Database',
    description: 'Search through MyAnimeList for detailed anime information.',
    command: '.anime recommend',
    embed: { 
      title: 'Anime Search Results', 
      description: 'Searching...', 
      color: '#FF6B9D', 
      footer: 'MyAnimeList • Jikan API',
      buttons: [
        { label: 'View Reviews', style: 'link', url: '#' },
        { label: 'Recommend', style: 'primary' }
      ]
    },
  },
  {
    id: 'action-commands',
    title: 'Action Commands',
    description: 'Interactive roleplay commands for fun interactions.',
    command: '.bite @user',
    embed: {
      title: 'Action: Bite',
      description: 'You playfully bit @senko!',
      color: '#FF6B9D',
      footer: 'Anya Bot • Roleplay Actions',
    },
  },
  
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
const SlidingFeatures: React.FC = () => {
  const [currentFeature, setCurrentFeature] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

  // Demo-specific state
  const [animeData, setAnimeData] = useState<AnimeData | null>(null);
  const [pokemonData, setPokemonData] = useState<PokemonData | null>(null);
  const [actionData, setActionData] = useState<ActionData | null>(null);
  const [currentAction, setCurrentAction] = useState<string>('');
  const [currentActionUser, setCurrentActionUser] = useState<string>('');
  const [actionGif, setActionGif] = useState<string>('');

  // Spawn detection state
  const [customSpawnUrl, setCustomSpawnUrl] = useState<string>('');
  const [cachedSpawnImageUrl, setCachedSpawnImageUrl] = useState<string>('');
  const [predictedPokemon, setPredictedPokemon] = useState<string>('');
  const [_spawnInputValue, setSpawnInputValue] = useState<string>('');
  const [_pokemonImageUrl, setPokemonImageUrl] = useState<string>('');

  const users = ['senko', 'anya', 'alex', 'jordan', 'sam', 'taylor', 'morgan', 'casey', 'riley', 'devin'];
  const total = featureDemos.length;

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------
  const changeFeature = (idx: number) => {
    if (isAnimating || idx === currentFeature) return;
    setIsAnimating(true);
    setCurrentFeature(idx);
    setTimeout(() => setIsAnimating(false), 400);
  };
  const nextFeature = () => changeFeature((currentFeature + 1) % total);
  const prevFeature = () => changeFeature((currentFeature - 1 + total) % total);

  const getCurrentTimestamp = () => new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });

  // Flag mapping for alternate names
  const getFlagEmoji = (lang: string): string => {
    const flagMapping: { [key: string]: string } = {
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
    return flagMapping[lang] || "";
  };

  // -----------------------------------------------------------------------
  // Data loading
  // -----------------------------------------------------------------------
  const fetchRandomAnime = async () => {
    try {
      const res = await fetch('https://api.jikan.moe/v4/random/anime');
      const data = await res.json();
      setAnimeData(data.data);
    } catch (err) {
      console.error('Failed to load anime:', err);
    }
  };

  const fetchRandomPokemon = async () => {
    try {
      const randomId = Math.floor(Math.random() * 1025) + 1;
      // Fetch basic Pokémon data
      const pokemonResponse = await fetch(`https://pokeapi.co/api/v2/pokemon/${randomId}`);
      if (!pokemonResponse.ok) {
        throw new Error(`Failed to fetch Pokémon: ${pokemonResponse.status}`);
      }
      const pokemon: PokemonData = await pokemonResponse.json();
      // Fetch species data for additional info
      const speciesUrl = pokemon.species.url;
      if (!speciesUrl) {
        throw new Error('Species URL not available');
      }
      const speciesResponse = await fetch(speciesUrl);
      if (!speciesResponse.ok) {
        throw new Error(`Failed to fetch species: ${speciesResponse.status}`);
      }
      const species: PokemonSpecies = await speciesResponse.json();
      setPokemonData({ ...pokemon, species });
    } catch (error) {
      console.error('Failed to fetch Pokémon data:', error);
      // Fallback to static data
      setPokemonData({
        id: 25,
        name: 'pikachu',
        height: 4,
        weight: 60,
        sprites: {
          other: {
            'official-artwork': {
              front_default: 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png'
            }
          },
          versions: {
            'generation-v': {
              'black-white': {
                animated: {
                  front_default: 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/animated/25.gif'
                }
              }
            }
          }
        },
        types: [{ type: { name: 'electric' } }],
        species: {
          id: 25,
          name: 'pikachu',
          genera: [{ genus: 'Mouse Pokémon', language: { name: 'en' } }],
          flavor_text_entries: [{ flavor_text: 'When several of these Pokémon gather, their electricity could build and cause lightning storms.', language: { name: 'en' } }],
          names: [
            { name: 'ピカチュウ', language: { name: 'ja' } },
            { name: 'Pikachu', language: { name: 'en' } },
            { name: 'Pikachu', language: { name: 'de' } },
            { name: 'Pikachu', language: { name: 'fr' } }
          ],
          gender_rate: 4,
          is_legendary: false,
          is_mythical: false
        } as PokemonSpecies
      });
    }
  };

  const loadActionData = async () => {
    try {
      const res = await fetch('/data/action-response.json');
      const data = await res.json();
      setActionData(data);
    } catch (e) {
      console.error('Failed to load action data', e);
    }
  };

  // -----------------------------------------------------------------------
  // Spawn detection prediction
  // -----------------------------------------------------------------------
  const predictAndSet = useCallback(async (url: string) => {
    try {
      const prediction = await pokemonPredictor.predictFromUrl(url);
      setPredictedPokemon(prediction.name);
      const imgRes = await fetch('/models/pokemon/image_urls.json');
      const map = await imgRes.json();
      setPokemonImageUrl(map[prediction.name] || '');
    } catch (e) {
      console.error('Prediction failed', e);
      setPredictedPokemon('unknown');
    }
  }, []);

  // Run prediction when we are on the spawn-detect slide
  useEffect(() => {
    if (featureDemos[currentFeature].id !== 'spawn-detect') {
      setCachedSpawnImageUrl('');
      setCustomSpawnUrl('');
      setPredictedPokemon('');
      setPokemonImageUrl('');
      return;
    }
    const url = customSpawnUrl || SAMPLE_SPAWN_IMAGE_URL;
    setCachedSpawnImageUrl(url);
    if (!customSpawnUrl) {
      predictAndSet(url);
    }
  }, [currentFeature, customSpawnUrl, predictAndSet]);

  // Handle manual URL submission (kept for future input feature)
  const handleSpawnUrlSubmit = (url: string) => {
    if (!url.trim()) return;
    setCustomSpawnUrl(url.trim());
    setSpawnInputValue('');
    predictAndSet(url.trim());
  };
  void handleSpawnUrlSubmit; // Suppress unused warning

  // -----------------------------------------------------------------------
  // Action command demo – random action + GIF
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (featureDemos[currentFeature].id !== 'action-commands' || !actionData) return;
    const actions = Object.keys(actionData.phrases.other);
    const randomAction = actions[Math.floor(Math.random() * actions.length)];
    setCurrentAction(randomAction);
    const randomUser = users[Math.floor(Math.random() * users.length)];
    setCurrentActionUser(randomUser);
    const fetchGif = async () => {
      try {
        const res = await fetch(`https://api.otakugifs.xyz/gif?reaction=${randomAction}`);
        const json = await res.json();
        setActionGif(json.url || '');
      } catch {
        setActionGif('');
      }
    };
    fetchGif();
  }, [currentFeature, actionData]);

  // -----------------------------------------------------------------------
  // Initial data loads
  // -----------------------------------------------------------------------
  useEffect(() => {
    fetchRandomAnime();
    fetchRandomPokemon();
    loadActionData();
    pokemonPredictor.loadModel().catch(console.error);
  }, []);

  // -----------------------------------------------------------------------
  // Embed formatting helpers
  // -----------------------------------------------------------------------
  const currentDemo = featureDemos[currentFeature];

  const getImageUrl = (images?: ImageUrls) => {
    const order = ['large_image_url', 'medium_image_url', 'small_image_url'] as const;
    for (const key of order) {
      if (images?.jpg?.[key]) return images.jpg[key];
      if (images?.webp?.[key]) return images.webp[key];
    }
    return undefined;
  };

  const formatAnimeEmbed = (anime: AnimeData) => {
    const imageUrl = getImageUrl(anime.images);
    const score = Math.floor(anime.score || 0);
    const bar = '▰'.repeat(score) + '▱'.repeat(10 - score);
    // Format synopsis with markdown blockquote
    const synopsis = anime.synopsis 
      ? anime.synopsis.split('\n').map(line => `> ${line}`).join('\n')
      : '> *Synopsis not available*';
    return {
      title: anime.title,
      description: synopsis,
      color: '#FF6B9D',
      image: imageUrl,
      fields: [{
        name: ' ',
        value: `**Episodes:** \`${anime.episodes || 'Unknown'}\`\n` +
               `**Status:** \`${anime.status || 'Unknown'}\`\n` +
               `**Genres:** \`${anime.genres?.map(g => g.name).join(', ') || 'Unknown'}\`\n` +
               `\`\`\`\nScore: ${ (anime.score || 0).toFixed(1) }/10\n${bar}\`\`\``,
        inline: false,
      }],
      footer: 'MyAnimeList • Source: Jikan API',
    };
  };

  const formatPokemonEmbed = (pokemon: PokemonData) => {
    const species = pokemon.species;
    const id = pokemon.id;
    const name = pokemon.name.replace('-', ' ').toLowerCase();

    // Get flavor text (English)
    const pokemonDescription = species.flavor_text_entries?.find(
      entry => entry.language.name === 'en'
    )?.flavor_text?.replace(/\n|\f/g, ' ') || '';

    // Determine region based on ID
    let region = 'Kanto';
    if (id >= 898 && id <= 1025) region = 'Paldea';
    else if (id >= 809 && id <= 898) region = 'Galar';
    else if (id >= 722 && id <= 809) region = 'Alola';
    else if (id >= 650 && id <= 721) region = 'Kalos';
    else if (id >= 494 && id <= 649) region = 'Unova';
    else if (id >= 387 && id <= 493) region = 'Sinnoh';
    else if (id >= 252 && id <= 386) region = 'Hoenn';
    else if (id >= 152 && id <= 251) region = 'Johto';

    // Get region emoji
    const regionEmoji = getRegionEmoji(region);
    const regionDisplay = regionEmoji ? `${regionEmoji} ${region}` : region;

    // Get alternate names
    const alternateNames = species.names || [];
    const altNamesInfo: { [key: string]: string } = {};
    for (const nameData of alternateNames) {
      const lang = nameData.language.name;
      const altName = nameData.name;
      const flag = getFlagEmoji(lang);
      if (flag && altName.toLowerCase() !== lang.toLowerCase()) {
        const key = altName.toLowerCase();
        if (!altNamesInfo[key]) {
          altNamesInfo[key] = `${flag} ${altName}`;
        }
      }
    }
    const nameList = Object.values(altNamesInfo).sort((a, b) => a.length - b.length);
    const altNamesStr = nameList.slice(0, 6).join('\n') || 'No alternate names available.';

    // Get gender ratio
    const genderRate = species.gender_rate ?? 4; // Default to 50/50 if undefined
    let gender = '♂ 50% - ♀ 50%';
    if (genderRate === -1) {
      gender = 'Genderless';
    } else if (genderRate === 0) {
      gender = '♂️ Male only';
    } else if (genderRate === 8) {
      gender = '♀️ Female only';
    } else {
      const femaleRatio = (8 - genderRate) / 8;
      const maleRatio = genderRate / 8;
      const malePercentage = Math.round(maleRatio * 100);
      const femalePercentage = Math.round(femaleRatio * 100);
      gender = `♂ ${malePercentage}% - ♀ ${femalePercentage}%`;
    }

    // Determine rarity
    const isLegendary = species.is_legendary;
    const isMythical = species.is_mythical;
    let rarity = '';
    if (isLegendary) rarity = 'Legendary';
    else if (isMythical) rarity = 'Mythical';

    // Get thumbnail (black-white animated sprite)
    const imageThumb = pokemon.sprites.versions?.['generation-v']?.['black-white']?.animated?.front_default;

    // Format height and weight
    const height = (pokemon.height / 10).toFixed(1);
    const weight = (pokemon.weight / 10).toFixed(1);

    // Build footer text with new lines
    let footerText = `${gender}\nHeight: ${height}m • Weight: ${weight}kg`;
    if (rarity) {
      footerText = `${rarity}\n${footerText}`;
    }
    footerText += `\nPokédex • Source: PokeAPI`;

    // Capitalize name for title
    const capitalizedName = name.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');

    return {
      title: `#${id} — ${capitalizedName}`,
      description: pokemonDescription,
      color: '#FF6B9D',
      image: pokemon.sprites.other['official-artwork'].front_default,
      fields: [{
        name: 'Region',
        value: regionDisplay,
        inline: true,
      }, {
        name: 'Alternate Names',
        value: altNamesStr,
        inline: true,
      }],
      footer: {
        text: footerText,
        icon_url: imageThumb,
      },
    };
  };

  const formatActionEmbed = () => {
    if (!actionData || !actionData.phrases.other[currentAction]) {
      return {
        title: 'Action: Bite',
        description: 'You playfully bit @senko!',
        color: '#FF6B9D',
        footer: 'Anya Bot • Roleplay Actions',
      };
    }
    const phrase = actionData.phrases.other[currentAction]
      .replace('{user}', 'You')
      .replace('{target}', `@${currentActionUser}`);
    return {
      title: phrase,
      //description: phrase,
      color: '#FF6B9D',
      image: actionGif,
      footer: 'Sent: 0 | Received: 0\nAnya Bot • Roleplay Actions',
    };
  };

  const formatFunEmbed = () => {
    const eightBallAnswers = [
      'It is certain.',
      'It is decidedly so.',
      'Without a doubt.',
      'Yes definitely.',
      'You may rely on it.',
      'As I see it, yes.',
      'Most likely.',
      'Outlook good.',
      'Yes.',
      'Signs point to yes.',
      'Reply hazy, try again.',
      'Ask again later.',
      'Better not tell you now.',
      'Cannot predict now.',
      'Concentrate and ask again.',
      "Don't count on it.",
      'My reply is no.',
      'My sources say no.',
      'Outlook not so good.',
      'Very doubtful.',
    ];
    const question = 'Will I become a Pokémon Master?';
    const answer = eightBallAnswers[Math.floor(Math.random() * eightBallAnswers.length)];
    return {
      title: '8Ball',
      description: `**${question}**\n${answer}`,
      color: '#FF6B9D',
      footer: 'Requested by You',
    };
  };

  const getCurrentEmbed = () => {
    if (currentDemo.id === 'pokedex' && pokemonData) return formatPokemonEmbed(pokemonData);
    if (currentDemo.id === 'anime-search' && animeData) return formatAnimeEmbed(animeData);
    if (currentDemo.id === 'action-commands' && actionData) return formatActionEmbed();
    if (currentDemo.id === 'fun-commands') return formatFunEmbed();
    return currentDemo.embed;
  };

  const getCurrentCommand = () => {
    if (currentDemo.id === 'pokedex' && pokemonData) {
      return `.pokedex ${pokemonData.name}`;
    }
    if (currentDemo.id === 'action-commands') {
      return `.${currentAction} @${currentActionUser}`;
    }
    return currentDemo.command;
  };

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <div className="flex-shrink-0 text-center mb-6">
        <h3 className="text-xl md:text-2xl font-bold text-white mb-2">Live Command Demos</h3>
        <p className="text-sm text-gray-400">See Anya Bot in action with real commands and responses</p>
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="relative overflow-hidden bg-dark-800 rounded-xl border border-dark-600 shadow-2xl">
          <div className={`transition-all duration-400 ease-in-out ${isAnimating ? 'opacity-0' : 'opacity-100'}`}>
            <div className="p-6 md:p-8">
              <div className="bg-dark-900 rounded-lg border border-dark-700 overflow-hidden">
                <div className="px-4 py-2 bg-dark-800 border-b border-dark-700 flex items-center gap-2">
                  <div className="w-2 h-2 bg-red-500 rounded-full" />
                  <span className="text-xs text-gray-400">Discord Preview</span>
                </div>
                <DiscordChannel channelName="bot-commands" className="border-0 rounded-none" flexibleHeight>
                  {currentDemo.id === 'spawn-detect' ? (
                    <>
                      <div className="px-4 py-3 border-b border-dark-700">
                                      </div>
                      <DiscordMessage
                        username="Pokétwo#8236"
                        avatar={<img src="https://poketwo.net/_next/image?url=%2Fassets%2Flogo.png&w=640&q=100" alt="Pokétwo" className="rounded-full" />}
                        isBot
                        embed={{
                          title: 'A wild pokémon has appeared!',
                          description: 'Guess the pokémon and type `@Pokétwo#8236 catch <pokémon>` to catch it!',
                          color: '#FF6B9D',
                          image: cachedSpawnImageUrl || SAMPLE_SPAWN_IMAGE_URL,
                        }}
                        timestamp={getCurrentTimestamp()}
                      />
                      {predictedPokemon && (
                        <DiscordMessage
                          username={BOT_CONFIG.name}
                          avatar={<BotAvatar />}
                          isBot
                          embed={{
                            image: "https://res.cloudinary.com/dbgrdkwfv/image/upload/v1761896637/poketwo_spawns/vulpix-alola.png", //pokemonImageUrl,
                          }}
                        
                          timestamp={getCurrentTimestamp()}
                        />
                      )}
                    </>
                  ) : (
                    <>
                      <DiscordMessage
                        username="You"
                        isBot={false}
                        content={getCurrentCommand()}
                        timestamp={getCurrentTimestamp()}
                      />
                      <DiscordMessage
                        username={BOT_CONFIG.name}
                        avatar={<BotAvatar />}
                        isBot
                        embed={getCurrentEmbed()}
                        components={
                          currentDemo.id === 'pokedex'
                            ? { buttons: [
                                { label: 'Stats', style: 'secondary' },
                                { label: 'Evolutions', style: 'secondary' }
                              ] }
                            : currentDemo.id === 'anime-search'
                            ? { buttons: [
                                { label: 'View Reviews', style: 'link', url: animeData?.trailer?.url || '#' },
                                { label: 'Recommend', style: 'primary', onClick: fetchRandomAnime }
                              ] }
                            : currentDemo.id === 'action-commands'
                            ? { buttons: [{ label: 'Do It Back', style: 'primary' }] }
                            : undefined
                        }
                        timestamp={getCurrentTimestamp()}
                      />
                    </>
                  )}
                </DiscordChannel>
              </div>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-center gap-4 mt-6 pb-6">
          <button
            onClick={prevFeature}
            disabled={isAnimating}
            className="p-2 bg-dark-800 hover:bg-dark-700 text-white rounded-lg transition-colors disabled:opacity-50 border border-dark-600"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <div className="flex gap-2">
            {featureDemos.map((_, i) => (
              <button
                key={i}
                onClick={() => changeFeature(i)}
                className={`w-2 h-2 rounded-full transition-all ${
                  i === currentFeature ? 'bg-primary w-8' : 'bg-gray-600 hover:bg-gray-500'
                }`}
              />
            ))}
          </div>
          <button
            onClick={nextFeature}
            disabled={isAnimating}
            className="p-2 bg-dark-800 hover:bg-dark-700 text-white rounded-lg transition-colors disabled:opacity-50 border border-dark-600"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default SlidingFeatures;