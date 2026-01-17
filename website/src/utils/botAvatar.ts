import { BOT_CONFIG } from '../config/bot';

let cachedAvatarUrl: string | null = null;

/**
 * Fetches the bot's avatar from Discord API
 * Falls back to local avatar if API fails
 */
export async function getBotAvatar(): Promise<string> {
  // Return cached URL if available
  if (cachedAvatarUrl) {
    return cachedAvatarUrl;
  }

  try {
    const response = await fetch(`https://discord.com/api/v10/applications/${BOT_CONFIG.id}/rpc`);
    
    if (response.ok) {
      const botData = await response.json();
      
      if (botData && botData.icon) {
        const url = `https://cdn.discordapp.com/app-icons/${BOT_CONFIG.id}/${botData.icon}.png?size=256`;
        cachedAvatarUrl = url;
        return url;
      }
    }
  } catch (err) {
    console.warn('[Bot Avatar] Failed to fetch from Discord API:', err);
  }

  // Fallback to local avatar
  return '/avatar.png';
}

/**
 * Hook to get bot avatar URL with fallback
 */
export function useBotAvatar(): string {
  return '/avatar.png'; // Default for SSR/initial render
}
