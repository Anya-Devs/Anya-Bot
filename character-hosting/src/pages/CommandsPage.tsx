import { Terminal } from 'lucide-react';
import RealCommandShowcase from '../components/RealCommandShowcase';

const CommandsPage = () => {
  return (
    <div className="pt-24 pb-20 min-h-screen bg-dark">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-12 animate-slide-up">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-primary rounded-2xl mb-4 shadow-lg">
            <Terminal className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl md:text-5xl font-display font-bold text-gradient mb-4">
            🎮 Bot Commands
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto font-medium">
            Explore all available commands and see them in action
          </p>
        </div>

        {/* Commands */}
        <RealCommandShowcase />
      </div>
    </div>
  );
};

export default CommandsPage;
