import { Link } from 'react-router-dom';
import { Heart, Github, MessageCircle, Home, Terminal, Sparkles } from 'lucide-react';
import { BOT_CONFIG } from '../config/bot';

const Footer = () => {
  return (
    <footer className="relative mt-auto">
      {/* Gradient fade transition from content */}
      <div className="h-24 bg-gradient-to-b from-transparent to-dark-950"></div>
      
      <div className="bg-dark-950">
        <div className="max-w-5xl mx-auto px-6 py-12">
          {/* Main footer content - clean and minimal */}
          <div className="flex flex-col md:flex-row justify-between items-center gap-8">
            
            {/* Brand */}
            <div className="text-center md:text-left">
              <h3 className="text-lg font-display font-bold text-white mb-1">
                {BOT_CONFIG.name}
              </h3>
              <p className="text-gray-500 text-sm max-w-xs">
                Your elegant Discord companion
              </p>
            </div>

            {/* Navigation */}
            <nav className="flex items-center gap-6">
              <Link to="/" className="text-gray-400 hover:text-white transition-colors flex items-center gap-1.5 text-sm">
                <Home className="w-4 h-4" /> Home
              </Link>
              <Link to="/commands" className="text-gray-400 hover:text-white transition-colors flex items-center gap-1.5 text-sm">
                <Terminal className="w-4 h-4" /> Commands
              </Link>
              <Link to="/updates" className="text-gray-400 hover:text-white transition-colors flex items-center gap-1.5 text-sm">
                <Sparkles className="w-4 h-4" /> Updates
              </Link>
              <Link to="/contact" className="text-gray-400 hover:text-white transition-colors flex items-center gap-1.5 text-sm">
                <MessageCircle className="w-4 h-4" /> Contact
              </Link>
            </nav>

            {/* Social links */}
            <div className="flex items-center gap-4">
              <a
                href={BOT_CONFIG.supportServer}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 text-gray-500 hover:text-primary hover:bg-primary/10 rounded-lg transition-all"
                title="Discord Support"
              >
                <MessageCircle className="w-5 h-5" />
              </a>
              <a
                href="https://github.com/Anya-Devs"
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 text-gray-500 hover:text-white hover:bg-white/10 rounded-lg transition-all"
                title="GitHub"
              >
                <Github className="w-5 h-5" />
              </a>
            </div>
          </div>

          {/* Divider */}
          <div className="my-8 h-px bg-gradient-to-r from-transparent via-dark-700 to-transparent"></div>

          {/* Bottom bar */}
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 text-sm text-gray-600">
            <p className="flex items-center gap-1">
              Made with <Heart className="w-3.5 h-3.5 text-primary" /> by Anya Devs
            </p>
            <p>© {new Date().getFullYear()} {BOT_CONFIG.name}</p>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
