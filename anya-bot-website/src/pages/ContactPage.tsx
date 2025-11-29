import { useState } from 'react';
import { 
  MessageCircle, Github, Heart, Mail, ExternalLink,
  Coffee, Sparkles, Star, Code2
} from 'lucide-react';
import { BOT_CONFIG } from '../config/bot';

const DEVELOPER_ID = '1124389055598170182';
const DEV_AVATAR = '/dev-avatar.png'; // Static developer avatar
const DEV_USERNAME = 'Senko';

const ContactPage = () => {
  const [hovered, setHovered] = useState(false);

  const socialLinks = [
    { 
      icon: MessageCircle, 
      label: 'Discord Server', 
      href: BOT_CONFIG.supportServer,
      color: 'from-indigo-500 to-purple-500',
      desc: 'Join our community!'
    },
    { 
      icon: Github, 
      label: 'GitHub', 
      href: 'https://github.com/Anya-Devs/Anya-Bot',
      color: 'from-gray-600 to-gray-800',
      desc: 'View source code'
    },
  ];

  return (
    <div className="pt-24 pb-20 min-h-screen">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Hero Header */}
        <div className="text-center mb-16 animate-fade-in">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-pink-500 to-rose-500 rounded-3xl mb-6 shadow-2xl shadow-pink-500/30">
            <Heart className="w-10 h-10 text-white animate-pulse" />
          </div>
          <h1 className="text-4xl md:text-6xl font-display font-bold mb-4">
            <span className="text-gradient">Get in Touch</span>
          </h1>
          <p className="text-xl text-gray-400 max-w-xl mx-auto">
            Have questions, suggestions, or just want to say hi? 
            We'd love to hear from you! 💌
          </p>
        </div>

        {/* Developer Card */}
        <div className="mb-12">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Code2 className="w-5 h-5 text-primary" />
            Meet the Developer
          </h2>
          
          <div 
            className={`relative bg-dark-800/50 border border-dark-700 rounded-2xl p-8 overflow-hidden transition-all duration-500 ${
              hovered ? 'border-primary shadow-xl shadow-primary/10' : ''
            }`}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
          >
            {/* Animated background gradient */}
            <div className={`absolute inset-0 bg-gradient-to-r from-primary/5 via-purple-500/5 to-pink-500/5 transition-opacity duration-500 ${
              hovered ? 'opacity-100' : 'opacity-0'
            }`}></div>

            <div className="relative flex flex-col md:flex-row items-center gap-8">
              {/* Avatar */}
              <div className="relative group">
                <div className={`absolute inset-0 bg-gradient-to-r from-primary to-purple-500 rounded-full blur-xl opacity-30 group-hover:opacity-50 transition-opacity ${
                  hovered ? 'animate-pulse' : ''
                }`}></div>
                <img
                  src={DEV_AVATAR}
                  alt={DEV_USERNAME}
                  className="relative w-32 h-32 rounded-full border-4 border-primary/30 shadow-2xl object-cover transition-transform duration-300 group-hover:scale-105"
                />
                
                {/* Online indicator */}
                <div className="absolute bottom-2 right-2 w-6 h-6 bg-green-500 rounded-full border-4 border-dark-800 animate-pulse"></div>
              </div>

              {/* Info */}
              <div className="flex-1 text-center md:text-left">
                <div className="flex items-center justify-center md:justify-start gap-2 mb-2">
                  <h3 className="text-2xl font-bold text-white">
                    {DEV_USERNAME}
                  </h3>
                  <Sparkles className="w-5 h-5 text-yellow-400" />
                </div>
                <p className="text-gray-400 mb-4">
                  Creator of Anya Bot • Full-Stack Developer • Silly Lil Guy
                </p>
                <div className="flex flex-wrap justify-center md:justify-start gap-2">
                  <span className="px-3 py-1 bg-dark-700 text-gray-300 rounded-lg text-sm flex items-center gap-1">
                    <Star className="w-3 h-3 text-yellow-400" /> Lead Developer
                  </span>
                  <span className="px-3 py-1 bg-dark-700 text-gray-300 rounded-lg text-sm flex items-center gap-1">
                    <Heart className="w-3 h-3 text-pink-400" /> Self Lover
                  </span>
                  <span className="px-3 py-1 bg-dark-700 text-gray-300 rounded-lg text-sm flex items-center gap-1">
                    <Coffee className="w-3 h-3 text-amber-400" /> Powered by Fun
                  </span>
                </div>

                {/* Discord ID */}
                <p className="mt-4 text-xs text-gray-500 font-mono">
                  Discord ID: {DEVELOPER_ID}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Contact Options */}
        <div className="mb-12">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <MessageCircle className="w-5 h-5 text-primary" />
            Connect With Us
          </h2>
          
          <div className="grid md:grid-cols-2 gap-4">
            {socialLinks.map((link, i) => {
              const Icon = link.icon;
              return (
                <a
                  key={i}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group relative bg-dark-800/50 border border-dark-700 rounded-2xl p-6 hover:border-primary/30 transition-all duration-300 hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-1"
                >
                  <div className={`absolute inset-0 bg-gradient-to-r ${link.color} opacity-0 group-hover:opacity-5 rounded-2xl transition-opacity`}></div>
                  <div className="relative flex items-center gap-4">
                    <div className={`p-3 rounded-xl bg-gradient-to-r ${link.color}`}>
                      <Icon className="w-6 h-6 text-white" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold text-white group-hover:text-primary transition-colors">
                        {link.label}
                      </h3>
                      <p className="text-sm text-gray-500">{link.desc}</p>
                    </div>
                    <ExternalLink className="w-5 h-5 text-gray-500 group-hover:text-primary transition-colors" />
                  </div>
                </a>
              );
            })}
          </div>
        </div>

        {/* Quick Contact Info */}
        <div className="bg-gradient-to-br from-primary/10 to-purple-500/10 border border-primary/20 rounded-2xl p-8 text-center">
          <Mail className="w-10 h-10 text-primary mx-auto mb-4" />
          <h3 className="text-xl font-bold text-white mb-2">Prefer Email?</h3>
          <p className="text-gray-400 mb-4">
            For business inquiries or partnerships, feel free to reach out!
          </p>
          <p className="text-primary font-mono">Comming Soon...</p>
        </div>

        {/* Fun Footer Message */}
        <div className="mt-16 text-center animate-fade-in">
          <p className="text-gray-500">
            Thanks for stopping by! 
            <span className="inline-block animate-wiggle ml-1">🎀</span>
          </p>
          <p className="text-gray-600 text-sm mt-2">
            "Waku waku!" - Anya Forger
          </p>
        </div>
      </div>
    </div>
  );
};

export default ContactPage;
