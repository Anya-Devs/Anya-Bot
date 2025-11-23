import { useState, useEffect } from 'react';
import { getBotAvatar } from '../utils/botAvatar';

interface BotAvatarProps {
  className?: string;
  alt?: string;
  size?: number;
}

/**
 * Component that fetches and displays the bot's avatar from Discord API
 * Falls back to local avatar if API fails
 */
const BotAvatar = ({ className = '', alt = 'Anya Bot', size }: BotAvatarProps) => {
  const [avatarUrl, setAvatarUrl] = useState('/avatar.png');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    getBotAvatar().then(url => {
      if (mounted) {
        setAvatarUrl(url);
        setIsLoading(false);
      }
    });

    return () => {
      mounted = false;
    };
  }, []);

  const sizeParam = size ? `?size=${size}` : '';
  const finalUrl = avatarUrl.includes('cdn.discordapp.com') 
    ? avatarUrl.replace(/\?size=\d+/, '') + sizeParam
    : avatarUrl;

  return (
    <img 
      src={finalUrl}
      alt={alt}
      className={`${className} ${isLoading ? 'opacity-75' : 'opacity-100'} transition-opacity`}
      loading="lazy"
    />
  );
};

export default BotAvatar;
