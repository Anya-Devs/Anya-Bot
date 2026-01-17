import { Code, Sparkles, Zap, Database, Brain, Gamepad2, Star, TrendingUp } from 'lucide-react';

const DeveloperNotes = () => {
  const features = [
    {
      icon: <Brain className="w-6 h-6" />,
      title: 'AI Integration',
      description: 'Advanced AI chat using OpenAI GPT models with custom personality',
      status: 'Live',
      color: 'from-purple-500 to-pink-500',
      details: [
        'Natural conversation with Anya personality',
        'Image generation with /imagine command',
        'Context-aware responses'
      ]
    },
    {
      icon: <Gamepad2 className="w-6 h-6" />,
      title: 'Pokémon System',
      description: 'Complete Pokémon collection and battling system with Pokétwo integration',
      status: 'Live',
      color: 'from-blue-500 to-cyan-500',
      details: [
        'Auto-naming for Pokétwo spawns',
        'Pokédex with detailed stats',
        'Shiny hunt tracking',
        'Pokemon image recognition'
      ]
    },
    {
      icon: <Star className="w-6 h-6" />,
      title: 'Character Gacha',
      description: 'Collect anime, manga, and game characters with rarity system',
      status: 'Live',
      color: 'from-yellow-500 to-orange-500',
      details: [
        'Multi-source character data (AniList, Jikan)',
        'Rarity tiers: Common, Rare, SR, SSR',
        'Trading and collection management',
        'Leaderboard system'
      ]
    },
    {
      icon: <Database className="w-6 h-6" />,
      title: 'Quest System',
      description: 'Daily and weekly quests with rewards',
      status: 'Live',
      color: 'from-green-500 to-emerald-500',
      details: [
        'Daily quest rotation',
        'Progress tracking',
        'Reward distribution',
        'Achievement system'
      ]
    },
    {
      icon: <Zap className="w-6 h-6" />,
      title: 'Fun Commands',
      description: 'Entertainment commands for server engagement',
      status: 'Live',
      color: 'from-pink-500 to-rose-500',
      details: [
        'Action commands (hug, pat, kiss)',
        'Anime image search',
        'Random facts and jokes',
        'Server games'
      ]
    },
    {
      icon: <TrendingUp className="w-6 h-6" />,
      title: 'Moderation Tools',
      description: 'Comprehensive moderation and server management',
      status: 'Live',
      color: 'from-red-500 to-orange-500',
      details: [
        'Kick, ban, timeout commands',
        'Message purging',
        'Warning system',
        'Auto-moderation features'
      ]
    }
  ];

  const upcomingFeatures = [
    {
      title: 'Economy System',
      description: 'Virtual currency, shops, and trading',
      eta: 'Coming Soon'
    },
    {
      title: 'Custom Profiles',
      description: 'Personalized user profiles with stats',
      eta: 'In Development'
    },
    {
      title: 'Music Player',
      description: 'High-quality music streaming',
      eta: 'Planned'
    }
  ];

  return (
    <section className="py-20 bg-gradient-to-b from-dark-900 to-dark">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center px-4 py-2 bg-primary/10 border border-primary/30 rounded-full mb-6">
            <Code className="w-4 h-4 mr-2 text-primary" />
            <span className="text-sm text-primary font-semibold">Developer Notes</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-display font-bold text-white mb-4">
            Built with <span className="text-gradient">Passion</span>
          </h2>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto">
            Anya Bot is actively developed with cutting-edge features. Here's what powers your favorite Discord companion.
          </p>
        </div>

        {/* Current Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
          {features.map((feature, idx) => (
            <div
              key={idx}
              className="group card-hover p-6 relative overflow-hidden"
            >
              {/* Gradient Background */}
              <div className={`absolute inset-0 bg-gradient-to-br ${feature.color} opacity-0 group-hover:opacity-10 transition-opacity duration-300`}></div>
              
              {/* Content */}
              <div className="relative z-10">
                {/* Icon & Status */}
                <div className="flex items-start justify-between mb-4">
                  <div className={`p-3 rounded-lg bg-gradient-to-br ${feature.color} text-white`}>
                    {feature.icon}
                  </div>
                  <span className="px-3 py-1 bg-green-500/20 text-green-400 text-xs font-semibold rounded-full border border-green-500/30">
                    {feature.status}
                  </span>
                </div>

                {/* Title & Description */}
                <h3 className="text-xl font-bold text-white mb-2">
                  {feature.title}
                </h3>
                <p className="text-gray-400 text-sm mb-4">
                  {feature.description}
                </p>

                {/* Details List */}
                <ul className="space-y-2">
                  {feature.details.map((detail, detailIdx) => (
                    <li key={detailIdx} className="flex items-start text-xs text-gray-500">
                      <Sparkles className="w-3 h-3 mr-2 mt-0.5 text-primary flex-shrink-0" />
                      <span>{detail}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>

        {/* Upcoming Features */}
        <div className="glass-card p-8">
          <div className="flex items-center mb-6">
            <div className="p-2 bg-primary/20 rounded-lg mr-3">
              <TrendingUp className="w-5 h-5 text-primary" />
            </div>
            <h3 className="text-2xl font-bold text-white">Coming Soon</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {upcomingFeatures.map((feature, idx) => (
              <div key={idx} className="p-4 bg-dark-800/50 rounded-lg border border-dark-600">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-white">{feature.title}</h4>
                  <span className="px-2 py-1 bg-primary/20 text-primary text-xs rounded-full">
                    {feature.eta}
                  </span>
                </div>
                <p className="text-sm text-gray-400">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Tech Stack */}
        <div className="mt-12 text-center">
          <p className="text-sm text-gray-500 mb-4">Built with</p>
          <div className="flex flex-wrap justify-center gap-3">
            {['Python', 'Discord.py', 'OpenAI', 'MongoDB', 'React', 'TypeScript', 'TailwindCSS'].map((tech) => (
              <span key={tech} className="px-4 py-2 bg-dark-800 border border-dark-600 rounded-lg text-sm text-gray-300">
                {tech}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default DeveloperNotes;
