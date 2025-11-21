import { useState, useEffect } from 'react';
import { Sparkles, Gamepad2, Laugh, Trophy, Book, Zap, Bot, ChevronDown } from 'lucide-react';
import DiscordChannel from './DiscordChannel';
import DiscordMessage from './DiscordMessage';
import BotAvatar from './BotAvatar';
import { BOT_CONFIG } from '../config/bot';
import { getBotAvatar } from '../utils/botAvatar';

interface BotCommand {
  aliases: string[];
  description: string;
  example: string;
  related_commands: string;
}

interface CommandsData {
  [category: string]: {
    [commandName: string]: BotCommand;
  };
}

const RealCommandShowcase = () => {
  const [commands, setCommands] = useState<CommandsData>({});
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedCommand, setSelectedCommand] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [categoryDropdownOpen, setCategoryDropdownOpen] = useState(false);
  const [commandDropdownOpen, setCommandDropdownOpen] = useState(false);
  const [botAvatar, setBotAvatar] = useState<string>('');
  const [currentTime, setCurrentTime] = useState<string>('');

  // Update time every second
  useEffect(() => {
    const updateTime = () => {
      setCurrentTime(new Date().toLocaleTimeString('en-US', { 
        hour: 'numeric', 
        minute: '2-digit',
        hour12: true 
      }));
    };
    
    updateTime(); // Initial update
    const interval = setInterval(updateTime, 1000); // Update every second
    
    return () => clearInterval(interval);
  }, []);

  // Load bot avatar
  useEffect(() => {
    getBotAvatar().then((url: string | null) => {
      if (url) setBotAvatar(url);
    });
  }, []);

  // Load commands from JSON
  useEffect(() => {
    fetch('/commands.json')
      .then(res => res.json())
      .then((data: CommandsData) => {
        setCommands(data);
        // Find first category with commands
        const firstCategoryWithCommands = Object.entries(data).find(
          ([_, cmds]) => typeof cmds === 'object' && Object.keys(cmds).length > 0
        );
        if (firstCategoryWithCommands) {
          const [catName, catCommands] = firstCategoryWithCommands;
          setSelectedCategory(catName);
          const firstCmd = Object.keys(catCommands)[0];
          setSelectedCommand(firstCmd);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load commands:', err);
        setLoading(false);
      });
  }, []);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setCategoryDropdownOpen(false);
      setCommandDropdownOpen(false);
    };
    
    if (categoryDropdownOpen || commandDropdownOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [categoryDropdownOpen, commandDropdownOpen]);

  // Category icons mapping
  const categoryIcons: { [key: string]: any } = {
    'Ai': Sparkles,
    'Anime': Book,
    'Fun': Laugh,
    'Information': Bot,
    'Pokemon': Gamepad2,
    'PoketwoCommands': Gamepad2,
    'Quest': Trophy,
    'System': Zap,
    'Recommendation': Book
  };

  // Get categories with commands
  const categoriesWithCommands = Object.entries(commands)
    .filter(([_, cmds]) => typeof cmds === 'object' && Object.keys(cmds).length > 0)
    .map(([name]) => ({
      id: name,
      icon: categoryIcons[name] || Bot,
      label: name
    }));

  const currentCmd = selectedCategory && selectedCommand && commands[selectedCategory] 
    ? commands[selectedCategory][selectedCommand] 
    : null;

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
        <p className="mt-4 text-gray-400">Loading commands...</p>
      </div>
    );
  }

  if (!currentCmd) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">No commands available</p>
      </div>
    );
  }

  const example = currentCmd.example.replace(/\{\}/g, BOT_CONFIG.prefix).replace(/\{prefix\}/g, BOT_CONFIG.prefix);
  const relatedCommands = currentCmd.related_commands 
    ? currentCmd.related_commands.replace(/\{\}/g, BOT_CONFIG.prefix).replace(/\{prefix\}/g, BOT_CONFIG.prefix)
    : '';
  
  const commandEmbed = {
    title: `${selectedCommand}`,
    description: currentCmd.description || 'No description provided',
    color: '#FF6B9D',
    fields: [
      { name: 'Usage Example', value: `\`\`\`${example}\`\`\``, inline: false },
      ...(currentCmd.aliases && currentCmd.aliases.length > 0 
        ? [{ name: 'Aliases', value: currentCmd.aliases.map(a => `\`${a}\``).join(', '), inline: true }] 
        : []),
      ...(relatedCommands 
        ? [{ name: 'Related Commands', value: relatedCommands, inline: false }] 
        : [])
    ],
    footer: `Category: ${selectedCategory} • Prefix: ${BOT_CONFIG.prefix}`
  };

  const selectedCategoryData = categoriesWithCommands.find(c => c.id === selectedCategory);
  const SelectedCategoryIcon = selectedCategoryData?.icon || Bot;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left Sidebar - Dropdown Selectors */}
      <div className="lg:col-span-1">
        <div className="card p-4 md:p-6 sticky top-24">
          <div className="flex items-center gap-3 mb-6">
            {/* Bot Avatar */}
            <div className="flex-shrink-0">
              <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-primary/30 shadow-lg">
                <BotAvatar className="w-full h-full object-cover" size={128} />
              </div>
            </div>
            
            <div className="flex-1">
              <h3 className="text-lg font-bold text-white mb-1">Commands</h3>
              <p className="text-xs text-gray-400">Select to preview</p>
            </div>
          </div>

          <div className="space-y-4">
          {/* Category Dropdown */}
          <div className="relative">
            <label className="block text-sm font-semibold text-gray-400 mb-2">Category</label>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setCategoryDropdownOpen(!categoryDropdownOpen);
              }}
              className="w-full px-4 py-3 bg-dark-800 border border-dark-600 rounded-lg text-white hover:border-primary transition-colors flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <SelectedCategoryIcon className="w-5 h-5 text-primary" />
                <span>{selectedCategoryData?.label || 'Select Category'}</span>
              </div>
              <ChevronDown className={`w-5 h-5 transition-transform ${categoryDropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {categoryDropdownOpen && (
              <div className="absolute z-10 w-full mt-2 bg-dark-800 border border-dark-600 rounded-lg shadow-xl max-h-64 overflow-y-auto">
                {categoriesWithCommands.map((cat) => {
                  const Icon = cat.icon;
                  return (
                    <button
                      key={cat.id}
                      onClick={() => {
                        setSelectedCategory(cat.id);
                        const firstCmd = Object.keys(commands[cat.id])[0];
                        setSelectedCommand(firstCmd);
                        setCategoryDropdownOpen(false);
                      }}
                      className={`w-full text-left px-4 py-3 hover:bg-dark-700 transition-colors flex items-center gap-3 ${
                        selectedCategory === cat.id ? 'bg-primary/10 text-primary' : 'text-gray-300'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      <span>{cat.label}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Command Dropdown */}
          <div className="relative">
            <label className="block text-sm font-semibold text-gray-400 mb-2">Command</label>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setCommandDropdownOpen(!commandDropdownOpen);
              }}
              className="w-full px-4 py-3 bg-dark-800 border border-dark-600 rounded-lg text-white hover:border-primary transition-colors flex items-center justify-between disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={!selectedCategory}
            >
              <span>{selectedCommand || 'Select Command'}</span>
              <ChevronDown className={`w-5 h-5 transition-transform ${commandDropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {commandDropdownOpen && selectedCategory && commands[selectedCategory] && (
              <div className="absolute z-10 w-full mt-2 bg-dark-800 border border-dark-600 rounded-lg shadow-xl max-h-64 overflow-y-auto">
                {Object.keys(commands[selectedCategory]).map((cmdName) => (
                  <button
                    key={cmdName}
                    onClick={() => {
                      setSelectedCommand(cmdName);
                      setCommandDropdownOpen(false);
                    }}
                    className={`w-full text-left px-4 py-3 hover:bg-dark-700 transition-colors ${
                      selectedCommand === cmdName ? 'bg-primary/10 text-primary font-semibold' : 'text-gray-300'
                    }`}
                  >
                    {cmdName}
                  </button>
                ))}
              </div>
            )}
          </div>
          </div>
        </div>
      </div>

      {/* Right Side - Discord Preview */}
      <div className="lg:col-span-2">
        <DiscordChannel channelName="bot-commands">
          {/* User Message */}
          <DiscordMessage
            username="You"
            isBot={false}
            content={`${BOT_CONFIG.prefix}${selectedCommand}`}
            timestamp={currentTime}
          />

          {/* Bot Response */}
          <DiscordMessage
            username={BOT_CONFIG.name}
            avatar={botAvatar}
            isBot={true}
            embed={commandEmbed}
            timestamp={currentTime}
          />
        </DiscordChannel>

        {/* Command Info */}
        <div className="mt-6 p-4 md:p-6 card">
          <h4 className="text-base md:text-lg font-semibold text-white mb-3">Try it yourself!</h4>
          <p className="text-sm md:text-base text-gray-400 mb-4">
            Invite Anya Bot to your server and use <code className="text-primary bg-primary/10 px-2 py-1 rounded font-semibold">{BOT_CONFIG.prefix}{selectedCommand}</code> to see this command in action.
          </p>
          <a
            href="https://discord.com/oauth2/authorize?client_id=1234247716243112100&scope=bot&permissions=8"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-4 md:px-6 py-2 md:py-3 bg-gradient-primary text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-300 hover:-translate-y-0.5 text-sm md:text-base"
          >
            <Sparkles className="w-4 h-4 md:w-5 md:h-5 mr-2" />
            Invite Bot Now
          </a>
        </div>
      </div>
    </div>
  );
};

export default RealCommandShowcase;
