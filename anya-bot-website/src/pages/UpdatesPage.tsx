import { useState, useEffect } from 'react';
import { 
  Sparkles, Rocket, Star, Heart, Zap, Gift, 
  CheckCircle2, Clock, PartyPopper, Wand2, LucideIcon
} from 'lucide-react';

interface Update {
  version: string;
  date: string;
  title: string;
  description: string;
  type: 'feature' | 'improvement' | 'fix' | 'upcoming';
  highlights: string[];
}

interface UpcomingFeature {
  icon: string;
  title: string;
  desc: string;
}

// Icon mapping for JSON data
const iconMap: Record<string, LucideIcon> = {
  Wand2, Star, Gift, Heart, Zap, Rocket, Sparkles
};

// Default data (fallback if JSON fails to load)
const defaultUpdates: Update[] = [
  {
    version: '2.5.0',
    date: 'Coming Soon',
    title: '✨ AI Chat Improvements',
    description: 'Enhanced AI conversations with better context memory and personality!',
    type: 'upcoming',
    highlights: ['Longer memory', 'Custom personalities', 'Image understanding'],
  }
];

const defaultUpcoming: UpcomingFeature[] = [
  { icon: 'Wand2', title: 'Custom Commands', desc: 'Create your own commands!' },
  { icon: 'Star', title: 'Leveling System', desc: 'XP and ranks for your server' },
  { icon: 'Gift', title: 'Economy System', desc: 'Virtual currency and shop' },
  { icon: 'Heart', title: 'Relationship System', desc: 'Marriage and families' },
];

const typeConfig = {
  feature: { color: 'from-green-500 to-emerald-500', icon: Rocket, label: 'New Feature' },
  improvement: { color: 'from-blue-500 to-cyan-500', icon: Zap, label: 'Improvement' },
  fix: { color: 'from-orange-500 to-yellow-500', icon: CheckCircle2, label: 'Bug Fix' },
  upcoming: { color: 'from-purple-500 to-pink-500', icon: Clock, label: 'Coming Soon' },
};

const UpdatesPage = () => {
  const [updates, setUpdates] = useState<Update[]>(defaultUpdates);
  const [upcomingFeatures, setUpcomingFeatures] = useState<UpcomingFeature[]>(defaultUpcoming);
  const [visibleItems, setVisibleItems] = useState<number[]>([]);

  // Load updates from JSON file
  useEffect(() => {
    fetch('/updates.json')
      .then(res => res.json())
      .then(data => {
        if (data.updates) setUpdates(data.updates);
        if (data.upcomingFeatures) setUpcomingFeatures(data.upcomingFeatures);
      })
      .catch(err => console.warn('Failed to load updates.json:', err));
  }, []);

  useEffect(() => {
    // Stagger animation for updates
    setVisibleItems([]);
    updates.forEach((_: Update, i: number) => {
      setTimeout(() => {
        setVisibleItems(prev => [...prev, i]);
      }, i * 150);
    });
  }, [updates]);

  return (
    <div className="pt-24 pb-20 min-h-screen">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Hero Header with bounce animation */}
        <div className="text-center mb-16 animate-fade-in">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-purple-500 to-pink-500 rounded-3xl mb-6 shadow-2xl shadow-purple-500/30 animate-bounce-slow">
            <Sparkles className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl md:text-6xl font-display font-bold mb-4">
            <span className="text-gradient">What's New?</span>
          </h1>
          <p className="text-xl text-gray-400 max-w-xl mx-auto">
            Stay updated with the latest features, improvements, and exciting things coming to Anya Bot! 
            <span className="inline-block animate-wiggle ml-1">🎉</span>
          </p>
        </div>

        {/* Upcoming Features Banner */}
        <div className="mb-12 p-6 bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-2xl">
          <div className="flex items-center gap-2 mb-4">
            <PartyPopper className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-bold text-white">Coming Soon!</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {upcomingFeatures.map((feature, i) => {
              const Icon = iconMap[feature.icon] || Star;
              return (
                <div 
                  key={i}
                  className="p-4 bg-dark-800/50 rounded-xl border border-dark-600 hover:border-purple-500/50 hover:scale-105 transition-all duration-300 cursor-default group"
                  style={{ animationDelay: `${i * 100}ms` }}
                >
                  <Icon className="w-8 h-8 text-purple-400 mb-2 group-hover:scale-110 transition-transform" />
                  <h3 className="font-semibold text-white text-sm">{feature.title}</h3>
                  <p className="text-xs text-gray-500">{feature.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Updates Timeline */}
        <div className="space-y-6">
          {updates.map((update, i) => {
            const config = typeConfig[update.type];
            const Icon = config.icon;
            const isVisible = visibleItems.includes(i);
            
            return (
              <div
                key={i}
                className={`relative pl-8 transition-all duration-500 ${
                  isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-8'
                }`}
              >
                {/* Timeline dot */}
                <div className={`absolute left-0 top-6 w-3 h-3 rounded-full bg-gradient-to-r ${config.color}`}></div>
                {i < updates.length - 1 && (
                  <div className="absolute left-[5px] top-10 w-0.5 h-full bg-dark-700"></div>
                )}

                {/* Update Card */}
                <div className="bg-dark-800/50 border border-dark-700 rounded-2xl p-6 hover:border-primary/30 transition-all hover:shadow-lg hover:shadow-primary/5">
                  {/* Header */}
                  <div className="flex flex-wrap items-center gap-3 mb-3">
                    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-gradient-to-r ${config.color} text-white`}>
                      <Icon className="w-3 h-3" />
                      {config.label}
                    </span>
                    <span className="text-xs text-gray-500">v{update.version}</span>
                    <span className="text-xs text-gray-500">• {update.date}</span>
                  </div>

                  {/* Title & Description */}
                  <h3 className="text-xl font-bold text-white mb-2">{update.title}</h3>
                  <p className="text-gray-400 mb-4">{update.description}</p>

                  {/* Highlights */}
                  <div className="flex flex-wrap gap-2">
                    {update.highlights.map((highlight, j) => (
                      <span 
                        key={j}
                        className="px-3 py-1 bg-dark-700 text-gray-300 rounded-lg text-sm hover:bg-dark-600 transition-colors"
                      >
                        {highlight}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Fun Footer */}
        <div className="mt-16 text-center">
          <p className="text-gray-500 text-sm">
            More exciting updates coming soon! 
            <span className="inline-block animate-pulse ml-1">💖</span>
          </p>
          <p className="text-gray-600 text-xs mt-2">
            Have a suggestion? Let us know in our Discord server!
          </p>
        </div>
      </div>
    </div>
  );
};

export default UpdatesPage;
