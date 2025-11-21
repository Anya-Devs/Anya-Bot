// =========================
// Bot Configuration
// =========================
export const botConfig = {
  botName: "Anya Bot",
  botId: "1234247716243112100",
  description: "Collect your favorite anime, manga, and game characters!",
  inviteLink: "https://discord.com/oauth2/authorize?client_id=1234247716243112100&scope=bot&permissions=8",
  supportServer: "https://discord.gg/5Sc82qwSxd",
  redirectUri: "http://127.0.0.1:5500/auth/callback"
};

// =========================
// Firebase Configuration
// =========================
window.FIREBASE_CONFIG = {
  apiKey: "YOUR_API_KEY",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};

// =========================
// Site Configuration
// =========================
export class AppConfig {
  constructor() {
    this.siteTitle = botConfig.botName;
    this.navLinks = [
      { name: "Home", id: "home" },
      { name: "Character Dex", id: "dex" },
      { name: "Leaderboard", id: "leaderboard" },
      { name: "Commands", id: "commands" }
    ];
    this.hero = {
      title: "Character Collection Hub",
      subtitle: "Discover, collect, and showcase your favorite anime, manga, video game, and cartoon characters through our gacha system!",
      inviteText: "Invite Bot",
      tagline: "🎴 Gotta catch 'em all!"
    };
    this.features = [
      {
        icon: "🎴",
        title: "Character Gacha",
        description: "Roll for your favorite characters from anime, manga, games, and cartoons with unique rarities!"
      },
      {
        icon: "📚",
        title: "Character Dex",
        description: "Browse our extensive database of characters with detailed information, images, and tags."
      },
      {
        icon: "🏆",
        title: "Leaderboard",
        description: "Compete with other collectors and climb the ranks to become the ultimate character collector!"
      },
      {
        icon: "🔍",
        title: "Advanced Search",
        description: "Filter characters by series, tags, rarity, and more to find exactly what you're looking for."
      },
      {
        icon: "🎨",
        title: "Multiple Images",
        description: "Each character features up to 100 unique, high-quality images hosted on our platform."
      },
      {
        icon: "⭐",
        title: "Rarity System",
        description: "Characters are categorized by rarity: Common, Rare, Super Rare, and Ultra Rare!"
      }
    ];
    this.footer = "© 2025 Anya Bot. All rights reserved.";
  }
}

// =========================
// Rarity Configuration
// =========================
export const RARITY_CONFIG = {
  'C': { 
    name: 'Common', 
    color: '#9CA3AF', 
    weight: 50,
    emoji: '⚪'
  },
  'R': { 
    name: 'Rare', 
    color: '#3B82F6', 
    weight: 30,
    emoji: '🔵'
  },
  'SR': { 
    name: 'Super Rare', 
    color: '#A855F7', 
    weight: 15,
    emoji: '🟣'
  },
  'SSR': { 
    name: 'Ultra Rare', 
    color: '#F59E0B', 
    weight: 5,
    emoji: '🟡'
  }
};

export default AppConfig;
