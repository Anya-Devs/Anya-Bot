import { Hash, Users, Pin, Search, Inbox, HelpCircle } from 'lucide-react';
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
    <div className={`bg-[#36393f] rounded-2xl overflow-hidden shadow-2xl border-2 border-light-200 ${className}`}>
      {/* Channel Header */}
      <div className="bg-[#36393f] border-b border-[#202225] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Hash className="w-5 h-5 text-gray-400" />
          <span className="font-semibold text-white">{channelName}</span>
          <div className="h-4 w-px bg-gray-600 mx-2" />
          <span className="text-sm text-gray-400">Bot command showcase</span>
        </div>
        <div className="flex items-center gap-4">
          <Users className="w-5 h-5 text-gray-400 hover:text-gray-300 cursor-pointer" />
          <Pin className="w-5 h-5 text-gray-400 hover:text-gray-300 cursor-pointer" />
          <Search className="w-5 h-5 text-gray-400 hover:text-gray-300 cursor-pointer" />
          <Inbox className="w-5 h-5 text-gray-400 hover:text-gray-300 cursor-pointer" />
          <HelpCircle className="w-5 h-5 text-gray-400 hover:text-gray-300 cursor-pointer" />
        </div>
      </div>

      {/* Channel Content */}
      <div className={`bg-[#36393f] ${flexibleHeight ? '' : 'min-h-[400px] max-h-[600px] overflow-y-auto'}`}>
        {children}
      </div>

      {/* Message Input (Disabled) */}
      <div className="bg-[#36393f] border-t border-[#202225] p-4">
        <div className="bg-[#40444b] rounded-lg px-4 py-3 text-gray-500 cursor-not-allowed">
          Message #{channelName}
        </div>
      </div>
    </div>
  );
};

export default DiscordChannel;
