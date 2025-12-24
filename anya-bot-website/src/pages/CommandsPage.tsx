import { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Search, Sparkles, Gamepad2, Laugh, Trophy, Book, Zap, Bot, 
  Copy, Check, ChevronDown, ChevronRight, Terminal, Heart, Music, Image, Command
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
  isCopied,
  isSubcommand = false
}: { 
  cmdName: string; 
  cmd: BotCommand; 
  isExpanded: boolean; 
  onToggle: () => void;
  onCopy: () => void;
  isCopied: boolean;
  isSubcommand?: boolean;
}) => {
  // Truncate description for preview (first line or first 80 chars)
  const getPreviewDescription = (desc: string) => {
    if (!desc) return '';
    const firstLine = desc.split('\n')[0];
    return firstLine.length > 100 ? firstLine.slice(0, 100) + '...' : firstLine;
  };

  return (
    <div className={`border rounded-xl transition-all duration-200 ${
      isExpanded ? 'border-primary bg-primary/5' : 'border-dark-600 bg-dark-800/50 hover:border-dark-500'
    } ${isSubcommand ? 'ml-4 border-l-2 border-l-primary/30' : ''}`}>
      {/* Command Header - Always Visible with Description */}
      <button
        onClick={onToggle}
        className="w-full flex items-start justify-between p-4 text-left gap-3"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <code className="text-primary font-semibold text-sm sm:text-base">{BOT_CONFIG.prefix}{cmdName}</code>
            {cmd.aliases?.length > 0 && (
              <div className="flex gap-1 flex-wrap">
                {cmd.aliases.slice(0, 2).map((alias, i) => (
                  <span key={i} className="px-1.5 py-0.5 bg-dark-700 text-gray-400 rounded text-xs font-mono">
                    {BOT_CONFIG.prefix}{alias}
                  </span>
                ))}
                {cmd.aliases.length > 2 && (
                  <span className="text-xs text-gray-500">+{cmd.aliases.length - 2}</span>
                )}
              </div>
            )}
          </div>
          {/* Description Preview - Always Visible */}
          <p className="text-gray-400 text-sm mt-1.5 leading-relaxed">
            {isExpanded ? '' : getPreviewDescription(cmd.description || 'No description available.')}
          </p>
        </div>
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 mt-1 ${isExpanded ? 'rotate-180' : ''}`} />
      </button>

      {/* Expandable Details */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 animate-fade-in border-t border-dark-700 pt-4 mx-4 -mt-2">
          {/* Full Description - render newlines as line breaks */}
          <p className="text-gray-300 text-sm whitespace-pre-line leading-relaxed">{cmd.description || 'No description available.'}</p>

          {/* Usage Example */}
          {cmd.example && (
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Usage</span>
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
            </div>
          )}

          {/* Aliases */}
          {cmd.aliases?.length > 0 && (
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Aliases</span>
              <div className="flex flex-wrap gap-2">
                {cmd.aliases.map((alias, i) => (
                  <span key={i} className="px-2 py-1 bg-dark-700 text-gray-300 rounded-lg text-xs font-mono">
                    {BOT_CONFIG.prefix}{alias}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Related Commands */}
          {cmd.related_commands && (
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Related</span>
              <p className="text-gray-400 text-sm">{cmd.related_commands}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Tree Branch Subcommand Item - with visual tree connector
const TreeCommandItem = ({ 
  cmdName, 
  cmd, 
  isExpanded, 
  onToggle, 
  onCopy, 
  isCopied,
  isLast = false
}: { 
  cmdName: string; 
  cmd: BotCommand; 
  isExpanded: boolean; 
  onToggle: () => void;
  onCopy: () => void;
  isCopied: boolean;
  isLast?: boolean;
}) => {
  const getPreviewDescription = (desc: string) => {
    if (!desc) return '';
    const firstLine = desc.split('\n')[0];
    return firstLine.length > 100 ? firstLine.slice(0, 100) + '...' : firstLine;
  };

  // Extract just the subcommand part (e.g., "anime search" -> "search")
  const subCmdPart = cmdName.includes(' ') ? cmdName.split(' ').slice(1).join(' ') : cmdName;

  return (
    <div className="flex">
      {/* Tree branch connector */}
      <div className="flex flex-col items-center w-6 flex-shrink-0">
        <div className={`w-px bg-primary/40 ${isLast ? 'h-5' : 'flex-1'}`}></div>
        <div className="w-3 h-px bg-primary/40 self-end"></div>
        {!isLast && <div className="w-px bg-primary/40 flex-1"></div>}
      </div>
      
      {/* Command card */}
      <div className={`flex-1 border rounded-xl transition-all duration-200 ${
        isExpanded ? 'border-primary bg-primary/5' : 'border-dark-600 bg-dark-800/50 hover:border-dark-500'
      }`}>
        <button
          onClick={onToggle}
          className="w-full flex items-start justify-between p-3 text-left gap-3"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <code className="text-primary/80 font-semibold text-sm">{subCmdPart}</code>
              {cmd.aliases?.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {cmd.aliases.slice(0, 2).map((alias, i) => (
                    <span key={i} className="px-1.5 py-0.5 bg-dark-700 text-gray-400 rounded text-xs font-mono">
                      {alias}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <p className="text-gray-400 text-xs mt-1 leading-relaxed">
              {isExpanded ? '' : getPreviewDescription(cmd.description || 'No description available.')}
            </p>
          </div>
          <ChevronDown className={`w-3 h-3 text-gray-400 transition-transform flex-shrink-0 mt-1 ${isExpanded ? 'rotate-180' : ''}`} />
        </button>

        {isExpanded && (
          <div className="px-3 pb-3 space-y-3 animate-fade-in border-t border-dark-700 pt-3 mx-3 -mt-1">
            <p className="text-gray-300 text-xs whitespace-pre-line leading-relaxed">{cmd.description || 'No description available.'}</p>
            {cmd.example && (
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wider mb-1 block">Usage</span>
                <div className="flex items-center gap-2">
                  <div className="flex-1 p-2 bg-dark-900 rounded-lg font-mono text-xs text-green-400 overflow-x-auto">
                    {cmd.example.replace(/\{\}/g, BOT_CONFIG.prefix).replace(/\{prefix\}/g, BOT_CONFIG.prefix)}
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); onCopy(); }}
                    className="p-1.5 rounded-lg bg-dark-700 hover:bg-primary/20 transition-colors flex-shrink-0"
                    title="Copy command"
                  >
                    {isCopied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3 text-gray-400" />}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// Command Group Component - groups related commands together with tree structure
const CommandGroup = ({
  groupName,
  commands,
  expandedCommand,
  onToggle,
  onCopy,
  copiedCommand
}: {
  groupName: string;
  commands: [string, BotCommand][];
  expandedCommand: string | null;
  onToggle: (cmd: string) => void;
  onCopy: (cmd: string) => void;
  copiedCommand: string | null;
}) => {
  const mainCmd = commands.find(([name]) => name === groupName);
  const subCmds = commands.filter(([name]) => name !== groupName);

  const getPreviewDescription = (desc: string) => {
    if (!desc) return '';
    const firstLine = desc.split('\n')[0];
    return firstLine.length > 100 ? firstLine.slice(0, 100) + '...' : firstLine;
  };

  return (
    <div className="rounded-2xl bg-dark-900/30 overflow-hidden">
      {/* Main/Parent Command - Tree Root */}
      {mainCmd && (
        <div className={`border rounded-xl transition-all duration-200 ${
          expandedCommand === mainCmd[0] ? 'border-primary bg-primary/5' : 'border-dark-600 bg-dark-800/50 hover:border-dark-500'
        }`}>
          <button
            onClick={() => onToggle(mainCmd[0])}
            className="w-full flex items-start justify-between p-4 text-left gap-3"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <Command className="w-4 h-4 text-primary" />
                  <code className="text-primary font-semibold text-sm sm:text-base">{BOT_CONFIG.prefix}{mainCmd[0]}</code>
                </div>
                {mainCmd[1].aliases?.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    {mainCmd[1].aliases.slice(0, 2).map((alias, i) => (
                      <span key={i} className="px-1.5 py-0.5 bg-dark-700 text-gray-400 rounded text-xs font-mono">
                        {BOT_CONFIG.prefix}{alias}
                      </span>
                    ))}
                  </div>
                )}
                <span className="text-xs text-gray-500 bg-dark-700 px-2 py-0.5 rounded-full">
                  {subCmds.length} subcommand{subCmds.length !== 1 ? 's' : ''}
                </span>
              </div>
              <p className="text-gray-400 text-sm mt-1.5 leading-relaxed">
                {expandedCommand === mainCmd[0] ? '' : getPreviewDescription(mainCmd[1].description || 'No description available.')}
              </p>
            </div>
            <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 mt-1 ${expandedCommand === mainCmd[0] ? 'rotate-180' : ''}`} />
          </button>

          {expandedCommand === mainCmd[0] && (
            <div className="px-4 pb-4 space-y-4 animate-fade-in border-t border-dark-700 pt-4 mx-4 -mt-2">
              <p className="text-gray-300 text-sm whitespace-pre-line leading-relaxed">{mainCmd[1].description || 'No description available.'}</p>
              {mainCmd[1].example && (
                <div>
                  <span className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Usage</span>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 p-2.5 bg-dark-900 rounded-lg font-mono text-sm text-green-400 overflow-x-auto">
                      {mainCmd[1].example.replace(/\{\}/g, BOT_CONFIG.prefix).replace(/\{prefix\}/g, BOT_CONFIG.prefix)}
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); onCopy(mainCmd[0]); }}
                      className="p-2 rounded-lg bg-dark-700 hover:bg-primary/20 transition-colors flex-shrink-0"
                      title="Copy command"
                    >
                      {copiedCommand === mainCmd[0] ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-gray-400" />}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* Subcommands - Tree Branches */}
      {subCmds.length > 0 && (
        <div className="ml-4 mt-1 space-y-1">
          {subCmds.map(([cmdName, cmd], index) => (
            <TreeCommandItem
              key={cmdName}
              cmdName={cmdName}
              cmd={cmd}
              isExpanded={expandedCommand === cmdName}
              onToggle={() => onToggle(cmdName)}
              onCopy={() => onCopy(cmdName)}
              isCopied={copiedCommand === cmdName}
              isLast={index === subCmds.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const CommandsPage = () => {
  const [commands, setCommands] = useState<CommandsData>({});
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [expandedCommand, setExpandedCommand] = useState<string | null>(null);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null);
  const categoryRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});

  // Load commands
  useEffect(() => {
    fetch('/commands.json')
      .then(res => res.json())
      .then((data: CommandsData) => {
        setCommands(data);
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

  // Filtered commands based on search - returns commands per category
  const filteredCommandsByCategory = useMemo(() => {
    const result: { [category: string]: [string, BotCommand][] } = {};
    const query = searchQuery.toLowerCase().trim();
    
    for (const [category, catCommands] of Object.entries(commands)) {
      if (typeof catCommands !== 'object') continue;
      
      let categoryCommandsList = Object.entries(catCommands) as [string, BotCommand][];
      
      if (query) {
        categoryCommandsList = categoryCommandsList.filter(([name, cmd]) => 
          name.toLowerCase().includes(query) ||
          cmd.description?.toLowerCase().includes(query) ||
          cmd.aliases?.some(a => a.toLowerCase().includes(query))
        );
      }
      
      if (categoryCommandsList.length > 0) {
        result[category] = categoryCommandsList;
      }
    }
    
    return result;
  }, [commands, searchQuery]);

  // Toggle category expansion
  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  // Scroll to category
  const scrollToCategory = (category: string) => {
    setSelectedCategory(category);
    if (!expandedCategories.has(category)) {
      setExpandedCategories(prev => new Set([...prev, category]));
    }
    categoryRefs.current[category]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // Group commands by their prefix for a specific category
  const groupCommandsForCategory = (categoryCommands: [string, BotCommand][]) => {
    const groups: { [key: string]: [string, BotCommand][] } = {};
    const standalone: [string, BotCommand][] = [];

    const commandNames = categoryCommands.map(([name]) => name);
    const groupPrefixes = new Set<string>();
    
    commandNames.forEach(name => {
      const hasSubcommands = commandNames.some(other => 
        other !== name && other.startsWith(name + ' ')
      );
      if (hasSubcommands) {
        const isSubcommandOfAnother = [...groupPrefixes].some(prefix => 
          name.startsWith(prefix + ' ')
        );
        if (!isSubcommandOfAnother) {
          groupPrefixes.add(name);
        }
      }
    });

    categoryCommands.forEach(([name, cmd]) => {
      let belongsToGroup: string | null = null;
      
      for (const prefix of groupPrefixes) {
        if (name === prefix || name.startsWith(prefix + ' ')) {
          belongsToGroup = prefix;
          break;
        }
      }

      if (belongsToGroup) {
        if (!groups[belongsToGroup]) {
          groups[belongsToGroup] = [];
        }
        groups[belongsToGroup].push([name, cmd]);
      } else {
        standalone.push([name, cmd]);
      }
    });

    return { groups, standalone };
  };

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

        {/* Two-column layout: Sidebar + Commands */}
        <div className="flex gap-8">
          {/* Sticky Sidebar Navigation */}
          <div className="hidden lg:block w-64 flex-shrink-0">
            <div className="sticky top-24 space-y-2 max-h-[calc(100vh-8rem)] overflow-y-auto pr-2">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 px-3">Categories</div>
              {categories.map((cat) => {
                const Icon = cat.icon;
                const isActive = selectedCategory === cat.id;
                const commandCount = filteredCommandsByCategory[cat.id]?.length || 0;
                if (commandCount === 0 && searchQuery) return null;
                
                return (
                  <button
                    key={cat.id}
                    onClick={() => scrollToCategory(cat.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-left ${
                      isActive 
                        ? `bg-gradient-to-r ${cat.gradient} text-white shadow-lg` 
                        : 'text-gray-400 hover:text-white hover:bg-dark-800'
                    }`}
                  >
                    <Icon className="w-4 h-4 flex-shrink-0" />
                    <span className="text-sm font-medium flex-1 truncate">{cat.id}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      isActive ? 'bg-white/20' : 'bg-dark-700'
                    }`}>
                      {commandCount || cat.count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Main Content - Collapsible Categories */}
          <div className="flex-1 min-w-0 space-y-4">
            {Object.keys(filteredCommandsByCategory).length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <Search className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No commands found matching "{searchQuery}"</p>
              </div>
            ) : (
              Object.entries(filteredCommandsByCategory).map(([category, categoryCommands]) => {
                const catConfig = categoryConfig[category] || { icon: Command, gradient: 'from-gray-500 to-gray-600' };
                const Icon = catConfig.icon;
                const isExpanded = expandedCategories.has(category);
                const { groups, standalone } = groupCommandsForCategory(categoryCommands);
                
                return (
                  <div 
                    key={category} 
                    ref={(el) => { categoryRefs.current[category] = el; }}
                    className="border border-dark-600 rounded-2xl bg-dark-900/50 overflow-hidden scroll-mt-24"
                  >
                    {/* Category Header - Clickable to expand/collapse */}
                    <button
                      onClick={() => toggleCategory(category)}
                      className={`w-full flex items-center gap-3 px-5 py-4 text-left transition-all hover:bg-dark-800/50 ${
                        isExpanded ? 'border-b border-dark-600' : ''
                      }`}
                    >
                      <div className={`p-2 rounded-lg bg-gradient-to-br ${catConfig.gradient}`}>
                        <Icon className="w-5 h-5 text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-lg font-semibold text-white">{category}</h3>
                        <p className="text-sm text-gray-500">{categoryCommands.length} command{categoryCommands.length !== 1 ? 's' : ''}</p>
                      </div>
                      {isExpanded ? (
                        <ChevronDown className="w-5 h-5 text-gray-400" />
                      ) : (
                        <ChevronRight className="w-5 h-5 text-gray-400" />
                      )}
                    </button>
                    
                    {/* Commands inside category - only show when expanded */}
                    {isExpanded && (
                      <div className="p-4 space-y-3 animate-fade-in">
                        {/* Render grouped commands */}
                        {Object.entries(groups).map(([groupName, cmds]) => (
                          <CommandGroup
                            key={groupName}
                            groupName={groupName}
                            commands={cmds}
                            expandedCommand={expandedCommand}
                            onToggle={(cmd) => setExpandedCommand(expandedCommand === cmd ? null : cmd)}
                            onCopy={copyCommand}
                            copiedCommand={copiedCommand}
                          />
                        ))}
                        
                        {/* Render standalone commands */}
                        {standalone.map(([cmdName, cmd]) => (
                          <CommandItem
                            key={cmdName}
                            cmdName={cmdName}
                            cmd={cmd}
                            isExpanded={expandedCommand === cmdName}
                            onToggle={() => setExpandedCommand(expandedCommand === cmdName ? null : cmdName)}
                            onCopy={() => copyCommand(cmdName)}
                            isCopied={copiedCommand === cmdName}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CommandsPage;
