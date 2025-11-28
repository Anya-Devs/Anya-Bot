/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary pink/magenta - Anya's warmth
        primary: {
          DEFAULT: '#FF6B9D',
          dark: '#E5568A',
          light: '#FFB3D1',
          50: '#FFF5F9',
          100: '#FFE5EF',
          200: '#FFCCE0',
          300: '#FFB3D1',
          400: '#FF8AB7',
          500: '#FF6B9D',
          600: '#FF4283',
          700: '#E5568A',
          800: '#CC3D6F',
          900: '#B32454',
        },
        secondary: {
          DEFAULT: '#C060A1',
          dark: '#A04D87',
          light: '#D98FBF',
          50: '#F9F0F6',
          100: '#F3E1ED',
          200: '#E7C3DB',
          300: '#D98FBF',
          400: '#CC75AD',
          500: '#C060A1',
          600: '#A04D87',
          700: '#8A4274',
          800: '#733761',
          900: '#5C2C4E',
        },
        // SPY x FAMILY Theme Colors
        spy: {
          burgundy: '#8B1538',      // Yor's elegant danger
          wine: '#722F37',          // Deep sophistication
          rose: '#C41E3A',          // Thorn Princess
          blush: '#FFB6C1',         // Soft innocence
          gold: '#D4AF37',          // Elegance & warmth
          champagne: '#F7E7CE',     // Mission briefings
          navy: '#1a1b2e',          // Loid's calculated cool
          midnight: '#0f1019',      // Deep secrets
          cream: '#FFFDD0',         // Classified docs
          ivory: '#FFFFF0',         // Paper texture
        },
        // Accent colors
        accent: {
          blue: '#4A9EFF',
          purple: '#9D4EDD',
          cyan: '#06FFA5',
          gold: '#D4AF37',
          orange: '#FF8C42',
          green: '#00D9A3',
          rose: '#C41E3A',
        },
        // Dark theme colors - Richer blacks with subtle color tints
        dark: {
          DEFAULT: '#0A0A0F',
          950: '#05050A',
          900: '#0D0D12',
          800: '#12121A',
          750: '#16161F',
          700: '#1A1A24',
          650: '#1E1E2A',
          600: '#22222E',
          550: '#262633',
          500: '#2A2A38',
        },
        // Gray scale for text - Better contrast
        gray: {
          50: '#F9FAFB',
          100: '#F3F4F6',
          200: '#E5E7EB',
          300: '#D1D5DB',
          400: '#9CA3AF',
          500: '#6B7280',
          600: '#4B5563',
          700: '#374151',
          800: '#1F2937',
          900: '#111827',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Poppins', 'system-ui', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.6s ease-out',
        'fade-in-up': 'fadeInUp 0.6s ease-out',
        'fade-in-down': 'fadeInDown 0.6s ease-out',
        'slide-up': 'slideUp 0.6s ease-out',
        'slide-down': 'slideDown 0.6s ease-out',
        'scale-in': 'scaleIn 0.5s ease-out',
        'glow': 'glow 2s ease-in-out infinite',
        'slide-in-left': 'slideInLeft 0.7s ease-out',
        'slide-in-right': 'slideInRight 0.7s ease-out',
        'bounce-in': 'bounceIn 0.8s ease-out',
        'zoom-in': 'zoomIn 0.5s ease-out',
        'wiggle': 'wiggle 1s ease-in-out infinite',
        'bounce-slow': 'bounceSlow 2s ease-in-out infinite',
        'float': 'float 3s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'pulse-gold': 'pulseGold 2s ease-in-out infinite',
        'rose-bloom': 'roseBloom 0.8s ease-out',
        'classified-stamp': 'classifiedStamp 0.5s ease-out',
        'typewriter': 'typewriter 2s steps(20) forwards',
        'blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(30px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeInDown: {
          '0%': { opacity: '0', transform: 'translateY(-30px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.9)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        glow: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(255, 107, 157, 0.5)' },
          '50%': { boxShadow: '0 0 40px rgba(255, 107, 157, 0.8)' },
        },
        slideInLeft: {
          '0%': { transform: 'translateX(-40px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        slideInRight: {
          '0%': { transform: 'translateX(40px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        bounceIn: {
          '0%': { transform: 'scale(0.3)', opacity: '0' },
          '50%': { transform: 'scale(1.05)' },
          '70%': { transform: 'scale(0.9)' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        zoomIn: {
          '0%': { transform: 'scale(0.8)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        wiggle: {
          '0%, 100%': { transform: 'rotate(-3deg)' },
          '50%': { transform: 'rotate(3deg)' },
        },
        bounceSlow: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0) rotate(0deg)' },
          '33%': { transform: 'translateY(-5px) rotate(1deg)' },
          '66%': { transform: 'translateY(-3px) rotate(-1deg)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        pulseGold: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(212, 175, 55, 0.3)' },
          '50%': { boxShadow: '0 0 40px rgba(212, 175, 55, 0.6)' },
        },
        roseBloom: {
          '0%': { transform: 'scale(0) rotate(-180deg)', opacity: '0' },
          '100%': { transform: 'scale(1) rotate(0deg)', opacity: '1' },
        },
        classifiedStamp: {
          '0%': { transform: 'scale(2) rotate(-15deg)', opacity: '0' },
          '50%': { transform: 'scale(1.1) rotate(-5deg)', opacity: '1' },
          '100%': { transform: 'scale(1) rotate(-3deg)', opacity: '1' },
        },
        typewriter: {
          '0%': { width: '0' },
          '100%': { width: '100%' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
      boxShadow: {
        'pink-glow': '0 0 30px rgba(255, 107, 157, 0.5)',
        'purple-glow': '0 0 30px rgba(192, 96, 161, 0.5)',
        'sharp': '0 2px 8px rgba(0, 0, 0, 0.8)',
        'gold-glow': '0 0 30px rgba(212, 175, 55, 0.4)',
        'rose-glow': '0 0 25px rgba(196, 30, 58, 0.3)',
        'elegant': '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
        'dossier': '0 4px 20px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
      },
      backgroundImage: {
        'spy-gradient': 'linear-gradient(135deg, #0f1019 0%, #1a1b2e 50%, #722F37 100%)',
        'gold-shimmer': 'linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.3), transparent)',
        'rose-fade': 'linear-gradient(180deg, rgba(196, 30, 58, 0.1) 0%, transparent 100%)',
        'paper-texture': 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.65\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\' opacity=\'0.05\'/%3E%3C/svg%3E")',
      },
    },
  },
  plugins: [],
}
