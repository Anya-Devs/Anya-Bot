# Command Parsing System

## 🎯 Overview

Automatically parses your Discord bot's Python command files and generates an up-to-date `commands.json` for the website.

## ✨ Features

✅ **Reads actual Python files** - Parses from `bot/cogs/*.py`
✅ **Groups subcommands** - Properly handles `pt qp`, `anime manga`, etc.
✅ **Excludes hidden commands** - Skips `hidden=True` commands
✅ **Excludes empty cogs** - Only includes cogs with visible commands
✅ **Extracts metadata** - Gets aliases, descriptions, examples
✅ **Auto-updates** - Runs on `npm run dev` and `npm run build`

## 🚀 Usage

### Automatic (Recommended)

```bash
# Automatically parses commands before starting dev server
npm run dev

# Automatically parses commands before building
npm run build
```

### Manual

```bash
# Parse commands manually
npm run parse-bot-commands
```

## 📝 What It Parses

### Command Decorators

```python
# Regular command
@commands.command(name="help", description="Show help")
async def help_command(self, ctx):
    """Display help information"""
    pass

# Hybrid command
@commands.hybrid_command(name="ping")
async def ping(self, ctx):
    """Check bot latency"""
    pass

# App command
@app_commands.command(name="info", description="Bot info")
async def info(self, interaction):
    pass
```

### Command Groups

```python
# Command group
@commands.group(name="anime")
async def anime(self, ctx):
    """Anime commands"""
    pass

@anime.command(name="search")
async def anime_search(self, ctx, query: str):
    """Search for anime"""
    pass

@anime.command(name="manga")
async def anime_manga(self, ctx, query: str):
    """Search for manga"""
    pass
```

**Output:**
```json
{
  "Anime": {
    "anime": { ... },
    "anime search": { ... },
    "anime manga": { ... }
  }
}
```

### Hidden Commands (Excluded)

```python
# This will be SKIPPED
@commands.command(hidden=True)
async def secret_command(self, ctx):
    pass

# This will be SKIPPED
@commands.group(hidden = True)
async def admin(self, ctx):
    pass
```

## 📊 Extracted Information

For each command, the parser extracts:

### 1. **Name**
```python
@commands.command(name="help")  # Uses "help"
async def help_command(self, ctx):  # Fallback to "help_command"
```

### 2. **Description**
```python
# From decorator
@commands.command(description="Show help menu")

# Or from docstring
async def help(self, ctx):
    """Show help menu"""  # Uses this
```

### 3. **Aliases**
```python
@commands.command(aliases=["h", "?"])
# Output: ["h", "?"]
```

### 4. **Example**
```python
async def help(self, ctx):
    """
    Show help menu
    Example: .help commands
    """
# Extracts: ".help commands"
```

## 🔧 Configuration

### Cogs Directory

Default: `bot/cogs/`

To change, edit `scripts/parse-bot-commands.js`:

```javascript
const BOT_COGS_DIR = path.join(__dirname, '../../bot/cogs');
```

### Output Path

Default: `character-hosting/public/commands.json`

To change:

```javascript
const OUTPUT_PATH = path.join(__dirname, '../public/commands.json');
```

## 📂 File Structure

```
bot/
├── cogs/
│   ├── ai.py           → Parsed
│   ├── anime.py        → Parsed
│   ├── fun.py          → Parsed
│   ├── pokemon.py      → Parsed
│   ├── admin.py        → Parsed (if has visible commands)
│   └── __init__.py     → Skipped
└── ...

character-hosting/
├── scripts/
│   └── parse-bot-commands.js  → Parser script
└── public/
    └── commands.json          → Generated output
```

## 📋 Example Output

### Input (Python)

```python
# bot/cogs/anime.py

class Anime(commands.Cog):
    """Anime-related commands"""
    
    @commands.command(name="anime", description="Search for anime")
    async def anime_search(self, ctx, *, query: str):
        """
        Search for anime information
        Example: .anime Spy x Family
        """
        pass
    
    @commands.command(name="character", aliases=["char"])
    async def character_search(self, ctx, *, name: str):
        """Search for anime character"""
        pass
    
    @commands.command(hidden=True)
    async def admin_only(self, ctx):
        """Hidden admin command"""
        pass
```

### Output (JSON)

```json
{
  "Anime": {
    "anime": {
      "aliases": [],
      "description": "Search for anime information",
      "example": "{prefix}anime Spy x Family",
      "related_commands": ""
    },
    "character": {
      "aliases": ["char"],
      "description": "Search for anime character",
      "example": "{prefix}character",
      "related_commands": ""
    }
  }
}
```

**Note:** `admin_only` is excluded because `hidden=True`

## 🎯 Command Grouping

### Before Parsing

```python
@commands.group(name="pt")
async def poketwo(self, ctx):
    pass

@poketwo.command(name="qp")
async def quick_party(self, ctx):
    """Quick party setup"""
    pass

@poketwo.command(name="sh")
async def shiny_hunt(self, ctx):
    """Shiny hunting mode"""
    pass
```

### After Parsing

```json
{
  "PoketwoCommands": {
    "pt": {
      "aliases": [],
      "description": "Poketwo commands",
      "example": "{prefix}pt",
      "related_commands": ""
    },
    "pt qp": {
      "aliases": [],
      "description": "Quick party setup",
      "example": "{prefix}pt qp",
      "related_commands": "{prefix}pt"
    },
    "pt sh": {
      "aliases": [],
      "description": "Shiny hunting mode",
      "example": "{prefix}pt sh",
      "related_commands": "{prefix}pt"
    }
  }
}
```

## 🐛 Troubleshooting

### "Bot cogs directory not found"

**Cause:** Script can't find `bot/cogs/` directory

**Solution:**
1. Check directory exists: `bot/cogs/`
2. Update path in `parse-bot-commands.js`
3. Run from correct directory

### "No commands found"

**Possible causes:**
1. All commands are `hidden=True`
2. No command decorators found
3. Incorrect Python syntax

**Solution:**
1. Check your cog files have `@commands.command()`
2. Ensure commands aren't hidden
3. Check Python syntax is valid

### "Commands not updating"

**Cause:** Old commands.json cached

**Solution:**
```bash
# Delete old file
rm character-hosting/public/commands.json

# Re-parse
npm run parse-bot-commands
```

## 📊 Parser Output

When you run the parser:

```bash
npm run parse-bot-commands

🔍 Parsing bot commands from Python files...

📁 Found 12 cog files

📂 Processing: Ai (ai.py)
  ✅ Found command: imagine
  ✅ Found command: vision
  ✅ Added 2 commands to Ai

📂 Processing: Anime (anime.py)
  ✅ Found command: anime
  ✅ Found command: character
  ✅ Found command: manga
  ✅ Added 3 commands to Anime

📂 Processing: Pokemon (pokemon.py)
  📦 Found group: pt with 5 subcommands
    ↳ qp
    ↳ sh
    ↳ special
    ↳ quest
    ↳ type
  ✅ Added 6 commands to Pokemon

📂 Processing: Admin (admin.py)
  ⏭️  Skipping hidden command: ban
  ⏭️  Skipping hidden command: kick
  ⏭️  Skipping Admin (no visible commands)

==================================================
✅ Commands parsed successfully!
📊 Categories: 8
📊 Total commands: 47
📁 Output: character-hosting/public/commands.json
==================================================
```

## ✅ Best Practices

### 1. Use Descriptive Names

```python
# ✅ Good
@commands.command(name="anime_search", description="Search for anime")

# ❌ Bad
@commands.command(name="as")  # Unclear
```

### 2. Add Docstrings

```python
# ✅ Good
async def help(self, ctx):
    """
    Display help information for all commands
    Example: .help commands
    """

# ❌ Bad
async def help(self, ctx):
    pass  # No documentation
```

### 3. Group Related Commands

```python
# ✅ Good
@commands.group(name="anime")
async def anime(self, ctx):
    pass

@anime.command(name="search")
@anime.command(name="manga")
@anime.command(name="character")

# ❌ Bad
@commands.command(name="anime_search")
@commands.command(name="anime_manga")
@commands.command(name="anime_character")
```

### 4. Use Hidden for Admin Commands

```python
# ✅ Good
@commands.command(hidden=True)
@commands.has_permissions(administrator=True)
async def admin_command(self, ctx):
    pass

# ❌ Bad
@commands.command()  # Visible to everyone
@commands.has_permissions(administrator=True)
async def admin_command(self, ctx):
    pass
```

## 🎉 Result

- ✅ **Always up-to-date** - Parses from actual bot code
- ✅ **No manual updates** - Automatic on dev/build
- ✅ **Properly grouped** - Subcommands organized
- ✅ **Clean output** - Only visible commands
- ✅ **Accurate info** - From actual decorators/docstrings

Your commands.json is now automatically generated from your bot's code! 🚀
