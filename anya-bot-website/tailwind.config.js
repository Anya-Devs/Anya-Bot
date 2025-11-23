/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary pink/magenta for accents
        primary: {
          DEFAULT: '#FF6B9D',
          dark: '#E5568A',
          light: '#FFB3D1',
        },
        secondary: {
          DEFAULT: '#C060A1',
          dark: '#A04D87',
          light: '#D98FBF',
        },
        // Accent colors
        accent: {
          blue: '#4A9EFF',
          purple: '#9D4EDD',
          cyan: '#06FFA5',
        },
        // Dark theme colors
        dark: {
          DEFAULT: '#0A0A0F',
          900: '#0D0D12',
          800: '#12121A',
          700: '#1A1A24',
          600: '#22222E',
          500: '#2A2A38',
        },
        // Gray scale for text
        gray: {
          300: '#D1D5DB',
          400: '#9CA3AF',
          500: '#6B7280',
          600: '#4B5563',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Poppins', 'system-ui', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in',
        'slide-up': 'slideUp 0.5s ease-out',
        'slide-down': 'slideDown 0.5s ease-out',
        'scale-in': 'scaleIn 0.3s ease-out',
        'glow': 'glow 2s ease-in-out infinite',
        'slide-in-left': 'slideInLeft 0.6s ease-out',
        'slide-in-right': 'slideInRight 0.6s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
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
          '0%': { transform: 'translateX(-30px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        slideInRight: {
          '0%': { transform: 'translateX(30px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
      },
      boxShadow: {
        'pink-glow': '0 0 30px rgba(255, 107, 157, 0.5)',
        'purple-glow': '0 0 30px rgba(192, 96, 161, 0.5)',
        'sharp': '0 2px 8px rgba(0, 0, 0, 0.8)',
      },
    },
  },
  plugins: [],
}
