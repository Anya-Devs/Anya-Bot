import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, Home, Terminal, Sparkles, MessageCircle } from 'lucide-react';
import { BOT_CONFIG } from '../config/bot';
import BotAvatar from './BotAvatar';

const Navbar = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { name: 'Home', path: '/', icon: Home },
    { name: 'Commands', path: '/commands', icon: Terminal },
    { name: 'Contact', path: '/contact', icon: MessageCircle },
  ];

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled 
          ? 'bg-dark-900/95 backdrop-blur-xl shadow-lg border-b border-primary/10' 
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14 sm:h-16 py-2">
          {/* Logo with elegant frame */}
          <Link to="/" className="flex items-center space-x-2 sm:space-x-3 group">
            <div className="relative">
              {/* Subtle glow */}
              <div className="absolute inset-0 bg-primary/20 rounded-full blur-md opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              {/* Warm ring frame - smaller on mobile */}
              <div className="relative w-9 h-9 sm:w-11 sm:h-11 rounded-full p-0.5 bg-gradient-to-br from-primary/60 to-primary/20">
                <div className="w-full h-full rounded-full overflow-hidden bg-dark-800">
                  <BotAvatar className="w-full h-full object-cover" size={128} />
                </div>
              </div>
            </div>
            <span className="text-base sm:text-lg font-display font-bold text-gradient">
              {BOT_CONFIG.name}
            </span>
          </Link>

          {/* Desktop Navigation - Elegant styling */}
          <div className="hidden md:flex items-center">
            <div className="flex items-center space-x-1 px-2 py-1.5 rounded-xl bg-dark-800/50">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const isActive = location.pathname === link.path;
                return (
                  <Link
                    key={link.path}
                    to={link.path}
                    className={`relative px-4 py-2 text-sm font-medium rounded-lg transition-all duration-300 flex items-center gap-2 ${
                      isActive
                        ? 'text-primary bg-primary/10'
                        : 'text-gray-400 hover:text-white hover:bg-dark-700/50'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{link.name}</span>
                    {/* Active indicator dot */}
                    {isActive && (
                      <span className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-primary" />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* CTA Button - Reveals on hover */}
          <div className="hidden md:block">
            <a
              href={BOT_CONFIG.inviteLink}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-center gap-0 p-2.5 hover:pl-4 hover:pr-5 bg-primary/10 hover:bg-gradient-primary text-primary hover:text-white rounded-xl transition-all duration-300 hover:shadow-pink-glow overflow-hidden"
            >
              <Sparkles className="w-5 h-5 flex-shrink-0" />
              <span className="max-w-0 group-hover:max-w-[100px] overflow-hidden whitespace-nowrap transition-all duration-300 font-medium text-sm">
                &nbsp;Invite Anya
              </span>
            </a>
          </div>

          {/* Mobile menu button */}
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="md:hidden p-2 sm:p-2.5 rounded-lg text-gray-300 hover:text-primary hover:bg-primary/10 transition-colors"
            aria-label="Toggle menu"
          >
            {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu - Full screen on small devices */}
      {isOpen && (
        <div className="md:hidden fixed inset-x-0 top-[56px] sm:top-[64px] bottom-0 bg-dark-900/98 backdrop-blur-xl border-t border-dark-700 animate-slide-down overflow-y-auto">
          <div className="px-4 py-6 space-y-2 max-w-lg mx-auto">
            
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive = location.pathname === link.path;
              return (
                <Link
                  key={link.path}
                  to={link.path}
                  onClick={() => setIsOpen(false)}
                  className={`flex items-center gap-4 px-5 py-4 rounded-xl text-base font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-primary/10 text-primary border border-primary/20'
                      : 'text-gray-300 hover:bg-dark-800 hover:text-white active:bg-dark-700'
                  }`}
                >
                  <div className={`p-2 rounded-lg ${isActive ? 'bg-primary/20' : 'bg-dark-700'}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  {link.name}
                </Link>
              );
            })}
            
            {/* Divider */}
            <div className="h-px bg-dark-700 my-4" />
            
            {/* Invite button - larger touch target */}
            <a
              href={BOT_CONFIG.inviteLink}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 px-6 py-4 bg-gradient-primary text-white font-semibold rounded-xl shadow-lg text-base active:scale-[0.98] transition-transform"
            >
              <Sparkles className="w-5 h-5" />
              Invite Anya
            </a>
            
            {/* Extra padding at bottom for safe area */}
            <div className="h-8" />
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;
