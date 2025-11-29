import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar.tsx';
import Footer from './components/Footer.tsx';
import HomePage from './pages/HomePage.tsx';
import CommandsPage from './pages/CommandsPage.tsx';
import UpdatesPage from './pages/UpdatesPage.tsx';
import ContactPage from './pages/ContactPage.tsx';
import OgPreviewHome from './pages/OgPreviewHome.tsx';
import OgPreviewCommands from './pages/OgPreviewCommands.tsx';
import OgPreviewUpdates from './pages/OgPreviewUpdates.tsx';
import OgPreviewContact from './pages/OgPreviewContact.tsx';
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
          <Route path="/updates" element={<UpdatesPage />} />
          <Route path="/contact" element={<ContactPage />} />
          {/* OG preview-only routes for generating social images */}
          <Route path="/og-preview/home" element={<OgPreviewHome />} />
          <Route path="/og-preview/commands" element={<OgPreviewCommands />} />
          <Route path="/og-preview/updates" element={<OgPreviewUpdates />} />
          <Route path="/og-preview/contact" element={<OgPreviewContact />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

export default App;
