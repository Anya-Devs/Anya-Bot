import BotAvatar from './BotAvatar';

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
  className?: string;
}

/**
 * Pixel-perfect Discord embed preview
 * Matches actual Discord embed appearance exactly
 */
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
  className = ''
}: DiscordPreviewCardProps) => {
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
            <div className="w-10 h-10 rounded-full bg-[#5865f2] flex items-center justify-center text-white font-medium text-sm flex-shrink-0">
              U
            </div>
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-[#f2f3f5] font-medium text-sm hover:underline cursor-pointer">User</span>
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
                      <div className="text-white font-semibold text-base mb-1">{title}</div>
                    )}
                    
                    {/* Description */}
                    {description && (
                      <div className="text-[#dbdee1] text-sm leading-[1.125rem] whitespace-pre-wrap mb-2">
                        {description}
                      </div>
                    )}

                    {/* Fields */}
                    {fields.length > 0 && (
                      <div className="grid gap-2 mt-2" style={{ gridTemplateColumns: fields.some(f => f.inline !== false) ? 'repeat(3, 1fr)' : '1fr' }}>
                        {fields.map((field, i) => (
                          <div key={i} className={field.inline === false ? 'col-span-full' : ''}>
                            <div className="text-[#dbdee1] font-semibold text-xs mb-0.5">{field.name}</div>
                            <div className="text-[#dbdee1] text-sm whitespace-pre-wrap">{field.value}</div>
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

                {/* GIF/Image */}
                {hasGif && gifUrl && (
                  <img 
                    src={gifUrl} 
                    alt="" 
                    className="mt-3 rounded max-w-full max-h-[300px] object-contain"
                  />
                )}

                {/* Large image */}
                {image && (
                  <img 
                    src={image} 
                    alt="" 
                    className="mt-3 rounded max-w-full max-h-[300px] object-contain"
                  />
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
