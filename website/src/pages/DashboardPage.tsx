import { useState, useEffect } from 'react';
import { Activity, Server, Users, Command, RefreshCw, Radio } from 'lucide-react';
import { fetchBotStats, getCachedStatus } from '../services/botStatsService';

const DashboardPage = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'commands' | 'status'>('overview');
  const [stats, setStats] = useState({
    servers: 'Loading...',
    users: 'Loading...',
    commands: 'Loading...'
  });
  const [botStatus, setBotStatus] = useState<'online' | 'offline' | 'idle' | 'unknown'>('unknown');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [commands, setCommands] = useState<Record<string, any>>({});

  // Fetch stats
  const refreshStats = async () => {
    setIsRefreshing(true);
    try {
      const newStats = await fetchBotStats();
      
      setStats({
        servers: String(newStats.servers),
        users: String(newStats.users),
        commands: String(newStats.commands)
      });
      
      // Get status from the fetched stats
      setBotStatus(newStats.status || getCachedStatus());
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Failed to refresh stats:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Load commands from local file
  const loadCommands = async () => {
    try {
      const response = await fetch('/commands.json');
      if (response.ok) {
        const data = await response.json();
        setCommands(data);
      }
    } catch (error) {
      console.error('Failed to load commands:', error);
    }
  };

  useEffect(() => {
    refreshStats();
    loadCommands();
    
    // Auto-refresh every 2 minutes
    const interval = setInterval(refreshStats, 2 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'commands', label: 'Commands', icon: Command },
    { id: 'status', label: 'Live Status', icon: Radio },
  ];

  const statCards = [
    { label: 'Servers', value: stats.servers, icon: Server, color: 'from-blue-500 to-cyan-500' },
    { label: 'Users', value: stats.users, icon: Users, color: 'from-purple-500 to-pink-500' },
    { label: 'Commands', value: stats.commands, icon: Command, color: 'from-green-500 to-emerald-500' },
  ];

  return (
    <div className="pt-24 pb-20 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-4xl md:text-5xl font-display font-bold text-white mb-2">
                Dashboard
              </h1>
              <p className="text-gray-400">Real-time bot statistics and monitoring</p>
            </div>
            <button
              onClick={refreshStats}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-4 py-2 bg-primary/10 hover:bg-primary/20 border border-primary/30 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              <span className="text-sm font-medium">Refresh</span>
            </button>
          </div>

          {/* Bot Status Indicator */}
          <div className="flex items-center gap-3 p-4 bg-dark-800 rounded-lg border border-dark-600">
            {botStatus === 'online' ? (
              <>
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-green-500 font-semibold">Online</span>
              </>
            ) : botStatus === 'idle' ? (
              <>
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <span className="text-yellow-500 font-semibold">Idle</span>
              </>
            ) : botStatus === 'offline' ? (
              <>
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <span className="text-red-500 font-semibold">Offline</span>
              </>
            ) : (
              <>
                <div className="w-3 h-3 bg-gray-500 rounded-full"></div>
                <span className="text-gray-400 font-semibold">Unknown</span>
              </>
            )}
            <span className="text-gray-500 text-sm ml-auto">
              Last updated: {lastUpdate.toLocaleTimeString()}
            </span>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b border-dark-600">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-6 py-3 font-medium transition-all ${
                  activeTab === tab.id
                    ? 'text-primary border-b-2 border-primary'
                    : 'text-gray-400 hover:text-gray-300'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6 animate-fade-in">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {statCards.map((stat, idx) => {
                const Icon = stat.icon;
                return (
                  <div
                    key={idx}
                    className="group card-hover p-6 relative overflow-hidden"
                  >
                    <div className={`absolute inset-0 bg-gradient-to-br ${stat.color} opacity-0 group-hover:opacity-10 transition-opacity duration-300`}></div>
                    <div className="relative z-10">
                      <div className="flex items-center justify-between mb-4">
                        <div className={`p-3 rounded-lg bg-gradient-to-br ${stat.color} text-white`}>
                          <Icon className="w-6 h-6" />
                        </div>
                      </div>
                      <div className="text-3xl font-bold text-gradient mb-1">{stat.value}</div>
                      <div className="text-sm text-gray-400">{stat.label}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Activity Chart Placeholder */}
            <div className="card p-6">
              <h3 className="text-xl font-bold text-white mb-4">Activity Overview</h3>
              <div className="h-64 flex items-center justify-center bg-dark-700 rounded-lg border border-dark-600">
                <p className="text-gray-500">Activity chart coming soon...</p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'commands' && (
          <div className="space-y-4 animate-fade-in">
            <div className="card p-6">
              <h3 className="text-xl font-bold text-white mb-4">
                Available Commands ({Object.keys(commands).length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(commands).map(([name, data]: [string, any]) => (
                  <div
                    key={name}
                    className="p-4 bg-dark-700 rounded-lg border border-dark-600 hover:border-primary/30 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <code className="text-primary font-mono text-sm">{name}</code>
                      {data.category && (
                        <span className="px-2 py-1 bg-primary/20 text-primary text-xs rounded-full">
                          {data.category}
                        </span>
                      )}
                    </div>
                    {data.description && (
                      <p className="text-gray-400 text-sm">{data.description}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'status' && (
          <div className="space-y-6 animate-fade-in">
            <div className="card p-6">
              <h3 className="text-xl font-bold text-white mb-4">System Status</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-dark-700 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                    <span className="text-white font-medium">Discord API</span>
                  </div>
                  <span className="text-green-500 text-sm">Connected</span>
                </div>
                <div className="flex items-center justify-between p-4 bg-dark-700 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                    <span className="text-white font-medium">Command Handler</span>
                  </div>
                  <span className="text-green-500 text-sm">Operational</span>
                </div>
                <div className="flex items-center justify-between p-4 bg-dark-700 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                    <span className="text-white font-medium">Database</span>
                  </div>
                  <span className="text-green-500 text-sm">Connected</span>
                </div>
              </div>
            </div>

            {/* Environment Status */}
            <div className="card p-6">
              <h3 className="text-xl font-bold text-white mb-4">Configuration</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 bg-dark-700 rounded-lg">
                  <span className="text-gray-300">Discord Token</span>
                  <span className={`text-sm ${import.meta.env.VITE_DISCORD_BOT_TOKEN ? 'text-green-500' : 'text-red-500'}`}>
                    {import.meta.env.VITE_DISCORD_BOT_TOKEN ? '✓ Configured' : '✗ Missing'}
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 bg-dark-700 rounded-lg">
                  <span className="text-gray-300">Commands Loaded</span>
                  <span className="text-green-500 text-sm">✓ {Object.keys(commands).length} commands</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardPage;
