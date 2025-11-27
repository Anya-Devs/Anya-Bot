import { Hash, Users, Search, Inbox, HelpCircle } from 'lucide-react';
import { ReactNode } from 'react';

interface DiscordChannelProps {
  channelName?: string;
  children: ReactNode;
  showSidebar?: boolean;
  className?: string;
  flexibleHeight?: boolean;
}

const DiscordChannel = ({ 
  channelName = 'bot-commands', 
  children,
  className = '',
  flexibleHeight = false
}: DiscordChannelProps) => {
  return (
    <div className={`bg-[#313338] rounded-lg overflow-hidden shadow-2xl ${className}`}>
      {/* Channel Header */}
      <div className="bg-[#313338] border-b border-[#3f4147] h-12 px-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Hash className="w-5 h-5 text-[#80848e]" />
          <span className="font-semibold text-[#f2f3f5]">{channelName}</span>
          <div className="h-6 w-px bg-[#3f4147] mx-3" />
          <span className="text-sm text-[#949ba4]">Bot command showcase</span>
        </div>
        <div className="flex items-center gap-4">
          <Hash className="w-5 h-5 text-[#b5bac1] hover:text-[#dbdee1] cursor-pointer transition-colors" />
          <Users className="w-5 h-5 text-[#b5bac1] hover:text-[#dbdee1] cursor-pointer transition-colors" />
          <Search className="w-5 h-5 text-[#b5bac1] hover:text-[#dbdee1] cursor-pointer transition-colors" />
          <Inbox className="w-5 h-5 text-[#b5bac1] hover:text-[#dbdee1] cursor-pointer transition-colors" />
          <HelpCircle className="w-5 h-5 text-[#b5bac1] hover:text-[#dbdee1] cursor-pointer transition-colors" />
        </div>
      </div>

      {/* Channel Content */}
      <div className={`bg-[#313338] ${flexibleHeight ? '' : 'min-h-[400px] max-h-[600px] overflow-y-auto'}`}>
        {children}
      </div>

      {/* Message Input (Disabled) */}
      <div className="bg-[#313338] px-4 pb-6 pt-1">
        <div className="bg-[#383a40] rounded-lg px-4 py-[11px] text-[#6d6f78] flex items-center gap-4">
          <span className="text-base">Message #{channelName}</span>
        </div>
      </div>
    </div>
  );
};

export default DiscordChannel;
