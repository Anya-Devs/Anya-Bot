# Anya Bot Website - Development Roadmap

## How to Update
- **Updates/Changelog**: Edit `public/updates.json` - the website reads this file automatically
- **Commands**: Edit `public/commands.json` - parsed and displayed on Commands page
- **Feature Sections**: Edit `anyaStory` array in `src/pages/HomePage.tsx`

---

## Current Status

### Working Features
- [x] Homepage with feature sections
- [x] Discord embed previews (DiscordMessage, DiscordPreviewCard)
- [x] Bot stats display (servers, users, commands)
- [x] Commands page with search/filter
- [x] Updates/Changelog page
- [x] Dashboard with live stats
- [x] Anime search showcase (Jikan API)
- [x] Pokemon showcase (PokeAPI)
- [x] Action commands showcase
- [x] Discord markdown formatter (bold, italic, code, spoilers, blockquotes)

### Needs Work

#### High Priority
- [ ] **Leaderboard Page** (`src/pages/LeaderboardPage.tsx`)
  - Currently shows "Coming Soon" placeholder
  - Needs: Backend API for leaderboard data, user rankings display

- [ ] **Dashboard Activity Chart** (`src/pages/DashboardPage.tsx` line 176)
  - Shows "Activity chart coming soon..."
  - Needs: Chart library integration, historical data API

- [ ] **CharacterDex Page** (`src/pages/CharacterDexPage.tsx`)
  - Has placeholder content
  - Needs: Character collection display, gacha system UI

#### Medium Priority
- [ ] **Quest System** (HomePage line 338-367)
  - Displayed as "Coming Soon" on homepage
  - Needs: Quest UI, progress tracking, rewards display

- [ ] **Economy System** (mentioned in DeveloperNotes)
  - Virtual currency, shops, trading
  - Needs: Full implementation

- [ ] **Custom Profiles** (mentioned in DeveloperNotes)
  - Personalized user profiles with stats
  - Status: In Development

- [ ] **Music Player** (mentioned in DeveloperNotes)
  - High-quality music streaming
  - Status: Planned

#### Low Priority / Polish
- [ ] **OG Image Generation** (`functions/src/index.ts`)
  - Has satori setup but may need testing
  - Used for social media previews

- [ ] **Mobile Responsiveness**
  - Review all pages on mobile devices
  - Some layouts may need adjustment

---

## File Structure Quick Reference

```
src/
├── pages/
│   ├── HomePage.tsx          # Main landing page with feature sections
│   ├── CommandsPage.tsx      # Commands list with search
│   ├── UpdatesPage.tsx       # Changelog (reads from /updates.json)
│   ├── DashboardPage.tsx     # Live bot stats
│   ├── LeaderboardPage.tsx   # [NEEDS WORK] Placeholder
│   └── CharacterDexPage.tsx  # [NEEDS WORK] Character collection
├── components/
│   ├── DiscordMessage.tsx    # Discord message embed renderer
│   ├── DiscordPreviewCard.tsx # Discord preview for showcases
│   ├── SlidingFeatures.tsx   # Interactive demo carousel
│   └── DeveloperNotes.tsx    # Feature status display
├── services/
│   ├── botStatsService.ts    # Fetches Discord API stats
│   └── discordAPI.ts         # Discord API utilities
├── config/
│   └── embedTemplates.ts     # Sample embed data
└── utils/
    └── discordFormatter.tsx  # Discord markdown parser

public/
├── updates.json              # [EDIT THIS] Changelog data
├── commands.json             # [EDIT THIS] Bot commands list
└── data/                     # Static data files
```

---

## Adding New Updates

Edit `public/updates.json`:

```json
{
  "version": "2.6.0",
  "date": "Dec 2024",
  "title": "🎉 Your Update Title",
  "description": "Description of what changed",
  "type": "feature",  // feature | improvement | fix | upcoming
  "highlights": ["Point 1", "Point 2", "Point 3"]
}
```

Types:
- `feature` - New feature (green badge)
- `improvement` - Enhancement (blue badge)
- `fix` - Bug fix (orange badge)
- `upcoming` - Coming soon (purple badge)

---

## Adding New Commands

Edit `public/commands.json` to add commands. The website parses this automatically.

---

## Bot Cogs Reference

From the Discord bot (`bot/cogs/`):

### Engagement Commands
- `poll` - Multi-option polls
- `quickpoll` - Yes/no polls
- `giveaway` - Timed giveaways
- `announce` - Announcements
- `remind` - Reminders
- `suggest` - Suggestions

### Utility Commands
- `serverinfo`, `userinfo`, `avatar`, `roleinfo`
- `membercount`, `emojis`, `ping`, `invite`

### Social Commands
- `8ball`, `ship`, `compliment`, `roast`
- `coinflip`, `dice`, `choose`, `rate`

### Pokemon Commands
- `.pt cl` - Collection management
- `.pt sh` - Shiny hunt tracking
- `.pt tp` - Type ping settings
- `.pt qp` - Quest ping settings
- `.pt config` - Server configuration
