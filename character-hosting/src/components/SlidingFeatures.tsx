import React, { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import DiscordChannel from './DiscordChannel';
import DiscordMessage from './DiscordMessage';
import BotAvatar from './BotAvatar';
import { BOT_CONFIG } from '../config/bot';
import { pokemonPredictor } from '../utils/pokemon/pokemon_predictor';

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
    fields?: { name: string; value: string; inline?: boolean }[];
    footer?: string;
    buttons?: { label: string; style?: 'primary' | 'secondary' | 'success' | 'danger' | 'link'; url?: string }[];
  };
}

const featureDemos: FeatureDemo[] = [
  {
    id: 'pokedex',
    title: '🔍 Pokédex Lookup',
    description: 'Search for any Pokémon and get detailed information, stats, and images from the comprehensive Pokédex database.',
    command: '.pokedex pikachu',
    embed: {
      title: '#025 — Pikachu',
      description: 'When several of these Pokémon gather, their electricity could build and cause lightning storms.',
      color: '#FF6B9D',
      image: 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png',
      fields: [
        { name: 'Names', value: '🇯🇵 ピカチュウ 🇺🇸 Pikachu 🇩🇪 Pikachu 🇫🇷 Pikachu 🇮🇹 Pikachu 🇰🇷 피카츄 🇯🇵 Pikachu', inline: true },
        { name: 'Region', value: '🗾 Kanto', inline: true }
      ],
      footer: 'Height: 1\'04" | Weight: 13.2 lbs | Gender: ♂ 50% - ♀ 50%'
    }
  },
  {
    id: 'spawn-detect',
    title: '⚡ Pokémon Spawn Events',
    description: 'Automatically detect wild Pokémon spawns in your server and get instant notifications with catch instructions.',
    command: '',
    embed: {
      title: 'A wild pokémon has appeared!',
      description: 'Guess the pokémon and type `@Pokétwo#8236 catch <pokémon>` to catch it!',
      color: '#FF6B9D',
      image: 'https://server.poketwo.io/image?time=day',
    }
  },
  {
    id: 'anime-search',
    title: '📺 Anime Database',
    description: 'Search through MyAnimeList database for detailed anime information, ratings, and recommendations.',
    command: '.anime recommend',
    embed: {
      title: 'Attack on Titan',
      description: 'Several hundred years ago, humans were nearly exterminated by Titans...',
      color: '#FF6B9D',
      image: 'https://cdn.myanimelist.net/images/anime/10/47347.jpg',
      fields: [
        { name: 'Rating', value: '⭐ 8.53/10', inline: false },
        { name: 'Episodes', value: '25', inline: false },
        { name: 'Status', value: 'Finished', inline: false },
        { name: 'Genres', value: 'Action, Drama, Fantasy', inline: false }
      ],
      footer: 'MyAnimeList • Source: Jikan API'
    }
  },
  {
    id: 'action-commands',
    title: '🎭 Action Commands',
    description: 'Interactive roleplay commands for fun interactions with other users in your server.',
    command: '.bite @user',
    embed: {
      title: 'Action: Bite',
      description: 'You playfully bit @senko!',
      color: '#FF6B9D',
      buttons: [
        { label: 'Do It Back', style: 'primary' }
      ],
      footer: 'Anya Bot • Roleplay Actions'
    }
  },
  {
    id: 'fun-commands',
    title: '🎮 Fun & Games',
    description: 'Enjoy interactive games and entertainment commands to engage your server community.',
    command: '.8ball Will I become a Pokémon Master?',
    embed: {
      title: '🎱 8Ball',
      description: '**Will I become a Pokémon Master?**\n◻️ It is decidedly so!',
      color: '#FF6B9D',
      footer: 'Requested by You'
    }
  }
];

const SlidingFeatures = () => {
  const [currentFeature, setCurrentFeature] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const [animeData, setAnimeData] = useState<any>(null);
  const [labels, setLabels] = useState<string[]>([]);
  const [predictedPokemon, setPredictedPokemon] = useState<string>('');
  const [pokemonImageUrl, setPokemonImageUrl] = useState<string>('');
  const [currentAction, setCurrentAction] = useState<string>('bite');
  const [currentUser, setCurrentUser] = useState<string>('senko');
  const [actionData, setActionData] = useState<any>(null);
  const [actionGif, setActionGif] = useState<string>('');
  const [cachedSpawnImageUrl, setCachedSpawnImageUrl] = useState<string>('');
  const [customSpawnUrl, setCustomSpawnUrl] = useState<string>('');
  const [spawnInputValue, setSpawnInputValue] = useState<string>('');

  const users = ['senko', 'anya', 'alex', 'jordan', 'sam', 'taylor', 'morgan', 'casey', 'riley', 'devin'];

  const len = featureDemos.length;

  // Get current timestamp in Discord format
  const getCurrentTimestamp = () => {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
    return `Today at ${timeString}`;
  };

  const changeFeature = (newIndex: number) => {
    if (isAnimating || newIndex === currentFeature) return;
    setIsAnimating(true);
    setCurrentFeature(newIndex);
    setTimeout(() => {
      setIsAnimating(false);
    }, 400);
  };

  const nextFeature = () => {
    changeFeature((currentFeature + 1) % len);
  };

  const prevFeature = () => {
    changeFeature((currentFeature - 1 + len) % len);
  };

  // Load labels for UI condition checks
  const loadLabels = async () => {
    try {
      // Labels are already loaded by loadModel(), just access them
      if (pokemonPredictor.labels && pokemonPredictor.labels.length > 0) {
        setLabels(pokemonPredictor.labels);
        console.log('Labels loaded for UI');
      } else {
        // If not loaded yet, wait a bit and try again
        setTimeout(() => {
          if (pokemonPredictor.labels && pokemonPredictor.labels.length > 0) {
            setLabels(pokemonPredictor.labels);
            console.log('Labels loaded for UI (delayed)');
          } else {
            setLabels(['pikachu', 'charizard', 'bulbasaur']);
            console.log('Using fallback labels for UI');
          }
        }, 1000);
      }
    } catch (error) {
      console.error('Failed to access labels:', error);
      setLabels(['pikachu', 'charizard', 'bulbasaur']);
    }
  };

  // Predict Pokémon from image URL using local predictor
  const predictPokemon = async (imageUrl: string) => {
    try {
      const prediction = await pokemonPredictor.predictFromUrl(imageUrl);
      console.log('Prediction result:', prediction);
      return prediction.name;
    } catch (error) {
      console.error('Prediction failed:', error);
      const predictorError = (pokemonPredictor as any).getError();
      if (predictorError) {
        console.error('Predictor error details:', predictorError);
        throw new Error(`Prediction failed: ${predictorError}`);
      }
      throw error;
    }
  };

  // Format embed like AnimeView class
  const formatAnimeEmbed = (anime: any) => {
    const imageUrl = getImageUrl(anime.images);
    const score = anime.score || 0;
    const scoreBar = '▰'.repeat(Math.floor(score)) + '▱'.repeat(10 - Math.floor(score));

    return {
      title: anime.title,
      description: anime.synopsis || '> <:anya_angy:1268976144548630608> Synopsis not available',
      color: '#FF6B9D',
      image: imageUrl,
      fields: [
        {
          name: ' ',
          value: `**Episodes:** \`${anime.episodes || 'Unknown'}\`\n` +
                 `**Status:** \`${anime.status || 'Unknown'}\`\n` +
                 `**Genres:** \`${anime.genres?.map((g: any) => g.name).join(', ') || 'Unknown'}\`\n` +
                 `${anime.trailer?.url ? '**Trailer:** ``' + anime.trailer.url + '``' : ''}\n` +
                 `\`\`\`py\nScore: ${score.toFixed(1).padStart(3)} (out of 10)\n${scoreBar}\`\`\``,
          inline: false
        }
      ],
      footer: 'MyAnimeList • Source: Jikan API'
    };
  };

  // Get image URL like AnimeView.get_image_url
  const getImageUrl = (images: any) => {
    const sizeOrder = ['large', 'medium', 'small'];
    for (const size of sizeOrder) {
      const jpgUrl = images?.jpg?.[`${size}_image_url`];
      if (jpgUrl) return jpgUrl;
    }
    for (const size of sizeOrder) {
      const webpUrl = images?.webp?.[`${size}_image_url`];
      if (webpUrl) return webpUrl;
    }
    return null;
  };

  // Fetch random anime data from Jikan API with rate limiting
  const fetchRandomAnime = async (retryCount = 0) => {
    const maxRetries = 5;
    const baseDelay = 1000;

    try {
      const randomId = Math.floor(Math.random() * 5000) + 1;
      const response = await fetch(`https://api.jikan.moe/v4/anime/${randomId}`);

      if (response.status === 429) {
        if (retryCount < maxRetries) {
          const delay = baseDelay * Math.pow(2, retryCount);
          console.log(`Jikan API rate limited, retrying in ${delay}ms (attempt ${retryCount + 1}/${maxRetries})`);
          await new Promise(resolve => setTimeout(resolve, delay));
          return fetchRandomAnime(retryCount + 1);
        } else {
          console.log('Max retries reached for Jikan API, using static anime data');
          setAnimeData({
            title: 'Attack on Titan',
            synopsis: 'Several hundred years ago, humans were nearly exterminated by Titans...',
            images: { jpg: { large_image_url: 'https://cdn.myanimelist.net/images/anime/10/47347.jpg' } },
            episodes: 25,
            status: 'Finished',
            genres: [{ name: 'Action' }, { name: 'Drama' }, { name: 'Fantasy' }],
            score: 8.53
          });
          return;
        }
      }

      if (!response.ok) {
        if (response.status === 404) {
          console.log(`Anime ID ${randomId} not found, trying another...`);
          return fetchRandomAnime(0);
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();

      if (data.data) {
        setAnimeData(data.data);
      } else {
        fetchRandomAnime(0);
      }
    } catch (error) {
      console.error('Failed to fetch anime data:', error);
      setAnimeData({
        title: 'Attack on Titan',
        synopsis: 'Several hundred years ago, humans were nearly exterminated by Titans...',
        images: { jpg: { large_image_url: 'https://cdn.myanimelist.net/images/anime/10/47347.jpg' } },
        episodes: 25,
        status: 'Finished',
        genres: [{ name: 'Action' }, { name: 'Drama' }, { name: 'Fantasy' }],
        score: 8.53
      });
    }
  };

  // Get Pokémon image URL from prediction
  const getPokemonImageUrl = async (pokemonName: string) => {
    try {
      const imageUrlsResponse = await fetch('/models/pokemon/image_urls.json');
      const imageUrls = await imageUrlsResponse.json();
      return imageUrls[pokemonName] || '';
    } catch (error) {
      console.error('Failed to get Pokémon image:', error);
      return '';
    }
  };

  const loadActionData = async () => {
    try {
      const response = await fetch('/data/action-response.json');
      const data = await response.json();
      setActionData(data);
      console.log('Action data loaded');
    } catch (error) {
      console.error('Failed to load action data:', error);
    }
  };

  const fetchActionGif = async (action: string) => {
    try {
      const response = await fetch(`https://api.otakugifs.xyz/gif?reaction=${action}`);
      const data = await response.json();
      return data.url || '';
    } catch (error) {
      console.error('Failed to fetch action GIF:', error);
      return '';
    }
  };

  const buildActionMessage = (action: string, user: string, target: string) => {
    if (!actionData) return '';

    const phrases = actionData.phrases;
    let phrase = '';

    if (user === target) {
      phrase = phrases.self[action] || `${action}s`;
    } else if (target.toLowerCase() === 'everyone') {
      phrase = phrases.everyone[action] || `${action}s`;
    } else {
      phrase = phrases.other[action] || `${action}s`;
    }

    phrase = phrase.replace('[no_embed]', '').trim();
    return phrase.replace('{user}', user).replace('{target}', target);
  };

  const handleSpawnUrlSubmit = async (url: string) => {
    if (!url.trim()) return;

    setCustomSpawnUrl(url.trim());
    setCachedSpawnImageUrl(url.trim());
    setSpawnInputValue('');

    try {
      const prediction = await predictPokemon(url.trim());
      setPredictedPokemon(prediction);
      const imageUrl = await getPokemonImageUrl(prediction);
      setPokemonImageUrl(imageUrl);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown prediction error';
      console.error('There was an error predicting image:', errorMessage);
      setPredictedPokemon(`Error: ${errorMessage}`);
      setPokemonImageUrl('');
    }
  };

  useEffect(() => {
    fetchRandomAnime();
    loadLabels();
    loadActionData();
    pokemonPredictor.loadModel().catch((error) => {
      console.error('Failed to load Pokemon predictor model:', error);
    });
  }, []);

  useEffect(() => {
    const predictForSpawn = async () => {
      if (currentFeature === 1 && labels.length > 0) {
        console.log('Detector:', pokemonPredictor);

        if (!cachedSpawnImageUrl) {
          try {
            const spawnImageUrl = customSpawnUrl || 'https://server.poketwo.io/image?time=day';
            setCachedSpawnImageUrl(spawnImageUrl);
            console.log('Cached spawn image:', spawnImageUrl);

            if (!customSpawnUrl) {
              const prediction = await predictPokemon(spawnImageUrl);
              setPredictedPokemon(prediction);
              const imageUrl = await getPokemonImageUrl(prediction);
              setPokemonImageUrl(imageUrl);
            }
          } catch (error) {
            console.error('Failed to cache spawn image:', error);
            return;
          }
        }
      } else {
        setCachedSpawnImageUrl('');
        setCustomSpawnUrl('');
        setPredictedPokemon('');
        setPokemonImageUrl('');
      }
    };

    predictForSpawn();
  }, [currentFeature, labels, cachedSpawnImageUrl, customSpawnUrl]);

  useEffect(() => {
    const loadActionDemo = async () => {
      if (currentFeature === 3 && actionData) {
        const availableActions = Object.keys(actionData.phrases.other);
        const randomAction = availableActions[Math.floor(Math.random() * availableActions.length)];
        const randomUser = users[Math.floor(Math.random() * users.length)];

        setCurrentAction(randomAction);
        setCurrentUser(randomUser);

        const gifUrl = await fetchActionGif(randomAction);
        setActionGif(gifUrl);
      }
    };

    loadActionDemo();
  }, [currentFeature, actionData]);

  const currentDemo = featureDemos[currentFeature];

  const getCurrentEmbed = () => {
    if (currentDemo.id === 'anime-search' && animeData) {
      return formatAnimeEmbed(animeData);
    }
    if (currentDemo.id === 'action-commands') {
      const message = buildActionMessage(currentAction, 'You', currentUser);
      return {
        title: message,
        color: '#FF6B9D',
        image: actionGif,
        footer: 'Sent: 0 | Received: 0',
      };
    }
    return currentDemo.embed;
  };

  const getCurrentCommand = () => {
    if (currentDemo.id === 'action-commands') {
      return `.${currentAction} @${currentUser}`;
    }
    return currentDemo.command;
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <div className="flex-shrink-0 text-center mb-6">
        <h3 className="text-xl md:text-2xl font-bold text-white mb-2">
          Live Command Demos
        </h3>
        <p className="text-sm text-gray-400">
          See Anya Bot in action with real commands and responses
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="relative overflow-hidden bg-dark-800 rounded-xl border border-dark-600 shadow-2xl">
          <div className={`transition-all duration-400 ease-in-out transform ${isAnimating ? 'opacity-0' : 'opacity-100'} translate-x-0`}>
            <div className="p-6 md:p-8">
              <div className="bg-dark-900 rounded-lg border border-dark-700 overflow-hidden">
                <div className="px-4 py-2 bg-dark-800 border-b border-dark-700">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                    <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span className="text-xs text-gray-400 ml-2">Discord Preview</span>
                  </div>
                </div>

                <div className="">
                  <DiscordChannel channelName="bot-commands" className="border-0 rounded-none" flexibleHeight={true}>
                    {currentDemo.id === 'spawn-detect' ? (
                      <>
                        <div className="px-4 py-3 border-b border-dark-700">
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={spawnInputValue}
                              onChange={(e) => setSpawnInputValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  handleSpawnUrlSubmit(spawnInputValue);
                                }
                              }}
                              placeholder="Enter image URL to test spawn detection..."
                              className="flex-1 px-3 py-2 bg-dark-800 border border-dark-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary"
                            />
                            <button
                              onClick={() => handleSpawnUrlSubmit(spawnInputValue)}
                              className="px-4 py-2 bg-primary hover:bg-primary/80 text-white rounded-lg transition-colors"
                            >
                              Test
                            </button>
                          </div>
                          <p className="text-xs text-gray-400 mt-1">
                            Enter any image URL to create a custom spawn and see Anya detect it!
                          </p>
                        </div>

                        <DiscordMessage
                          username="Pokétwo#8236"
                          avatar={<img src="https://poketwo.net/_next/image?url=%2Fassets%2Flogo.png&w=640&q=100" alt="Pokétwo" className="rounded-full object-cover" />}
                          isBot={true}
                          embed={{
                            title: 'A wild pokémon has appeared!',
                            description: 'Guess the pokémon and type `@Pokétwo#8236 catch <pokémon>` to catch it!',
                            color: '#FF6B9D',
                            image: cachedSpawnImageUrl || 'https://server.poketwo.io/image?time=day',
                          }}
                          timestamp={getCurrentTimestamp()}
                        />

                        <DiscordMessage
                          username={BOT_CONFIG.name}
                          avatar={<BotAvatar />}
                          isBot={true}
                          embed={{
                            title: `Pokémon Detected: ${predictedPokemon}`,
                            color: '#FF6B9D',
                            image: pokemonImageUrl,
                            footer: 'Anya Bot • Pokémon Detection',
                          }}
                          timestamp={getCurrentTimestamp()}
                        />
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
                          isBot={true}
                          embed={getCurrentEmbed()}
                          components={currentDemo.id === 'action-commands' ? { buttons: [{ label: 'Do It Back', style: 'primary' }] } : undefined}
                          timestamp={getCurrentTimestamp()}
                        />
                      </>
                    )}
                  </DiscordChannel>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-shrink-0 flex items-center justify-center gap-4 mt-6 pb-6">
        <button
          onClick={prevFeature}
          disabled={isAnimating}
          className="p-2 bg-dark-800 hover:bg-dark-700 text-white rounded-lg transition-colors disabled:opacity-50 border border-dark-600"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        <div className="flex gap-2">
          {featureDemos.map((_, index) => (
            <button
              key={index}
              onClick={() => changeFeature(index)}
              className={`w-2 h-2 rounded-full transition-all duration-200 ${
                index === currentFeature
                  ? 'bg-primary w-6'
                  : 'bg-gray-600 hover:bg-gray-500'
              }`}
            />
          ))}
        </div>

        <button
          onClick={nextFeature}
          disabled={isAnimating}
          className="p-2 bg-dark-800 hover:bg-dark-700 text-white rounded-lg transition-colors disabled:opacity-50 border border-dark-600"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default SlidingFeatures;