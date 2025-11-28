import { useRef, useEffect, useState } from 'react';
import { 
  Gamepad2, Search, Sparkles, Wand2, Heart, Music
} from 'lucide-react';

interface Feature {
  id: string;
  icon: React.ElementType;
  title: string;
  anyaComment: string;
  description: string;
  highlights: string[];
  accentColor: string;
  emoji: string;
  serverBenefit: string;
}

const features: Feature[] = [
  {
    id: 'pokemon',
    icon: Gamepad2,
    title: 'Pokémon Detection',
    anyaComment: "Anya can find all the rare ones~",
    description: 'Advanced spawn detection with complete Pokédex, shiny tracking, and collection management.',
    highlights: ['Auto Detection', 'Full Pokédex', 'Shiny Tracker', 'Collection'],
    accentColor: 'from-amber-400 to-orange-500',
    emoji: '⚡',
    serverBenefit: 'Keeps Pokétwo hunters alert without staring at chat 24/7.'
  },
  {
    id: 'anime',
    icon: Search,
    title: 'Anime Search',
    anyaComment: "Spy x Family is the best~",
    description: 'Search anime and manga with MyAnimeList integration. Synopses, ratings, and recommendations.',
    highlights: ['MAL Integration', 'Character Search', 'Seasonal Picks', 'Recommendations'],
    accentColor: 'from-pink-400 to-rose-500',
    emoji: '📺',
    serverBenefit: 'Instant answer machine for "what should we watch next?" debates.'
  },
  {
    id: 'roleplay',
    icon: Heart,
    title: 'Expressive Actions',
    anyaComment: "Hugs make everyone happy~",
    description: 'Over 50 expressive actions with beautiful animated GIFs for your server.',
    highlights: ['hug', 'pat', 'poke', 'kiss', 'wave', 'boop'],
    accentColor: 'from-pink-400 to-purple-500',
    emoji: '💕',
    serverBenefit: 'Makes even quiet days feel alive with wholesome reactions.'
  },
  {
    id: 'fun',
    icon: Sparkles,
    title: 'Fun & Games',
    anyaComment: "Anya predicts good fortune~",
    description: '8ball fortunes, jokes, memes, and mini-games to brighten your server.',
    highlights: ['8Ball', 'Jokes', 'Memes', 'Mini-games'],
    accentColor: 'from-cyan-400 to-blue-500',
    emoji: '🎉',
    serverBenefit: 'Breaks awkward silences with playful prompts and games.'
  },
  {
    id: 'utility',
    icon: Wand2,
    title: 'Utility Tools',
    anyaComment: "Very helpful for everyone~",
    description: 'Essential server tools: avatars, user info, server stats, and role management.',
    highlights: ['Avatar Grab', 'User Info', 'Server Stats', 'Role Tools'],
    accentColor: 'from-emerald-400 to-teal-500',
    emoji: '🛠️',
    serverBenefit: 'Saves mods time on common lookups and user checks.'
  },
  {
    id: 'music',
    icon: Music,
    title: 'Music Player',
    anyaComment: "Music makes Anya happy~",
    description: 'High-quality playback with queue management from YouTube and more.',
    highlights: ['YouTube', 'Queue', 'Volume', 'Playlists'],
    accentColor: 'from-violet-400 to-purple-500',
    emoji: '🎵',
    serverBenefit: 'Keeps vibe sessions going with curated queues.'
  },
];

// Discord-styled Feature Card with scroll animation
const FeatureCard = ({ feature, index, isEven }: { feature: Feature; index: number; isEven: boolean }) => {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const Icon = feature.icon;

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.2, rootMargin: '-50px' }
    );

    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`transition-all duration-1000 ease-out ${
        isVisible 
          ? 'opacity-100 translate-y-0' 
          : `opacity-0 ${isEven ? 'translate-x-8' : '-translate-x-8'} translate-y-4`
      }`}
      style={{ transitionDelay: `${index * 120}ms` }}
    >
      <div className="bg-dark-900/80 border border-dark-700/50 rounded-3xl p-5 sm:p-6 shadow-xl shadow-black/30 backdrop-blur">
        {/* Top summary row */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div className="flex items-center gap-4">
            <div className={`relative w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-gradient-to-br ${feature.accentColor} p-[2px]`}> 
              <div className="w-full h-full rounded-2xl bg-[#151621] flex items-center justify-center">
                <Icon className="w-7 h-7 sm:w-8 sm:h-8 text-white" />
              </div>
              <span className="absolute -top-2 -right-2 text-lg">{feature.emoji}</span>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-primary/70 mb-1">Discord-ready module</p>
              <h3 className="text-xl sm:text-2xl font-display font-semibold text-white">{feature.title}</h3>
              <p className="text-sm text-gray-400">{feature.serverBenefit}</p>
            </div>
          </div>
          <div className="text-xs sm:text-sm text-gray-500 flex items-center gap-2">
            <span className="inline-flex px-2 py-1 rounded-full bg-dark-800/80 border border-dark-600/80">Servers ask for this daily</span>
          </div>
        </div>

        {/* Discord-style embed */}
        <div className="bg-[#1c1d2c] border border-[#24263a] rounded-2xl p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <div className="w-11 h-11 rounded-full bg-[#2b2d41] flex items-center justify-center text-2xl">
              {feature.emoji}
            </div>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm">
                <span className="text-white font-semibold">Anya Bot</span>
                <span className="text-[10px] tracking-wide font-bold uppercase px-2 py-0.5 rounded bg-primary/20 text-primary">BOT</span>
                <span className="text-gray-500">just now</span>
              </div>
              <p className="text-gray-300 text-sm sm:text-base mt-2 leading-relaxed">
                {feature.description}
              </p>
              <p className="text-primary/80 italic text-sm sm:text-base mt-3">
                “{feature.anyaComment}”
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                {feature.highlights.map((highlight, i) => (
                  <span
                    key={i}
                    className="px-3 py-1.5 rounded-full text-xs sm:text-sm bg-dark-800/70 border border-dark-600 text-gray-200 tracking-wide"
                  >
                    {highlight}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const FeatureShowcase = () => {
  const [headerVisible, setHeaderVisible] = useState(false);
  const headerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setHeaderVisible(true);
      },
      { threshold: 0.3 }
    );

    if (headerRef.current) observer.observe(headerRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section className="py-16 sm:py-24 relative overflow-hidden">
      {/* Subtle background gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-dark-900 via-dark-900/40 to-dark-900 pointer-events-none" />
      
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 relative">
        {/* Elegant Header */}
        <div 
          ref={headerRef}
          className={`text-center mb-16 sm:mb-20 transition-all duration-1000 ease-out ${
            headerVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          {/* Decorative line */}
          <div className="flex items-center justify-center gap-4 mb-6">
            <div className="h-px w-16 sm:w-24 bg-gradient-to-r from-transparent to-primary/30" />
            <Sparkles className="w-5 h-5 text-primary/60" />
            <div className="h-px w-16 sm:w-24 bg-gradient-to-l from-transparent to-primary/30" />
          </div>
          
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-display font-bold text-white mb-3">
            Features crafted with care
          </h2>
          <p className="text-sm sm:text-base text-gray-400 max-w-lg mx-auto">
            Each feature sits in a Discord-ready container so members instantly get why Anya belongs in their server
          </p>
        </div>

        {/* Features - alternating layout */}
        <div className="space-y-8">
          {features.map((feature, index) => (
            <FeatureCard 
              key={feature.id} 
              feature={feature} 
              index={index} 
              isEven={index % 2 === 0}
            />
          ))}
        </div>
        
        {/* Elegant closing */}
        <div className="text-center mt-16 sm:mt-20">
          <div className="flex items-center justify-center gap-4">
            <div className="h-px w-12 bg-gradient-to-r from-transparent to-primary/20" />
            <Heart className="w-4 h-4 text-primary/40 fill-primary/20" />
            <div className="h-px w-12 bg-gradient-to-l from-transparent to-primary/20" />
          </div>
        </div>
      </div>
    </section>
  );
};

export default FeatureShowcase;
