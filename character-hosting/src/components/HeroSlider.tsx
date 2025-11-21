import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface Slide {
  id: number;
  title: string;
  description: string;
  image: string;
  cta: string;
  ctaLink: string;
}

const HeroSlider = () => {
  const [currentSlide, setCurrentSlide] = useState(0);

  const slides: Slide[] = [
    {
      id: 1,
      title: 'Welcome to Anya Bot',
      description: 'Your ultimate Discord companion for anime character collection and fun!',
      image: '/avatar.png',
      cta: 'Get Started',
      ctaLink: '#features'
    },
    {
      id: 2,
      title: 'Collect Characters',
      description: 'Roll for your favorite anime characters and build your collection',
      image: '/bot_icon.png',
      cta: 'View Collection',
      ctaLink: '/dex'
    },
    {
      id: 3,
      title: 'Compete & Win',
      description: 'Climb the leaderboards and show off your collection',
      image: '/avatar.png',
      cta: 'View Leaderboard',
      ctaLink: '/leaderboard'
    }
  ];

  const nextSlide = () => {
    setCurrentSlide((prev) => (prev + 1) % slides.length);
  };

  const prevSlide = () => {
    setCurrentSlide((prev) => (prev - 1 + slides.length) % slides.length);
  };

  // Auto-advance slides
  useEffect(() => {
    const timer = setInterval(nextSlide, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="relative w-full h-[500px] md:h-[600px] overflow-hidden rounded-2xl">
      {/* Slides */}
      {slides.map((slide, index) => (
        <div
          key={slide.id}
          className={`absolute inset-0 transition-opacity duration-1000 ${
            index === currentSlide ? 'opacity-100' : 'opacity-0'
          }`}
        >
          {/* Background Image */}
          <div 
            className="absolute inset-0 bg-contain bg-right bg-no-repeat"
            style={{ backgroundImage: `url(${slide.image})` }}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-dark via-dark/95 to-dark/60" />
          </div>

          {/* Content */}
          <div className="relative h-full flex items-center">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
              <div className="max-w-2xl">
                <h1 className="text-4xl md:text-6xl font-display font-bold text-white mb-4 animate-slide-up">
                  {slide.title}
                </h1>
                <p className="text-lg md:text-xl text-gray-300 mb-8 animate-slide-up" style={{ animationDelay: '0.1s' }}>
                  {slide.description}
                </p>
                <a
                  href={slide.ctaLink}
                  className="inline-block px-8 py-4 bg-gradient-primary text-white font-bold rounded-lg hover:shadow-pink-glow transition-all duration-300 hover:-translate-y-1 animate-slide-up"
                  style={{ animationDelay: '0.2s' }}
                >
                  {slide.cta}
                </a>
              </div>
            </div>
          </div>
        </div>
      ))}

      {/* Navigation Arrows */}
      <button
        onClick={prevSlide}
        className="absolute left-4 top-1/2 -translate-y-1/2 p-2 bg-dark-800/80 hover:bg-dark-700 text-white rounded-full transition-all duration-200 backdrop-blur-sm z-10"
        aria-label="Previous slide"
      >
        <ChevronLeft className="w-6 h-6" />
      </button>
      <button
        onClick={nextSlide}
        className="absolute right-4 top-1/2 -translate-y-1/2 p-2 bg-dark-800/80 hover:bg-dark-700 text-white rounded-full transition-all duration-200 backdrop-blur-sm z-10"
        aria-label="Next slide"
      >
        <ChevronRight className="w-6 h-6" />
      </button>

      {/* Dots Indicator */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex gap-2 z-10">
        {slides.map((_, index) => (
          <button
            key={index}
            onClick={() => setCurrentSlide(index)}
            className={`w-2 h-2 rounded-full transition-all duration-300 ${
              index === currentSlide ? 'bg-primary w-8' : 'bg-white/50 hover:bg-white/75'
            }`}
            aria-label={`Go to slide ${index + 1}`}
          />
        ))}
      </div>
    </div>
  );
};

export default HeroSlider;
