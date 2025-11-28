/**
 * Embed Templates - Exact replicas of bot embed outputs from cogs
 * 
 * These templates match EXACTLY what the bot produces in:
 * - bot/cogs/fun.py (8ball, action commands)
 * - bot/cogs/anime.py (anime/manga search)
 * - bot/cogs/pokemon.py (pokedex)
 * - bot/cogs/ai.py (imagine)
 * - utils/cogs/fun.py (action command embeds)
 * - utils/cogs/anime.py (anime embed formatting)
 * - utils/cogs/pokemon.py (pokemon embed formatting)
 */

// Primary color used by the bot (from data/local/const.py)
export const PRIMARY_COLOR = '#FF6B9D';

// Blank emoji used in 8ball (from data/local/emojis.py)
export const BLANK_EMOJI = '⠀'; // Unicode blank character

/**
 * 8Ball Command Embed
 * Source: bot/cogs/fun.py lines 21-32
 * 
 * embed = discord.Embed(
 *     title="🎱 8Ball",
 *     description=f"**{question}**\n{blank_emoji} {ans}",
 *     color=primary_color()
 * ).set_footer(
 *     text=f"Requested by {ctx.author}",
 *     icon_url=ctx.author.avatar.url
 * )
 */
export interface EightBallEmbed {
  title: '🎱 8Ball';
  description: string; // "**{question}**\n⠀ {answer}"
  color: string;
  footer: string; // "Requested by {username}"
  footerIcon?: string;
}

export const createEightBallEmbed = (
  question: string,
  answer: string,
  username: string = 'User',
  avatarUrl?: string
): EightBallEmbed => ({
  title: '🎱 8Ball',
  description: `Q: **${question}**\nA: ${answer}`,
  color: PRIMARY_COLOR,
  footer: `Requested by ${username}`,
  footerIcon: avatarUrl,
});

// 8Ball responses (from data/commands/fun/8ball-responses.txt)
export const EIGHT_BALL_RESPONSES = [
  'It is certain.',
  'It is decidedly so.',
  'Without a doubt.',
  'Yes definitely.',
  'You may rely on it.',
  'As I see it, yes.',
  'Most likely.',
  'Outlook good.',
  'Yes.',
  'Signs point to yes.',
  'Reply hazy, try again.',
  'Ask again later.',
  'Better not tell you now.',
  'Cannot predict now.',
  'Concentrate and ask again.',
  "Don't count on it.",
  'My reply is no.',
  'My sources say no.',
  'Outlook not so good.',
  'Very doubtful.',
];

/**
 * Action Command Embed (hug, pat, bite, etc.)
 * Source: utils/cogs/fun.py line 68
 * 
 * embed = discord.Embed(
 *     title=msg,  # e.g., "Loid hugs Yor"
 *     color=primary_color()
 * ).set_image(url=gif).set_footer(text=f"Sent: {sent} | Received: {received}")
 */
export interface ActionEmbed {
  title: string; // "{user} {action}s {target}"
  color: string;
  image: string; // GIF URL from otakugifs API
  footer: string; // "Sent: {sent} | Received: {received}"
  userAvatar?: string; // Avatar of user who sent the command
  command?: string; // The command used
}

export const createActionEmbed = (
  phrase: string,
  gifUrl: string,
  sent: number,
  received: number
): ActionEmbed => ({
  title: phrase,
  color: PRIMARY_COLOR,
  image: gifUrl,
  footer: `Sent: ${sent} | Received: ${received}`,
});

/**
 * Anime Search Embed
 * Source: utils/cogs/anime.py lines 125-148
 * 
 * embed = discord.Embed(title=anime["title"])
 * embed.set_image(url=image_url)
 * embed.add_field(
 *     name=" ",
 *     value=f"**Episodes:** `{anime['episodes']}`\n"
 *           f"**Status:** `{anime['status']}`\n"
 *           f"**Genres:** `{', '.join(genre['name'] for genre in anime['genres'])}`\n"
 *           f"{'**Trailer:** ' + '``' + anime['trailer']['url'] + '``' if anime['trailer']['url'] else ''}\n"
 *           f"```py\nScore: {anime['score']:>3} (out of 10)\n"
 *           f"{'▰' * int(anime['score'] * 10 / 10)}{'▱' * (10 - int(anime['score'] * 10 / 10))}```",
 *     inline=False,
 * )
 * embed.description = anime.get("synopsis", "> Synopsis not available")
 * embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages + 1}")
 */
export interface AnimeEmbed {
  title: string;
  description: string; // Synopsis
  color: string;
  image?: string;
  fields: Array<{ name: string; value: string; inline: boolean }>;
  footer: string; // "Page {current}/{total}"
}

export const createAnimeEmbed = (
  title: string,
  synopsis: string,
  imageUrl: string | undefined,
  episodes: number | string,
  status: string,
  genres: string[],
  score: number,
  trailerUrl?: string,
  currentPage: number = 1,
  totalPages: number = 1
): AnimeEmbed => {
  const scoreBar = '▰'.repeat(Math.floor(score)) + '▱'.repeat(10 - Math.floor(score));
  
  let fieldValue = `**Episodes:** \`${episodes || 'Unknown'}\`\n`;
  fieldValue += `**Status:** \`${status || 'Unknown'}\`\n`;
  fieldValue += `**Genres:** \`${genres.join(', ') || 'Unknown'}\`\n`;
  if (trailerUrl) {
    fieldValue += `**Trailer:** \`\`${trailerUrl}\`\`\n`;
  }
  fieldValue += `\`\`\`py\nScore: ${score.toFixed(1).padStart(3)} (out of 10)\n${scoreBar}\`\`\``;

  return {
    title,
    description: synopsis || '> Synopsis not available',
    color: PRIMARY_COLOR,
    image: imageUrl,
    fields: [{ name: ' ', value: fieldValue, inline: false }],
    footer: `Page ${currentPage}/${totalPages}`,
  };
};

/**
 * Pokemon/Pokedex Embed
 * Source: utils/cogs/pokemon.py lines 147-224
 * 
 * embed = discord.Embed(
 *     title=f" #{id} — {species_name.title()}",
 *     description=f"\n{pokemon_description}\n",
 *     color=color,
 * )
 * embed.set_image(url=image_url)
 * embed.add_field(name="Region", value=f"{region_emoji} {region}", inline=True)
 * embed.add_field(name="Names", value=alt_names_str, inline=True)
 * embed.set_footer(icon_url=image_thumb, text=f"Height: {height:.2f} m\nWeight: {weight:.2f} kg")
 */
export interface PokemonEmbed {
  title: string; // " #{id} — {name}" or " #{id} — ✨ {name}" for shiny
  description: string;
  color: string;
  image: string; // Official artwork
  fields: Array<{ name: string; value: string; inline: boolean }>;
  footer: string;
  footerIcon?: string; // Animated sprite
}

// Region emoji mappings (from utils/cogs/pokemon.py)
export const REGION_EMOJIS: Record<string, string> = {
  Paldea: '<:Paldea:1212335178714980403>',
  Sinnoh: '<:Sinnoh:1212335180459544607>',
  Alola: '<:Alola:1212335185228472411>',
  Kalos: '<:Kalos:1212335190656024608>',
  Galar: '<:Galar:1212335192740470876>',
  Hoenn: '<:Hoenn:1212335197304004678>',
  Unova: '<:Unova:1212335199095095306>',
  Kanto: '<:Kanto:1212335202341363713>',
  Johto: '<:Kanto:1212335202341363713>',
};

// For website display, use text representations
export const REGION_DISPLAY: Record<string, string> = {
  Paldea: '🟣 Paldea',
  Sinnoh: '💎 Sinnoh',
  Alola: '🌴 Alola',
  Kalos: '💙 Kalos',
  Galar: '🔴 Galar',
  Hoenn: '🌊 Hoenn',
  Unova: '⚫ Unova',
  Kanto: '🔴 Kanto',
  Johto: '🔴 Johto',
  Hisui: '⭐ Hisui',
};

export const createPokemonEmbed = (
  id: number,
  name: string,
  description: string,
  imageUrl: string,
  region: string,
  alternateNames: string,
  height: number, // in meters
  weight: number, // in kg
  animatedSprite?: string,
  isShiny: boolean = false,
  gender?: string,
  rarity?: string
): PokemonEmbed => {
  const titleName = name.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  const title = isShiny ? ` #${id} — ✨ ${titleName}` : ` #${id} — ${titleName}`;
  
  let footerText = `Height: ${height.toFixed(2)} m\nWeight: ${weight.toFixed(2)} kg`;
  if (gender && gender !== '♂ 50% - ♀ 50%') {
    footerText += `\nGender: ${gender}`;
  }
  if (rarity) {
    footerText = `Rarity: ${rarity}\n\n${footerText}`;
  }

  return {
    title,
    description: `\n${description}\n`,
    color: PRIMARY_COLOR,
    image: imageUrl,
    fields: [
      { name: 'Region', value: REGION_DISPLAY[region] || region, inline: true },
      { name: 'Names', value: alternateNames, inline: true },
    ],
    footer: footerText,
    footerIcon: animatedSprite,
  };
};

/**
 * AI Image Generation Embed
 * Source: bot/cogs/ai.py lines 38-45
 * 
 * embed = discord.Embed(
 *     description=f"**Prompt:** ```{prompt}```",
 *     color=primary_color(),
 *     timestamp=datetime.now(),
 *     url="https://rajtech.me"
 * )
 * embed.set_image(url="attachment://1.png")
 * embed.set_footer(icon_url=ctx.author.avatar, text=f"Requested by {ctx.author}")
 */
export interface ImagineEmbed {
  title?: string;
  description: string;
  color: string;
  progress?: number; // 0-100 for visual progress bar
  image?: string;
  footer: string;
  footerIcon?: string;
}

export const createImagineEmbed = (
  prompt: string,
  progress: number = 0, // 0-100
  imageUrl?: string,
  username?: string,
  avatarUrl?: string
): ImagineEmbed => {
  return {
    title: '🎨 Generating Image',
    description: `**Prompt:** ${prompt}`,
    color: PRIMARY_COLOR,
    progress, // Visual progress bar rendered by component
    image: imageUrl,
    footer: `Requested by ${username || 'User'}`,
    footerIcon: avatarUrl,
  };
};

/**
 * Shiny Hunt Set Embed
 * Source: bot/cogs/pokemon.py (PoketwoCommands)
 */
export interface ShinyHuntEmbed {
  title: string;
  description: string;
  color: string;
  footer: string;
}

export const createShinyHuntEmbed = (
  pokemonName: string,
  success: boolean = true
): ShinyHuntEmbed => ({
  title: success ? '✓ Shiny Hunt Set' : '✗ Error',
  description: success 
    ? `You'll be pinged when **${pokemonName}** spawns in protected channels.`
    : `Could not set shiny hunt for ${pokemonName}.`,
  color: success ? '#34D399' : '#EF4444',
  footer: 'Use .pt sh remove to clear',
});

// ============================================================================
// SAMPLE DATA FOR WEBSITE PREVIEWS
// These are real examples that exactly match bot output
// ============================================================================

export const SAMPLE_EMBEDS = {
  eightBall: createEightBallEmbed(
    'Will Anya pass her exam?',
    'Without a doubt.',
  ),

  action: {
    title: 'Yor hugs Anya',
    color: PRIMARY_COLOR,
    image: 'https://media1.tenor.com/m/sQ_isTxT-EEAAAAd/anya-hug.gif',
    footer: 'Sent: 42 | Received: 38',
    userAvatar: 'https://i.pinimg.com/736x/c2/d3/3d/c2d33dae68145c7c07ff74a66872fecf.jpg',
    command: '.hug @Anya',
  } as ActionEmbed,

  anime: createAnimeEmbed(
    'Spy x Family',
    'A spy on an undercover mission gets married and adopts a child as part of his cover. His wife and daughter have secrets of their own, and all three must strive to keep together.',
    'https://cdn.myanimelist.net/images/anime/1441/122795l.jpg',
    25,
    'Finished Airing',
    ['Action', 'Comedy', 'Childcare'],
    8.5,
    undefined,
    1,
    25
  ),

  pokemon: createPokemonEmbed(
    37,
    'vulpix',
    'At the time of its birth, Vulpix has one white tail. The tail separates into six if this Pokémon receives plenty of love from its Trainer.',
    'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/37.png',
    'Kanto',
    '🇯🇵 Rokon\n🇫🇷 Goupix\n🇩🇪 Vulpix',
    0.6,
    9.9,
    'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/animated/37.gif',
  ),

  imagine: createImagineEmbed(
    '1girl, pink hair, green eyes, school uniform, cherry blossoms, masterpiece, high quality, detailed',
    75, // 75% progress
    undefined,
    'User',
  ),

  shinyHunt: createShinyHuntEmbed('Alolan Vulpix'),
};

// Export type for use in components
export type EmbedTemplate = 
  | EightBallEmbed 
  | ActionEmbed 
  | AnimeEmbed 
  | PokemonEmbed 
  | ImagineEmbed 
  | ShinyHuntEmbed;
