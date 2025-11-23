import { useEffect } from 'react';
import { getBotAvatar } from '../utils/botAvatar';

/**
 * Hook to dynamically set the favicon to the bot's Discord avatar
 */
export function useBotFavicon() {
  useEffect(() => {
    getBotAvatar().then(avatarUrl => {
      const favicon = document.querySelector<HTMLLinkElement>("link[rel*='icon']") || document.createElement("link");
      favicon.rel = "icon";
      favicon.type = "image/png";
      favicon.href = avatarUrl;

      if (!document.querySelector("link[rel*='icon']")) {
        document.head.appendChild(favicon);
      }
    });
  }, []);
}
