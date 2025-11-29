import { Sparkles, Rocket, Clock } from 'lucide-react';

const OgPreviewUpdates = () => {
  return (
    <div className="w-[1200px] h-[630px] flex items-center justify-center bg-gradient-to-br from-[#0b1020] via-[#020617] to-[#1e1030] text-white font-sans">
      <div className="absolute -top-24 left-10 w-[320px] h-[320px] bg-purple-500/35 rounded-full blur-3xl" />
      <div className="absolute bottom-[-120px] right-0 w-[420px] h-[420px] bg-pink-500/25 rounded-full blur-3xl" />

      <div className="relative max-w-4xl w-full px-16 z-10 space-y-6">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-purple-500/20 border border-purple-400/40 text-sm">
          <Sparkles className="w-4 h-4 text-purple-200" />
          <span className="text-purple-100 font-medium">Anya Bot · Update Log</span>
        </div>

        <h1 className="text-5xl font-extrabold leading-tight">
          <span className="bg-gradient-to-r from-purple-300 to-pink-200 bg-clip-text text-transparent">
            What's New?
          </span>
        </h1>

        <p className="text-lg text-gray-200/90 max-w-2xl">
          Follow the latest features, improvements, and upcoming magic for Anya Bot.
        </p>

        <div className="grid grid-cols-3 gap-4 pt-4 text-sm">
          <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <Rocket className="w-4 h-4 text-emerald-300" />
              <span className="text-xs text-emerald-200/90">New Feature</span>
            </div>
            <p className="font-semibold text-sm">Pokémon Detection v2</p>
            <p className="text-xs text-gray-300 mt-1">Higher accuracy spawn alerts and shiny highlights.</p>
          </div>

          <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-4 h-4 text-pink-300" />
              <span className="text-xs text-pink-200/90">Cozy Actions</span>
            </div>
            <p className="font-semibold text-sm">50+ new GIF actions</p>
            <p className="text-xs text-gray-300 mt-1">Hugs, pats, cuddles, and more ways to say "waku waku".</p>
          </div>

          <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3">
            <div className="flex items-center gap-2 mb-1">
              <Clock className="w-4 h-4 text-yellow-300" />
              <span className="text-xs text-yellow-200/90">Coming Soon</span>
            </div>
            <p className="font-semibold text-sm">Quest System</p>
            <p className="text-xs text-gray-300 mt-1">Server-wide adventures and collaborative goals.</p>
          </div>
        </div>

        <p className="pt-4 text-sm text-gray-400">anya-bot-1fe76.web.app/updates</p>
      </div>
    </div>
  );
};

export default OgPreviewUpdates;
