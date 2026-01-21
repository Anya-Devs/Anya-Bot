# Anime Trope Command

## Overview
The `.trope` command is a fun Discord bot command that randomly assigns anime character traits to users, creating a unique character profile with personality type, facial expression, gender, and size.

## Usage

### Basic Usage
```
.trope
```
Generates an anime character profile for yourself.

### Check Another User
```
.trope @username
```
Generates an anime character profile for the mentioned user.

## Features

### Personality Types (20 total)
The command includes 20 different anime personality tropes:
- **Tsundere** - Acts cold but is warm inside
- **Yandere** - Sweet but obsessive
- **Kuudere** - Cool and collected
- **Dandere** - Shy but opens up
- **Deredere** - Cheerful and affectionate
- **Himedere** - Acts like royalty (like your example!)
- **Kamidere** - God complex
- **Sadodere** - Enjoys teasing
- **Bakadere** - Clumsy and lovable
- **Undere** - Always agrees
- **Shundere** - Sad but comforted
- **Bodere** - Violent and aggressive
- **Hinedere** - Cynical and sarcastic
- **Oujidere** - Acts like a prince
- **Kanedere** - Loves money
- **Mayadere** - Former antagonist
- **Nyandere** - Cat-like personality
- **Dorodere** - Sweet outside, disturbed inside
- **Darudere** - Lazy but caring
- **Hajidere** - Extremely shy

### Facial Expressions (25 total)
Includes cute anime-style emoticons like:
- `=w=` (your favorite!)
- `^_^`
- `>_<`
- `UwU`
- `OwO`
- `◕‿◕`
- And many more!

### Gender Options (5 total)
- Male
- Female
- Non-binary
- Genderfluid
- Agender

### Size Categories (6 total)
- Smol Bean (4'0" - 4'11")
- Short King/Queen (5'0" - 5'4")
- Average Height (5'5" - 5'9")
- Tall (5'10" - 6'2")
- Giant (6'3" - 7'0")
- Literal Giant (7'0"+)

## Output
The command generates a beautiful Discord embed with:
- A color scheme matching the personality type
- The user's avatar as a thumbnail
- Personality description
- All four randomly selected attributes
- Timestamp and requester information

## Files
- **Command**: `bot/cogs/fun.py`
- **Data**: `data/commands/fun/anime-tropes.json`

## Example Output
When you run `.trope`, you might get:
```
✨ Your Name's Anime Character Profile
Acts like royalty and expects to be treated as such

🎭 Personality Type: Himedere
😊 Facial Expression: =w=
⚧️ Gender: Female
📏 Size: Short Queen (5'0" - 5'4")
```

Each personality type has its own unique color in the embed!
