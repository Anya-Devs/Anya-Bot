export const BOT_CONFIG = {
  name: 'Anya Bot',
  id: '1234247716243112100',
  description: 'Your ultimate Discord companion for character collection, fun commands, and community engagement!',
  inviteLink: 'https://discord.com/oauth2/authorize?client_id=1234247716243112100&scope=bot&permissions=8',
  supportServer: 'https://discord.gg/5Sc82qwSxd',
  version: '2.0.0',
  prefix: '.',
  features: [
    {
      icon: '🎴',
      title: 'Character Gacha',
      description: 'Collect your favorite anime, manga, and game characters with our advanced gacha system!',
    },
    {
      icon: '🎮',
      title: 'Fun Commands',
      description: 'Enjoy a variety of entertaining commands to engage with your community.',
    },
    {
      icon: '🤖',
      title: 'AI Integration',
      description: 'Chat with Anya using advanced AI for natural conversations.',
    },
    {
      icon: '🏆',
      title: 'Leaderboards',
      description: 'Compete with others and climb the ranks in various categories.',
    },
    {
      icon: '⚙️',
      title: 'Customizable',
      description: 'Configure the bot to fit your server\'s unique needs.',
    },
    {
      icon: '🎨',
      title: 'Rich Embeds',
      description: 'Beautiful, informative embeds for all bot responses.',
    },
  ],
  // Stats are fetched dynamically from botStatsService
  // No static stats defined here
};

export const FIREBASE_CONFIG = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
};

export const RARITY_CONFIG = {
  C: { name: 'Common', color: '#9CA3AF', weight: 50, emoji: '⚪' },
  R: { name: 'Rare', color: '#3B82F6', weight: 30, emoji: '🔵' },
  SR: { name: 'Super Rare', color: '#A855F7', weight: 15, emoji: '🟣' },
  SSR: { name: 'Ultra Rare', color: '#FFD700', weight: 5, emoji: '🟡' },
};
