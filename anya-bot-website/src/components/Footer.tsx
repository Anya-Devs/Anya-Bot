import { useState, useEffect } from 'react';
import { Heart, Github, MessageCircle } from 'lucide-react';
import { BOT_CONFIG } from '../config/bot';
import { fetchBotStats } from '../services/botStatsService';

const Footer = () => {
  const [stats, setStats] = useState({
    servers: '...',
    users: '...',
    commands: '...',
    uptime: '...'
  });

  useEffect(() => {
    fetchBotStats().then(setStats);
  }, []);

  return (
    <footer className="bg-dark-900 border-t border-primary/20 mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* About */}
          <div className="col-span-1 md:col-span-2">
            <h3 className="text-xl font-display font-bold text-gradient mb-4">
              {BOT_CONFIG.name} 🎀
            </h3>
            <p className="text-gray-400 mb-4">
              {BOT_CONFIG.description}
            </p>
            <div className="flex items-center space-x-4">
              <a
                href={BOT_CONFIG.supportServer}
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-400 hover:text-primary transition-colors"
              >
                <MessageCircle className="w-5 h-5" />
              </a>
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-400 hover:text-primary transition-colors"
              >
                <Github className="w-5 h-5" />
              </a>
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h4 className="text-lg font-semibold text-white mb-4">Quick Links</h4>
            <ul className="space-y-2">
              <li>
                <a href="#" className="text-gray-400 hover:text-primary transition-colors">
                  Documentation
                </a>
              </li>
              <li>
                <a href="#" className="text-gray-400 hover:text-primary transition-colors">
                  Support
                </a>
              </li>
              <li>
                <a href="#" className="text-gray-400 hover:text-primary transition-colors">
                  Terms of Service
                </a>
              </li>
              <li>
                <a href="#" className="text-gray-400 hover:text-primary transition-colors">
                  Privacy Policy
                </a>
              </li>
            </ul>
          </div>

          {/* Stats */}
          <div>
            <h4 className="text-lg font-semibold text-white mb-4">Stats ⭐</h4>
            <ul className="space-y-2 text-gray-400">
              <li>Servers: <span className="text-primary font-semibold">{stats.servers}</span></li>
              <li>Users: <span className="text-primary font-semibold">{stats.users}</span></li>
              <li>Commands: <span className="text-primary font-semibold">{stats.commands}</span></li>
              <li>Uptime: <span className="text-primary font-semibold">{stats.uptime}</span></li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t border-primary/20 text-center text-gray-400">
          <p className="flex items-center justify-center">
            Made with <Heart className="w-4 h-4 mx-2 text-primary animate-pulse" /> by the Anya Bot Team
          </p>
          <p className="mt-2 text-sm">
            © {new Date().getFullYear()} {BOT_CONFIG.name}. All rights reserved. 🎀
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
