import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar.tsx';
import Footer from './components/Footer.tsx';
import HomePage from './pages/HomePage.tsx';
import CommandsPage from './pages/CommandsPage.tsx';
import CharacterDexPage from './pages/CharacterDexPage.tsx';
import LeaderboardPage from './pages/LeaderboardPage.tsx';
import { useBotFavicon } from './hooks/useBotFavicon.ts';

function App() {
  // Dynamically set favicon from Discord API
  useBotFavicon();

  return (
    <div className="min-h-screen flex flex-col bg-dark">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/commands" element={<CommandsPage />} />
          <Route path="/dex" element={<CharacterDexPage />} />
          <Route path="/leaderboard" element={<LeaderboardPage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

export default App;
