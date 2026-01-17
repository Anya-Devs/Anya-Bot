import { Heart, MessageCircle, Github, Mail } from 'lucide-react';
import { BOT_CONFIG } from '../config/bot';

const OgPreviewContact = () => {
  return (
    <div className="w-[1200px] h-[630px] flex items-center justify-center bg-gradient-to-br from-[#16061f] via-[#020617] to-[#1b0b1f] text-white font-sans">
      <div className="absolute -top-20 right-0 w-[360px] h-[360px] bg-pink-500/30 rounded-full blur-3xl" />
      <div className="absolute bottom-[-120px] left-0 w-[380px] h-[380px] bg-violet-500/25 rounded-full blur-3xl" />

      <div className="relative max-w-4xl w-full px-16 z-10 flex gap-12 items-center">
        {/* Icon stack */}
        <div className="flex flex-col items-center gap-4">
          <div className="w-40 h-40 rounded-full bg-gradient-to-br from-pink-500 to-rose-400 flex items-center justify-center shadow-2xl shadow-pink-500/40">
            <Heart className="w-20 h-20 text-white" />
          </div>
          <p className="text-sm text-pink-100/90">Made with love by Senko</p>
        </div>

        {/* Text */}
        <div className="flex-1 space-y-4">
          <h1 className="text-5xl font-extrabold leading-tight">
            <span className="bg-gradient-to-r from-pink-300 to-rose-200 bg-clip-text text-transparent">
              Get in Touch
            </span>
          </h1>
          <p className="text-lg text-gray-200/90 leading-relaxed">
            Questions, ideas, or bug reports? The Anya Bot dev is just a ping away. Reach out and help shape the future of {BOT_CONFIG.name}.
          </p>

          <div className="grid grid-cols-2 gap-3 pt-2 text-sm">
            <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 flex items-center gap-3">
              <div className="p-2 rounded-lg bg-indigo-500/40">
                <MessageCircle className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="font-semibold text-sm">Discord Server</p>
                <p className="text-xs text-gray-200/80 truncate max-w-[220px]">{BOT_CONFIG.supportServer}</p>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 flex items-center gap-3">
              <div className="p-2 rounded-lg bg-gray-700/60">
                <Github className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="font-semibold text-sm">GitHub · Anya-Devs</p>
                <p className="text-xs text-gray-200/80">Open source & issues</p>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 flex items-center gap-3 col-span-2">
              <div className="p-2 rounded-lg bg-pink-500/40">
                <Mail className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="font-semibold text-sm">Email</p>
                <p className="text-xs text-gray-200/80">support@anya-bot.com</p>
              </div>
            </div>
          </div>

          <p className="pt-4 text-sm text-gray-400">anya-bot-1fe76.web.app/contact</p>
        </div>
      </div>
    </div>
  );
};

export default OgPreviewContact;
