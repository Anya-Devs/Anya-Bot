import { Terminal, Command } from 'lucide-react';
import { BOT_CONFIG } from '../config/bot';

const OgPreviewCommands = () => {
  return (
    <div className="w-[1200px] h-[630px] flex items-center justify-center bg-gradient-to-br from-[#050816] via-[#020617] to-[#020617] text-white font-sans">
      <div className="absolute -top-24 -right-10 w-[380px] h-[380px] bg-purple-500/30 rounded-full blur-3xl" />
      <div className="absolute -bottom-24 -left-10 w-[320px] h-[320px] bg-pink-500/25 rounded-full blur-3xl" />

      <div className="relative max-w-4xl w-full flex gap-12 items-center px-16 z-10">
        {/* Icon column */}
        <div className="flex flex-col items-center gap-6">
          <div className="w-40 h-40 rounded-3xl bg-gradient-to-br from-pink-500 to-purple-500 flex items-center justify-center shadow-2xl shadow-pink-500/40">
            <Terminal className="w-20 h-20 text-white" />
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-300">
            <Command className="w-4 h-4 text-pink-300" />
            <span>{BOT_CONFIG.prefix}help · Command Center</span>
          </div>
        </div>

        {/* Text column */}
        <div className="flex-1 space-y-4">
          <h1 className="text-5xl font-extrabold leading-tight">
            <span className="bg-gradient-to-r from-pink-400 to-purple-300 bg-clip-text text-transparent">
              Command Library
            </span>
          </h1>
          <p className="text-lg text-gray-200/90 leading-relaxed">
            Browse every action, utility, and Pokétwo helper Anya Bot offers – with clean
            categories, search, and copy-paste-ready examples.
          </p>

          <div className="grid grid-cols-2 gap-3 text-sm text-gray-200/90 pt-2">
            <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3">
              <p className="text-xs text-gray-400 mb-1">Examples</p>
              <p className="font-mono text-sm">{BOT_CONFIG.prefix}hug @friend</p>
              <p className="font-mono text-sm">{BOT_CONFIG.prefix}anime spy x family</p>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3">
              <p className="text-xs text-gray-400 mb-1">Pokémon & Pokétwo</p>
              <p className="font-mono text-sm">{BOT_CONFIG.prefix}pokedex vulpix</p>
              <p className="font-mono text-sm">{BOT_CONFIG.prefix}pt sh alolan vulpix</p>
            </div>
          </div>

          <p className="pt-4 text-sm text-gray-400">anya-bot-1fe76.web.app/commands</p>
        </div>
      </div>
    </div>
  );
};

export default OgPreviewCommands;
