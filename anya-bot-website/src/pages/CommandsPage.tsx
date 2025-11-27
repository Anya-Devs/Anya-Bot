import { useState, useEffect, useMemo } from 'react';
import { 
  Search, Sparkles, Gamepad2, Laugh, Trophy, Book, Zap, Bot, 
  Copy, Check, ChevronDown, Terminal, Heart, Music, Image, Command
} from 'lucide-react';
import { BOT_CONFIG } from '../config/bot';

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

// Category configuration
const categoryConfig: { [key: string]: { icon: any; gradient: string } } = {
  'Ai': { icon: Sparkles, gradient: 'from-purple-500 to-pink-500' },
  'Anime': { icon: Book, gradient: 'from-pink-500 to-rose-500' },
  'Fun': { icon: Laugh, gradient: 'from-yellow-500 to-orange-500' },
  'Information': { icon: Bot, gradient: 'from-blue-500 to-cyan-500' },
  'Pokemon': { icon: Gamepad2, gradient: 'from-green-500 to-emerald-500' },
  'PoketwoCommands': { icon: Gamepad2, gradient: 'from-emerald-500 to-teal-500' },
  'Quest': { icon: Trophy, gradient: 'from-amber-500 to-yellow-500' },
  'System': { icon: Zap, gradient: 'from-red-500 to-orange-500' },
  'Recommendation': { icon: Heart, gradient: 'from-rose-500 to-pink-500' },
  'Action': { icon: Heart, gradient: 'from-pink-500 to-purple-500' },
  'Music': { icon: Music, gradient: 'from-violet-500 to-purple-500' },
  'Image': { icon: Image, gradient: 'from-cyan-500 to-blue-500' }
};

// Expandable Command Item Component
const CommandItem = ({ 
  cmdName, 
  cmd, 
  isExpanded, 
  onToggle, 
  onCopy, 
  isCopied 
}: { 
  cmdName: string; 
  cmd: BotCommand; 
  isExpanded: boolean; 
  onToggle: () => void;
  onCopy: () => void;
  isCopied: boolean;
}) => {
  return (
    <div className={`border rounded-xl transition-all duration-200 ${
      isExpanded ? 'border-primary bg-primary/5' : 'border-dark-600 bg-dark-800/50 hover:border-dark-500'
    }`}>
      {/* Command Header - Always Visible */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <div className="flex items-center gap-3">
          <code className="text-primary font-semibold">{BOT_CONFIG.prefix}{cmdName}</code>
          {cmd.aliases?.length > 0 && (
            <span className="text-xs text-gray-500 hidden sm:inline">
              +{cmd.aliases.length} alias{cmd.aliases.length > 1 ? 'es' : ''}
            </span>
          )}
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
      </button>

      {/* Expandable Details */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 animate-fade-in">
          {/* Description */}
          <p className="text-gray-300 text-sm">{cmd.description || 'No description available.'}</p>

          {/* Usage Example */}
          {cmd.example && (
            <div className="flex items-center gap-2">
              <div className="flex-1 p-2.5 bg-dark-900 rounded-lg font-mono text-sm text-green-400 overflow-x-auto">
                {cmd.example.replace(/\{\}/g, BOT_CONFIG.prefix).replace(/\{prefix\}/g, BOT_CONFIG.prefix)}
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); onCopy(); }}
                className="p-2 rounded-lg bg-dark-700 hover:bg-primary/20 transition-colors flex-shrink-0"
                title="Copy command"
              >
                {isCopied ? (
                  <Check className="w-4 h-4 text-green-400" />
                ) : (
                  <Copy className="w-4 h-4 text-gray-400" />
                )}
              </button>
            </div>
          )}

          {/* Aliases */}
          {cmd.aliases?.length > 0 && (
            <div className="flex flex-wrap gap-2">
              <span className="text-xs text-gray-500">Aliases:</span>
              {cmd.aliases.map((alias, i) => (
                <span key={i} className="px-2 py-0.5 bg-dark-700 text-gray-300 rounded text-xs font-mono">
                  {BOT_CONFIG.prefix}{alias}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const CommandsPage = () => {
  const [commands, setCommands] = useState<CommandsData>({});
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [expandedCommand, setExpandedCommand] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null);

  // Load commands
  useEffect(() => {
    fetch('/commands.json')
      .then(res => res.json())
      .then((data: CommandsData) => {
        setCommands(data);
        const firstCat = Object.keys(data).find(
          cat => typeof data[cat] === 'object' && Object.keys(data[cat]).length > 0
        );
        if (firstCat) setSelectedCategory(firstCat);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load commands:', err);
        setLoading(false);
      });
  }, []);

  // Get categories with commands
  const categories = useMemo(() => {
    return Object.entries(commands)
      .filter(([_, cmds]) => typeof cmds === 'object' && Object.keys(cmds).length > 0)
      .map(([name, cmds]) => ({
        id: name,
        count: Object.keys(cmds).length,
        ...categoryConfig[name] || { icon: Command, gradient: 'from-gray-500 to-gray-600' }
      }));
  }, [commands]);

  // Total command count
  const totalCommands = useMemo(() => {
    return categories.reduce((sum, cat) => sum + cat.count, 0);
  }, [categories]);

  // Filtered commands based on search
  const filteredCommands = useMemo(() => {
    if (!selectedCategory || !commands[selectedCategory]) return [];
    const categoryCommands = Object.entries(commands[selectedCategory]);
    if (!searchQuery.trim()) return categoryCommands;
    
    const query = searchQuery.toLowerCase();
    return categoryCommands.filter(([name, cmd]) => 
      name.toLowerCase().includes(query) ||
      cmd.description?.toLowerCase().includes(query) ||
      cmd.aliases?.some(a => a.toLowerCase().includes(query))
    );
  }, [commands, selectedCategory, searchQuery]);

  // Copy command to clipboard
  const copyCommand = (cmd: string) => {
    navigator.clipboard.writeText(`${BOT_CONFIG.prefix}${cmd}`);
    setCopiedCommand(cmd);
    setTimeout(() => setCopiedCommand(null), 2000);
  };

  if (loading) {
    return (
      <div className="pt-24 pb-20 min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent mb-4"></div>
          <p className="text-gray-400">Loading commands...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="pt-24 pb-20 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Hero Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-primary to-purple-600 rounded-3xl mb-6 shadow-2xl shadow-primary/30">
            <Terminal className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl md:text-6xl font-display font-bold mb-4">
            <span className="text-gradient">Command Center</span>
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-8">
            Explore {totalCommands}+ powerful commands across {categories.length} categories
          </p>
          
          {/* Search Bar */}
          <div className="max-w-xl mx-auto relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search commands by name, description, or alias..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-4 bg-dark-800 border border-dark-600 rounded-2xl text-white placeholder-gray-500 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all text-lg"
            />
          </div>
        </div>

        {/* Category Tabs */}
        <div className="flex flex-wrap gap-2 mb-8">
          {categories.map((cat) => {
            const Icon = cat.icon;
            const isActive = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => {
                  setSelectedCategory(cat.id);
                  setExpandedCommand(null);
                  setSearchQuery('');
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
                  isActive 
                    ? `bg-gradient-to-r ${cat.gradient} text-white` 
                    : 'bg-dark-800 text-gray-400 hover:text-white hover:bg-dark-700'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span className="text-sm font-medium">{cat.id}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${isActive ? 'bg-white/20' : 'bg-dark-700'}`}>
                  {cat.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Commands List - Clean single column with expandable items */}
        <div className="max-w-3xl mx-auto space-y-3">
          {filteredCommands.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <Search className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No commands found matching "{searchQuery}"</p>
            </div>
          ) : (
            filteredCommands.map(([cmdName, cmd]) => (
              <CommandItem
                key={cmdName}
                cmdName={cmdName}
                cmd={cmd}
                isExpanded={expandedCommand === cmdName}
                onToggle={() => setExpandedCommand(expandedCommand === cmdName ? null : cmdName)}
                onCopy={() => copyCommand(cmdName)}
                isCopied={copiedCommand === cmdName}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default CommandsPage;
