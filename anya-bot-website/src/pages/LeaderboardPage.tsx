import { Trophy } from 'lucide-react';

const LeaderboardPage = () => {
  return (
    <div className="pt-24 pb-20 min-h-screen bg-dark">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-12 animate-slide-up">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-primary rounded-2xl mb-4 shadow-lg">
            <Trophy className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl md:text-5xl font-display font-bold text-gradient mb-4">
            🏆 Leaderboard
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto font-medium">
            See who's leading the character collection race
          </p>
        </div>

        {/* Coming Soon */}
        <div className="card p-12 text-center">
          <div className="text-6xl mb-4">🏆</div>
          <h2 className="text-2xl font-bold text-white mb-2">Coming Soon!</h2>
          <p className="text-gray-400">
            The leaderboard will be available once we have enough collectors!
          </p>
        </div>
      </div>
    </div>
  );
};

export default LeaderboardPage;
