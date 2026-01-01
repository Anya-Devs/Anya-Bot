# 🎨 Cover Art System Documentation

## Overview

The Cover Art System is a dynamic character cover art marketplace that allows users to purchase and collect high-quality cover art variants for anime characters. The system integrates with multiple art providers (Wallhaven, Safebooru, etc.) to source cover images and implements a rarity-based pricing system.

## Features

### ✨ Core Features
- **Dynamic Character Lookup**: Characters are queried from MongoDB using normalized keys (lowercase, spaces → underscores)
- **Cover Art Shop**: Paginated interface showing available cover art from multiple providers
- **Purchase System**: Confirmation-based purchasing with rarity-scaled pricing
- **Variant Selection**: Users can cycle through owned cover art variants
- **Inventory Management**: Persistent storage of purchased covers per user/character

### 🎯 Key Components
- **Art Aggregation**: Leverages existing `art.py` system for sourcing images
- **MongoDB Integration**: Character data, user inventories, and balances
- **Discord UI**: Interactive buttons and paginated embeds
- **Pricing System**: Extremely expensive pricing based on character rarity

## Commands

### `.draw view <character_id>`
View a character with selectable cover art variants.

**Examples:**
```
.draw view anya_forger
.draw view naruto_uzumaki
.draw view zero_two
```

**Features:**
- Shows character information and current cover art
- Navigate between owned cover variants with ◀️/▶️ buttons
- Access Cover Art Shop with 🛒 button

### `.balance`
Check your current coin balance.

### `.addcoins <user> <amount>` (Admin Only)
Add coins to a user's balance.

## Database Schema

### Characters Collection
```json
{
  "_id": "anya_forger",  // Normalized key (lowercase, spaces → underscores)
  "name": "Anya Forger",
  "series": "Spy x Family",
  "description": "Character description...",
  "rarity": "SSR",  // C, R, SR, SSR
  "default_image": "https://example.com/image.jpg",
  "aliases": ["Anya", "Subject 007"],
  "tags": ["telepath", "student", "pink_hair"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Cover Inventory Collection
```json
{
  "user_id": 123456789,
  "character_id": "anya_forger",
  "covers": [
    {
      "id": "anya_forger_0_12345",
      "url": "https://safebooru.org/image.jpg",
      "source": "Safebooru",
      "artist": "Artist Name",
      "width": 1920,
      "height": 1080,
      "price": 50000
    }
  ]
}
```

### User Balances Collection
```json
{
  "user_id": 123456789,
  "balance": 1000000
}
```

## Pricing System

Cover art prices are **extremely expensive** and scale based on character rarity:

| Rarity | Base Price | Description |
|--------|------------|-------------|
| C (Common) | 50,000 coins | Background characters |
| R (Rare) | 100,000 coins | Regular characters |
| SR (Super Rare) | 250,000 coins | Important supporting characters |
| SSR (Ultra Rare) | 500,000 coins | Main protagonists |

**Price Variation**: ±20% random multiplier for variety

## Art Sources

The system uses SFW-only art sources for cover images:
- **Safebooru**: SFW anime art database
- **Wallhaven**: High-quality wallpapers
- **Konachan Safe**: Anime wallpapers (SFW)
- **AIBooru**: AI-generated anime art

## User Interface Flow

### 1. Character View (`.draw view <id>`)
```
🎨 Anya Forger
[Character Image]

📊 Info                    🎨 Covers
Series: Spy x Family      3 owned
Rarity: SSR

[◀️ Previous] [▶️ Next] [🛒 Cover Art Shop]
```

### 2. Cover Art Shop
```
🎨 Cover Art Shop - Anya Forger
[Cover Image]

📋 Details
Source: Safebooru
Artist: Artist Name
Quality: 1920x1080
Price: 75,000 coins

Status: 🛒 Available for Purchase

[◀️ Previous] [▶️ Next] [💰 Buy (75,000 coins)]
```

### 3. Purchase Confirmation
```
🛒 Confirm Purchase
[Cover Image]

Your Balance: 100,000 coins
After Purchase: 25,000 coins

[✅ Confirm Purchase] [❌ Cancel]
```

## Setup Instructions

### 1. Database Setup
Run the setup script to populate sample characters:
```bash
python utils/cogs/cover_art_setup.py
```

### 2. Environment Variables
Ensure `MONGO_URL` is set in your environment:
```
MONGO_URL=mongodb://localhost:27017/
```

### 3. Load the Cog
Add to your bot's cog loading:
```python
await bot.load_extension('utils.cogs.cover_art')
```

## Sample Characters

The setup script includes these sample characters:

| Character | ID | Series | Rarity |
|-----------|----|---------| -------|
| Anya Forger | `anya_forger` | Spy x Family | SSR |
| Naruto Uzumaki | `naruto_uzumaki` | Naruto | SSR |
| Zero Two | `zero_two` | Darling in the FranXX | SR |
| Rem | `rem` | Re:Zero | SR |
| Sakura Haruno | `sakura_haruno` | Naruto | R |

## Technical Implementation

### Key Classes

#### `CoverArtDatabase`
- MongoDB interface for character data and user inventories
- Handles balance management and purchase transactions

#### `CoverArtShopView`
- Paginated Discord UI for browsing available covers
- Integrates with art aggregator for dynamic cover sourcing

#### `CoverArtVariantView`
- Character display with owned cover variants
- Navigation between different purchased covers

#### `CoverPurchaseConfirmView`
- Purchase confirmation with balance verification
- Transaction processing and inventory updates

### Art Integration

The system leverages the existing `art.py` aggregator:
```python
art_aggregator = ArtAggregator(session)
search_results = await art_aggregator.search_all(
    query=character_name,
    limit=20,
    nsfw=False,
    selected_sources={"safebooru", "wallhaven", "konachan_safe", "aibooru"}
)
```

## Error Handling

- **Character Not Found**: Clear error message with suggestion
- **Insufficient Funds**: Balance check with required amount
- **Database Errors**: Graceful fallback with user notification
- **Art Source Failures**: Retry logic and alternative sources

## Future Enhancements

### Planned Features
- **Cover Art Rarity**: Different rarity tiers for covers themselves
- **Daily Shop Rotation**: Limited-time exclusive covers
- **Achievement System**: Unlock covers through gameplay
- **Trading System**: User-to-user cover exchanges
- **Custom Uploads**: Allow users to submit custom covers (moderated)

### Performance Optimizations
- **Image Caching**: Cache frequently accessed covers
- **Lazy Loading**: Load covers on-demand
- **Database Indexing**: Optimize query performance
- **Rate Limiting**: Prevent API abuse

## Troubleshooting

### Common Issues

**"Database connection not available"**
- Check MongoDB connection string
- Verify database server is running
- Check network connectivity

**"Character not found in database"**
- Run the setup script to populate sample data
- Verify character ID format (lowercase, underscores)
- Check database for character existence

**"No cover art found"**
- Art sources may be temporarily unavailable
- Try different character names
- Check network connectivity to art providers

### Debug Mode
Enable debug logging:
```python
import logging
logging.getLogger('cover_art').setLevel(logging.DEBUG)
```

## Contributing

When adding new characters:
1. Use normalized IDs (lowercase, spaces → underscores)
2. Include proper rarity classification
3. Add relevant tags and aliases
4. Test with the cover art system

When modifying pricing:
1. Consider game economy balance
2. Test with different rarity levels
3. Update documentation accordingly
