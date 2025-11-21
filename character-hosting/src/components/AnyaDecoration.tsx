/**
 * Anya Forger themed decorative elements
 */

interface AnyaDecorationProps {
  variant?: 'peanuts' | 'stars' | 'sparkles' | 'hearts';
  className?: string;
}

const AnyaDecoration = ({ variant = 'sparkles', className = '' }: AnyaDecorationProps) => {
  const decorations = {
    peanuts: (
      <div className={`absolute pointer-events-none ${className}`}>
        <div className="text-4xl opacity-20 animate-bounce">🥜</div>
      </div>
    ),
    stars: (
      <div className={`absolute pointer-events-none ${className}`}>
        <div className="text-3xl opacity-30 animate-pulse">⭐</div>
      </div>
    ),
    sparkles: (
      <div className={`absolute pointer-events-none ${className}`}>
        <div className="text-2xl opacity-40 animate-pulse">✨</div>
      </div>
    ),
    hearts: (
      <div className={`absolute pointer-events-none ${className}`}>
        <div className="text-3xl opacity-25 animate-pulse">💖</div>
      </div>
    ),
  };

  return decorations[variant];
};

export default AnyaDecoration;
