import { Link } from 'react-router-dom';
import { Heart, Github, MessageCircle, Home, Terminal, Sparkles } from 'lucide-react';
import { BOT_CONFIG } from '../config/bot';

const Footer = () => {
  return (
    <footer className="relative mt-auto">
      {/* Gradient fade */}
      <div className="h-16 sm:h-20 bg-gradient-to-b from-transparent to-dark-900"></div>
      
      <div className="bg-dark-900">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
          
          {/* Mobile: Stacked layout. Desktop: Row layout */}
          <div className="flex flex-col gap-8">
            
            {/* Top section: Brand + Social on mobile, all in row on desktop */}
            <div className="flex flex-col md:flex-row justify-between items-center gap-6 md:gap-8">
              
              {/* Brand */}
              <div className="text-center md:text-left">
                <h3 className="text-base sm:text-lg font-display font-bold text-gradient mb-0.5 sm:mb-1">
                  {BOT_CONFIG.name}
                </h3>
                <p className="text-gray-500 text-xs sm:text-sm">
                  Your cozy Discord companion
                </p>
              </div>

              {/* Navigation - 2x2 grid on mobile, row on tablet+ */}
              <nav className="grid grid-cols-4 sm:flex sm:items-center gap-4 sm:gap-6">
                {[
                  { to: '/', icon: Home, label: 'Home' },
                  { to: '/commands', icon: Terminal, label: 'Commands' },
                  { to: '/updates', icon: Sparkles, label: 'Updates' },
                  { to: '/contact', icon: MessageCircle, label: 'Contact' },
                ].map((link) => (
                  <Link 
                    key={link.to}
                    to={link.to} 
                    className="flex flex-col sm:flex-row items-center gap-1 sm:gap-1.5 text-gray-400 hover:text-primary transition-colors"
                  >
                    <link.icon className="w-4 h-4" />
                    <span className="text-[10px] sm:text-sm">{link.label}</span>
                  </Link>
                ))}
              </nav>

              {/* Social links */}
              <div className="flex items-center gap-2 sm:gap-3">
                <a
                  href={BOT_CONFIG.supportServer}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 sm:p-2.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded-lg transition-all"
                  title="Discord Support"
                >
                  <MessageCircle className="w-4 h-4 sm:w-5 sm:h-5" />
                </a>
                <a
                  href="https://github.com/Anya-Devs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 sm:p-2.5 text-gray-500 hover:text-white hover:bg-white/10 rounded-lg transition-all"
                  title="GitHub"
                >
                  <Github className="w-4 h-4 sm:w-5 sm:h-5" />
                </a>
              </div>
            </div>

            {/* Divider */}
            <div className="flex items-center justify-center gap-3 sm:gap-4">
              <div className="h-px flex-1 bg-dark-700" />
              <Heart className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary/40 fill-primary/20" />
              <div className="h-px flex-1 bg-dark-700" />
            </div>

            {/* Bottom bar */}
            <div className="flex flex-col sm:flex-row justify-between items-center gap-2 sm:gap-4 text-xs sm:text-sm text-gray-600">
              <p className="flex items-center gap-1.5">
                Made with <Heart className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-primary fill-primary/30" /> by Anya Devs
              </p>
              <p>© {new Date().getFullYear()} {BOT_CONFIG.name}</p>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
