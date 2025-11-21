import { useState, useEffect } from 'react';
import { Sparkles, Zap, ArrowRight } from 'lucide-react';
import { BOT_CONFIG } from '../config/bot';
import BotAvatar from '../components/BotAvatar';
import SlidingFeatures from '../components/SlidingFeatures';
import { fetchBotStats } from '../services/botStatsService';

const HomePage = () => {
  const [stats, setStats] = useState({
    servers: 'Loading...',
    users: 'Loading...',
    commands: 'Loading...',
    uptime: 'Loading...'
  });

  useEffect(() => {
    // Fetch real stats on mount
    fetchBotStats().then(newStats => {
      setStats({
        servers: String(newStats.servers),
        users: String(newStats.users),
        commands: String(newStats.commands),
        uptime: newStats.uptime
      });
    });
  }, []);

  return (
    <div className="pt-24">
      {/* Bot Info Section */}
      <section className="py-12 md:py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            {/* Bot Icon/Mascot */}
            <div className="flex justify-center lg:justify-end">
              <div className="relative w-64 h-64 md:w-80 md:h-80">
                <div className="absolute inset-0 bg-gradient-primary rounded-full blur-3xl opacity-20 animate-pulse"></div>
                <div className="relative w-full h-full bg-dark-800 rounded-full shadow-2xl flex items-center justify-center border-4 border-primary/30 overflow-hidden">
                  <BotAvatar 
                    className="w-full h-full object-cover"
                    size={512}
                  />
                </div>
              </div>
            </div>

            {/* Bot Description */}
            <div className="text-center lg:text-left">
              <div className="inline-flex items-center px-4 py-2 bg-primary/10 border border-primary/30 rounded-full mb-6">
                <span className="text-sm text-primary font-semibold">Version {BOT_CONFIG.version}</span>
              </div>

              <h1 className="text-4xl md:text-6xl font-display font-bold mb-6">
                <span className="text-gradient">Anya Bot</span>
              </h1>

              <p className="text-lg md:text-xl text-gray-400 mb-8 max-w-2xl">
                {BOT_CONFIG.description}
              </p>

              <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
                <a
                  href={BOT_CONFIG.inviteLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group px-8 py-4 bg-gradient-primary text-white font-bold rounded-lg shadow-xl hover:shadow-pink-glow transition-all duration-300 hover:-translate-y-1 flex items-center justify-center"
                >
                  <Sparkles className="w-5 h-5 mr-2" />
                  Invite to Server
                  <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
                </a>
                <a
                  href={BOT_CONFIG.supportServer}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-8 py-4 bg-dark-800 text-white font-bold rounded-lg border-2 border-primary/30 hover:border-primary hover:bg-dark-700 shadow-lg transition-all duration-300"
                >
                  Join Support
                </a>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
            {Object.entries(stats)
              .filter(([key]) => key !== 'lastUpdated') // Filter out Date object
              .map(([key, value]) => (
              <div key={key} className="card p-4 md:p-6 text-center hover:scale-105 transition-transform">
                <div className="text-2xl md:text-4xl font-bold text-gradient mb-2">{value}</div>
                <div className="text-xs md:text-sm text-gray-400 capitalize">{key}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section - Full View Discord Style */}
      <section className="min-h-screen bg-dark-900 flex flex-col">
        <div className="flex-1 flex flex-col max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
          <div className="flex-shrink-0 text-center mb-6 pt-12">
            <h2 className="text-3xl md:text-5xl font-display font-bold text-gradient mb-4">
              Powerful Features
            </h2>
            <p className="text-lg md:text-xl text-gray-400 mb-8">
              See Anya Bot in action with live command demonstrations
            </p>
          </div>

          <div className="flex-1">
            <SlidingFeatures />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-12 md:py-20 bg-dark-900">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl md:text-5xl font-display font-bold text-white mb-6">
            Ready to Get Started?
          </h2>
          <p className="text-lg md:text-xl text-gray-400 mb-8">
            Join thousands of servers already using Anya Bot
          </p>
          <a
            href={BOT_CONFIG.inviteLink}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-8 md:px-10 py-4 md:py-5 bg-gradient-primary text-white font-bold text-base md:text-lg rounded-lg shadow-2xl hover:shadow-pink-glow transition-all duration-300 hover:-translate-y-1"
          >
            <Zap className="w-5 h-5 md:w-6 md:h-6 mr-2" />
            Add Anya Bot Now
            <ArrowRight className="w-5 h-5 md:w-6 md:h-6 ml-2" />
          </a>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
