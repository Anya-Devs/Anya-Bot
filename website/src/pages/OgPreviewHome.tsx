import BotAvatar from '../components/BotAvatar';
import { BOT_CONFIG } from '../config/bot';
import { Sparkles, Users, Server, FileText } from 'lucide-react';

const OgPreviewHome = () => {
  return (
    <div
      className="w-[1200px] h-[630px] flex items-center justify-center bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f0f23] text-white font-sans"
    >
      <div className="absolute -top-24 -right-24 w-[400px] h-[400px] bg-pink-400/30 rounded-full blur-3xl" />
      <div className="absolute -bottom-24 -left-24 w-[320px] h-[320px] bg-purple-500/20 rounded-full blur-3xl" />

      <div className="relative flex items-center gap-16 z-10 px-16">
        {/* Avatar */}
        <div className="relative">
          <div className="absolute inset-0 bg-gradient-to-br from-pink-400/50 to-purple-400/40 rounded-full blur-3xl" />
          <div className="relative w-56 h-56 rounded-full border-4 border-pink-400/60 shadow-[0_0_80px_rgba(255,107,157,0.6)] overflow-hidden bg-[#0f0f23]">
            <BotAvatar className="w-full h-full object-cover" size={512} />
          </div>
        </div>

        {/* Content */}
        <div className="max-w-xl space-y-4">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-pink-500/15 border border-pink-400/40 text-sm">
            <Sparkles className="w-4 h-4 text-pink-300" />
            <span className="text-pink-200 font-medium">{BOT_CONFIG.name} · Cozy Discord Companion</span>
          </div>

          <h1 className="text-5xl font-extrabold leading-tight">
            <span className="text-white">Welcome home to</span>
            <br />
            <span className="bg-gradient-to-r from-pink-400 to-purple-300 bg-clip-text text-transparent">
              {BOT_CONFIG.name}
            </span>
          </h1>

          <p className="text-lg text-gray-200/90 leading-relaxed">
            Fun actions, anime lookups, Pokémon helpers, and cozy tools that make your Discord server feel like home.
          </p>

          <div className="flex gap-4 pt-2 text-sm text-gray-200/90">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-pink-300" />
              <span>Trusted in many servers</span>
            </div>
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-pink-300" />
              <span>Made for tight-knit communities</span>
            </div>
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-pink-300" />
              <span>100+ commands</span>
            </div>
          </div>

          <p className="pt-4 text-sm text-gray-400">anya-bot-1fe76.web.app</p>
        </div>
      </div>
    </div>
  );
};

export default OgPreviewHome;
