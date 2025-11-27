import { useRef, useEffect, useState } from 'react';
import { 
  Gamepad2, Search, Sparkles, Wand2, Heart,
  Music, Star
} from 'lucide-react';

interface Feature {
  id: string;
  icon: React.ElementType;
  title: string;
  anyaComment: string;  // Anya's reaction to this feature
  description: string;
  highlights: string[];
  gradient: string;
  command?: string;
  layout: 'hero' | 'split' | 'cards' | 'minimal' | 'spotlight' | 'compact';
  emoji?: string;
}

const features: Feature[] = [
  {
    id: 'pokemon',
    icon: Gamepad2,
    title: 'Pokémon Detection',
    anyaComment: "Waku waku! Anya can find all the Pokémon! ✨",
    description: 'Advanced spawn detection that identifies Pokémon instantly. Complete Pokédex with stats, evolutions, and shiny tracking.',
    highlights: ['🔍 Auto Detection', '📖 Full Pokédex', '✨ Shiny Tracker', '📊 IV Lookup'],
    gradient: 'from-yellow-400 via-orange-500 to-red-500',
    command: '.pokedex pikachu',
    layout: 'hero',
    emoji: '🎮',
  },
  {
    id: 'anime',
    icon: Search,
    title: 'Anime Search',
    anyaComment: "Spy x Family is Anya's favorite! Heh~ 😏",
    description: 'Search any anime or manga with MyAnimeList integration. Synopses, ratings, and personalized recommendations.',
    highlights: ['MAL Integration', 'Character Search', 'Seasonal Picks', 'Smart Recommendations'],
    gradient: 'from-pink-500 via-rose-500 to-red-500',
    command: '.anime Spy x Family',
    layout: 'split',
    emoji: '📺',
  },
  {
    id: 'roleplay',
    icon: Heart,
    title: 'Roleplay Actions',
    anyaComment: "Anya loves hugs from Papa and Mama! 💕",
    description: '50+ expressive actions with animated GIFs. Hug, pat, boop, and more!',
    highlights: ['hug', 'pat', 'poke', 'slap', 'kiss', 'wave'],
    gradient: 'from-pink-400 to-purple-500',
    command: '.hug @friend',
    layout: 'cards',
    emoji: '💖',
  },
  {
    id: 'fun',
    icon: Sparkles,
    title: 'Fun & Games',
    anyaComment: "Anya predicts... you will have fun! 🔮",
    description: '8ball fortunes, jokes, memes, and mini-games to keep your server entertained.',
    highlights: ['🎱 8Ball', '😂 Jokes', '🖼️ Memes', '🎲 Games'],
    gradient: 'from-cyan-400 via-blue-500 to-indigo-500',
    command: '.8ball Am I elegant?',
    layout: 'minimal',
    emoji: '🎉',
  },
  {
    id: 'utility',
    icon: Wand2,
    title: 'Utility Tools',
    anyaComment: "Very useful! Anya is big brain! 🧠",
    description: 'Essential server tools: avatar lookup, user info, server stats, and more.',
    highlights: ['Avatar Grab', 'User Info', 'Server Stats', 'Role Tools'],
    gradient: 'from-emerald-400 to-teal-500',
    command: '.avatar @user',
    layout: 'spotlight',
    emoji: '🛠️',
  },
  {
    id: 'music',
    icon: Music,
    title: 'Music Player',
    anyaComment: "Anya wants to listen to Spy x Family opening! 🎵",
    description: 'High-quality playback with queue management. YouTube, Spotify, and more.',
    highlights: ['🎵 YouTube', '📋 Queue', '🔊 Volume', '▶️ Controls'],
    gradient: 'from-violet-500 via-purple-500 to-fuchsia-500',
    command: '.play Mixed Nuts',
    layout: 'compact',
    emoji: '🎧',
  },
];

// Different layout components for variety
const HeroLayout = ({ feature, isVisible }: { feature: Feature; isVisible: boolean }) => {
  const Icon = feature.icon;
  return (
    <div className={`relative overflow-hidden rounded-3xl bg-gradient-to-br ${feature.gradient} p-1`}>
      <div className="bg-dark-900 rounded-[22px] p-8 md:p-12">
        <div className="flex flex-col lg:flex-row items-center gap-8">
          <div className="flex-1 text-center lg:text-left">
            <span className="text-4xl mb-4 block">{feature.emoji}</span>
            <h3 className="text-3xl md:text-5xl font-display font-bold text-white mb-4">{feature.title}</h3>
            <p className="text-gray-400 text-lg mb-6">{feature.description}</p>
            
            {/* Anya's Comment Speech Bubble */}
            <div className="relative inline-block bg-pink-500/20 border border-pink-500/30 rounded-2xl rounded-bl-none px-4 py-2 mb-6">
              <span className="text-pink-300 italic">"{feature.anyaComment}"</span>
              <div className="absolute -bottom-2 left-0 w-4 h-4 bg-pink-500/20 border-l border-b border-pink-500/30 transform rotate-[-45deg]"></div>
            </div>
            
            <div className="flex flex-wrap gap-3 justify-center lg:justify-start">
              {feature.highlights.map((h, i) => (
                <span key={i} className="px-4 py-2 bg-dark-800 rounded-full text-sm text-white border border-dark-600">{h}</span>
              ))}
            </div>
          </div>
          <div className={`p-8 rounded-2xl bg-gradient-to-br ${feature.gradient} shadow-2xl`}>
            <Icon className="w-20 h-20 text-white" />
          </div>
        </div>
      </div>
    </div>
  );
};

const SplitLayout = ({ feature, isVisible }: { feature: Feature; isVisible: boolean }) => {
  const Icon = feature.icon;
  return (
    <div className="grid md:grid-cols-2 gap-8 items-center">
      <div className="order-2 md:order-1">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-3xl">{feature.emoji}</span>
          <h3 className="text-2xl md:text-4xl font-display font-bold text-white">{feature.title}</h3>
        </div>
        <p className="text-gray-400 mb-4">{feature.description}</p>
        <div className="bg-dark-800/50 border border-pink-500/20 rounded-xl p-4 mb-6">
          <p className="text-pink-300 text-sm italic">💭 {feature.anyaComment}</p>
        </div>
        <div className="space-y-2">
          {feature.highlights.map((h, i) => (
            <div key={i} className="flex items-center gap-2 text-gray-300">
              <div className={`w-1.5 h-1.5 rounded-full bg-gradient-to-r ${feature.gradient}`}></div>
              <span>{h}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="order-1 md:order-2 flex justify-center">
        <div className={`relative p-10 rounded-3xl bg-gradient-to-br ${feature.gradient}`}>
          <Icon className="w-24 h-24 text-white" />
          <Star className="absolute top-4 right-4 w-6 h-6 text-white/30" />
        </div>
      </div>
    </div>
  );
};

const CardsLayout = ({ feature, isVisible }: { feature: Feature; isVisible: boolean }) => {
  return (
    <div className="text-center">
      <span className="text-4xl mb-4 block">{feature.emoji}</span>
      <h3 className="text-2xl md:text-4xl font-display font-bold text-white mb-2">{feature.title}</h3>
      <p className="text-pink-300 italic mb-6">"{feature.anyaComment}"</p>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {feature.highlights.map((action, i) => (
          <div 
            key={i}
            className={`p-4 rounded-xl bg-gradient-to-br ${feature.gradient} text-white font-medium text-center hover:scale-105 transition-transform cursor-pointer`}
          >
            .{action}
          </div>
        ))}
      </div>
    </div>
  );
};

const MinimalLayout = ({ feature, isVisible }: { feature: Feature; isVisible: boolean }) => {
  const Icon = feature.icon;
  return (
    <div className="flex flex-col md:flex-row items-center gap-8 bg-dark-800/30 rounded-2xl p-8 border border-dark-700">
      <div className={`p-6 rounded-2xl bg-gradient-to-br ${feature.gradient}`}>
        <Icon className="w-12 h-12 text-white" />
      </div>
      <div className="flex-1 text-center md:text-left">
        <div className="flex items-center gap-2 justify-center md:justify-start mb-2">
          <span className="text-2xl">{feature.emoji}</span>
          <h3 className="text-2xl font-display font-bold text-white">{feature.title}</h3>
        </div>
        <p className="text-gray-400 mb-3">{feature.description}</p>
        <p className="text-pink-300 italic text-sm">~ {feature.anyaComment}</p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center">
        {feature.highlights.map((h, i) => (
          <span key={i} className="px-3 py-1 bg-dark-700 rounded-lg text-sm text-gray-300">{h}</span>
        ))}
      </div>
    </div>
  );
};

const SpotlightLayout = ({ feature, isVisible }: { feature: Feature; isVisible: boolean }) => {
  const Icon = feature.icon;
  return (
    <div className="relative">
      <div className={`absolute inset-0 bg-gradient-to-r ${feature.gradient} opacity-5 rounded-3xl blur-3xl`}></div>
      <div className="relative bg-dark-800/50 backdrop-blur border border-dark-700 rounded-3xl p-8 md:p-12">
        <div className="flex flex-col items-center text-center">
          <div className={`p-6 rounded-full bg-gradient-to-br ${feature.gradient} mb-6 shadow-2xl`}>
            <Icon className="w-16 h-16 text-white" />
          </div>
          <span className="text-3xl mb-2">{feature.emoji}</span>
          <h3 className="text-3xl md:text-4xl font-display font-bold text-white mb-3">{feature.title}</h3>
          <p className="text-gray-400 max-w-xl mb-4">{feature.description}</p>
          <div className="bg-pink-500/10 border border-pink-500/20 rounded-full px-6 py-2 mb-6">
            <span className="text-pink-300 italic">🧠 "{feature.anyaComment}"</span>
          </div>
          <div className="flex flex-wrap gap-3 justify-center">
            {feature.highlights.map((h, i) => (
              <span key={i} className={`px-4 py-2 rounded-full bg-gradient-to-r ${feature.gradient} text-white text-sm font-medium`}>{h}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const CompactLayout = ({ feature, isVisible }: { feature: Feature; isVisible: boolean }) => {
  const Icon = feature.icon;
  return (
    <div className="grid md:grid-cols-3 gap-6">
      <div className={`md:col-span-1 p-8 rounded-2xl bg-gradient-to-br ${feature.gradient} flex flex-col items-center justify-center text-center`}>
        <Icon className="w-16 h-16 text-white mb-4" />
        <span className="text-2xl">{feature.emoji}</span>
      </div>
      <div className="md:col-span-2 flex flex-col justify-center">
        <h3 className="text-2xl md:text-3xl font-display font-bold text-white mb-2">{feature.title}</h3>
        <p className="text-gray-400 mb-4">{feature.description}</p>
        <div className="bg-dark-800 rounded-xl p-3 mb-4 inline-block">
          <span className="text-pink-300 italic text-sm">🎵 {feature.anyaComment}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {feature.highlights.map((h, i) => (
            <span key={i} className="px-3 py-1 bg-dark-700 border border-dark-600 rounded-lg text-sm text-gray-300">{h}</span>
          ))}
        </div>
      </div>
    </div>
  );
};

const FeatureCard = ({ feature, index }: { feature: Feature; index: number }) => {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.15, rootMargin: '-30px' }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, []);

  const renderLayout = () => {
    switch (feature.layout) {
      case 'hero': return <HeroLayout feature={feature} isVisible={isVisible} />;
      case 'split': return <SplitLayout feature={feature} isVisible={isVisible} />;
      case 'cards': return <CardsLayout feature={feature} isVisible={isVisible} />;
      case 'minimal': return <MinimalLayout feature={feature} isVisible={isVisible} />;
      case 'spotlight': return <SpotlightLayout feature={feature} isVisible={isVisible} />;
      case 'compact': return <CompactLayout feature={feature} isVisible={isVisible} />;
      default: return <HeroLayout feature={feature} isVisible={isVisible} />;
    }
  };

  return (
    <div
      ref={ref}
      className={`py-12 md:py-16 transition-all duration-700 ${
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'
      }`}
      style={{ transitionDelay: `${index * 50}ms` }}
    >
      {renderLayout()}
    </div>
  );
};

const FeatureShowcase = () => {
  return (
    <section className="bg-dark-900 py-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Anya-themed Section Header */}
        <div className="text-center mb-12">
          <div className="inline-block mb-4">
            <span className="text-5xl">✨</span>
          </div>
          <h2 className="text-3xl md:text-5xl font-display font-bold text-white mb-4">
            <span className="text-gradient">Waku Waku Features!</span>
          </h2>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto mb-4">
            Discover what makes Anya Bot the perfect companion for your Discord server
          </p>
        </div>

        {/* Features */}
        <div className="divide-y divide-dark-700">
          {features.map((feature, index) => (
            <FeatureCard key={feature.id} feature={feature} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
};

export default FeatureShowcase;
