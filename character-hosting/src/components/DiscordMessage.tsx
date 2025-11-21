import { Bot } from 'lucide-react';
import { ReactNode } from 'react';
import { DiscordText } from '../utils/discordFormatter';

interface DiscordMessageProps {
  username?: string;
  avatar?: string | ReactNode;
  content?: string;
  embed?: {
    title?: string;
    description?: string;
    color?: string;
    image?: string;
    thumbnail?: string;
    fields?: { name: string; value: string; inline?: boolean }[];
    footer?: string;
  };
  components?: { 
    buttons?: { label: string; style?: 'primary' | 'secondary' | 'success' | 'danger' | 'link'; url?: string }[] 
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
    <div className="flex gap-4 p-4 hover:bg-dark-700/30 transition-colors group">
      {/* Avatar */}
      <div className="flex-shrink-0">
        <div className="w-10 h-10 rounded-full overflow-hidden bg-dark-600">
          {avatar ? (
            typeof avatar === 'string' ? (
              <img src={avatar} alt={username} className="w-full h-full object-cover" />
            ) : (
              avatar
            )
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-primary text-white font-bold">
              {username[0]}
            </div>
          )}
        </div>
      </div>

      {/* Message Content */}
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 mb-1">
          <span className="font-semibold text-white hover:underline cursor-pointer">
            {username}
          </span>
          {isBot && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 bg-[#5865F2] text-white text-xs font-semibold rounded">
              <Bot className="w-3 h-3" />
              BOT
            </span>
          )}
          <span className="text-xs text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity">
            {timestamp}
          </span>
        </div>

        {/* Text Content */}
        {content && (
          <div className="text-gray-300 text-sm leading-relaxed mb-2">
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

        {/* Embed */}
        {embed && (
          <div 
            className="mt-2 max-w-xl border-l-4 rounded bg-dark-700/50 overflow-hidden"
            style={{ borderColor: embed.color || '#FF6B9D' }}
          >
            <div className="p-4">
              {/* Embed Title */}
              {embed.title && (
                <div className="font-semibold text-white mb-2 text-base">
                  {embed.title}
                </div>
              )}

              {/* Embed Description */}
              {embed.description && (
                <div className="text-gray-300 text-sm mb-3 leading-relaxed whitespace-pre-line">
                  <DiscordText>{embed.description}</DiscordText>
                </div>
              )}

              {/* Embed Fields */}
              {embed.fields && embed.fields.length > 0 && (
                <div className={`grid gap-2 ${embed.fields.some(f => f.inline) ? 'grid-cols-2' : 'grid-cols-1'}`}>
                  {embed.fields.map((field, idx) => (
                    <div key={idx} className={field.inline ? '' : 'col-span-full'}>
                      <div className="font-semibold text-white text-xs mb-1">
                        <DiscordText>{field.name}</DiscordText>
                      </div>
                      <div className="text-gray-300 text-xs whitespace-pre-line">
                        <DiscordText>{field.value}</DiscordText>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Embed Image */}
              {embed.image && (
                <div className="mt-3">
                  <img 
                    src={embed.image} 
                    alt="Embed" 
                    className="rounded max-h-80 object-contain cursor-pointer hover:opacity-90 transition-opacity"
                  />
                </div>
              )}

              {/* Embed Thumbnail */}
              {embed.thumbnail && !embed.image && (
                <div className="float-right ml-4 mb-2">
                  <img 
                    src={embed.thumbnail} 
                    alt="Thumbnail" 
                    className="rounded w-20 h-20 object-cover"
                  />
                </div>
              )}

              {/* Embed Footer */}
              {embed.footer && (
                <div className="text-xs text-gray-500 mt-3 pt-2 border-t border-dark-600">
                  {embed.footer}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Discord Components (Buttons) */}
        {components?.buttons && components.buttons.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {components.buttons.map((button, idx) => {
              const styleClasses = {
                primary: 'bg-[#5865F2] hover:bg-[#4752C4] text-white',
                secondary: 'bg-[#6D6F78] hover:bg-[#5B5D66] text-white',
                success: 'bg-[#57F287] hover:bg-[#4ACB7B] text-black',
                danger: 'bg-[#ED4245] hover:bg-[#C03537] text-white',
                link: 'bg-transparent hover:bg-dark-600 text-[#00AFF4] hover:underline'
              };

              return (
                <button
                  key={idx}
                  className={`px-4 py-2 text-sm font-medium rounded transition-colors ${
                    styleClasses[button.style || 'secondary']
                  } ${button.url ? 'cursor-pointer' : 'cursor-default'}`}
                  onClick={() => button.url && window.open(button.url, '_blank')}
                >
                  {button.label}
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
