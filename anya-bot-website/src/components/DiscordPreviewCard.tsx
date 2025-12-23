import { User, Image as ImageIcon } from 'lucide-react';
import { useEffect, useState } from 'react';
import BotAvatar from './BotAvatar';
import { DiscordText } from '../utils/discordFormatter';

interface DiscordPreviewCardProps {
  title?: string;
  description?: string;
  command?: string;
  embedColor?: string;
  fields?: { name: string; value: string; inline?: boolean }[];
  image?: string;
  thumbnail?: string;
  footer?: string;
  footerIcon?: string;
  hasGif?: boolean;
  gifUrl?: string;
  progress?: number; // 0-100 for visual progress bar
  userAvatar?: string; // Custom user avatar URL
  userName?: string; // Custom user name
  className?: string;
}

/**
 * Pixel-perfect Discord embed preview
 * Matches actual Discord embed appearance exactly
 */
// Preload images to reduce loading delays
const preloadImage = (src: string): Promise<boolean> => {
  return new Promise((resolve) => {
    if (!src) {
      resolve(false);
      return;
    }
    
    // Convert local paths to absolute URLs if needed
    const isLocalPath = src.startsWith('/') && !src.startsWith('http');
    const finalSrc = isLocalPath ? `${window.location.origin}${src}` : src;
    
    const img = new Image();
    img.src = finalSrc;
    
    // Set a timeout to prevent hanging
    const timeout = setTimeout(() => {
      img.onload = null;
      img.onerror = null;
      resolve(false);
    }, 10000); // 10 second timeout
    
    img.onload = () => {
      clearTimeout(timeout);
      resolve(true);
    };
    
    img.onerror = () => {
      clearTimeout(timeout);
      console.warn(`Failed to load image: ${src}`);
      resolve(false);
    };
  });
};

const DiscordPreviewCard = ({
  title,
  description,
  command,
  embedColor = '#FF6B9D',
  fields = [],
  image,
  thumbnail,
  footer,
  footerIcon,
  hasGif = false,
  gifUrl,
  progress,
  userAvatar,
  userName = 'User',
  className = ''
}: DiscordPreviewCardProps) => {
  const [isImageLoaded, setIsImageLoaded] = useState(false);
  const [isThumbnailLoaded, setIsThumbnailLoaded] = useState(false);
  const [isGifLoaded, setIsGifLoaded] = useState(false);
  const [gifDataUrl, setGifDataUrl] = useState<string | null>(null);
  const [imageDataUrl, setImageDataUrl] = useState<string | null>(null);

  useEffect(() => {
    // Reset load states when URLs change
    setIsImageLoaded(false);
    setIsThumbnailLoaded(false);
    setIsGifLoaded(false);
    setGifDataUrl(null);
    setImageDataUrl(null);

    // Preload and cache images for instant display
    const preloadAndCache = async () => {
      try {
        // Preload and cache GIF if it exists
        if (gifUrl) {
          const response = await fetch(gifUrl);
          const blob = await response.blob();
          const reader = new FileReader();
          reader.onload = () => {
            setGifDataUrl(reader.result as string);
            setIsGifLoaded(true);
          };
          reader.readAsDataURL(blob);
        }

        // Preload and cache static image if it exists
        if (image) {
          const finalImageUrl = image.startsWith('/') ? `${window.location.origin}${image}` : image;
          const response = await fetch(finalImageUrl);
          const blob = await response.blob();
          const reader = new FileReader();
          reader.onload = () => {
            setImageDataUrl(reader.result as string);
            setIsImageLoaded(true);
          };
          reader.readAsDataURL(blob);
        }

        // Preload thumbnail if it exists
        if (thumbnail) {
          await preloadImage(thumbnail);
          setIsThumbnailLoaded(true);
        }
      } catch (error) {
        console.error('Error preloading images:', error);
        // Fallback to direct URLs if caching fails
        if (gifUrl) setIsGifLoaded(true);
        if (image) setIsImageLoaded(true);
        if (thumbnail) setIsThumbnailLoaded(true);
      }
    };

    preloadAndCache();
  }, [image, thumbnail, gifUrl]);
  return (
    <div className={`bg-[#313338] rounded-lg overflow-hidden shadow-2xl ${className}`}>
      {/* Channel bar */}
      <div className="bg-[#2b2d31] px-4 py-2 flex items-center gap-2 border-b border-[#1e1f22]">
        <span className="text-[#80848e] text-lg">#</span>
        <span className="text-[#f2f3f5] text-sm font-medium">bot-commands</span>
      </div>

      {/* Messages */}
      <div className="p-4 bg-[#313338]">
        {/* User message */}
        {command && (
          <div className="flex gap-4 mb-4 hover:bg-[#2e3035] -mx-4 px-4 py-0.5">
            {userAvatar ? (
              <img 
                src={userAvatar} 
                alt="" 
                className="w-10 h-10 rounded-full object-cover flex-shrink-0"
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary via-pink-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                <User className="w-6 h-6 text-white drop-shadow-lg" />
              </div>
            )}
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-[#f2f3f5] font-medium text-sm hover:underline cursor-pointer">{userName}</span>
                <span className="text-[#949ba4] text-xs">Today at 4:20 PM</span>
              </div>
              <div className="text-[#dbdee1] text-[15px] leading-[1.375rem]">{command}</div>
            </div>
          </div>
        )}

        {/* Bot message with embed */}
        <div className="flex gap-4 hover:bg-[#2e3035] -mx-4 px-4 py-0.5">
          <div className="w-10 h-10 rounded-full overflow-hidden flex-shrink-0">
            <BotAvatar className="w-full h-full object-cover" size={40} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <span className="text-[#f2f3f5] font-medium text-sm hover:underline cursor-pointer">Anya Bot</span>
              <span className="bg-[#5865f2] text-white text-[10px] font-medium px-[5px] py-[1px] rounded">BOT</span>
              <span className="text-[#949ba4] text-xs">Today at 4:20 PM</span>
            </div>

            {/* Embed container */}
            <div 
              className="mt-1 rounded overflow-hidden max-w-[520px] grid"
              style={{ 
                borderLeft: `4px solid ${embedColor}`,
                backgroundColor: '#2b2d31'
              }}
            >
              <div className="p-4 overflow-hidden">
                <div className="flex gap-4">
                  <div className="flex-1 min-w-0">
                    {/* Title */}
                    {title && (
                      <div className="text-white font-semibold text-base mb-1">
                        <DiscordText>{title}</DiscordText>
                      </div>
                    )}
                    
                    {/* Description */}
                    {description && (
                      <div className="text-[#dbdee1] text-sm leading-[1.375rem] whitespace-pre-line mb-2">
                        <DiscordText>{description}</DiscordText>
                      </div>
                    )}

                    {/* Fields */}
                    {fields.length > 0 && (
                      <div className="grid gap-2 mt-2" style={{ gridTemplateColumns: fields.some(f => f.inline !== false) ? 'repeat(auto-fill, minmax(150px, 1fr))' : '1fr' }}>
                        {fields.map((field, i) => (
                          <div key={i} className={field.inline === false ? 'col-span-full' : ''} style={{ minWidth: 0 }}>
                            <div className="text-white font-semibold text-[0.875rem] leading-[1.125rem] mb-0.5">
                              <DiscordText>{field.name}</DiscordText>
                            </div>
                            <div className="text-[#dbdee1] text-sm leading-[1.125rem] whitespace-pre-line break-words">
                              <DiscordText>{field.value}</DiscordText>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Thumbnail */}
                  {thumbnail && (
                    <div className="flex-shrink-0">
                      <img 
                        src={thumbnail} 
                        alt="" 
                        className="w-20 h-20 rounded object-cover"
                      />
                    </div>
                  )}
                </div>

                {/* GIF/Image with loading state */}
                {(hasGif && gifUrl) && (
                  <div className="mt-3 relative bg-[#2b2d31] rounded overflow-hidden min-h-[100px]">
                    {gifDataUrl ? (
                      <img 
                        src={gifDataUrl}
                        alt="" 
                        className="max-w-full max-h-[300px] object-contain mx-auto"
                        style={{ opacity: isGifLoaded ? 1 : 0, transition: 'opacity 100ms ease-in' }}
                        onLoad={() => setIsGifLoaded(true)}
                        loading="eager"
                      />
                    ) : (
                      <img 
                        src={gifUrl}
                        alt="" 
                        className="max-w-full max-h-[300px] object-contain mx-auto"
                        style={{ opacity: isGifLoaded ? 1 : 0, transition: 'opacity 100ms ease-in' }}
                        onLoad={() => setIsGifLoaded(true)}
                        onError={() => {
                          console.error('Failed to load GIF:', gifUrl);
                          setIsGifLoaded(false);
                        }}
                        loading="eager"
                      />
                    )}
                    {!isGifLoaded && !isImageLoaded && (
                      <div className="absolute inset-0 flex items-center justify-center bg-[#2b2d31]">
                        <div className="flex flex-col items-center">
                          <ImageIcon className="w-8 h-8 text-[#4e5058] animate-pulse" />
                          <span className="text-xs text-[#949ba4] mt-2">Loading GIF...</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Large image - shows if no GIF or if GIF failed to load */}
                {image && (isImageLoaded || !hasGif || !gifUrl) && (
                  <div className="mt-3 relative bg-[#2b2d31] rounded overflow-hidden min-h-[100px]">
                    {imageDataUrl ? (
                      <img 
                        src={imageDataUrl}
                        alt="" 
                        className="max-w-full max-h-[300px] object-contain mx-auto"
                        style={{ opacity: isImageLoaded ? 1 : 0, transition: 'opacity 100ms ease-in' }}
                      />
                    ) : (
                      <img 
                        src={image.startsWith('/') ? `${window.location.origin}${image}` : image}
                        alt="" 
                        className="max-w-full max-h-[300px] object-contain mx-auto"
                        style={{ opacity: isImageLoaded ? 1 : 0, transition: 'opacity 100ms ease-in' }}
                        onLoad={() => setIsImageLoaded(true)}
                        onError={() => {
                          console.error('Failed to load image:', image);
                          setIsImageLoaded(false);
                        }}
                        loading="eager"
                      />
                    )}
                    {!isImageLoaded && (
                      <div className="absolute inset-0 flex items-center justify-center bg-[#2b2d31]">
                        <div className="flex flex-col items-center">
                          <ImageIcon className="w-8 h-8 text-[#4e5058] animate-pulse" />
                          <span className="text-xs text-[#949ba4] mt-2">Loading image...</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Visual Progress Bar */}
                {progress !== undefined && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[#dbdee1] text-xs font-medium">Progress</span>
                      <span className="text-[#dbdee1] text-xs">{progress}%</span>
                    </div>
                    <div className="w-full h-2 bg-[#1e1f22] rounded-full overflow-hidden">
                      <div 
                        className="h-full rounded-full transition-all duration-300"
                        style={{ 
                          width: `${progress}%`,
                          backgroundColor: embedColor
                        }}
                      />
                    </div>
                  </div>
                )}

                {/* Footer */}
                {footer && (
                  <div className="flex items-center gap-2 mt-3 text-xs text-[#dbdee1]">
                    {footerIcon && (
                      <img src={footerIcon} alt="" className="w-5 h-5 rounded-full" />
                    )}
                    <span>{footer}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DiscordPreviewCard;
