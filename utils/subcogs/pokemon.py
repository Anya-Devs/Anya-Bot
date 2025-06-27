import os, re, csv, json, asyncio, multiprocessing as mp, csv, difflib
from functools import partial
from tqdm import tqdm, asyncio as async_tqdm
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from fuzzywuzzy import fuzz
from motor.motor_asyncio import AsyncIOMotorClient

from imports.discord_imports import *
from data.local.const import *
from bot.token import use_test_bot as ut
from utils.subcogs.pokemon import *


MAX_POKEMON, CHUNK_SIZE, RESULTS_PER_PAGE, MIN_SIMILARITY_RATIO  = 50, 15, 10, 0.65


class AdvancedStringFlagParser:
    
    def __init__(self):
        # Define flag patterns and their variations
        self.flag_patterns = {
            'alolan': r'\b(?:alolan?|alola)\b',
            'galarian': r'\b(?:galarians?|galar)\b', 
            'hisuian': r'\b(?:hisuians?|hisui)\b',
            'paldean': r'\b(?:paldeans?|paldea)\b',
            'mega': r'\b(?:mega)\b',
            'legendary': r'\b(?:legendary?|legendaries|leg)\b',
            'mythical': r'\b(?:mythicals?|myth)\b',
            'shiny': r'\b(?:shiny|shinies)\b',
            'limit': r'\b(?:limit|max|top)\s+(\d+)\b',
            'skip': r'\b(?:skip|offset)\s+(\d+)\b',
        }
        
        # Type patterns
        self.type_pattern = r'\b(?:type|types?)\s+([a-zA-Z]+(?:\s*,\s*[a-zA-Z]+)*)\b'
        
        # Name patterns  
        self.name_pattern = r'\b(?:name|named?|pokemon)\s+([a-zA-Z0-9\s,\-\']+?)(?:\s+(?:type|limit|skip|legendary|mythical|alolan|galarian|hisuian|paldean|mega)|$)'
        
        # Region patterns
        self.region_pattern = r'\b(?:region|from)\s+([a-zA-Z]+(?:\s*,\s*[a-zA-Z]+)*)\b'

    def parse_flags_from_string(self, text: str) -> Dict[str, Any]:
        """Parse flags from a natural language string"""
        if not text:
            return {}
            
        text_lower = text.lower()
        flags = {}
        
        # Parse boolean flags
        for flag_name, pattern in self.flag_patterns.items():
            if flag_name in ['limit', 'skip']:
                match = re.search(pattern, text_lower)
                if match:
                    flags[flag_name] = int(match.group(1))
            else:
                if re.search(pattern, text_lower):
                    flags[flag_name] = True
        
        # Parse type filters
        type_match = re.search(self.type_pattern, text_lower)
        if type_match:
            types = [t.strip() for t in type_match.group(1).split(',')]
            flags['type'] = types
        
        # Parse name filters
        name_match = re.search(self.name_pattern, text_lower)
        if name_match:
            names = [n.strip() for n in name_match.group(1).split(',')]
            # Group names for the existing filter logic
            flags['name'] = [[name] for name in names]
        
        # Parse region filters
        region_match = re.search(self.region_pattern, text_lower)
        if region_match:
            regions = [r.strip() for r in region_match.group(1).split(',')]
            flags['region'] = regions
            
        return flags

    def extract_pokemon_names_from_string(self, text: str, action: str) -> Tuple[str, str]:
        """Extract Pokemon names from string, removing flag-related words"""
        if not text:
            return "", ""
            
        # Remove action words
        action_words = r'\b(?:add|remove|delete|clear|list|show|help)\b'
        text = re.sub(action_words, '', text, flags=re.IGNORECASE).strip()
        
        # Remove flag-related words
        flag_words = [
            r'\b(?:alolan?|alola|galarians?|galar|hisuians?|hisui|paldeans?|paldea|mega)\b',
            r'\b(?:legendary?|legendaries|leg|mythicals?|myth|shiny|shinies)\b',
            r'\b(?:limit|max|top|skip|offset)\s+\d+\b',
            r'\b(?:type|types?)\s+[a-zA-Z,\s]+?\b',
            r'\b(?:region|from)\s+[a-zA-Z,\s]+?\b',
            r'\b(?:name|named?|pokemon)\s+'
        ]
        
        for pattern in flag_words:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and commas
        text = re.sub(r'\s*,\s*', ',', text)
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.strip(',')
        
        return text, action




class NavigationView(View):
    def __init__(self, embeds, ctx, timeout=300):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.ctx = ctx
        self.current_index = 0
        
        # Create navigation buttons
        self.prev_button = Button(label="◀", style=ButtonStyle.secondary, disabled=self.current_index == 0)
        self.next_button = Button(label="▶", style=ButtonStyle.secondary, disabled=self.current_index >= len(embeds) - 1)
        self.prev_button.callback = self.go_prev
        self.next_button.callback = self.go_next
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
    
    async def go_prev(self, interaction):
        if self.current_index > 0:
            self.current_index -= 1
            await self.update_view(interaction)
    
    async def go_next(self, interaction):
        if self.current_index < len(self.embeds) - 1:
            self.current_index += 1
            await self.update_view(interaction)
    
    async def update_view(self, interaction):
        # Update button states
        self.prev_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index >= len(self.embeds) - 1
        
        # Update the message with new embed and view
        await interaction.response.edit_message(embed=self.embeds[self.current_index], view=self)
    
    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.author

class Ping_Pokemon(commands.Cog):
    
    ICONS = {"success": "[✓]", "error": "[✕]", "exists": "[⍻]", "removed": "[−]", "not_found": "[𐄂]"}
    MIN_SUGGEST_LEN, MAX_SUGGESTIONS = 3, 5
    MAX_POKEMON, CHUNK_SIZE, RESULTS_PER_PAGE, MIN_SIMILARITY_RATIO = 50, 15, 10, 0.65

    def __init__(self, bot):
        self.bot = bot
        self.shiny_collection = "shiny_hunt"
        self.collection_collection = "collection"
        self.pokemon_names_csv = os.path.join("data", "commands", "pokemon", "pokemon_names.csv")
        self.pokemon_types_csv = os.path.join("data", "commands", "pokemon", "pokemon_types.csv")
        self.pokemon_rarity_csv = os.path.join("data", "commands", "pokemon", "pokemon_rarity.csv")
        self.pokemon_species_url = "https://pokeapi.co/api/v2/pokemon-species"
        
        # Initialize MongoDB connection
        try:
            # You'll need to add your MongoHelper class or replace this with your actual MongoDB setup
            self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        except:
            print("Warning: MongoDB connection failed. Make sure MongoHelper is imported and MONGO_URI is set.")
            self.mongo = None
            
        self._valid_slugs = None
        self._pokemon_types = None
        self._pokemon_rarity = None
        
        # Initialize helper classes - you'll need to make sure these are imported
        try:
            self.pe = Pokemon_Emojis(bot)
            self.ph = PokemonNameHelper()
        except:
            print("Warning: Pokemon helper classes not found. Some features may not work.")
            self.pe = None
            self.ph = None
        
        # Initialize the advanced string parser
        self.flag_parser = AdvancedStringFlagParser()
        
        self.region_map = {"alolan": "-alola", "galarian": "-galar", "hisuian": "-hisui", "paldean": "-paldea", "mega": "-mega"}
        self.reverse_region_map = {
            "alola": "Alolan",
            "galar": "Galarian", 
            "hisui": "Hisuian",
            "paldea": "Paldean",
            "mega": "Mega"
        }

    def normalize_regional_name(self, name: str) -> str:
        parts = name.lower().split("-")
        for i, p in enumerate(parts):
            if p in self.region_map:
                parts.pop(i)
                return "-".join(parts) + self.region_map[p]
        return name

    def display_name_with_region(self, slug: str) -> str:
        parts = slug.lower().split("-")
        if parts[-1] in self.reverse_region_map:
            region_prefix = self.reverse_region_map[parts[-1]]
            base_name = " ".join(parts[:-1]).title()
            return f"{region_prefix} {base_name}"
        return " ".join(parts).title()

    async def load_valid_slugs(self):
        if not os.path.isfile(self.pokemon_names_csv):
            os.makedirs(os.path.dirname(self.pokemon_names_csv), exist_ok=True)
            
            species_list = await self.afetch_pokemon_species()
            pokemon_list = [{"id": int(p["url"].rstrip("/").split("/")[-1]), "name": p["name"]} for p in species_list]
            
            with open(self.pokemon_names_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["id", "name"])
                writer.writeheader()
                writer.writerows(pokemon_list)
                
        with open(self.pokemon_names_csv, newline="", encoding="utf-8") as f:
            return {row["name"].lower() for row in csv.DictReader(f)}

    async def afetch_pokemon_species(self):
        species_list = []
        url = self.pokemon_species_url
        total_pages = 0
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    total_pages = (data["count"] + 19) // 20
                else:
                    return []

        url = self.pokemon_species_url
        with tqdm(total=total_pages, desc="Fetching Pokemon species") as pbar:
            async with aiohttp.ClientSession() as session:
                while url:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            species_list.extend(data["results"])
                            url = data.get("next")
                            pbar.update(1)
                        else:
                            break
        return species_list

    async def fetch_pokemon_details(self, pokemon_list):
        detailed_pokemon = []
        
        async with aiohttp.ClientSession() as session:
            for pokemon in tqdm(pokemon_list, desc="Fetching Pokemon details"):
                try:
                    pokemon_id = int(pokemon["url"].rstrip("/").split("/")[-1])
                    pokemon_url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
                    
                    async with session.get(pokemon_url) as response:
                        if response.status == 200:
                            pokemon_data = await response.json()
                            types = [t["type"]["name"] for t in pokemon_data["types"]]
                            
                            detailed_pokemon.append({
                                "id": pokemon_id,
                                "name": pokemon["name"],
                                "type1": types[0] if types else "",
                                "type2": types[1] if len(types) > 1 else ""
                            })
                except Exception as e:
                    print(f"Error fetching details for {pokemon['name']}: {e}")
                    continue
                    
        return detailed_pokemon

    async def generate_pokemon_types_csv(self):
        if not os.path.isfile(self.pokemon_types_csv):
            os.makedirs(os.path.dirname(self.pokemon_types_csv), exist_ok=True)
            
            species_list = await self.afetch_pokemon_species()
            detailed_pokemon = await self.fetch_pokemon_details(species_list)
            
            with open(self.pokemon_types_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["id", "name", "type1", "type2"])
                writer.writeheader()
                writer.writerows(detailed_pokemon)

    async def load_pokemon_types(self):
        if not os.path.isfile(self.pokemon_types_csv):
            await self.generate_pokemon_types_csv()
        
        types_map = {}
        with open(self.pokemon_types_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").lower()
                type1 = row.get("type1", "").lower()
                type2 = row.get("type2", "").lower()
                types_map[name] = [type1] + ([type2] if type2 else [])
        return types_map

    async def load_pokemon_rarity(self):
        if not os.path.isfile(self.pokemon_rarity_csv):
            return {}
        
        rarity_map = {}
        with open(self.pokemon_rarity_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").lower()
                rarity = row.get("rarity", "").lower()
                region = row.get("region", "").lower()
                rarity_map[name] = {"rarity": rarity, "region": region}
        return rarity_map

    @property
    async def valid_slugs(self):
        if self._valid_slugs is None:
            self._valid_slugs = await self.load_valid_slugs()
        return self._valid_slugs

    @property
    async def pokemon_types(self):
        if self._pokemon_types is None:
            self._pokemon_types = await self.load_pokemon_types()
        return self._pokemon_types

    @property
    async def pokemon_rarity(self):
        if self._pokemon_rarity is None:
            self._pokemon_rarity = await self.load_pokemon_rarity()
        return self._pokemon_rarity

    async def filter_by_flags(self, entries: list[str], flags_obj) -> list[str]:
        """Filter entries based on flags"""
        try:
            flags_dict = flags_obj if isinstance(flags_obj, dict) else {}
            if not any(flags_dict.values()):
                return entries
            filtered = []

            suffix_map = {
                'alolan': '-alola',
                'galarian': '-galar', 
                'hisuian': '-hisui',
                'paldean': '-paldea',
                'mega': '-mega'
            }

            rarity_checks = {
                'legendary': 'legendary',
                'mythical': 'mythical'
            }

            for entry in entries:
                pokemon_name = self.extract_pokemon_name(entry)
                slug = self.normalize_regional_name(pokemon_name.lower().replace(" ", "-"))

                # Regional form checks
                for flag, suffix in suffix_map.items():
                    if flags_dict.get(flag) and not slug.endswith(suffix):
                        break
                else:
                    # Get rarity data
                    try:
                        rarity_data = (await self.pokemon_rarity).get(slug, {})
                        rarity = rarity_data.get("rarity", "")
                    except:
                        rarity_data = {}
                        rarity = ""

                    # Rarity checks
                    for flag, rarity_val in rarity_checks.items():
                        if flags_dict.get(flag) and rarity != rarity_val:
                            break
                    else:
                        # Name filter
                        if flags_dict.get('name'):
                            name_matches = False
                            for name_group in flags_dict['name']:
                                for name_filter in name_group:
                                    if name_filter.lower() in pokemon_name.lower():
                                        name_matches = True
                                        break
                                if name_matches:
                                    break
                            if not name_matches:
                                continue

                        # Type filter
                        if flags_dict.get('type'):
                            try:
                                pokemon_types_data = (await self.pokemon_types).get(slug, [])
                                type_filters = [t.lower() for t in pokemon_types_data]
                                if not any(type_filter.lower() in type_filters for type_filter in flags_dict['type']):
                                    continue
                            except:
                                continue

                        # Region filter
                        if flags_dict.get('region'):
                            region_data = rarity_data.get("region", "").lower()
                            if not any(region_filter.lower() == region_data for region_filter in flags_dict['region']):
                                continue

                        filtered.append(entry)

            # Apply limit and skip
            if flags_dict.get('skip'):
                filtered = filtered[flags_dict['skip']:]
            if flags_dict.get('limit'):
                filtered = filtered[:flags_dict['limit']]

            return filtered
        except Exception as e:
            print(f"Error in filter_by_flags: {e}")
            return entries
     
    def extract_pokemon_name(self, entry: str) -> str:
        return re.sub(r'<:[^:]+:\d+>\s*', '', entry).strip()

    def find_similar_names(self, query: str, valid_names: list) -> list[str]:
        query_lower = query.lower()
        
        exact_matches = [name for name in valid_names if query_lower in name.lower()]
        
        if not exact_matches:
            fuzzy_matches = difflib.get_close_matches(
                query_lower, 
                [name.lower() for name in valid_names], 
                n=self.MAX_SUGGESTIONS,
                cutoff=self.MIN_SIMILARITY_RATIO
            )
            return [name for name in valid_names if name.lower() in fuzzy_matches]
        
        return exact_matches[:self.MAX_SUGGESTIONS]

    def create_collection_embeds(self, entries: list[str], title: str, ctx) -> list[Embed]:
        """Create paginated embeds for collection display"""
        if not entries:
            embed = Embed(
                title=title,
                description="No Pokémon found matching your criteria.",
                color=0x3498db
            )
            embed.set_footer(text=f"Use {ctx.prefix}{ctx.invoked_with} help for more information")
            return [embed]
        
        embeds = []
        total_pages = (len(entries) + self.RESULTS_PER_PAGE - 1) // self.RESULTS_PER_PAGE
        
        for page in range(total_pages):
            start_idx = page * self.RESULTS_PER_PAGE
            end_idx = min(start_idx + self.RESULTS_PER_PAGE, len(entries))
            page_entries = entries[start_idx:end_idx]
            
            # Create chunks for better formatting
            chunks = []
            current_chunk = []
            
            for entry in page_entries:
                current_chunk.append(entry)
                if len(current_chunk) >= self.CHUNK_SIZE:
                    chunks.append(current_chunk)
                    current_chunk = []
            
            if current_chunk:
                chunks.append(current_chunk)
            
            # Build embed description
            description_parts = []
            for i, chunk in enumerate(chunks):
                chunk_text = "\n".join(f"{start_idx + (i * self.CHUNK_SIZE) + j + 1}. {entry}" 
                                     for j, entry in enumerate(chunk))
                description_parts.append(chunk_text)
            
            embed = Embed(
                title=f"{title}",
                description="\n\n".join(description_parts),
                color=primary_color()
            )
            
            # Add statistics
            embed.add_field(
                name=" ",
                value=f"**Total:** {len(entries)} Pokémon\n**Page:** {page + 1}/{total_pages}\n**Showing:** {start_idx + 1}-{end_idx}",
                inline=True
            )
            
            embed.set_footer(text=f"Use {ctx.prefix}{ctx.invoked_with} help for more information")
            embeds.append(embed)
        
        return embeds

    async def paginate_and_send(self, ctx, entries: list[str], title="Your Pokémon Collection", flags_obj=None):
        """Send paginated collection with navigation buttons"""
        try:
            embeds = self.create_collection_embeds(entries, title, ctx)
            
            if len(embeds) == 1:
                # Single page, no navigation needed
                await ctx.send(embed=embeds[0])
            else:
                # Multiple pages, add navigation
                view = NavigationView(embeds, ctx)
                await ctx.send(embed=embeds[0], view=view)
                
        except Exception as e:
            print(f"Error in paginate_and_send: {e}")
            error_embed = Embed(
                title="❌ Error",
                description="Failed to display your Pokémon collection. Please try again.",
                color=0xff0000
            )
            error_embed.set_footer(text=f"Use {ctx.prefix}{ctx.invoked_with} help for more information")
            await ctx.send(embed=error_embed)

    async def handle_collection(self, ctx, col, action, pokemon=None, max_one=False, flags_obj=None):
     if not self.mongo:
        await ctx.reply("❌ Database connection not available.", mention_author=False)
        return

     try:
        valid_slugs = await self.valid_slugs
        valid_slugs_list = list(valid_slugs)
        uid = ctx.author.id
        cur = await self.mongo.list(col, uid)

        # Clean invalid entries
        invalids = [n for n in cur if n.lower() not in valid_slugs]
        for n in invalids:
            await self.mongo.remove(col, n, uid)

        cur = await self.mongo.list(col, uid)
        if len(cur) > self.MAX_POKEMON:
            for n in cur[self.MAX_POKEMON:]:
                await self.mongo.remove(col, n, uid)
            cur = cur[:self.MAX_POKEMON]

        if action == "list":
            if not cur:
                embed = Embed(description="Your list is empty.", color=0x3498db)
                embed.set_footer(text=f"Use {ctx.prefix}{ctx.invoked_with} help for more information")
                return await ctx.reply(embed=embed, mention_author=False)

            entries = []
            for n in cur:
                emoji = ""
                if self.pe:
                    try:
                        pid = Pokemon_Subcogs.pokemon_name_to_id(n) if 'Pokemon_Subcogs' in globals() else None
                        if pid:
                            emoji = self.pe.get_emoji_for_pokemon(pid) or ""
                    except:
                        pass

                display_name = self.display_name_with_region(n)
                entries.append(f"{emoji} {display_name}" if emoji else display_name)

            if flags_obj:
                entries = await self.filter_by_flags(entries, flags_obj)

            title = "Your Shiny Hunt Target" if col == self.shiny_collection else "Your Pokémon Collection"
            return await self.paginate_and_send(ctx, entries, title, flags_obj=flags_obj)

        if action == "clear":
            await self.mongo.clear(col, uid)
            embed = Embed(description="🗑️ Cleared your Pokémon list.", color=0x3498db)
            embed.set_footer(text=f"Use {ctx.prefix}{ctx.invoked_with} help for more information")
            return await ctx.reply(embed=embed, mention_author=False)

        if not pokemon:
            embed = Embed(description=f"{self.ICONS['error']} Specify Pokémon name(s).", color=0xff0000)
            embed.set_footer(text=f"Use {ctx.prefix}{ctx.invoked_with} help for more information")
            return await ctx.reply(embed=embed, mention_author=False)

        names = []
        success, failed, exists = [], [], []
        all_suggestions = []

        for entry in pokemon.split(","):
            raw = entry.strip()
            norm = self.normalize_regional_name(raw.lower().replace(" ", "-"))
            names.append((raw, norm))

        cur = await self.mongo.list(col, uid)

        for raw, name in names:
            name_lower = name.lower()
            if name_lower in valid_slugs:
                matched_slug = name_lower
                pid = Pokemon_Subcogs.pokemon_name_to_id(matched_slug) if 'Pokemon_Subcogs' in globals() else None
                emoji = self.pe.get_emoji_for_pokemon(pid) or "" if self.pe and pid else ""

                if action == "add":
                    if max_one:
                        await self.mongo.replace(col, matched_slug, uid)
                        name_disp = self.display_name_with_region(matched_slug)
                        success.append(f"{self.ICONS['success']} Set your shiny hunt to {emoji} {name_disp}!")
                        break
                    if len(cur) >= self.MAX_POKEMON and matched_slug not in cur:
                        exists.append(f"{self.ICONS['error']} Max {self.MAX_POKEMON} Pokémon. {matched_slug.title()} not added.")
                        continue
                    ok = await self.mongo.add(col, matched_slug, uid)
                    (success if ok else exists).append(f"{self.ICONS['success'] if ok else self.ICONS['exists']} {emoji} {self.display_name_with_region(matched_slug)}")
                    if ok:
                        cur.append(matched_slug)
                elif action == "remove":
                    ok = await self.mongo.remove(col, matched_slug, uid)
                    (success if ok else exists).append(f"{self.ICONS['removed'] if ok else self.ICONS['not_found']} {emoji} {self.display_name_with_region(matched_slug)}")
            else:
                similar = self.find_similar_names(raw, valid_slugs_list)
                if similar:
                    for suggestion in similar:
                        all_suggestions.append((raw, suggestion))
                else:
                    failed.append(f"{self.ICONS['error']} Invalid Pokémon name: {raw}.")

        if success or failed or exists or all_suggestions:
            if success:
                initial_type = "success"
                initial_content = success
            elif failed:
                initial_type = "invalid"
                initial_content = failed
            elif exists:
                initial_type = "other"
                initial_content = exists
            else:
                initial_type = "suggestions"
                initial_content = []

            if initial_type == "suggestions":
                total = len(all_suggestions)
                unique = len(set(orig for orig, _ in all_suggestions))
                embed = Embed(
                    title="Pokémon Suggestions",
                    description=f"Found {total} suggestions for {unique} invalid name(s). Select the Pokémon to {action}:",
                    color=0x3498db
                )
            else:
                view_titles = {
                    "success": "✅ Successful Results",
                    "invalid": "❌ Invalid Results",
                    "other": "⛔ Other Results"
                }
                content = "\n".join(initial_content[:self.RESULTS_PER_PAGE])
                embed = Embed(
                    description=f"{view_titles[initial_type]}\n\n{content[:3900]}",
                    color=0x3498db
                )
                embed.set_footer(text="" if max_one else "Updated Your Pokémon Collection")

            view = UnifiedResultView(
                success_results=success,
                failed_results=failed,
                exists_results=exists,
                suggestions_list=all_suggestions,
                parent_cog=self,
                ctx=ctx,
                col=col,
                uid=uid,
                action=action,
                max_one=max_one
            )
            await ctx.reply(embed=embed, view=view, mention_author=False)

     except Exception as e:
        print(f"Error in handle_collection: {e}")
        embed = Embed(
            title="❌ Error",
            description="An error occurred while processing your request.",
            color=0xff0000
        )
        embed.set_footer(text=f"Use {ctx.prefix}{ctx.invoked_with} help for more information")
        await ctx.reply(embed=embed, mention_author=False)
    # MAIN COMMANDS
    @commands.command(name="collection", aliases=["cl"])
    async def collection_string(self, ctx, *, args: str = "list"):
        """Collection command with advanced string flag detection"""
        
        # Parse the input string
        action = "list"  # default
        pokemon_names = ""
        
        # Extract action if present
        args_lower = args.lower().strip()
        if args_lower.startswith(('add ', 'remove ', 'delete ', 'clear', 'help')):
            parts = args.split(' ', 1)
            action = parts[0].lower()
            if action == "delete":
                action = "remove"
            remaining_text = parts[1] if len(parts) > 1 else ""
        else:
            remaining_text = args
        
        # Handle help
        if action == "help" or args_lower == "help":
            help_embed = Embed(
                title="Collection Command Help",
                description="Use natural language to filter and search your Pokemon collection",
                color=0x3498db
            )
            help_embed.add_field(
                name="Regional Filters",
                value="alolan | galarian | hisuian | paldean | mega",
                inline=False
            )
            help_embed.add_field(
                name="Special Filters", 
                value="legendary | mythical | shiny",
                inline=False
            )
            help_embed.add_field(
                name="Search Filters",
                value="name eevee | type fire | region kanto",
                inline=False
            )
            help_embed.add_field(
                name="Utility Filters",
                value="limit 10 | skip 5 | max 20 | top 15",
                inline=False
            )
            help_embed.add_field(
                name="Examples",
                value=f".{ctx.invoked_with} alolan - Show Alolan forms\n"
                      f".{ctx.invoked_with} name eevee - Search for Eevee\n"
                      f".{ctx.invoked_with} legendary type dragon - Legendary Dragon types\n"
                      f".{ctx.invoked_with} hisuian limit 5 - First 5 Hisuian forms\n"
                      f".{ctx.invoked_with} add pikachu - Add Pikachu to collection\n"
                      f".{ctx.invoked_with} remove charizard mega - Remove Mega Charizard",
                inline=False
            )
            help_embed.add_field(
                name="Actions",
                value="list (default) | add | remove | clear | help",
                inline=False
            )
            help_embed.set_footer(text=f"Max {self.MAX_POKEMON} Pokémon per collection | {self.RESULTS_PER_PAGE} results per page")
            return await ctx.reply(embed=help_embed, mention_author=False)
        
        # Parse flags and extract Pokemon names
        flags_dict = self.flag_parser.parse_flags_from_string(remaining_text)
        pokemon_names, _ = self.flag_parser.extract_pokemon_names_from_string(remaining_text, action)
        
        # Handle the collection action
        await self.handle_collection(
            ctx, 
            self.collection_collection, 
            action, 
            pokemon_names if pokemon_names else None, 
            flags_obj=flags_dict
        )







class Pokemon_Emojis(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.GUILD_IDS = ["1216270817101611058","1216270002127114340","1216269922263371876","1340447626105065585", "1340447685685153852", "1340447747974762556", "1340447749111545998", "1340447923548459133", "1340447977340145717", "1340448026740916338", "1340448028196212807", "1340448148866469971", "1340448241069723749", "1340448280966074519", "1340448379729346560", "1340448496100053055", "1340448546603667619", "1340448595052335104", "1340448664157687830", "1340448723603296300", "1340448725314703390", "1340448849281548363", "1340449016089153598", "1340449082971390033", "1340449185933299723", "1340449231194030121", "1340449271366815806", "1340449391533625398", "1340449491765166231", "1340449540175691847", "1340698929922183300", "1340699061992558665", "1340699001011437610"]
        self.POKEMON_IMAGES_FOLDER = "data/commands/pokemon/pokemon_emojis"
        self.IMAGE_SOURCES = ["https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{}.png", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{}.png", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/{}.png"]
        self.emoji_json_path = "data/commands/pokemon/pokemon_emojis.json"
        self.owner_id = [1124389055598170182, 1320515815270907957]
        self.failed_downloads = set()
        self.emoji_mapping = self.load_emoji_mapping()
        os.makedirs(os.path.dirname(self.emoji_json_path), exist_ok=True)
        os.makedirs(self.POKEMON_IMAGES_FOLDER, exist_ok=True)


    def get_server_emoji_limit(self, guild):
        if guild.premium_tier >= 2:
            return 512 * 1024
        else:
            return 256 * 1024

    def resize_image_for_discord(self, image_data, guild=None):
        try:
            max_size_bytes = self.get_server_emoji_limit(guild) if guild else 256 * 1024
            img = Image.open(io.BytesIO(image_data))
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            max_dimension = 128
            quality = 95
            while max_dimension >= 32:
                img_resized = img.copy()
                img_resized.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                for current_quality in range(quality, 50, -5):
                    output = io.BytesIO()
                    img_resized.save(output, format='PNG', optimize=True, compress_level=9)
                    output_size = output.tell()
                    self.logger.debug(f"Resized to {max_dimension}x{max_dimension}, size: {output_size} bytes (limit: {max_size_bytes})")
                    if output_size <= max_size_bytes:
                        output.seek(0)
                        return output.read()
                max_dimension = int(max_dimension * 0.8)
            img_minimal = img.copy()
            img_minimal.thumbnail((32, 32), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            img_minimal.save(output, format='PNG', optimize=True, compress_level=9)
            output.seek(0)
            final_size = output.tell()
            self.logger.warning(f"Had to reduce image to minimal size: {final_size} bytes")
            output.seek(0)
            return output.read()
        except Exception as e:
            self.logger.error(f"Error resizing image: {e}")
            return None

    def validate_image_size(self, image_data, guild=None):
        if not image_data:
            return False, "No image data"
        max_size = self.get_server_emoji_limit(guild) if guild else 256 * 1024
        actual_size = len(image_data)
        if actual_size > max_size:
            return False, f"Image too large: {actual_size} bytes (limit: {max_size} bytes)"
        return True, "OK"

    def load_emoji_mapping(self):
        if os.path.exists(self.emoji_json_path):
            with open(self.emoji_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def get_pokemon_id(self, filename):
        return filename.split(".")[0].zfill(3)

    async def get_server_emoji_counts(self):
        self.logger.info("Fetching server emoji counts...")
        tasks = []
        for guild_id in self.GUILD_IDS:
            guild = self.bot.get_guild(int(guild_id))
            if guild and guild.me.guild_permissions.manage_emojis:
                tasks.append(self._get_single_server_count(guild, guild_id))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        counts = {r[0]: r[1] for r in results if not isinstance(r, Exception)}
        self.logger.info(f"Found {len(counts)} available servers")
        return counts

    async def _get_single_server_count(self, guild, guild_id):
        emoji_count = len(guild.emojis)
        max_emojis = 50 + (guild.premium_tier * 50)
        return guild_id, {'current': emoji_count, 'max': max_emojis, 'available': max_emojis - emoji_count, 'guild': guild}

    async def find_available_servers(self, min_slots=1):
        server_counts = await self.get_server_emoji_counts()
        available = [info['guild'] for info in server_counts.values() if info['available'] >= min_slots]
        self.logger.info(f"Found {len(available)} servers with {min_slots}+ available slots")
        return available

    async def download_pokemon_images(self):
        self.logger.info("Starting Pokemon image download process...")
        pokemon_ids = await self.fetch_all_pokemon_ids()
        existing_images = set(self.load_images())
        missing_pokemon_ids = [pid for pid in pokemon_ids if f"{str(pid).zfill(3)}.png" not in existing_images and pid not in self.failed_downloads]
        if not missing_pokemon_ids:
            self.logger.info("No missing images to download")
            return
        self.logger.info(f"Downloading {len(missing_pokemon_ids)} missing Pokemon images")
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=20)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            semaphore = asyncio.Semaphore(50)
            tasks = [self._download_with_semaphore(semaphore, session, pid) for pid in missing_pokemon_ids]
            results = []
            batch_size = 100
            for batch_start in range(0, len(tasks), batch_size):
                batch = tasks[batch_start:batch_start + batch_size]
                self.logger.info(f"Processing download batch {batch_start//batch_size + 1}/{(len(tasks) + batch_size - 1)//batch_size}")
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                results.extend(batch_results)
                await asyncio.sleep(0.1)
        successful = sum(1 for r in results if r is True)
        self.logger.info(f"Download complete: {successful}/{len(missing_pokemon_ids)} successful")

    async def _download_with_semaphore(self, semaphore, session, pokemon_id):
        async with semaphore:
            success = await self.download_single_image(session, pokemon_id)
            if not success:
                self.failed_downloads.add(pokemon_id)
                self.logger.warning(f"Failed to download Pokemon ID {pokemon_id}")
            return success

    async def download_single_image(self, session, pokemon_id):
        img_path = os.path.join(self.POKEMON_IMAGES_FOLDER, f"{str(pokemon_id).zfill(3)}.png")
        for source_url_template in self.IMAGE_SOURCES:
            img_url = source_url_template.format(pokemon_id)
            try:
                async with session.get(img_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        resized_content = await asyncio.get_event_loop().run_in_executor(None, self.resize_image_for_discord, content, None)
                        if resized_content:
                            is_valid, message = self.validate_image_size(resized_content)
                            if is_valid:
                                await asyncio.get_event_loop().run_in_executor(None, self._write_image_file, img_path, resized_content)
                                self.logger.debug(f"Successfully downloaded and resized Pokemon {pokemon_id}")
                                return True
                            else:
                                self.logger.error(f"Image validation failed for Pokemon {pokemon_id}: {message}")
                        else:
                            self.logger.error(f"Failed to resize image for Pokemon {pokemon_id}")
            except Exception as e:
                self.logger.debug(f"Error downloading {img_url}: {e}")
                continue
        return False

    def _write_image_file(self, path, content):
        with open(path, "wb") as f:
            f.write(content)

    def load_images(self):
        try:
            return os.listdir(self.POKEMON_IMAGES_FOLDER)
        except:
            return []

    async def fetch_all_pokemon_ids(self):
        self.logger.info("Fetching all Pokemon IDs from PokeAPI...")
        pokemon_ids = []
        invalid_ids = {10265, 10266, 10267, 10268, 10269}
        connector = aiohttp.TCPConnector(limit=50)
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            url = "https://pokeapi.co/api/v2/pokemon"
            all_pokemon = []
            page_count = 0
            while url:
                page_count += 1
                self.logger.info(f"Fetching Pokemon list page {page_count}...")
                async with session.get(url) as response:
                    if response.status != 200:
                        break
                    data = await response.json()
                    all_pokemon.extend(data["results"])
                    url = data.get("next")
            self.logger.info(f"Found {len(all_pokemon)} Pokemon entries across {page_count} pages")
            semaphore = asyncio.Semaphore(30)
            tasks = [self._fetch_pokemon_data(semaphore, session, result, invalid_ids) for result in all_pokemon]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            pokemon_ids = [r for r in results if isinstance(r, int)]
        self.logger.info(f"Valid Pokemon IDs collected: {len(pokemon_ids)}")
        return sorted(pokemon_ids)

    async def _fetch_pokemon_data(self, semaphore, session, result, invalid_ids):
        async with semaphore:
            try:
                async with session.get(result["url"]) as response:
                    if response.status == 200:
                        data = await response.json()
                        poke_id = data["id"]
                        if poke_id not in invalid_ids:
                            return poke_id
            except Exception as e:
                self.logger.debug(f"Error fetching Pokemon data for {result.get('name', 'unknown')}: {e}")
        return None

    async def list_existing_emojis(self, server):
        if not server or not server.me.guild_permissions.manage_emojis:
            return {}
        try:
            return {emoji.name: emoji.id for emoji in server.emojis}
        except:
            return {}

    async def upload_single_emoji(self, server, pokemon_id):
        existing_emojis = await self.list_existing_emojis(server)
        emoji_name = str(pokemon_id).zfill(3)
        if emoji_name in existing_emojis:
            return False
        if (str(server.id) in self.emoji_mapping and str(pokemon_id) in self.emoji_mapping[str(server.id)]):
            return False
        if pokemon_id in self.failed_downloads:
            return False
        emoji_image_path = os.path.join(self.POKEMON_IMAGES_FOLDER, f"{emoji_name}.png")
        try:
            emoji_data = await asyncio.get_event_loop().run_in_executor(None, self._read_image_file, emoji_image_path)
            if not emoji_data:
                self.logger.error(f"Could not read image file for Pokemon {pokemon_id}")
                return False
            is_valid, message = self.validate_image_size(emoji_data, server)
            if not is_valid:
                self.logger.error(f"Image validation failed for Pokemon {pokemon_id} on {server.name}: {message}")
                original_data = emoji_data
                resized_data = await asyncio.get_event_loop().run_in_executor(None, self.resize_image_for_discord, original_data, server)
                if resized_data:
                    is_valid, message = self.validate_image_size(resized_data, server)
                    if is_valid:
                        emoji_data = resized_data
                        await asyncio.get_event_loop().run_in_executor(None, self._write_image_file, emoji_image_path, resized_data)
                    else:
                        self.logger.error(f"Could not resize image small enough for Pokemon {pokemon_id}: {message}")
                        return False
                else:
                    return False
            emoji = await server.create_custom_emoji(name=emoji_name, image=emoji_data)
            if str(server.id) not in self.emoji_mapping:
                self.emoji_mapping[str(server.id)] = {}
            self.emoji_mapping[str(server.id)][str(pokemon_id)] = {"name": emoji_name, "id": emoji.id}
            await asyncio.get_event_loop().run_in_executor(None, self._save_emoji_mapping)
            self.logger.info(f"SUCCESS: Uploaded Pokemon {pokemon_id} to {server.name}")
            return True
        except discord.errors.HTTPException as e:
            if e.status == 429:
                retry_after = int(e.response.headers.get("Retry-After", 30))
                self.logger.warning(f"Rate limited, waiting {retry_after}s for Pokemon {pokemon_id}")
                await asyncio.sleep(retry_after)
                return await self.upload_single_emoji(server, pokemon_id)
            elif e.code == 30008:
                self.logger.warning(f"Server {server.name} at emoji capacity")
                return False
            elif e.code == 50045:
                self.logger.error(f"Asset too large for Pokemon {pokemon_id} on {server.name}: {len(emoji_data) if 'emoji_data' in locals() else 'unknown'} bytes")
                return False
            else:
                self.logger.error(f"HTTP Error uploading Pokemon {pokemon_id} to {server.name}: {e}")
                return False
        except Exception as e:
            self.logger.error(f"Unexpected error uploading Pokemon {pokemon_id} to {server.name}: {e}")
            return False

    def _read_image_file(self, path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except:
            return None

    def _save_emoji_mapping(self):
        with open(self.emoji_json_path, "w", encoding="utf-8") as f:
            json.dump(self.emoji_mapping, f, indent=2)

    async def create_emoji_image(self, pokemon_id):
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            return await self.download_single_image(session, pokemon_id)

    async def upload_emojis_for_server(self, servers, global_existing, embed_message=None, ctx=None, embed=None):
        self.logger.info("Starting emoji upload process...")
        available_servers = await self.find_available_servers(min_slots=5)
        if not available_servers:
            message = "ERROR: All servers at emoji capacity!"
            self.logger.warning(message)
            if embed_message and embed:
                embed.description = message
                await embed_message.edit(embed=embed)
            elif ctx:
                await ctx.send(message)
            return
        images = self.load_images()
        pokemon_ids = [int(self.get_pokemon_id(img)) for img in images if str(int(self.get_pokemon_id(img))) not in global_existing and int(self.get_pokemon_id(img)) not in self.failed_downloads]
        if not pokemon_ids:
            self.logger.info("No new Pokemon to upload")
            return
        self.logger.info(f"Uploading {len(pokemon_ids)} Pokemon emojis across {len(available_servers)} servers")
        emojis_uploaded = 0
        server_index = 0
        upload_semaphore = asyncio.Semaphore(5)
        
        async def upload_with_server_rotation(pokemon_id):
            nonlocal server_index, emojis_uploaded
            async with upload_semaphore:
                for attempt in range(len(available_servers)):
                    if not available_servers:
                        return False
                    server = available_servers[server_index % len(available_servers)]
                    current_count = len(await self.list_existing_emojis(server))
                    max_emojis = 50 + (server.premium_tier * 50)
                    if current_count >= max_emojis:
                        available_servers.remove(server)
                        self.logger.info(f"Server {server.name} removed - at capacity")
                        continue
                    result = await self.upload_single_emoji(server, pokemon_id)
                    if result:
                        emojis_uploaded += 1
                        server_index += 1
                        await asyncio.sleep(0.5)
                        return True
                    server_index += 1
                return False

        batch_size = 10
        total_batches = (len(pokemon_ids) + batch_size - 1) // batch_size
        for i in range(0, len(pokemon_ids), batch_size):
            batch = pokemon_ids[i:i + batch_size]
            batch_num = i // batch_size + 1
            self.logger.info(f"Processing upload batch {batch_num}/{total_batches} ({len(batch)} Pokemon)")
            tasks = [upload_with_server_rotation(pid) for pid in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            if not available_servers:
                self.logger.warning("No more available servers, stopping upload")
                break
            if embed_message and embed:
                embed.description = f"Uploading... {emojis_uploaded} emojis added (Batch {batch_num}/{total_batches})"
                await embed_message.edit(embed=embed)
            await asyncio.sleep(2)
        
        final_message = f"SUCCESS: Upload complete! Added {emojis_uploaded}/{len(pokemon_ids)} emojis"
        self.logger.info(final_message)
        if embed_message and embed:
            embed.description = final_message
            embed.color = discord.Color.green()
            await embed_message.edit(embed=embed)

    @commands.command(hidden=True)
    async def create_emojis(self, ctx):
        if ctx.author.id not in self.owner_id:
            await ctx.reply("ERROR: No permission")
            return
        self.logger.info(f"Emoji creation command started by {ctx.author}")
        embed = discord.Embed(description="Starting emoji creation process...", color=discord.Color.blue())
        initial_message = await ctx.send(embed=embed)
        self.emoji_mapping = self.load_emoji_mapping()
        global_existing = set()
        for server_data in self.emoji_mapping.values():
            global_existing.update(server_data.keys())
        self.logger.info(f"Found {len(global_existing)} existing emojis")
        servers = [self.bot.get_guild(int(gid)) for gid in self.GUILD_IDS]
        servers = [s for s in servers if s]
        server_counts = await self.get_server_emoji_counts()
        available_servers = [info['guild'] for info in server_counts.values() if info['available'] > 0]
        if not available_servers:
            embed.description = "ERROR: All servers at capacity!"
            embed.color = discord.Color.red()
            await initial_message.edit(embed=embed)
            return
        embed.description = "Downloading Pokemon images..."
        embed.color = discord.Color.orange()
        await initial_message.edit(embed=embed)
        await self.download_pokemon_images()
        embed.description = "Uploading emojis to servers..."
        embed.color = discord.Color.yellow()
        await initial_message.edit(embed=embed)
        await self.upload_emojis_for_server(servers, global_existing, embed_message=initial_message, ctx=ctx, embed=embed)

    @commands.command(hidden=True)
    async def server_status(self, ctx):
        if ctx.author.id not in self.owner_id:
            await ctx.reply("ERROR: No permission")
            return
        self.logger.info(f"Server status requested by {ctx.author}")
        server_counts = await self.get_server_emoji_counts()
        embed = discord.Embed(title="Server Emoji Status", color=discord.Color.blue())
        total_emojis = sum(info['current'] for info in server_counts.values())
        total_capacity = sum(info['max'] for info in server_counts.values())
        embed.description = f"**Total: {total_emojis}/{total_capacity} emojis used**"
        for guild_id, info in server_counts.items():
            guild = info['guild']
            percentage = (info['current'] / info['max']) * 100
            status_emoji = "RED" if percentage >= 90 else "YELLOW" if percentage >= 70 else "GREEN"
            status = f"{status_emoji} {info['current']}/{info['max']} ({info['available']} free)"
            embed.add_field(name=guild.name[:20], value=status, inline=True)
        await ctx.send(embed=embed)

    def get_emoji_for_pokemon(self, pokemon_id):
        pokemon_id_str = str(pokemon_id).zfill(3)
        for server_id, server_data in self.emoji_mapping.items():
            if str(pokemon_id) in server_data:
                emoji_data = server_data[str(pokemon_id)]
                return f"<:{emoji_data['name']}:{emoji_data['id']}>"
        return None

    def call_emoji(self, emoji_mapping, pokemon_id):
        pokemon_id = pokemon_id['id']
        for server_id, server_data in emoji_mapping.items():
            if str(pokemon_id) in server_data:
                emoji_data = server_data[str(pokemon_id)]
                return f"<:{emoji_data['name']}:{int(emoji_data['id'])}>"
        return None

    @commands.command(hidden=True)
    async def get_pokemon_emoji(self, ctx, pokemon_id: int):
        emoji_str = self.get_emoji_for_pokemon(pokemon_id)
        if emoji_str:
            await ctx.send(f"Pokemon emoji: {emoji_str}")
        else:
            await ctx.send(f"ERROR: No emoji found for Pokemon ID {pokemon_id}")

    @commands.command(hidden=True)
    async def force_download(self, ctx, start_id: int = 1, end_id: int = 2000):
        if ctx.author.id not in self.owner_id:
            return
        self.logger.info(f"Force download requested by {ctx.author} for IDs {start_id}-{end_id}")
        embed = discord.Embed(description=f"Force downloading Pokemon {start_id}-{end_id}...", color=discord.Color.orange())
        msg = await ctx.send(embed=embed)
        pokemon_ids = list(range(start_id, end_id + 1))
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            semaphore = asyncio.Semaphore(60)
            tasks = [self._download_with_semaphore(semaphore, session, pid) for pid in pokemon_ids]
            results = []
            batch_size = 50
            total_batches = (len(tasks) + batch_size - 1) // batch_size
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i + batch_size]
                batch_num = i // batch_size + 1
                embed.description = f"Downloading batch {batch_num}/{total_batches}..."
                await msg.edit(embed=embed)
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                results.extend(batch_results)
        successful = sum(1 for r in results if r)
        embed.description = f"SUCCESS: Downloaded {successful}/{len(pokemon_ids)} images"
        embed.color = discord.Color.green()
        await msg.edit(embed=embed)
        self.logger.info(f"Force download complete: {successful}/{len(pokemon_ids)} successful")

            
            
            
            
            
            
            
            
class Pokemon_Subcogs:
    
 @staticmethod
 def pokemon_name_to_id(pokemon_name, file_path="data/commands/pokemon/pokemon_names.csv"):
    try:
        with open(file_path, mode="r", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if row["name"].lower() == pokemon_name.lower():
                    return row["id"]
    except Exception as e:
        print(f"Error: {e}")
        return None
    
class MongoHelper:
    def __init__(self, db): self.db = db
    async def add(self, col, pokemon, uid):
        c, d = self.db[col], await self.db[col].find_one({"user_id": uid})
        if not d: await c.insert_one({"user_id": uid, "pokemon": [pokemon]}); return True
        if pokemon in d["pokemon"]: return False
        await c.update_one({"user_id": uid}, {"$push": {"pokemon": pokemon}}); return True
    async def remove(self, col, pokemon, uid):
        d = await self.db[col].find_one({"user_id": uid})
        if not d or pokemon not in d["pokemon"]: return False
        await self.db[col].update_one({"user_id": uid}, {"$pull": {"pokemon": pokemon}}); return True
    async def list(self, col, uid):
        d = await self.db[col].find_one({"user_id": uid})
        return d["pokemon"] if d else []
    async def replace(self, col, pokemon, uid):
        await self.db[col].update_one({"user_id": uid}, {"$set": {"pokemon": [pokemon]}}, upsert=True); return True
    async def clear(self, col, uid):
        await self.db[col].update_one({"user_id": uid}, {"$set": {"pokemon": []}}); return True

class PokemonNameHelper:
    def __init__(self, csv_file=None):
        self.csv_file = csv_file
        self.rare, self.regional = [], []

    def load_data(self):
        try:
            with open(self.csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if row[0]: self.rare.append(row[0].lower().strip())
                    if row[1]: self.regional.append(row[1].lower().strip())
        except FileNotFoundError:
            self.rare, self.regional = [], []

    def transform_name(self, name):
        map_ = {"alolan":"-alola","galarian":"-galar","hisuian":"-hisui","paldean":"-paldea","mega":"-mega"}
        name_clean = re.sub(r'[^a-zA-Z\s]', '', name)
        lower = name_clean.lower()
        for k,v in map_.items():
            if k in lower:
                parts = name_clean.split()
                base = parts[1].capitalize() if len(parts)>1 else parts[0].capitalize()
                return f"{base.lower()}{v}", k
        return name_clean, None
    
    def reverse_transform_name(self, name):
     rev_map = {"-alola": "Alolan", "-galar": "Galarian", "-hisui": "Hisuian", "-paldea": "Paldean", "-mega": "Mega"}
     n = name.lower()
     for suf, pre in rev_map.items():
        if n.endswith(suf):
            base = name[:-len(suf)]
            return f"{pre} {base}", pre
     return name, ''
    
    def check_match(self, name):
        rare_match = next((p for p in self.rare if fuzz.ratio(name, p) > 90), None)
        regional_match = next((p for p in self.regional if fuzz.ratio(name, p) > 90), None)
        return rare_match, regional_match


class PokemonNameHelperCollection:
    def transform_name(self, name):
        name = name.lower().strip()
        if any(name.endswith(suffix) for suffix in CollectionViewUI.REGIONAL_SUFFIXES):
            return name, name
        return name, name




























class CollectionViewUI(View):
    REGIONAL_SUFFIXES = ("-alola", "-galar", "-hisui", "-paldea")
    REGIONAL_PREFIXES = {
        "alolan": "-alola",
        "galarian": "-galar",
        "hisuian": "-hisui",
        "paldean": "-paldea"
    }
    REGION_EMOJIS = {
        "paldea": "<:Paldea:1212335178714980403>",
        "sinnoh": "<:Sinnoh:1212335180459544607>",
        "alola": "<:Alola:1212335185228472411>",
        "kalos": "<:Kalos:1212335190656024608>",
        "galar": "<:Galar:1212335192740470876>",
        "pasio": "<:848495108667867139:1212335194628034560>",
        "hoenn": "<:Hoenn:1212335197304004678>",
        "unova": "<:Unova:1212335199095095306>",
        "kanto": "<:Kanto:1212335202341363713>",
        "johto": "<:Kanto:1212335202341363713>"
    }
    FILTER_KEYS = ["rare", "regional", "show_all"]
    FILTER_LABELS = {"rare": "Rare", "regional": "Regional", "show_all": "Showing All"}
    NAV_BUTTONS = [("⏮", 0), ("◀", 1), ("▶", 2), ("⏭", 3)]
    ALL_REGIONS = set(REGION_EMOJIS.keys())

    def __init__(self, ctx, entries, title):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.entries = entries
        self.title = title
        self.page = 0
        self.filters = {k: False for k in self.FILTER_KEYS}
        self.selected_regions = set()
        self.ph = PokemonNameHelperCollection()
        self.description_path = "data/commands/pokemon/pokemon_description.csv"
        self.special_path = "data/commands/pokemon/pokemon_special_names.csv"
        self.name_to_region = self._load_region_map()
        self.rare_names, self.regional_names = self._load_special_names()
        # Do NOT update regional_names with name_to_region keys — ONLY from special CSV!
        self.user_regions = self._extract_user_regions()
        self.has_rare = any(self._is_rare_pokemon(e) for e in self.entries)
        self.has_regional = any(self._is_regional_pokemon(e) for e in self.entries)
        self._update_filtered_entries()
        self._update_embeds()
        self._build_components()

    def _extract_pokemon_name(self, entry):
        return re.sub(r'<:[^:]+:\d+>\s*', '', entry).strip()

    def _normalize_name_to_slug(self, name):
        clean = name.lower().strip()
        for prefix, suffix in self.REGIONAL_PREFIXES.items():
            if clean.startswith(f"{prefix} "):
                base_name = clean[len(prefix) + 1:]
                return base_name + suffix
        return clean

    def _normalize_name(self, name):
        n = self._extract_pokemon_name(name) if '<:' in name else name.lower().strip()
        return self._normalize_name_to_slug(n)

    def convert_regional_name(self, name: str) -> str:
        region_map = {
            "alolan": "-alola",
            "galarian": "-galar",
            "hisuian": "-hisui",
            "paldean": "-paldea"
        }
        name_lower = name.lower().strip()
        for prefix, suffix in region_map.items():
            if name_lower.startswith(f"{prefix} "):
                base_name = name_lower[len(prefix) + 1:]
                return base_name + suffix
        return name_lower

    def _load_region_map(self):
        region_map = {}
        try:
            with open(self.description_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    slug = row["slug"].lower()
                    region = row.get("region", "").strip().lower()
                    if region in self.ALL_REGIONS:
                        region_map[slug] = region
        except Exception:
            pass
        return region_map

    def _load_special_names(self):
        rare, regional = set(), set()
        try:
            with open(self.special_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fields = {k.lower().replace(" ", "").replace("é", "e"): k for k in reader.fieldnames}
                rare_col = fields.get("rarepokemon", "")
                regional_col = fields.get("regionalpokemon", "")
                for row in reader:
                    rare_name = row.get(rare_col, "").strip().lower()
                    regional_name = row.get(regional_col, "").strip().lower()
                    if rare_name:
                        rare.add(rare_name)
                    if regional_name:
                        # Only add raw names exactly as in Regional Pokémon column
                        regional.add(regional_name)
        except Exception as e:
            print(f"Error loading special names: {e}")
            pass
        return rare, regional

    def _extract_user_regions(self):
        regions = set()
        for e in self.entries:
            name = self._extract_pokemon_name(e)
            slug = self._normalize_name_to_slug(name)
            try:
                slug, _ = self.ph.transform_name(slug)
            except:
                pass
            if not any(slug.endswith(sfx) for sfx in self.REGIONAL_SUFFIXES):
                region = self.name_to_region.get(slug)
                if region:
                    regions.add(region)
        return sorted(regions)

    def _is_rare_pokemon(self, entry):
        name = self._extract_pokemon_name(entry)
        slug = self._normalize_name_to_slug(name)
        try:
            slug, _ = self.ph.transform_name(slug)
            return slug in self.rare_names
        except:
            return slug in self.rare_names

    def _is_regional_pokemon(self, entry):
        name = self._extract_pokemon_name(entry)
        raw_name = self.convert_regional_name(name)
        try:
            raw_name, _ = self.ph.transform_name(raw_name)
        except:
            pass
        return raw_name in self.regional_names

    def filter_rare_and_regional(self, type: str, entries: list[str]) -> list[str]:
        ready = []
        for e in entries:
            name = self._extract_pokemon_name(e)
            slug = self._normalize_name_to_slug(name)
            try:
                slug, _ = self.ph.transform_name(slug)
            except:
                pass
            region = self.name_to_region.get(slug) if not any(slug.endswith(s) for s in self.REGIONAL_SUFFIXES) else None

            if type == "rare":
                if slug in self.rare_names:
                    ready.append(e)
            elif type == "regional":
                raw_name = self.convert_regional_name(name)
                try:
                    raw_name, _ = self.ph.transform_name(raw_name)
                except:
                    pass
                print(f"[DEBUG] Regional filter check: Entry='{e}', Name='{name}', Raw='{raw_name}', In regional_names={raw_name in self.regional_names}")
                if raw_name in self.regional_names:
                    ready.append(e)
            elif type == "region_filter":
                if self.selected_regions:
                    if region in self.selected_regions:
                        ready.append(e)
                else:
                    ready.append(e)
            else:
                ready.append(e)

        if type == "regional":
            print(f"[DEBUG] Regional filter result count: {len(ready)} out of {len(entries)} entries")
            print(f"[DEBUG] After regional filter: {len(ready)} entries")

        return ready

    def _update_filtered_entries(self):
        if self.filters["show_all"]:
            self.filtered_entries = self.entries[:]
            return
        entries = self.entries[:]
        if self.filters["rare"]:
            print("[DEBUG] Filter 'rare' toggled to True")
            entries = self.filter_rare_and_regional("rare", entries)
        if self.filters["regional"]:
            print("[DEBUG] Filter 'regional' toggled to True")
            entries = self.filter_rare_and_regional("regional", entries)
        if self.selected_regions:
            entries = self.filter_rare_and_regional("region_filter", entries)
        self.filtered_entries = entries

    def _update_embeds(self):
        chunks = [self.filtered_entries[i:i+CHUNK_SIZE] for i in range(0, len(self.filtered_entries), CHUNK_SIZE)] or [[]]
        self.embeds = []
        for i, chunk in enumerate(chunks):
            start = i * CHUNK_SIZE + 1
            end = start + len(chunk) - 1
            active = [self.FILTER_LABELS[k] for k in self.FILTER_KEYS if k != "show_all" and self.filters[k]]
            if self.selected_regions:
                active.append(f"Regions: {', '.join(sorted(self.selected_regions))}")
            if self.filters["show_all"]:
                active.append(self.FILTER_LABELS["show_all"])
            footer = f"Page {i+1}/{len(chunks)} | Showing entries {start}–{end} out of {len(self.filtered_entries)} | {' | '.join(active) or 'No filters active'}"
            embed = Embed(
                title=self.title,
                description="\n".join(chunk) or "No Pokémon found.",
                color=self.primary_color() if chunk else 0xFF0000
            )
            embed.set_footer(text=footer)
            self.embeds.append(embed)
        self.page = min(self.page, len(self.embeds) - 1)

    def _build_components(self):
        self.clear_items()
        last = len(self.embeds) - 1
        for label, idx in self.NAV_BUTTONS:
            disabled = (idx in (0, 1) and self.page == 0) or (idx in (2, 3) and self.page == last)
            b = Button(label=label, style=ButtonStyle.gray, disabled=disabled, row=0)
            b.callback = [self._first, self._prev, self._next, self._last][idx]
            self.add_item(b)
        region_button_labels = set()
        for e in self.entries:
            name = self._extract_pokemon_name(e).lower()
            for region in self.ALL_REGIONS:
                if name.startswith(region + " "):
                    region_button_labels.add(region)
        for region in sorted(region_button_labels):
            b = Button(
                label=region.capitalize(),
                style=ButtonStyle.primary if region in self.selected_regions else ButtonStyle.secondary,
                row=1
            )
            b.callback = self._region_button_callback(region)
            self.add_item(b)
        region_opts = [r for r in self.user_regions if r not in region_button_labels]
        opts = [
            SelectOption(
                label=r.capitalize(),
                value=r,
                emoji=self.REGION_EMOJIS.get(r),
                default=r in self.selected_regions
            )
            for r in region_opts
        ]
        if opts:
            class RegionSelect(Select):
                def __init__(s):
                    super().__init__(placeholder="Select Regions...", options=opts, min_values=0, max_values=len(opts), row=2)
                async def callback(s, interaction):
                    await self._region_select(interaction, s.values)
            self.add_item(RegionSelect())
        if self.has_rare:
            b = Button(
                label=self.FILTER_LABELS["rare"],
                style=ButtonStyle.success if self.filters["rare"] else ButtonStyle.secondary,
                row=3
            )
            b.callback = self._toggle("rare")
            self.add_item(b)
        if self.has_regional:
            b = Button(
                label=self.FILTER_LABELS["regional"],
                style=ButtonStyle.success if self.filters["regional"] else ButtonStyle.secondary,
                row=3
            )
            b.callback = self._toggle("regional")
            self.add_item(b)
        if any(self.filters[k] for k in ("rare", "regional")) or self.selected_regions:
            b = Button(
                label=self.FILTER_LABELS["show_all"],
                style=ButtonStyle.primary if self.filters["show_all"] else ButtonStyle.secondary,
                row=3
            )
            b.callback = self._toggle("show_all", clear_others=True)
            self.add_item(b)

    def _region_button_callback(self, region):
        async def cb(interaction):
            if region in self.selected_regions:
                self.selected_regions.remove(region)
            else:
                self.selected_regions.add(region)
            self.filters["show_all"] = False
            self._update_filtered_entries()
            self._update_embeds()
            self._build_components()
            await interaction.response.edit_message(embed=self.embeds[self.page], view=self)
        return cb

    def _toggle(self, key, clear_others=False):
        async def cb(interaction):
            if clear_others:
                self.filters = {k: False for k in self.filters}
                self.selected_regions.clear()
            self.filters[key] = not self.filters[key]
            self._update_filtered_entries()
            self._update_embeds()
            self._build_components()
            await interaction.response.edit_message(embed=self.embeds[self.page], view=self)
        return cb

    async def _region_select(self, interaction, values):
        self.selected_regions = set(values)
        self.filters["show_all"] = False
        self._update_filtered_entries()
        self._update_embeds()
        self._build_components()
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    async def _first(self, interaction):
        self.page = 0
        await self._refresh(interaction)

    async def _prev(self, interaction):
        self.page = max(0, self.page - 1)
        await self._refresh(interaction)

    async def _next(self, interaction):
        self.page = min(self.page + 1, len(self.embeds) - 1)
        await self._refresh(interaction)

    async def _last(self, interaction):
        self.page = len(self.embeds) - 1
        await self._refresh(interaction)

    async def _refresh(self, interaction):
        self._update_embeds()
        self._build_components()
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.author

    @staticmethod
    def primary_color():
        return 0x3498db






















































































class UnifiedResultView(View):
    def __init__(self, success_results, failed_results, exists_results, suggestions_list=None, parent_cog=None, ctx=None, col=None, uid=None, action=None, max_one=False):
        super().__init__(timeout=300)
        
        # Store all instance variables first
        self.parent_cog = parent_cog  # Store reference to parent cog
        self.ctx = ctx
        self.col = col
        self.uid = uid
        self.action = action
        self.max_one = max_one
        
        self.results = {
            "success": success_results,
            "invalid": failed_results,
            "other": exists_results
        }
        self.suggestions = suggestions_list or []
        self.current_view = "success"  # Default to success view
        self.current_page = 0
        self.items_per_page = self.parent_cog.RESULTS_PER_PAGE if parent_cog else 10
        self.selected_items = set()
        self.show_suggestions = bool(suggestions_list)
        
        # If no success results, default to first available type
        if not success_results:
            if failed_results:
                self.current_view = "invalid"
            elif exists_results:
                self.current_view = "other"
            elif suggestions_list:
                self.current_view = "suggestions"
                self.show_suggestions = True
        
        self.update_components()

    def get_pages(self, result_type):
        if result_type == "suggestions":
            return [self.suggestions[i:i + 25] for i in range(0, len(self.suggestions), 25)]
        data = self.results[result_type]
        if not data:
            return [[]]
        return [data[i:i + self.items_per_page] for i in range(0, len(data), self.items_per_page)]

    def update_components(self):
        self.clear_items()
        
        # Result type buttons (row 0)
        if self.results["success"]:
            btn_success = Button(
                label=f"✅ Success ({len(self.results['success'])})",
                style=ButtonStyle.success if self.current_view == "success" else ButtonStyle.secondary,
                row=0
            )
            btn_success.callback = lambda i: self.switch_view(i, "success")
            self.add_item(btn_success)
        
        if self.results["invalid"]:
            btn_invalid = Button(
                label=f"❌ Invalid ({len(self.results['invalid'])})",
                style=ButtonStyle.danger if self.current_view == "invalid" else ButtonStyle.secondary,
                row=0
            )
            btn_invalid.callback = lambda i: self.switch_view(i, "invalid")
            self.add_item(btn_invalid)
        
        if self.results["other"]:
            btn_other = Button(
                label=f"⛔ Other ({len(self.results['other'])})",
                style=ButtonStyle.primary if self.current_view == "other" else ButtonStyle.secondary,
                row=0
            )
            btn_other.callback = lambda i: self.switch_view(i, "other")
            self.add_item(btn_other)

        if self.suggestions:
            btn_suggestions = Button(
                label=f"🔍 Suggestions ({len(self.suggestions)})",
                style=ButtonStyle.primary if self.current_view == "suggestions" else ButtonStyle.secondary,
                row=0
            )
            btn_suggestions.callback = lambda i: self.switch_view(i, "suggestions")
            self.add_item(btn_suggestions)

        if self.current_view == "suggestions":
            # Add select dropdown for suggestions
            pages = self.get_pages("suggestions")
            if pages and pages[self.current_page]:
                page_items = pages[self.current_page]
                options = []
                for original_name, suggestion in page_items:
                    pid = Pokemon_Subcogs.pokemon_name_to_id(suggestion)
                    emoji = self.parent_cog.pe.get_emoji_for_pokemon(pid)
                    display_name = self.parent_cog.display_name_with_region(suggestion)
                    option_label = f"{display_name} (for '{original_name}')"
                    if len(option_label) > 100:  # Discord limit
                        option_label = f"{display_name[:80]}... (for '{original_name}')"
                    
                    option = SelectOption(
                        label=option_label,
                        value=f"{original_name}|{suggestion}",
                        emoji=emoji,
                        default=f"{original_name}|{suggestion}" in self.selected_items
                    )
                    options.append(option)
                
                select = Select(
                    placeholder=f"Select Pokémon to {self.action}",
                    options=options,
                    min_values=0,
                    max_values=len(options),
                    row=1
                )
                select.callback = self.select_callback
                self.add_item(select)

            # Action buttons for suggestions (row 2)
            confirm_btn = Button(
                label=f"Confirm {self.action.title()} ({len(self.selected_items)})", 
                style=ButtonStyle.success, 
                disabled=len(self.selected_items) == 0, 
                row=2
            )
            cancel_btn = Button(label="Cancel", style=ButtonStyle.danger, row=2)
            
            confirm_btn.callback = self.confirm_action
            cancel_btn.callback = self.cancel_action
            
            self.add_item(confirm_btn)
            self.add_item(cancel_btn)

        # Page navigation buttons (row 3 for suggestions, row 1 for others)
        pages = self.get_pages(self.current_view)
        nav_row = 5 if self.current_view == "suggestions" else 1
        
        if len(pages) > 1:
            prev_btn = Button(
                label="◀",
                style=ButtonStyle.secondary,
                disabled=self.current_page == 0,
                row=nav_row
            )
            next_btn = Button(
                label="▶",
                style=ButtonStyle.secondary,
                disabled=self.current_page >= len(pages) - 1,
                row=nav_row
            )
            page_btn = Button(
                label=f"Page {self.current_page + 1}/{len(pages)}",
                style=ButtonStyle.secondary,
                disabled=True,
                row=nav_row
            )
            
            prev_btn.callback = lambda i: self.change_page(i, -1)
            next_btn.callback = lambda i: self.change_page(i, 1)
            
            self.add_item(prev_btn)
            self.add_item(page_btn)
            self.add_item(next_btn)

    async def select_callback(self, interaction: Interaction):
        # Update selected items
        selected_values = set(interaction.data['values'])
        pages = self.get_pages("suggestions")
        page_items = pages[self.current_page] if pages else []
        page_values = {f"{orig}|{sugg}" for orig, sugg in page_items}
        
        # Remove deselected items from this page
        self.selected_items = {item for item in self.selected_items if item not in page_values}
        # Add selected items from this page
        self.selected_items.update(selected_values)
        
        self.update_components()
        await interaction.response.edit_message(view=self)

    async def confirm_action(self, interaction: Interaction):
        # Process selected items
        current_list = await self.parent_cog.mongo.list(self.col, self.uid)
        new_success = []
        new_other = []
        
        for selected_item in self.selected_items:
            original_name, selected_slug = selected_item.split("|", 1)
            
            if self.action == "add":
                if self.max_one:
                    await self.parent_cog.mongo.replace(self.col, selected_slug, self.uid)
                    pid = Pokemon_Subcogs.pokemon_name_to_id(selected_slug)
                    emoji = self.parent_cog.pe.get_emoji_for_pokemon(pid) or ""
                    name_disp = self.parent_cog.display_name_with_region(selected_slug)
                    new_success.append(f"`{self.parent_cog.ICONS['success']}` Set your shiny hunt to {emoji} {name_disp}!")
                    break
                else:
                    if len(current_list) >= MAX_POKEMON and selected_slug not in current_list:
                        new_other.append(f"`{self.parent_cog.ICONS['error']}` Max {MAX_POKEMON} Pokémon. `{selected_slug.title()}` not added.")
                        continue
                    ok = await self.parent_cog.mongo.add(self.col, selected_slug, self.uid)
                    pid = Pokemon_Subcogs.pokemon_name_to_id(selected_slug)
                    emoji = self.parent_cog.pe.get_emoji_for_pokemon(pid) or ""
                    icon = self.parent_cog.ICONS['success'] if ok else self.parent_cog.ICONS['exists']
                    name_disp = self.parent_cog.display_name_with_region(selected_slug)
                    result_text = f"`{icon}` {emoji} {name_disp}"
                    if ok:
                        new_success.append(result_text)
                        current_list.append(selected_slug)
                    else:
                        new_other.append(result_text)
                        
            elif self.action == "remove":
                ok = await self.parent_cog.mongo.remove(self.col, selected_slug, self.uid)
                pid = Pokemon_Subcogs.pokemon_name_to_id(selected_slug)
                emoji = self.parent_cog.pe.get_emoji_for_pokemon(pid) or ""
                icon = self.parent_cog.ICONS['removed'] if ok else self.parent_cog.ICONS['not_found']
                name_disp = self.parent_cog.display_name_with_region(selected_slug)
                result_text = f"`{icon}` {emoji} {name_disp}"
                if ok:
                    new_success.append(result_text)
                else:
                    new_other.append(result_text)

        # Update results and switch view
        self.results["success"].extend(new_success)
        self.results["other"].extend(new_other)
        self.suggestions = []  # Clear suggestions
        self.selected_items = set()
        self.current_view = "success" if new_success else ("other" if new_other else "success")
        self.current_page = 0
        
        await self.update_message(interaction)

    async def cancel_action(self, interaction: Interaction):
        # Clear suggestions and show results
        self.suggestions = []
        self.current_view = "success" if self.results["success"] else ("invalid" if self.results["invalid"] else "other")
        self.current_page = 0
        await self.update_message(interaction)

    async def switch_view(self, interaction: Interaction, view_type):
        self.current_view = view_type
        self.current_page = 0
        await self.update_message(interaction)

    async def change_page(self, interaction: Interaction, direction):
        pages = self.get_pages(self.current_view)
        self.current_page = max(0, min(len(pages) - 1, self.current_page + direction))
        await self.update_message(interaction)

    async def update_message(self, interaction: Interaction):
        if self.current_view == "suggestions":
            # Show suggestions selection interface
            total_suggestions = len(self.suggestions)
            unique_originals = len(set(orig for orig, _ in self.suggestions))
            
            embed = Embed(
                title="Pokémon Selection",
                description=f"Found {total_suggestions} suggestions for {unique_originals} invalid name(s). "
                           f"Select the Pokémon you want to {self.action}:",
                color=primary_color()
            )
        else:
            # Show results
            pages = self.get_pages(self.current_view)
            current_data = pages[self.current_page] if pages else []
            content = "\n".join(current_data) if current_data else "No entries to display."
            
            view_names = {
                "success": "✅ Successful Results",
                "invalid": "❌ Invalid Results",
                "other": "⛔ Other Results"
            }
            header = f"**{view_names[self.current_view]}**\n\n"
            
            embed = Embed(description=header + content[:3900], color=primary_color())
            
            if len(pages) > 1:
                embed.set_footer(text=f"Page {self.current_page + 1} of {len(pages)} • {len(current_data)} entries shown")
            else:
                embed.set_footer(text="" if self.max_one else "Updated Your Pokemon Collection")
        
        self.update_components()
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: Interaction):
        return interaction.user == self.ctx.author













