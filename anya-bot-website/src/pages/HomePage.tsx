import { useState, useEffect } from 'react';
import { ArrowRight, Shield, Users, Server, Heart, FileText, Sparkles, MessageCircle, Zap, Trophy, Gamepad2 } from 'lucide-react';

import { BOT_CONFIG } from '../config/bot';
import BotAvatar from '../components/BotAvatar';
import SlidingFeatures from '../components/SlidingFeatures';
import DiscordPreviewCard from '../components/DiscordPreviewCard';
import { fetchBotStats } from '../services/botStatsService';

// Progress bar emoji utility
const getEmojiUrl = (emojiId: string, size: number = 16): string => {
  return `https://cdn.discordapp.com/emojis/${emojiId}.webp?size=${size}&quality=lossless`;
};

const generateProgressBar = (current: number, max: number, length: number = 10): string => {
  const progress = Math.min(Math.max(current / max, 0), 1);
  const filledSegments = Math.round(progress * length);
  const percentage = Math.round(progress * 100);
  
  const emojiIds = {
    front_empty: '1421229056946470993',
    front_full: '1421224992263114905',
    mid_empty: '1421229540444737727',
    mid_full: '1421222542596771891',
    back_empty: '1421228774761959464',
    back_full: '1421225912657252452',
  };
  
  let bar = `<span style="color: #dbdee1; font-family: monospace;">${current}/${max}</span> `;
  
  const frontEmojiId = filledSegments > 0 ? emojiIds.front_full : emojiIds.front_empty;
  bar += `<img src="${getEmojiUrl(frontEmojiId)}" alt="[" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />`;
  
  for (let i = 1; i < length - 1; i++) {
    const isFilled = i < filledSegments;
    const emojiId = isFilled ? emojiIds.mid_full : emojiIds.mid_empty;
    bar += `<img src="${getEmojiUrl(emojiId)}" alt="${isFilled ? '█' : ' '}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />`;
  }
  
  const backEmojiId = emojiIds.back_empty;
  bar += `<img src="${getEmojiUrl(backEmojiId)}" alt="]" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />`;
  bar += ` <span style="color: #dbdee1; font-family: monospace; vertical-align: middle;">${percentage}%</span>`;
  
  return bar;
};

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

// Feature showcase data - Wick Bot style sections
const featureShowcases = [
  {
    id: 'quests',
    icon: Trophy,
    title: 'Quest System',
    description: 'I created this bot so people can complete quests by talking to each other and being active. Members earn rewards for chatting, reacting, and engaging naturally. The goal is simple: get people talking.',
    tags: ['Daily Quests', 'Message Rewards', 'Reaction Tracking', 'Leaderboards', 'Custom Rewards'],
    preview: {
      command: '.quest',
      title: 'Your Quests',
      embedColor: '#FF6B9D',
      fields: [
        { 
          name: '', 
          value: '**#1** - Send: Hello {user}\n' +
            '`0/5` ' +
            `<img src="${getEmojiUrl('1421229056946470993')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421228774761959464')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            ' `0%`\n' +
            '📍 In this channel • ' +
            `<img src="https://cdn.discordapp.com/emojis/1247800150479339581.gif" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            ' `100 stp`',
          inline: false 
        },
        { 
          name: '', 
          value: '**#2** - React with: :thumbsup:\n' +
            '`2/10` ' +
            `<img src="${getEmojiUrl('1421224992263114905')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421222542596771891')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421222542596771891')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421229540444737727')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            `<img src="${getEmojiUrl('1421228774761959464')}" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            ' `20%`\n' +
            '📍 In this channel • ' +
            `<img src="https://cdn.discordapp.com/emojis/1247800150479339581.gif" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" />` +
            ' `250 stp`',
          inline: false 
        }
      ],
      footer: "User's quests • Page 1/1",
    }
  },
  {
    id: 'characters',
    icon: Heart,
    title: 'Spy x Family Characters',
    description: 'Buy characters from the shop, feed them, customize their appearance, play mini-games, and battle with other members. Each character has unique stats and abilities.',
    tags: ['Character Shop', 'Feeding System', 'Customization', 'Mini-Games', 'PvP Battles'],
    preview: {
      command: '.character',
      title: '👤 Anya Forger',
      description: 'She is the adopted daughter of Loid and Yor Forger. She attends Eden Academy as a first-year student in Cecile Hall, Class 3.\n\n> **Fighting Ability:** Able to dodge 65% of attacks\n> **Food Ability:** Hp + 20 boost when included peanuts',
      image: '/images/characters/anya-forger.png',
      embedColor: '#FFB6C1',
      fields: [
        { 
          name: 'HP', 
          value: generateProgressBar(80, 100),
          inline: false,
        },
        { 
          name: 'Stats', 
          value: '⚔️ ATK: 10\n🛡️ DEF: 8\n⚡ SPD: 14\n🎯 CRIT: 5%\n🎭 EVA: 10%', 
          inline: true 
        },
        { 
          name: 'Info', 
          value: '❤️ Bond: 0/10\n🍽️ Next meal: 1h 23m\n🍳 Cooking: Normal', 
          inline: true 
        }
      ],
    }
  },
  {
    id: 'poketwo',
    icon: Shield,
    title: 'Pokétwo Helper',
    description: 'Never miss a spawn again. Get pinged for specific Pokémon types, protect your shiny hunts, and track your collection. Built for servers that love catching Pokémon together.',
    tags: ['Spawn Alerts', 'Shiny Protection', 'Type Pings', 'Collection Tracking', 'Quest Pings'],
    preview: {
      command: '.pt sh alolan vulpix',
      description: '✅ <img src="https://cdn.discordapp.com/emojis/1340557284597698682.webp?size=96" style="width: 20px; height: 20px; display: inline-block; vertical-align: middle;" /> You are now shiny hunting Alolan Vulpix!',
      embedColor: '#5865F2',
    }
  },
  {
    id: 'fun',
    icon: Gamepad2,
    title: 'Fun & Social Commands',
    description: 'Hugs, pats, bites, and other action commands to interact with friends. Anime lookups, 8ball, and more ways to have fun and keep the chat active.',
    tags: ['Action Commands', 'Anime Search', '8Ball', 'Social Interactions'],
    preview: {
      command: '.hug @Anya',
      title: 'Yor hugs Anya',
      embedColor: '#FF6B9D',
      hasGif: true,
      gifUrl: 'https://media1.tenor.com/m/sQ_isTxT-EEAAAAd/anya-hug.gif',
      footer: 'Sent: 42 | Received: 38',
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
                A Discord bot made for people to <span className="text-primary">talk</span>, <span className="text-primary">complete quests</span>, and <span className="text-primary">be active together</span>. 
                Built to keep your community engaged.
              </p>

              {/* Quick pitch - hidden on mobile, shown on sm+ */}
              <div className="hidden sm:block mb-6 sm:mb-8 text-left max-w-md mx-auto lg:mx-0">
                <p className="text-sm text-gray-500 leading-relaxed">
                  Quests reward chatting • Pokétwo spawn helper • Spy x Family characters to collect & battle
                </p>
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
          WHY ANYA - Brief intro
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="py-16 sm:py-24 relative">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary/90 text-sm font-display mb-6">
            <Sparkles className="w-4 h-4" />
            Why I Made Anya
          </div>
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-display font-bold text-white mb-6">
            A bot with a purpose
          </h2>
          <p className="text-base sm:text-lg text-gray-400 leading-relaxed max-w-3xl mx-auto">
            I created Anya so people can complete quests by talking to each other and being active. 
            No other bot does exactly what Anya does - she's built to keep your community <span className="text-primary">engaging</span> and <span className="text-primary">alive</span>. 
            The developer is constantly adding new features to keep things fresh.
          </p>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════════
          FEATURE SHOWCASES - Wick Bot style sections
      ═══════════════════════════════════════════════════════════════════════ */}
      {featureShowcases.map((feature, idx) => (
        <section 
          key={feature.id}
          className={`py-16 sm:py-24 relative overflow-hidden ${
            idx % 2 === 0 ? 'bg-dark-800/30' : ''
          }`}
        >
          {/* Background accent */}
          <div className="absolute inset-0 pointer-events-none">
            <div className={`absolute ${idx % 2 === 0 ? 'right-0' : 'left-0'} top-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-primary/5 rounded-full blur-[100px]`} />
          </div>

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
            <div className={`grid lg:grid-cols-2 gap-12 lg:gap-16 items-center ${
              idx % 2 === 1 ? 'lg:grid-flow-dense' : ''
            }`}>
              {/* Discord Preview Side */}
              <div className={`${idx % 2 === 1 ? 'lg:col-start-2' : ''}`}>
                <div className="relative">
                  {/* Decorative elements */}
                  <div className="absolute -inset-4 bg-gradient-to-br from-primary/10 to-transparent rounded-2xl blur-xl" />
                  <DiscordPreviewCard 
                    {...feature.preview} 
                    className="relative shadow-2xl transform hover:scale-[1.02] transition-transform duration-300"
                  />
                </div>
              </div>

              {/* Content Side */}
              <div className={`space-y-6 ${idx % 2 === 1 ? 'lg:col-start-1' : ''}`}>
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-2xl bg-primary/10 text-primary">
                    <feature.icon className="w-8 h-8" />
                  </div>
                  <h2 className="text-2xl sm:text-3xl lg:text-4xl font-display font-bold text-white">
                    {feature.title}
                  </h2>
                </div>

                <p className="text-gray-400 text-base sm:text-lg leading-relaxed">
                  {feature.description}
                </p>

                {/* Feature Tags */}
                <div className="flex flex-wrap gap-2 pt-2">
                  {feature.tags.map((tag) => (
                    <span 
                      key={tag}
                      className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 transition-colors"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Try it hint */}
                <div className="pt-4">
                  <span className="text-xs text-gray-500 uppercase tracking-wider">Try it →</span>
                  <code className="ml-2 px-3 py-1.5 bg-dark-700/60 rounded-lg text-primary text-sm font-mono">
                    {feature.preview.command}
                  </code>
                </div>
              </div>
            </div>
          </div>
        </section>
      ))}

      {/* ═══════════════════════════════════════════════════════════════════════
          ALWAYS GROWING - Brief section
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="py-16 sm:py-24 relative">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="p-4 rounded-2xl bg-primary/10 text-primary inline-block mb-6">
            <Zap className="w-8 h-8" />
          </div>
          <h2 className="text-2xl sm:text-3xl font-display font-bold text-white mb-4">
            Always Growing
          </h2>
          <p className="text-gray-400 text-base sm:text-lg leading-relaxed max-w-2xl mx-auto">
            The developer is constantly adding new features. More characters, more quests, more ways to keep your community engaged. 
            Anya can already do a lot, and she'll be able to do even more in the future.
          </p>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════════
          LIVE PREVIEW CAROUSEL
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="py-16 sm:py-24 relative bg-dark-800/30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <p className="text-sm uppercase tracking-[0.4em] text-primary/70 mb-3">See It In Action</p>
            <h3 className="text-xl sm:text-2xl font-semibold text-white">A glimpse of what Anya can do</h3>
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
            Keep your community active with quests, help with Pokétwo, and have fun with Spy x Family characters.
            <span className="text-primary/80"> Let's build something great together! </span>
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
              <MessageCircle className="w-4 h-4 text-primary/50" />
              Community Focused
            </span>
            <span className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-primary/50" />
              Always Improving
            </span>
            <span className="flex items-center gap-2">
              <Heart className="w-4 h-4 text-primary/50" />
              Made With Love
            </span>
          </div>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
