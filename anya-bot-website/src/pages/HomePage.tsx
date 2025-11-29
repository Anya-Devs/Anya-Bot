import { useState, useEffect } from 'react';
import { ArrowRight, Shield, Star, Users, Server, Heart, FileText, Gamepad2, Image, Sparkles } from 'lucide-react';
import { BOT_CONFIG } from '../config/bot';
import { SAMPLE_EMBEDS } from '../config/embedTemplates';
import BotAvatar from '../components/BotAvatar';
import SlidingFeatures from '../components/SlidingFeatures';
import DiscordPreviewCard from '../components/DiscordPreviewCard';
import { fetchBotStats } from '../services/botStatsService';

// Stat display component - warm style with responsive design
interface StatCardProps {
  value: number;
  label: string;
  icon: any;
  suffix?: string;
}

const StatCard = ({ value, label, icon: Icon, suffix = '' }: StatCardProps) => {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    let frame: number;
    const duration = 1200;
    const start = performance.now();

    const animate = (time: number) => {
      const progress = Math.min((time - start) / duration, 1);
      setDisplayValue(Math.floor(progress * value));
      if (progress < 1) {
        frame = requestAnimationFrame(animate);
      }
    };

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return (
    <div className="text-center group flex-1 min-w-[110px]">
      <div className="inline-flex items-center justify-center w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-primary/10 text-primary mb-3 group-hover:scale-110 transition-transform">
        <Icon className="w-5 h-5 sm:w-6 sm:h-6" />
      </div>
      <div className="text-3xl sm:text-4xl font-display font-bold text-white mb-1">
        {displayValue}
        <span className="text-primary text-lg sm:text-xl ml-1">{suffix}</span>
      </div>
      <div className="text-xs sm:text-sm text-gray-500 tracking-wide uppercase">{label}</div>
    </div>
  );
};

interface ParsedStat {
  value: number;
  suffix: string;
}

const parseStatValue = (raw: number | string): ParsedStat => {
  if (typeof raw === 'number') {
    return { value: raw, suffix: '' };
  }

  const match = raw.match(/([0-9.]+)/);
  const value = match ? parseFloat(match[1]) : 0;
  const suffix = raw.replace(match ? match[1] : '', '').trim();
  return { value, suffix };
};

// Feature sections using exact embed templates from bot cogs
const anyaStory = [
  {
    icon: Heart,
    title: 'Cozy Actions',
    summary: 'Hugs, pats, cuddles, and wholesome interactions. Every action comes with an animated GIF and tracks how many times you\'ve sent and received each action.',
    preview: {
      command: SAMPLE_EMBEDS.action.command,
      // Exact format from utils/cogs/fun.py line 68:
      // embed = discord.Embed(title=msg, color=primary_color()).set_image(url=gif).set_footer(text=f"Sent: {sent} | Received: {received}")
      title: SAMPLE_EMBEDS.action.title,
      hasGif: true,
      gifUrl: SAMPLE_EMBEDS.action.image,
      embedColor: SAMPLE_EMBEDS.action.color,
      footer: SAMPLE_EMBEDS.action.footer,
      userAvatar: SAMPLE_EMBEDS.action.userAvatar,
      userName: 'Yor'
    }
  },
  {
    icon: Star,
    title: 'Anime Lookups',
    summary: 'Search anime, manga, and characters using live data from MyAnimeList via Jikan API. Get episodes, status, genres, scores, and synopses instantly.',
    preview: {
      command: '.anime search Spy x Family',
      // Exact format from utils/cogs/anime.py lines 125-148
      title: SAMPLE_EMBEDS.anime.title,
      description: SAMPLE_EMBEDS.anime.description,
      image: SAMPLE_EMBEDS.anime.image,
      embedColor: SAMPLE_EMBEDS.anime.color,
      fields: SAMPLE_EMBEDS.anime.fields,
      footer: SAMPLE_EMBEDS.anime.footer
    }
  },
  {
    icon: Gamepad2,
    title: 'Pokédex & Pokétwo',
    summary: 'Full Pokédex lookups with stats, types, and region data. Plus Pokétwo helper tools: shiny hunt alerts, collection tracking, and spawn protection.',
    preview: {
      command: '.pokedex vulpix',
      // Exact format from utils/cogs/pokemon.py lines 147-224
      title: SAMPLE_EMBEDS.pokemon.title,
      description: SAMPLE_EMBEDS.pokemon.description,
      image: SAMPLE_EMBEDS.pokemon.image,
      embedColor: SAMPLE_EMBEDS.pokemon.color,
      fields: SAMPLE_EMBEDS.pokemon.fields,
      footer: SAMPLE_EMBEDS.pokemon.footer,
      footerIcon: SAMPLE_EMBEDS.pokemon.footerIcon
    }
  },
  {
    icon: Shield,
    title: '8Ball & Mini Games',
    summary: 'Classic magic 8-ball predictions, emoji memory games, server Q&A channels, and more fun commands to keep your community engaged.',
    preview: {
      command: '.8ball Will Anya pass her exam?',
      // Exact format from bot/cogs/fun.py lines 21-32:
      // embed = discord.Embed(title="🎱 8Ball", description=f"**{question}**\n{blank_emoji} {ans}", color=primary_color())
      // .set_footer(text=f"Requested by {ctx.author}")
      title: SAMPLE_EMBEDS.eightBall.title,
      description: SAMPLE_EMBEDS.eightBall.description,
      embedColor: SAMPLE_EMBEDS.eightBall.color,
      footer: SAMPLE_EMBEDS.eightBall.footer
    }
  },
  {
    icon: Image,
    title: 'AI Art Studio',
    summary: 'Generate anime-styled images using Animagine XL 4.0. Detailed prompts create stunning artwork delivered directly to your Discord channel.',
    preview: {
      command: '.imagine 1girl, pink hair, green eyes, school uniform, cherry blossoms, masterpiece, high quality, detailed',
      // Exact format from bot/cogs/ai.py with visual progress bar
      title: SAMPLE_EMBEDS.imagine.title,
      description: SAMPLE_EMBEDS.imagine.description,
      embedColor: SAMPLE_EMBEDS.imagine.color,
      progress: SAMPLE_EMBEDS.imagine.progress,
      footer: SAMPLE_EMBEDS.imagine.footer
    }
  }
];

const HomePage = () => {
  const [stats, setStats] = useState({
    servers: { value: 0, suffix: '' },
    users: { value: 0, suffix: '' },
    commands: { value: 0, suffix: '' },
  });
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    setIsLoaded(true);
    fetchBotStats().then(newStats => {
      setStats({
        servers: parseStatValue(newStats.servers),
        users: parseStatValue(newStats.users),
        commands: parseStatValue(newStats.commands)
      });
    });
  }, []);

  return (
    <div className="relative overflow-hidden">
      {/* Warm background glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-[100px]" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-primary/3 rounded-full blur-[80px]" />
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════
          HERO - Welcome Home
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="relative pt-24 pb-12 sm:pt-28 sm:pb-16 md:pt-32 lg:pt-36 md:pb-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Mobile: Avatar first, then text. Desktop: Side by side */}
          <div className="flex flex-col-reverse lg:grid lg:grid-cols-2 gap-8 sm:gap-12 lg:gap-16 items-center">
            
            {/* Left: Welcome message */}
            <div className={`text-center lg:text-left transition-all duration-1000 ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
              
              {/* Version badge */}
              <div className="inline-flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 py-1.5 sm:py-2 bg-primary/10 border border-primary/20 rounded-full mb-4 sm:mb-6">
                <Heart className="w-3 h-3 sm:w-4 sm:h-4 text-primary fill-primary/30" />
                <span className="text-xs sm:text-sm text-primary font-medium">Version {BOT_CONFIG.version}</span>
              </div>

              {/* Main Title - responsive sizing */}
              <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-display font-bold mb-4 sm:mb-6 leading-tight">
                <span className="text-white">Welcome home to</span>
                <br />
                <span className="text-gradient">{BOT_CONFIG.name}</span>
              </h1>

              {/* Subtitle - responsive */}
              <p className="text-base sm:text-lg md:text-xl text-gray-400 mb-6 sm:mb-8 max-w-lg mx-auto lg:mx-0 leading-relaxed">
                Your cozy companion for Discord. Bringing{' '}
                <span className="text-primary">warmth</span>,{' '}
                <span className="text-primary">joy</span>, and a little bit of{' '}
                <span className="text-primary">magic</span> to every server.
              </p>

              {/* Features list - hidden on mobile, shown on sm+ */}
              <div className="hidden sm:flex flex-col gap-2 sm:gap-3 mb-6 sm:mb-8 text-left max-w-md mx-auto lg:mx-0">
                {[
                  { icon: Heart, text: "Fun interactions that bring people together" },
                  { icon: Shield, text: "Keep your community safe and happy" },
                  { icon: Star, text: "Anime, games, and endless entertainment" },
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-2 sm:gap-3 text-gray-400">
                    <div className="p-1 sm:p-1.5 rounded-lg bg-primary/10">
                      <item.icon className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                    </div>
                    <span className="text-xs sm:text-sm">{item.text}</span>
                  </div>
                ))}
              </div>

              {/* CTA Buttons - responsive sizing */}
              <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center lg:justify-start">
                <a
                  href={BOT_CONFIG.inviteLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group px-6 sm:px-8 py-3 sm:py-4 bg-gradient-primary text-white font-semibold rounded-xl shadow-lg hover:shadow-pink-glow transition-all duration-300 hover:-translate-y-1 flex items-center justify-center gap-2 text-sm sm:text-base"
                >
                  <Sparkles className="w-4 h-4 sm:w-5 sm:h-5" />
                  Invite Anya
                  <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5 group-hover:translate-x-1 transition-transform" />
                </a>
                <a
                  href={BOT_CONFIG.supportServer}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 sm:px-8 py-3 sm:py-4 bg-dark-800 text-white font-semibold rounded-xl border border-dark-600 hover:border-primary/50 hover:bg-dark-700 transition-all duration-300 flex items-center justify-center gap-2 text-sm sm:text-base"
                >
                  <Users className="w-4 h-4 sm:w-5 sm:h-5" />
                  Join Community
                </a>
              </div>
            </div>

            {/* Bot Avatar - responsive sizes */}
            <div className={`flex justify-center mb-6 lg:mb-0 transition-all duration-1000 delay-300 ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
              <div className="relative">
                {/* Warm glow behind avatar */}
                <div className="absolute inset-0 bg-gradient-to-br from-primary/30 to-secondary/20 rounded-full blur-3xl scale-110 animate-pulse" />
                
                {/* Avatar container - smaller on mobile */}
                <div className="relative w-48 h-48 sm:w-56 sm:h-56 md:w-72 md:h-72 lg:w-80 lg:h-80">
                  <div className="absolute inset-0 rounded-full bg-gradient-to-br from-primary/20 to-secondary/10 p-1">
                    <div className="w-full h-full rounded-full bg-dark-800 overflow-hidden shadow-2xl border-2 border-primary/20">
                      <BotAvatar 
                        className="w-full h-full object-cover"
                        size={512}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Stats - responsive grid */}
          <div className={`mt-12 transition-all duration-1000 delay-500 ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
            <div className="bg-dark-900/60 border border-dark-700/60 rounded-3xl px-6 sm:px-10 py-6 sm:py-8 shadow-xl shadow-black/20">
              <div className="flex flex-col sm:flex-row gap-6 sm:gap-8 md:gap-12">
                <StatCard icon={Server} value={stats.servers.value} suffix={stats.servers.suffix} label="Happy Servers" />
                <StatCard icon={Users} value={stats.users.value} suffix={stats.users.suffix} label="Friends Made" />
                <StatCard icon={FileText} value={stats.commands.value} suffix={stats.commands.suffix} label="Commands" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════════
          OVERVIEW - Why Anya Exists
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="py-20 sm:py-28 relative">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary/90 text-sm font-display mb-6">
            <Sparkles className="w-4 h-4" />
            Why Anya was made
          </div>
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-display font-bold text-white mb-6">
            A companion built for Discord communities
          </h2>
          <p className="text-base sm:text-lg text-gray-400 leading-relaxed max-w-3xl mx-auto">
            Papa created Anya because every server deserves a friend who can make people smile, 
            help with anime lookups, alert Pokémon hunters, and keep the chat safe—all while being cute about it. 
            She learns new tricks every day to bring communities closer together.
          </p>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════════
          FEATURE SECTIONS - Each gets its own section
      ═══════════════════════════════════════════════════════════════════════ */}
      {anyaStory.map((item, idx) => (
        <section 
          key={item.title} 
          className={`py-16 sm:py-24 relative ${idx % 2 === 1 ? 'bg-dark-800/30' : ''}`}
        >
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
              {/* Text side */}
              <div className={`space-y-6 ${idx % 2 === 1 ? 'lg:order-2' : ''}`}>
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-2xl bg-primary/10 text-primary">
                    <item.icon className="w-7 h-7" />
                  </div>
                  <h3 className="text-2xl sm:text-3xl font-display font-bold text-white">{item.title}</h3>
                </div>
                <p className="text-gray-400 text-base sm:text-lg leading-relaxed">
                  {item.summary}
                </p>
                <div className="pt-2">
                  <span className="text-xs text-gray-500 uppercase tracking-wider">Try it →</span>
                  <code className="ml-2 px-3 py-1.5 bg-dark-700/60 rounded-lg text-primary text-sm font-mono">
                    {item.preview.command}
                  </code>
                </div>
              </div>
              
              {/* Discord preview side */}
              <div className={idx % 2 === 1 ? 'lg:order-1' : ''}>
                <DiscordPreviewCard {...item.preview} className="shadow-2xl" />
              </div>
            </div>
          </div>
        </section>
      ))}

      {/* ═══════════════════════════════════════════════════════════════════════
          QUEST SYSTEM - Coming Soon
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="py-20 sm:py-28 relative bg-gradient-to-b from-amber-500/5 to-transparent">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm font-display mb-6">
            <Sparkles className="w-4 h-4" />
            Coming Soon
          </div>
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-display font-bold text-white mb-6">
            Quest System
          </h2>
          <p className="text-base sm:text-lg text-gray-400 leading-relaxed max-w-2xl mx-auto mb-8">
            This is the feature that will bring communities together like never before. 
            Server-wide quests, collaborative challenges, rewards, and events that make every member feel like part of something special.
          </p>
          <div className="inline-flex items-center gap-3 px-6 py-3 bg-dark-800/60 border border-amber-500/20 rounded-2xl">
            <div className="w-10 h-10 rounded-full overflow-hidden border border-primary/30">
              <BotAvatar className="w-full h-full object-cover" size={40} />
            </div>
            <p className="text-sm text-gray-400 italic">
              "Anya and Papa are working very hard on this. Please wait a little longer~"
            </p>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════════
          LIVE PREVIEW CAROUSEL
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="py-16 sm:py-24 relative">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <p className="text-sm uppercase tracking-[0.4em] text-primary/70 mb-3">Live Preview</p>
            <h3 className="text-xl sm:text-2xl font-semibold text-white">More examples of Anya in action</h3>
            <p className="text-gray-400 text-sm sm:text-base mt-2">Slide through demo conversations.</p>
          </div>
          <SlidingFeatures />
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════════
          FINAL CTA - Elegant invitation
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="py-16 sm:py-20 md:py-24 relative">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          {/* Anya's elegant portrait */}
          <div className="inline-block mb-6 sm:mb-8 relative">
            <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-full overflow-hidden border-2 border-primary/20 shadow-xl shadow-primary/10 hover:border-primary/40 transition-all duration-500">
              <BotAvatar className="w-full h-full object-cover" size={128} />
            </div>
            <div className="absolute -bottom-1 -right-1 w-8 h-8 bg-dark-800 rounded-full border border-primary/30 flex items-center justify-center">
              <Heart className="w-4 h-4 text-primary fill-primary/30" />
            </div>
          </div>
          
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-display font-bold text-white mb-3 sm:mb-4 px-4">
            Would you like to be friends?
          </h2>
          
          <p className="text-base sm:text-lg text-gray-400 mb-8 sm:mb-10 max-w-lg mx-auto px-4">
            Anya would be very happy to join your server~
            <span className="text-primary/80"> Let's have fun together! </span>
          </p>
          
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center px-4">
            <a
              href={BOT_CONFIG.inviteLink}
              target="_blank"
              rel="noopener noreferrer"
              className="group px-8 sm:px-10 py-3.5 sm:py-4 bg-gradient-primary text-white font-semibold rounded-xl shadow-lg hover:shadow-pink-glow transition-all duration-500 hover:-translate-y-0.5 flex items-center justify-center gap-2.5 text-sm sm:text-base"
            >
              <Sparkles className="w-4 h-4 sm:w-5 sm:h-5" />
              Invite Anya
              <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5 group-hover:translate-x-1 transition-transform duration-300" />
            </a>
          </div>
          
          {/* Trust indicators - elegant */}
          <div className="mt-10 sm:mt-12 flex flex-wrap items-center justify-center gap-6 sm:gap-8 text-gray-500 text-xs sm:text-sm">
            <span className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-primary/50" />
              Trusted
            </span>
            <span className="flex items-center gap-2">
              <Heart className="w-4 h-4 text-primary/50" />
              With Love
            </span>
            <span className="flex items-center gap-2">
              <Star className="w-4 h-4 text-primary/50" />
              Growing
            </span>
          </div>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
