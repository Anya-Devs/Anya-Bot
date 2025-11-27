import { Bot, ExternalLink, User } from 'lucide-react';
import { ReactNode } from 'react';
import { DiscordText } from '../utils/discordFormatter';

interface EmbedAuthor {
  name: string;
  icon_url?: string;
  url?: string;
}

interface EmbedFooter {
  text: string;
  icon_url?: string;
}

interface EmbedField {
  name: string;
  value: string;
  inline?: boolean;
}

interface Embed {
  author?: EmbedAuthor;
  title?: string;
  url?: string;
  description?: string;
  color?: string;
  image?: string;
  thumbnail?: string;
  fields?: EmbedField[];
  footer?: EmbedFooter | string;
  timestamp?: string;
}

interface DiscordMessageProps {
  username?: string;
  avatar?: string | ReactNode;
  content?: string;
  embed?: Embed;
  components?: { 
    buttons?: { label: string; style?: 'primary' | 'secondary' | 'success' | 'danger' | 'link'; url?: string; emoji?: string }[] 
  };
  isBot?: boolean;
  timestamp?: string;
  image?: string;
}

const DiscordMessage = ({ 
  username = 'Anya Bot', 
  avatar, 
  content, 
  embed, 
  components,
  isBot = true,
  timestamp = 'Today at 12:00 PM',
  image
}: DiscordMessageProps) => {
  
  return (
    <div className="flex gap-4 py-[0.125rem] px-4 mt-[1.0625rem] hover:bg-[#2e3035] transition-colors group relative">
      {/* Avatar */}
      <div className="flex-shrink-0 mt-[2px]">
        <div className={`w-10 h-10 rounded-full overflow-hidden ${!avatar ? (isBot ? 'bg-[#5865F2]' : 'bg-gradient-to-br from-primary via-pink-500 to-purple-600') : ''}`}>
          {avatar ? (
            typeof avatar === 'string' ? (
              <img src={avatar} alt={username} className="w-full h-full object-cover" />
            ) : (
              avatar
            )
          ) : isBot ? (
            <div className="w-full h-full flex items-center justify-center text-white font-semibold text-lg">
              {username[0]}
            </div>
          ) : (
            /* Styled user icon with website colors */
            <div className="w-full h-full flex items-center justify-center">
              <User className="w-6 h-6 text-white drop-shadow-lg" />
            </div>
          )}
        </div>
      </div>

      {/* Message Content */}
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-baseline gap-2">
          <span className="font-medium text-[#f2f3f5] hover:underline cursor-pointer leading-[1.375rem]">
            {username}
          </span>
          {isBot && (
            <span className="inline-flex items-center gap-0.5 px-[0.275rem] py-0 bg-[#5865F2] text-white text-[0.625rem] font-medium rounded-[3px] uppercase h-[0.9375rem] leading-[0.9375rem]">
              <Bot className="w-[10px] h-[10px]" />
              <span className="ml-[1px]">Bot</span>
            </span>
          )}
          <span className="text-xs text-[#949ba4] ml-1">
            {timestamp}
          </span>
        </div>

        {/* Text Content */}
        {content && (
          <div className="text-[#dbdee1] text-base leading-[1.375rem]">
            <DiscordText>{content}</DiscordText>
          </div>
        )}

        {/* Standalone Image */}
        {image && !embed && (
          <div className="mt-2 max-w-lg">
            <img 
              src={image} 
              alt="Message attachment" 
              className="rounded-lg max-h-96 object-contain cursor-pointer hover:opacity-90 transition-opacity"
            />
          </div>
        )}

        {/* Embed - Modern Discord Style */}
        {embed && (
          <div 
            className="mt-2 max-w-[520px] rounded-[4px] overflow-hidden grid"
            style={{ 
              borderLeft: `4px solid ${embed.color || '#5865F2'}`,
              backgroundColor: '#2b2d31'
            }}
          >
            <div className="p-4 overflow-hidden">
              {/* Content wrapper with thumbnail */}
              <div className="flex">
                {/* Main content */}
                <div className="flex-1 min-w-0">
                  {/* Author */}
                  {embed.author && (
                    <div className="flex items-center gap-2 mb-2">
                      {embed.author.icon_url && (
                        <img 
                          src={embed.author.icon_url} 
                          alt="" 
                          className="w-6 h-6 rounded-full"
                        />
                      )}
                      {embed.author.url ? (
                        <a 
                          href={embed.author.url}
                          className="text-sm font-medium text-white hover:underline"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {embed.author.name}
                        </a>
                      ) : (
                        <span className="text-sm font-medium text-white">
                          {embed.author.name}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Title */}
                  {embed.title && (
                    <div className="mb-2">
                      {embed.url ? (
                        <a 
                          href={embed.url}
                          className="font-semibold text-[#00a8fc] hover:underline text-base leading-snug"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {embed.title}
                        </a>
                      ) : (
                        <div className="font-semibold text-white text-base leading-snug">
                          {embed.title}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Description */}
                  {embed.description && (
                    <div className="text-[#dbdee1] text-sm leading-[1.375rem] whitespace-pre-line mb-2">
                      <DiscordText>{embed.description}</DiscordText>
                    </div>
                  )}

                  {/* Fields */}
                  {embed.fields && embed.fields.length > 0 && (
                    <div className="grid gap-2 mt-2" style={{ 
                      gridTemplateColumns: embed.fields.some(f => f.inline) 
                        ? 'repeat(auto-fill, minmax(150px, 1fr))' 
                        : '1fr' 
                    }}>
                      {embed.fields.map((field, idx) => (
                        <div 
                          key={idx} 
                          className={field.inline ? '' : 'col-span-full'}
                          style={{ minWidth: 0 }}
                        >
                          <div className="font-semibold text-white text-[0.875rem] leading-[1.125rem] mb-0.5">
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
                {embed.thumbnail && (
                  <div className="ml-4 flex-shrink-0">
                    <img 
                      src={embed.thumbnail} 
                      alt="" 
                      className="rounded-[3px] max-w-[80px] max-h-[80px] object-cover cursor-pointer"
                    />
                  </div>
                )}
              </div>

              {/* Image - Full width */}
              {embed.image && (
                <div className="mt-4">
                  <img 
                    src={embed.image} 
                    alt="" 
                    className="rounded-[4px] max-w-full max-h-[300px] object-contain cursor-pointer hover:opacity-95 transition-opacity"
                  />
                </div>
              )}

              {/* Footer */}
              {(embed.footer || embed.timestamp) && (
                <div className="flex items-center gap-2 mt-2 text-xs text-[#949ba4] leading-4">
                  {typeof embed.footer === 'object' && embed.footer.icon_url && (
                    <img 
                      src={embed.footer.icon_url} 
                      alt="" 
                      className="w-5 h-5 rounded-full flex-shrink-0"
                    />
                  )}
                  <span className="whitespace-pre-wrap leading-5">
                    {typeof embed.footer === 'string' 
                      ? embed.footer 
                      : embed.footer?.text}
                  </span>
                  {embed.footer && embed.timestamp && (
                    <span className="mx-1">•</span>
                  )}
                  {embed.timestamp && (
                    <span>{embed.timestamp}</span>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Discord Components (Buttons) */}
        {components?.buttons && components.buttons.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {components.buttons.map((button, idx) => {
              const styleClasses = {
                primary: 'bg-[#5865F2] hover:bg-[#4752C4] text-white',
                secondary: 'bg-[#4e5058] hover:bg-[#6d6f78] text-white',
                success: 'bg-[#248046] hover:bg-[#1a6334] text-white',
                danger: 'bg-[#da373c] hover:bg-[#a12d31] text-white',
                link: 'bg-[#4e5058] hover:bg-[#6d6f78] text-white'
              };

              return (
                <button
                  key={idx}
                  className={`inline-flex items-center justify-center gap-2 px-4 py-[2px] h-8 text-sm font-medium rounded-[3px] transition-colors ${
                    styleClasses[button.style || 'secondary']
                  } ${button.url ? 'cursor-pointer' : 'cursor-default'}`}
                  onClick={() => button.url && window.open(button.url, '_blank')}
                >
                  {button.emoji && <span>{button.emoji}</span>}
                  <span>{button.label}</span>
                  {button.style === 'link' && (
                    <ExternalLink className="w-4 h-4 ml-1 opacity-80" />
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default DiscordMessage;
