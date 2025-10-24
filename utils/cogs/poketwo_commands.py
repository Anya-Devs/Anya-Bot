import os, re, csv,aiohttp, traceback, json

from tqdm import tqdm
from imports.log_imports import *
from utils.subcogs.pokemon import *
from imports.discord_imports import *
from data.local.const import *

pt_help_description = (
    "Collection | {}pt cl\n"
    "- `{}pt cl add (eevee, pikachu, vulpix)` (add Pokémon | 50 max)\n"
    "- `{}pt cl remove (eevee, vulpix)` (remove Pokémon)\n"
    "- `{}pt cl` (view collection)\n"
    "- `{}pt cl clear` (clear collection)\n\n"
    
    "Shiny Hunt | {}pt sh\n"
    "- `{}pt sh (alolan vulpix)` (set shiny hunt)\n"
    "- `{}pt sh remove` (remove shiny hunt)\n"
    "- `{}pt sh` (view shiny hunt)\n\n"
    
    "Type Ping | {}pt tp\n"
    "- Manage pings for Pokémon types (fire, water, grass, etc.)\n\n"
    
    "Quest Ping | {}pt qp\n"
    "- Manage pings for Pokémon regions (Kanto, Alola, Galar, etc.)\n\n"
    
    "Configuration | {}pt config\n"
    "- Opens interactive menu to toggle features & set rare/regional roles.\n"
    "- Use the select menus to enable/disable spawn options or assign roles.\n"
    "- Requires Manage Server permission.\n\n"
    
    "Starboard | {}pt starboard\n"
    "- Configure starboard settings (Manage Channel required)\n\n"
    
    "Shiny Protection | {}pt shinychannel\n"
    "- `{}pt sc` (view protected channels)\n"
    "- `{}pt sc <#channel>` (set protected channel)\n"
    "- `{}pt sc log <#channel>` (set log channel)\n"
    "- `{}pt sc log remove` (remove log)\n"
    "- `{}pt sc log` (view log channel)\n"
)

MAX_POKEMON, CHUNK_SIZE, RESULTS_PER_PAGE, MIN_SIMILARITY_RATIO  = 50, 15, 10, 0.65



class PokemonDataManager:
    def __init__(self, mongo_client, pokemon_names_csv, pokemon_types_csv, pokemon_rarity_csv):
        self.mongo = mongo_client
        self.pokemon_names_csv = pokemon_names_csv
        self.pokemon_types_csv = pokemon_types_csv
        self.pokemon_rarity_csv = pokemon_rarity_csv
        self.pokemon_species_url = "https://pokeapi.co/api/v2/pokemon-species"
        self._valid_slugs = None
        self._pokemon_types = None
        self._pokemon_rarity = None
        self.region_map = {"alolan": "-alola", "galarian": "-galar", "hisuian": "-hisui", "paldean": "-paldea", "mega": "-mega"}
        self.reverse_region_map = {"alola": "Alolan", "galar": "Galarian", "hisui": "Hisuian", "paldea": "Paldean", "mega": "Mega"}
        self.ultra_beasts = ["nihilego", "buzzwole", "pheromosa", "xurkitree", "celesteela", "kartana", "guzzlord", "poipole", "naganadel", "stakataka", "blacephalon"]
        self.generation_map = {
            "generation-i": "kanto", "generation-ii": "johto", "generation-iii": "hoenn", "generation-iv": "sinnoh",
            "generation-v": "unova", "generation-vi": "kalos", "generation-vii": "alola", "generation-viii": "galar", "generation-ix": "paldea"
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

    def extract_pokemon_name(self, entry: str) -> str:
        return re.sub(r'<:[^:]+:\d+>\s*', '', entry).strip()

    def find_similar_names(self, query: str, valid_names: list, max_suggestions=20, min_similarity=0.65) -> list[str]:
        query_lower = query.lower()
        exact_matches = [name for name in valid_names if query_lower in name.lower()]
        if not exact_matches:
            fuzzy_matches = difflib.get_close_matches(query_lower, [name.lower() for name in valid_names], n=max_suggestions, cutoff=min_similarity)
            return [name for name in valid_names if name.lower() in fuzzy_matches]
        return exact_matches[:max_suggestions]

    def is_ultra_beast(self, pokemon_name: str) -> bool:
        return pokemon_name.lower() in self.ultra_beasts

    def map_generation_to_region(self, generation_name: str) -> str:
        return self.generation_map.get(generation_name, "unknown")

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
                            type_data = {"id": pokemon_id, "name": pokemon["name"], "types": ",".join(types)}
                            detailed_pokemon.append(type_data)
                except Exception as e:
                    print(f"Error fetching details for {pokemon['name']}: {e}")
                    continue
        return detailed_pokemon

    async def fetch_pokemon_rarity_data(self):
        rarity_data = []
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("https://pokeapi.co/api/v2/pokemon-species?limit=2000") as response:
                    if response.status == 200:
                        data = await response.json()
                        species_list = data["results"]
                        
                        for species in tqdm(species_list, desc="Fetching Pokemon rarity data"):
                            try:
                                species_id = int(species["url"].rstrip("/").split("/")[-1])
                                species_url = f"https://pokeapi.co/api/v2/pokemon-species/{species_id}"
                                async with session.get(species_url) as species_response:
                                    if species_response.status == 200:
                                        species_data = await species_response.json()
                                        name = species_data["name"]
                                        is_legendary = species_data.get("is_legendary", False)
                                        is_mythical = species_data.get("is_mythical", False)
                                        generation = species_data.get("generation", {})
                                        generation_name = generation.get("name", "") if generation else ""
                                        region = self.map_generation_to_region(generation_name)
                                        
                                        if is_mythical:
                                            rarity = "mythical"
                                        elif is_legendary:
                                            rarity = "legendary"
                                        else:
                                            rarity = "ultra beast" if self.is_ultra_beast(name) else "common"
                                        
                                        rarity_data.append({"id": species_id, "name": name, "rarity": rarity, "region": region})
                            except Exception as e:
                                print(f"Error processing species {species.get('name', 'unknown')}: {e}")
                                continue
            except Exception as e:
                print(f"Error fetching species list: {e}")
        return rarity_data

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

    async def generate_pokemon_types_csv(self):
        if not os.path.isfile(self.pokemon_types_csv):
            os.makedirs(os.path.dirname(self.pokemon_types_csv), exist_ok=True)
            species_list = await self.afetch_pokemon_species()
            detailed_pokemon = await self.fetch_pokemon_details(species_list)
            fieldnames = ["id", "name", "types"]
            
            with open(self.pokemon_types_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(detailed_pokemon)

    async def generate_pokemon_rarity_csv(self):
        if not os.path.isfile(self.pokemon_rarity_csv):
            os.makedirs(os.path.dirname(self.pokemon_rarity_csv), exist_ok=True)
            print("Generating Pokemon rarity data...")
            rarity_data = await self.fetch_pokemon_rarity_data()
            fieldnames = ["id", "name", "rarity", "region"]
            
            with open(self.pokemon_rarity_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rarity_data)
            print(f"Pokemon rarity data saved to {self.pokemon_rarity_csv}")

    async def load_pokemon_types(self):
        if not os.path.isfile(self.pokemon_types_csv):
            await self.generate_pokemon_types_csv()
        
        types_map = {}
        with open(self.pokemon_types_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").lower()
                types_str = row.get("types", "").strip()
                types = [t.strip().lower() for t in types_str.split(",") if t.strip()]
                types_map[name] = types
        return types_map

    async def load_pokemon_rarity(self):
        if not os.path.isfile(self.pokemon_rarity_csv):
            await self.generate_pokemon_rarity_csv()
        
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
        try:
            flags_dict = flags_obj if isinstance(flags_obj, dict) else {}
            if not any(flags_dict.values()):
                return entries
            
            filtered = []
            suffix_map = {'alolan': '-alola', 'galarian': '-galar', 'hisuian': '-hisui', 'paldean': '-paldea', 'mega': '-mega'}
            rarity_checks = {'legendary': 'legendary', 'mythical': 'mythical', 'ultra_beast': 'ultra beast'}

            for entry in entries:
                pokemon_name = self.extract_pokemon_name(entry)
                slug = self.normalize_regional_name(pokemon_name.lower().replace(" ", "-"))

                skip_pokemon = False
                for flag, suffix in suffix_map.items():
                    if flags_dict.get(flag) and not slug.endswith(suffix):
                        skip_pokemon = True
                        break
                
                if skip_pokemon:
                    continue

                try:
                    rarity_data = (await self.pokemon_rarity).get(slug, {})
                    rarity = rarity_data.get("rarity", "").lower()
                except:
                    rarity = ""

                rarity_match = True
                for flag, rarity_val in rarity_checks.items():
                    if flags_dict.get(flag):
                        if rarity != rarity_val:
                            rarity_match = False
                            break
                
                if not rarity_match:
                    continue

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

                if flags_dict.get('type'):
                    try:
                        pokemon_types_data = (await self.pokemon_types).get(slug, [])
                        type_match = False
                        for filter_type in flags_dict['type']:
                            if filter_type.lower() in [t.lower() for t in pokemon_types_data]:
                                type_match = True
                                break
                        if not type_match:
                            continue
                    except:
                        continue

                if flags_dict.get('region'):
                    try:
                        region_data = rarity_data.get("region", "").lower()
                        if not any(region_filter.lower() == region_data for region_filter in flags_dict['region']):
                            continue
                    except:
                        continue

                filtered.append(entry)

            if flags_dict.get('skip'):
                filtered = filtered[flags_dict['skip']:]
            if flags_dict.get('limit'):
                filtered = filtered[:flags_dict['limit']]

            return filtered
        except Exception as e:
            print(f"Error in filter_by_flags: {e}")
            return entries


class PokemonEmbedManager:
    def __init__(self, embed_default_color, icons, results_per_page=RESULTS_PER_PAGE, chunk_size=CHUNK_SIZE):
        self.embed_default_color = embed_default_color
        self.icons = icons
        self.results_per_page = results_per_page
        self.chunk_size = chunk_size

    def create_collection_embeds(self, entries: list[str], title: str, ctx) -> list[Embed]:
        if not entries:
            embed = Embed(
                title=title,
                description="No Pokémon found matching your criteria.",
                color=self.embed_default_color
            )
            embed.set_footer(text=f"Use {ctx.prefix}pt {ctx.invoked_with} help for more information")
            return [embed]
        
        embeds = []
        total_pages = (len(entries) + self.results_per_page - 1) // self.results_per_page
        
        for page in range(total_pages):
            start_idx = page * self.results_per_page
            end_idx = min(start_idx + self.results_per_page, len(entries))
            page_entries = entries[start_idx:end_idx]
            
            chunks = []
            current_chunk = []
            
            for entry in page_entries:
                current_chunk.append(entry)
                if len(current_chunk) >= self.chunk_size:
                    chunks.append(current_chunk)
                    current_chunk = []
            
            if current_chunk:
                chunks.append(current_chunk)
            
            description_parts = []
            for i, chunk in enumerate(chunks):
                chunk_text = "\n".join(f"{start_idx + (i * self.chunk_size) + j + 1}. {entry}" 
                                     for j, entry in enumerate(chunk))
                description_parts.append(chunk_text)
            
            embed = Embed(
                title=f"{title}",
                description="\n\n".join(description_parts),
                color=self.embed_default_color
            )

            embed.set_thumbnail(url=ctx.author.avatar)


            
            embed.add_field(
                name=" ",
                value=f"**Total:** {len(entries)} Pokémon\n**Page:** {page + 1}/{total_pages}\n**Showing:** {start_idx + 1}-{end_idx}",
                inline=True
            )
            
            embed.set_footer(text=f"Use {ctx.prefix}pt {ctx.invoked_with} help for more information")
            embeds.append(embed)
        
        return embeds

    def create_error_embed(self, ctx, message="An error occurred while processing your request."):
        embed = Embed(title="❌ Error", description=message, color=0xff0000)
        embed.set_footer(text=f"Use {ctx.prefix}{ctx.invoked_with} help for more information")
        return embed

    def create_success_embed(self, ctx, message, footer_text="", color=None):
        embed = Embed(
            description=message,
            color=color or self.embed_default_color
        )
        if footer_text:
            embed.set_footer(text=footer_text)
        return embed


class PokemonCollectionHandler:
    def __init__(self, data_manager, embed_manager, pokemon_emojis=None, pokemon_subcogs=None, max_pokemon=50):
        self.data_manager = data_manager
        self.embed_manager = embed_manager
        self.pe = pokemon_emojis
        self.pokemon_subcogs = pokemon_subcogs
        self.max_pokemon = max_pokemon
        self.RESULTS_PER_PAGE = 10
        self.icons = {
            "success": "<:check:1399603549100441723>",
            "error": "<:x_:1399603637105463386>",
            "exists": "<:already_exists:1399604560598663188>",
            "removed": "<:minus:1399613745784946728>",
            "not_found": "<:question_white:1399604993228804136>"
        }

    async def paginate_and_send(self, ctx, entries: list[str], title="Your Pokémon Collection", flags_obj=None):
        try:
            embeds = self.embed_manager.create_collection_embeds(entries, title, ctx)
            if len(embeds) == 1:
                await ctx.send(embed=embeds[0])
            else:
                view = NavigationView(embeds, ctx) if 'NavigationView' in globals() else None
                if view:
                    await ctx.reply(embed=embeds[0], mention_author=False, view=view)
                else:
                    await ctx.reply(embed=embeds[0], mention_author=False)
        except Exception as e:
            print(f"Error in paginate_and_send: {e}")
            error_embed = self.embed_manager.create_error_embed(
                ctx, "Failed to display your Pokémon collection. Please try again."
            )
            await ctx.send(embed=error_embed)

    async def handle_collection(self, ctx, col, action, pokemon=None, max_one=False, flags_obj=None):
        if not self.data_manager.mongo:
            await ctx.reply("❌ Database connection not available.", mention_author=False)
            return

        try:
            valid_slugs = await self.data_manager.valid_slugs
            valid_slugs_list = list(valid_slugs)
            uid = ctx.author.id
            cur = await self.data_manager.mongo.list(col, uid)

            invalids = [n for n in cur if n.lower() not in valid_slugs]
            if action == "list" and invalids:
                for n in invalids:
                    await self.data_manager.mongo.remove(col, n, uid)
                cur = await self.data_manager.mongo.list(col, uid)
                suggestions = []
                for invalid_name in invalids:
                    similar = self.data_manager.find_similar_names(invalid_name, valid_slugs_list)
                    if similar:
                        for s in similar:
                            suggestions.append((invalid_name, s))
                if suggestions:
                    embed = Embed(
                        title="Invalid Pokémon Found in Collection",
                        description=(
                            f"Found {len(invalids)} invalid Pokémon in your collection. "
                            "Would you like to replace them with suggestions?"
                        ),
                        color=self.embed_manager.embed_default_color
                    )
                    view = UnifiedResultView(
                        success_results=[], failed_results=[], exists_results=[],
                        suggestions_list=suggestions,
                        parent_cog=self, ctx=ctx, col=col, uid=uid,
                        action="add", max_one=max_one
                    ) if 'UnifiedResultView' in globals() else None
                    return await ctx.reply(embed=embed, view=view, mention_author=False) \
                        if view else await ctx.reply(embed=embed, mention_author=False)
            else:
                for n in invalids:
                    await self.data_manager.mongo.remove(col, n, uid)
                cur = await self.data_manager.mongo.list(col, uid)

            if len(cur) > self.max_pokemon:
                for n in cur[self.max_pokemon:]:
                    await self.data_manager.mongo.remove(col, n, uid)
                cur = cur[:self.max_pokemon]

            if action == "list":
                if not cur:
                    embed = self.embed_manager.create_success_embed(ctx, "Your list is empty.")
                    return await ctx.reply(embed=embed, mention_author=False)

                entries = []
                for name in cur:
                    emoji = ""
                    if self.pe:
                        try:
                            pid = (self.pokemon_subcogs.pokemon_name_to_id(name)
                                   if self.pokemon_subcogs else None)
                            emoji = self.pe.get_emoji_for_pokemon(pid) or ""
                        except:
                            pass
                    display_name = self.data_manager.display_name_with_region(name)
                    entries.append(f"{emoji} {display_name}" if emoji else display_name)

                if flags_obj:
                    entries = await self.data_manager.filter_by_flags(entries, flags_obj)

                title = "Your Shiny Hunt Target" if col == "shiny_hunt" else "Your Pokémon Collection"
                return await self.paginate_and_send(ctx, entries, title, flags_obj=flags_obj)

            if action == "clear":
                await self.data_manager.mongo.clear(col, uid)
                embed = self.embed_manager.create_success_embed(ctx, "🗑️ Cleared your Pokémon list.")
                return await ctx.reply(embed=embed, mention_author=False)

            if not pokemon:
                embed = self.embed_manager.create_error_embed(
                    ctx, f"{self.icons['error']} Specify Pokémon name(s)."
                )
                return await ctx.reply(embed=embed, mention_author=False)

            names = [(raw.strip(), self.data_manager.normalize_regional_name(raw.strip().lower().replace(" ", "-")))
                     for raw in pokemon.split(",")]
            cur = await self.data_manager.mongo.list(col, uid)

            success, failed, exists = [], [], []
            suggestions = []

            for raw, norm in names:
                name_lower = norm.lower()
                if name_lower in valid_slugs:
                    pid = (self.pokemon_subcogs.pokemon_name_to_id(name_lower)
                           if self.pokemon_subcogs else None)
                    emoji = (self.pe.get_emoji_for_pokemon(pid) or "") if self.pe and pid else ""
                    disp = self.data_manager.display_name_with_region(name_lower)

                    if action == "add":
                        if max_one:
                            await self.data_manager.mongo.replace(col, name_lower, uid)
                            success.append(f"{self.icons['success']} {emoji} You are now shiny hunting {disp}!")
                            break
                        if len(cur) >= self.max_pokemon and name_lower not in cur:
                            exists.append(f"{self.icons['error']} Max {self.max_pokemon} reached. {disp} not added.")
                            continue
                        ok = await self.data_manager.mongo.add(col, name_lower, uid)
                        if ok:
                            success.append(f"{self.icons['success']} {emoji} {disp} has been added.")
                            cur.append(name_lower)
                        else:
                            exists.append(f"{self.icons['exists']} {emoji} {disp} already exists.")
                    elif action == "remove":
                        ok = await self.data_manager.mongo.remove(col, name_lower, uid)
                        if ok:
                            success.append(f"{self.icons['removed']} {emoji} {disp} has been removed.")
                        else:
                            exists.append(f"{self.icons['not_found']} {emoji} {disp} was not found.")
                else:
                    similar = self.data_manager.find_similar_names(raw, valid_slugs_list)
                    if similar:
                        for s in similar:
                            suggestions.append((raw, s))
                    else:
                        failed.append(f"{self.icons['error']} Pokémon named '{raw}' is invalid and could not be processed.")

            if success or failed or exists or suggestions:
                if success and col == "shiny_hunt" and max_one:
                    embed = self.embed_manager.create_success_embed(ctx, success[0])
                    return await ctx.reply(embed=embed, mention_author=False)

                if suggestions and not success:
                    embed = Embed(
                        title="Pokémon Suggestions",
                        description=(f"Found {len(suggestions)} suggestion(s) for invalid name(s). "
                                     f"Select the Pokémon to {action}:"),
                        color=self.embed_manager.embed_default_color
                    )
                    view = UnifiedResultView(
                        success_results=success, failed_results=failed, exists_results=exists,
                        suggestions_list=suggestions,
                        parent_cog=self, ctx=ctx, col=col, uid=uid,
                        action=action, max_one=max_one
                    ) if 'UnifiedResultView' in globals() else None
                    return await ctx.reply(embed=embed, view=view, mention_author=False) \
                        if view else await ctx.reply(embed=embed, mention_author=False)

                if success or failed or exists:
                    label_map = {
                        "success": "✅ Successful Results",
                        "invalid": "❌ Invalid Results",
                        "other": "⛔ Other Results"
                    }
                    if success:
                        init = success; key="success"
                    elif failed:
                        init = failed; key="invalid"
                    else:
                        init = exists; key="other"
                    content = "\n".join(init[:self.embed_manager.results_per_page])
                    embed = Embed(
                        description = f"{content[:3900]}", # potato | {label_map[key] if key != 'success' else ''}\n\n
                        color=self.embed_manager.embed_default_color
                    )
                    if not max_one:
                        embed.set_footer(text="Updated Your Pokémon Collection")
                    view = UnifiedResultView(
                        success_results=success, failed_results=failed,
                        exists_results=exists, suggestions_list=suggestions,
                        parent_cog=self, ctx=ctx, col=col, uid=uid,
                        action=action, max_one=max_one
                    ) if 'UnifiedResultView' in globals() else None
                    return await (ctx.reply(embed=embed, view=view, mention_author=False)
                                  if view else ctx.reply(embed=embed, mention_author=False))

        except Exception as e:
            print(f"Error in handle_collection: {e}")
            import traceback; traceback.print_exc()
            embed = self.embed_manager.create_error_embed(ctx)
            await ctx.reply(embed=embed, mention_author=False)
            
############################################



class UnifiedResultView(View):
    def __init__(self, success_results, failed_results, exists_results, suggestions_list=None, parent_cog=None, ctx=None, col=None, uid=None, action=None, max_one=False):
        super().__init__(timeout=300)
        
        
        self.parent_cog = parent_cog  
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
        self.current_view = "success"  
        self.current_page = 0
        self.items_per_page = self.parent_cog.RESULTS_PER_PAGE if parent_cog else 10
        self.selected_items = set()
        self.show_suggestions = bool(suggestions_list)
        
        
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

    def should_show_category_buttons(self):
        """Check if we should show category buttons (only if there are multiple categories with data)"""
        categories_with_data = sum(1 for results in self.results.values() if results)
        has_suggestions = bool(self.suggestions)
        return categories_with_data + (1 if has_suggestions else 0) > 1

    def update_components(self):
        self.clear_items()
        
        # Only show category buttons if there are multiple categories with data
        if self.should_show_category_buttons():
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
            
            pages = self.get_pages("suggestions")
            if pages and pages[self.current_page]:
                page_items = pages[self.current_page]
                options = []
                for original_name, suggestion in page_items:
                    pid = self.parent_cog.pokemon_subcogs.pokemon_name_to_id(suggestion) if self.parent_cog.pokemon_subcogs else None
                    emoji = self.parent_cog.pe.get_emoji_for_pokemon(pid) if self.parent_cog.pe and pid else ""
                    display_name = self.parent_cog.data_manager.display_name_with_region(suggestion)
                    option_label = f"{display_name} (for '{original_name}')"
                    if len(option_label) > 100:  
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

    async def on_timeout(self):
        """Called when the view times out - removes all components"""
        self.clear_items()
        try:
            # Try to edit the message to remove buttons
            # You'll need to store the message object when you first send it
            if hasattr(self, 'message') and self.message:
                await self.message.edit(view=None)
        except:
            # If editing fails (message deleted, etc.), just pass
            pass

    async def select_callback(self, interaction: Interaction):
        
        selected_values = set(interaction.data['values'])
        pages = self.get_pages("suggestions")
        page_items = pages[self.current_page] if pages else []
        page_values = {f"{orig}|{sugg}" for orig, sugg in page_items}
        
        
        self.selected_items = {item for item in self.selected_items if item not in page_values}
        
        self.selected_items.update(selected_values)
        
        self.update_components()
        await interaction.response.edit_message(view=self)

    async def confirm_action(self, interaction: Interaction):
        
        current_list = await self.parent_cog.data_manager.mongo.list(self.col, self.uid)
        new_success = []
        new_other = []
        
        for selected_item in self.selected_items:
            original_name, selected_slug = selected_item.split("|", 1)
            
            if self.action == "add":
                if self.max_one:
                    await self.parent_cog.data_manager.mongo.replace(self.col, selected_slug, self.uid)
                    pid = self.parent_cog.pokemon_subcogs.pokemon_name_to_id(selected_slug) if self.parent_cog.pokemon_subcogs else None
                    emoji = self.parent_cog.pe.get_emoji_for_pokemon(pid) if self.parent_cog.pe and pid else ""
                    name_disp = self.parent_cog.data_manager.display_name_with_region(selected_slug)
                    new_success.append(f"{self.parent_cog.icons['success']} Set your shiny hunt to {emoji} {name_disp}!")
                    break
                else:
                    if len(current_list) >= self.parent_cog.max_pokemon and selected_slug not in current_list:
                        new_other.append(f"{self.parent_cog.icons['error']} Max {self.parent_cog.max_pokemon} Pokémon. {selected_slug.title()} not added.")
                        continue
                    ok = await self.parent_cog.data_manager.mongo.add(self.col, selected_slug, self.uid)
                    pid = self.parent_cog.pokemon_subcogs.pokemon_name_to_id(selected_slug) if self.parent_cog.pokemon_subcogs else None
                    emoji = self.parent_cog.pe.get_emoji_for_pokemon(pid) if self.parent_cog.pe and pid else ""
                    icon = self.parent_cog.icons['success'] if ok else self.parent_cog.icons['exists']
                    name_disp = self.parent_cog.data_manager.display_name_with_region(selected_slug)
                    result_text = f"{icon} {emoji} {name_disp}"
                    if ok:
                        new_success.append(result_text)
                        current_list.append(selected_slug)
                    else:
                        new_other.append(result_text)
                        
            elif self.action == "remove":
                ok = await self.parent_cog.data_manager.mongo.remove(self.col, selected_slug, self.uid)
                pid = self.parent_cog.pokemon_subcogs.pokemon_name_to_id(selected_slug) if self.parent_cog.pokemon_subcogs else None
                emoji = self.parent_cog.pe.get_emoji_for_pokemon(pid) if self.parent_cog.pe and pid else ""
                icon = self.parent_cog.icons['removed'] if ok else self.parent_cog.icons['not_found']
                name_disp = self.parent_cog.data_manager.display_name_with_region(selected_slug)
                result_text = f"{icon} {emoji} {name_disp}"
                if ok:
                    new_success.append(result_text)
                else:
                    new_other.append(result_text)

        
        self.results["success"].extend(new_success)
        self.results["other"].extend(new_other)
        self.suggestions = []  
        self.selected_items = set()
        self.current_view = "success" if new_success else ("other" if new_other else "success")
        self.current_page = 0
        
        await self.update_message(interaction)

    async def cancel_action(self, interaction: Interaction):
        
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
            
            total_suggestions = len(self.suggestions)
            unique_originals = len(set(orig for orig, _ in self.suggestions))
            
            embed = Embed(
                title="Pokémon Selection",
                description=f"Found {total_suggestions} suggestions for {unique_originals} invalid name(s). "
                           f"Select the Pokémon you want to {self.action}:",
                color=self.parent_cog.embed_manager.embed_default_color
            )
        else:
            
            pages = self.get_pages(self.current_view)
            current_data = pages[self.current_page] if pages else []
            content = "\n".join(current_data) if current_data else "No entries to display."
            
            view_names = {
                "success": "✅ Successful Results",
                "invalid": "❌ Invalid Results",
                "other": "⛔ Other Results"
            }
            
            # Only show header if there are multiple categories
            if self.should_show_category_buttons():
                header = f"**{view_names[self.current_view]}**\n\n"
            else:
                header = ""
            
            embed = Embed(description=header + content[:3900], color=self.parent_cog.embed_manager.embed_default_color)
            
            if len(pages) > 1:
                embed.set_footer(text=f"Page {self.current_page + 1} of {len(pages)} • {len(current_data)} entries shown")
            else:
                embed.set_footer(text="" if self.max_one else "Updated Your Pokemon Collection")
        
        self.update_components()
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: Interaction):
        return interaction.user == self.ctx.author

class NavigationView(View):
    def __init__(self, embeds, ctx, timeout=300):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.ctx = ctx
        self.current_index = 0
        self.prev_button = Button(label="◀", style=ButtonStyle.secondary, disabled=True)
        self.next_button = Button(label="▶", style=ButtonStyle.secondary, disabled=len(embeds) <= 1)
        self.prev_button.callback = self.go_prev
        self.next_button.callback = self.go_next
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

    async def go_prev(self, interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.defer()
            return
        if self.current_index > 0:
            self.current_index -= 1
            await self.update_view(interaction)

    async def go_next(self, interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.defer()
            return
        if self.current_index < len(self.embeds) - 1:
            self.current_index += 1
            await self.update_view(interaction)

    async def update_view(self, interaction):
        self.prev_button.disabled = self.current_index == 0
        self.next_button.disabled = self.current_index >= len(self.embeds) - 1
        await interaction.response.edit_message(embed=self.embeds[self.current_index], view=self)

    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.author

    async def on_timeout(self):
        self.prev_button.disabled = True
        self.next_button.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass


class AdvancedStringFlagParser:
    def __init__(self):
        self.flag_patterns = {
            'alolan': r'--alolan\b',
            'galarian': r'--galarian\b',
            'hisuian': r'--hisuian\b',
            'paldean': r'--paldean\b',
            'legendary': r'--legendary\b',
            'mythical': r'--mythical\b',
            'ultra_beast': r'--ultra[-_ ]?beast\b',
            'limit': r'--(?:limit|max|top)\s+(\d+)\b',
            'skip': r'--(?:skip|offset)\s+(\d+)\b',
        }

        self.type_pattern = r'--(?:type|t)\s+([a-zA-Z]+(?:\s*,\s*[a-zA-Z]+)*)'
        self.region_pattern = r'--(?:region|r)\s+([a-zA-Z]+(?:\s*,\s*[a-zA-Z]+)*)'
        self.name_pattern = r'--(?:name|n)\s+([a-zA-Z0-9\s,\-\']+?)(?=\s+--|\s*$)'

    def parse_flags_from_string(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        text_lower = text.lower()
        flags = {}
        for flag_name, pattern in self.flag_patterns.items():
            if flag_name in ['limit', 'skip']:
                match = re.search(pattern, text_lower)
                if match:
                    flags[flag_name] = int(match.group(1))
            else:
                if re.search(pattern, text_lower):
                    flags[flag_name] = True

        type_match = re.search(self.type_pattern, text_lower)
        if type_match:
            types = [t.strip() for t in type_match.group(1).split(',')]
            flags['type'] = types

        region_match = re.search(self.region_pattern, text_lower)
        if region_match:
            regions = [r.strip() for r in region_match.group(1).split(',')]
            flags['region'] = regions

        name_match = re.search(self.name_pattern, text_lower)
        if name_match:
            names = [n.strip() for n in name_match.group(1).split(',')]
            flags['name'] = [[name] for name in names]

        return flags

    def extract_pokemon_names_from_string(self, text: str, action: str) -> tuple[str, dict]:
        if not text:
            return "", {}

        flags_dict = self.parse_flags_from_string(text)
        words = text.lower().split()
        pokemon_words = []
        i = 0
        while i < len(words):
            word = words[i].strip(',-')
            if word.startswith('--'):
                i += 1
                if i < len(words) and not words[i].startswith('--'):
                    i += 1
                continue
            if word.isdigit():
                i += 1
                continue
            pokemon_words.append(words[i])
            i += 1

        pokemon_names = ' '.join(pokemon_words).strip()
        pokemon_names = re.sub(r'\s*,\s*', ', ', pokemon_names)
        pokemon_names = re.sub(r'\s+', ' ', pokemon_names)

        if action in ['add', 'remove'] and not pokemon_names:
            remaining_text = text
            remaining_text = re.sub(self.type_pattern, '', remaining_text, flags=re.IGNORECASE)
            remaining_text = re.sub(self.region_pattern, '', remaining_text, flags=re.IGNORECASE)
            remaining_text = re.sub(self.name_pattern, '', remaining_text, flags=re.IGNORECASE)
            for _, pattern in self.flag_patterns.items():
                remaining_text = re.sub(pattern, '', remaining_text, flags=re.IGNORECASE)
            pokemon_names = re.sub(r'\s+', ' ', remaining_text).strip()
            pokemon_names = re.sub(r'^[,\s]+|[,\s]+$', '', pokemon_names)

        return pokemon_names, flags_dict

# ===================================================================================


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
    
#####################

class PokemonHelpEmbed:
 @staticmethod
 def generate_collection_help_embed(self, ctx):
    prefix = ctx.prefix
    embed = Embed(
        title="Collection Command Help",
        description="Manage your Pokémon collection with powerful filtering options!",
        color=self.embed_default_color
    )

    embed.add_field(
        name="Basic Commands",
        value=(
            f"**{prefix}cl** - View your collection\n"
            f"**{prefix}cl add pikachu** - Add Pokémon\n"
            f"**{prefix}cl remove charizard** - Remove Pokémon\n"
            f"**{prefix}cl clear** - Clear entire collection"
        ),
        inline=False
    )

    embed.add_field(
        name="Regional Variants",
        value=(
            f"**{prefix}cl --galarian** - Show only Galarian forms\n"
            f"**{prefix}cl --hisuian --paldean** - Show Hisuian and Paldean forms"
        ),
        inline=False
    )

    embed.add_field(
        name="Type & Region Filters",
        value=(
            f"**{prefix}cl --type fire** - Show only Fire types\n"
            f"**{prefix}cl --t grass,water** - Show Grass and Water types\n"
            f"**{prefix}cl --region kanto** - Show only Kanto Pokémon\n"
            f"**{prefix}cl --r johto,hoenn** - Show Johto and Hoenn Pokémon"
        ),
        inline=False
    )

    embed.add_field(
        name="Special Categories",
        value=(
            f"**{prefix}cl --legendary** - Show only legendary Pokémon\n"
            f"**{prefix}cl --mythical** - Show only mythical Pokémon\n"
            f"**{prefix}cl --ultra-beast** - Show only Ultra Beasts"
        ),
        inline=False
    )

    embed.add_field(
        name="Name Searching",
        value=(
            f"**{prefix}cl --name eevee** - Show only Eevee\n"
            f"**{prefix}cl --n pikachu,raichu** - Show Pikachu and Raichu\n"
            f"**{prefix}cl add eevee, vaporeon, jolteon** - Add multiple Pokémon"
        ),
        inline=False
    )

    embed.add_field(
        name="Advanced Examples",
        value=(
            f"**{prefix}cl --type electric --region kanto** - Electric Kanto Pokémon\n"
            f"**{prefix}cl --legendary --t psychic** - Legendary Psychic types\n"
            f"**{prefix}cl --galarian --type steel** - Galarian Steel types\n"
            f"**{prefix}cl --limit 5** - Show only first 5 results"
        ),
        inline=False
    )

    embed.add_field(
        name="Pro Tips",
        value=(
            "• Use short flags: **--t** for type, **--r** for region, **--n** for name\n"
            "• Combine multiple filters for precise searches\n"
            "• Add multiple Pokémon at once with commas\n"
            "• Use **--limit** to control how many results you see"
        ),
        inline=False
    )

    embed.set_footer(text=f"Collection limit: {self.MAX_POKEMON} Pokémon • Results per page: {self.RESULTS_PER_PAGE}")
    return embed




class RoleSelect(discord.ui.Select):
    def __init__(self, guild: discord.Guild, role_type: str, mongo_helper, guild_id):
        self.guild = guild
        self.role_type = role_type
        self.mongo = mongo_helper
        self.guild_id = guild_id
        

        options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in guild.roles if not role.is_bot_managed() and role.name != "@everyone"
        ]

        super().__init__(
            placeholder=f"Select a role for {role_type.title()} Pokémon (optional)",
            min_values=0, max_values=1,
            options=options[:25]  # Discord limit
        )

    async def callback(self, interaction: discord.Interaction):
        if not self.values:
            await self.mongo.db["server_config"].update_one(
                {"guild_id": self.guild_id},
                {"$unset": {f"{self.role_type}_role": ""}},
                upsert=True
            )
            return await interaction.response.send_message(
                f"❎ Cleared {self.role_type.title()} Pokémon role.", ephemeral=True
            )

        role_id = int(self.values[0])
        role = self.guild.get_role(role_id)

        await self.mongo.db["server_config"].update_one(
            {"guild_id": self.guild_id},
            {"$set": {f"{self.role_type}_role": role_id}},
            upsert=True
        )

        await interaction.response.send_message(
            f"✅ {self.role_type.title()} Pokémon role set to {role.mention}",
            ephemeral=True
        )

class ServerConfigView(discord.ui.View):
    def __init__(self, guild: discord.Guild, mongo_helper):
        super().__init__(timeout=300)
        self.guild = guild
        self.mongo = mongo_helper

        self.add_item(RoleSelect(guild, "rare", mongo_helper, guild.id))
        self.add_item(RoleSelect(guild, "regional", mongo_helper, guild.id))











class ConfigToggleSelect(discord.ui.Select):
    def __init__(self, config: dict):
        options = [
            discord.SelectOption(label="Images", value="images", emoji="✅" if config.get("images_enabled", True) else "❌"),
            discord.SelectOption(label="Buttons", value="buttons", emoji="✅" if config.get("buttons_enabled", True) else "❌"),
            discord.SelectOption(label="Rare", value="rare", emoji="✅" if config.get("rare_enabled", True) else "❌"),
            discord.SelectOption(label="Regional", value="regional", emoji="✅" if config.get("regional_enabled", True) else "❌"),
            discord.SelectOption(label="Collection", value="cl", emoji="✅" if config.get("cl_enabled", True) else "❌"),
            discord.SelectOption(label="Shiny", value="sh", emoji="✅" if config.get("sh_enabled", True) else "❌"),
            discord.SelectOption(label="Type", value="type", emoji="✅" if config.get("type_enabled", True) else "❌"),
            discord.SelectOption(label="Quest", value="quest", emoji="✅" if config.get("quest_enabled", True) else "❌"),
        ]
        super().__init__(placeholder="Toggle a feature", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("You lack permission to manage server.", ephemeral=True)

        feature = self.values[0]
        key = f"{feature}_enabled"
        new_value = not self.view.config.get(key, True)
        updates = {key: new_value}

        await self.view.mongo.db[self.view.server_config_collection].update_one(
            {"guild_id": self.view.guild_id}, {"$set": updates}, upsert=True
        )

        self.view.config.update(updates)

        for option in self.options:
            if option.value == feature:
                option.emoji = "✅" if new_value else "❌"
                break

        embed = self.view.cog.create_config_embed(self.view.config, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self.view)

class RoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder="Select roles...", min_values=1, max_values=2)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message("You lack permission.", ephemeral=True)

        updates = {}
        for i, role in enumerate(self.values):
            # Assign first role as rare_role, second as regional_role if two are selected
            key = "rare_role" if i == 0 else "regional_role"
            updates[key] = role.id

        await self.view.mongo.db[self.view.server_config_collection].update_one(
            {"guild_id": self.view.guild_id}, {"$set": updates}, upsert=True
        )

        self.view.config.update(updates)

        embed = self.view.cog.create_config_embed(self.view.config, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self.view)
        

class ConfigView(discord.ui.View):
    def __init__(self, cog, guild_id: int, mongo, config: dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id
        self.mongo = mongo
        self.config = config.copy()
        self.server_config_collection = cog.server_config_collection

        toggle_select = ConfigToggleSelect(self.config)
        self.add_item(toggle_select)

     

        role_select = RoleSelect()
        role_select.row = 2
        self.add_item(role_select)







class TR_Embed_Config:
    bullet_format = "- {emoji_str} {item}"
    row_separator = "\n"
    group_size = 3
    primary_color = primary_color()
    afk_color = 0xFF6B6B
    error_color = 0xFF4757

    def get_title(self, selection_type: str, is_afk: bool = False):
        base = "<:gear:1430580748682793041>" if not is_afk else ":zzz:"
        return f"{selection_type.title()} Ping"

    def get_afk_description(self, selection_type: str):
        return (
            "### 😴 AFK Mode is Currently Active\n"
            f"Your {selection_type} ping notifications are **paused**. "
            "Toggle AFK mode below to reactivate them and restore your saved preferences."
        )

    def get_no_selection_description(self, selection_type: str):
        return (
            f"### No {selection_type.title()}s Selected\n"
            #f"Select Pokémon {selection_type}s from the dropdown below to receive spawn notifications."
        )

    #def get_how_it_works_field(self, selection_type: str):
    #    return {
    #        "name": "How it works",
    #        "value": (
    #            f"• Choose {selection_type}s from the dropdown menu\n"
    #            f"• Get pinged when those {selection_type}s spawn\n"
    #            "• Use AFK mode to temporarily pause pings"
    #        ),
    #        "inline": False
    #    }

    def get_footer_text(self, status_message: str | None = None):
        default = "Use the dropdown to select multiple items at once."
        return status_message or default

    def get_help_title(self, selection_type: str):
        return f"❓ {selection_type.title()} Ping Help Guide"

    def get_help_description(self, selection_type: str):
        return f"Learn how to use the {selection_type.title()} Ping system effectively!"

    def get_how_pings_work_field(self, selection_type: str, bot_mention: str):
        return {
            "name": f"🎯 How {selection_type.title()} Pings Work",
            "value": (
                f"Whenever a <@716390085896962058> Pokémon spawns with any of your **selected {selection_type}s**, "
                f"{bot_mention} will mention you in this server."
            ),
            "inline": False
        }

    def get_interface_usage_field(self, selection_type: str):
        return {
            "name": "Using the Interface",
            "value": (
                "• **Dropdown Menu**: Select multiple items at once\n"
                "• **Clear All**: Remove all selected items\n"
                "• **AFK Mode**: Temporarily pause pings"
            ),
            "inline": False
        }

    def get_afk_benefits_field(self):
        return {
            "name": "AFK Mode Benefits",
            "value": (
                "• **Pause** all pings when you're away\n"
                "• **Save** your current selections\n"
                "• **Restore** everything when you're back\n"
                "• Perfect for breaks, sleep, or busy periods"
            ),
            "inline": False
        }

    def get_error_embed(self, title: str, description: str):
        return discord.Embed(title=title, description=description, color=self.error_color)

    def get_afk_saved_field(self, count: int, selection_type: str):
        return {
            "name": f"Saved {selection_type.title()}s",
            "value": f"Your {count} selected {selection_type}(s) are safely stored and will be restored when you disable AFK mode.",
            "inline": False
        }

    def get_afk_off_status(self, count: int, selection_type: str):
        return f"AFK mode disabled - Restored {count} saved {selection_type}(s)."

    def get_afk_on_status(self, count: int, selection_type: str):
        return f"😴 AFK mode enabled. {count} {selection_type}(s) saved."

    def get_cleared_status(self, selection_type: str):
        return f"🗑️ All {selection_type} selections have been cleared."

    def get_timeout_status(self):
        return "⏰ This interface has expired due to inactivity."

        
class PokemonTypeSelect(discord.ui.View):
    def __init__(self, bot, user_id: int, collection_type: str, mongo_helper,
                 pokemon_types: list[str], current_types: list[str] | None = None, status=None):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.collection_type = collection_type
        self.mongo = mongo_helper
        self.pokemon_types = pokemon_types
        self.current_types = set(current_types or [])
        self.status_message = status
        self.message = None
        self.config = TR_Embed_Config()
        self.afk_collection = self.mongo.db["afk_type_storage"]

        try:
            with open("data/commands/pokemon/pokemon_emojis/_pokemon_types.json", "r", encoding="utf-8") as f:
                raw_emojis = json.load(f)
        except Exception:
            print("Error loading emoji JSON:\n", traceback.format_exc())
            raw_emojis = {}

        self.emojis = {}
        for key, raw in raw_emojis.items():
            try:
                parts = raw.strip('<>').split(':')
                if len(parts) == 3:
                    _, name, emoji_id = parts
                    self.emojis[key.lower()] = discord.PartialEmoji(name=name, id=int(emoji_id))
                else:
                    self.emojis[key.lower()] = raw
            except Exception:
                print(f"Error parsing emoji for {key}:\n", traceback.format_exc())
                self.emojis[key.lower()] = raw

        self.clear_items()
        self.add_type_select(disabled=False)
        self.add_clear_button(disabled=False)
        self.add_afk_button(afk_on=False)
        self.add_help_button()

    def _get_emoji_by_name(self, name: str):
        for key, emoji in self.emojis.items():
            if name.lower() in key:
                return emoji
        return None

    def add_type_select(self, disabled=False):
        options = []
        for pt in self.pokemon_types:
            selected = pt in self.current_types
            emoji = self._get_emoji_by_name(pt)
            options.append(discord.SelectOption(
                label=pt.title(),
                value=pt,
                emoji=emoji if isinstance(emoji, (discord.PartialEmoji, str)) else None,
                default=selected
            ))
        select = discord.ui.Select(
            placeholder="🎯 Select Pokémon Types to get pinged for...",
            min_values=0,
            max_values=len(self.pokemon_types),
            options=options,
            custom_id="pokemon_type_select",
            disabled=disabled
        )
        select.callback = self.select_callback
        self.add_item(select)

    def add_clear_button(self, disabled=False):
        clear_button = discord.ui.Button(
            label="Clear All", 
            style=discord.ButtonStyle.danger, 
            disabled=disabled,
            emoji="🗑️"
        )
        clear_button.callback = self.clear_callback
        self.add_item(clear_button)

    def add_help_button(self):
        help_button = discord.ui.Button(
            label="Help", 
            style=discord.ButtonStyle.primary,
            emoji="❓"
        )
        help_button.callback = self.help_callback
        self.add_item(help_button)

    def add_afk_button(self, afk_on: bool):
        label = "AFK Mode (ON)" if afk_on else "AFK Mode (OFF)"
        style = discord.ButtonStyle.success if afk_on else discord.ButtonStyle.secondary
        emoji = "😴" if afk_on else "💤"
        afk_button = discord.ui.Button(label=label, style=style, emoji=emoji)
        afk_button.callback = self.afk_toggle_callback
        self.add_item(afk_button)

    async def refresh_view(self):
        try:
            afk_data = await self.afk_collection.find_one({"user_id": self.user_id})
            afk_on = bool(afk_data)
            self.clear_items()
            self.add_type_select(disabled=afk_on)
            self.add_clear_button(disabled=afk_on)
            self.add_afk_button(afk_on)
            self.add_help_button()
        except Exception:
            print("Error in refresh_view:\n", traceback.format_exc())

    async def _create_embed(self, ctx=None, status_message=None, user=None):
        try:
            if user is None:
                if ctx:
                    if hasattr(ctx, "author"):
                        user = ctx.author
                    elif hasattr(ctx, "user"):
                        user = ctx.user

            afk_data = await self.afk_collection.find_one({"user_id": self.user_id})
            afk_on = bool(afk_data)

            title = self.config.get_title("type", is_afk=afk_on)
            color = self.config.afk_color if afk_on else self.config.primary_color
            embed = discord.Embed(title=title, color=color)

            if user and getattr(user, "avatar", None):
                embed.set_thumbnail(url=user.avatar.url)

            if afk_on:
                embed.description = self.config.get_afk_description("type")
                count = len(afk_data.get("types", []))
                if count > 0:
                    embed.add_field(**self.config.get_afk_saved_field(count, "type"))
            else:
                type_lines = []
                sorted_types = sorted(self.pokemon_types)
                for i in range(0, len(sorted_types), self.config.group_size):
                    row_types = sorted_types[i:i + self.config.group_size]
                    row_text = []
                    for pt in row_types:
                        selected = pt in self.current_types
                        mark = "`✅`" if selected else "`❌`"
                        emoji = self._get_emoji_by_name(pt)
                        emoji_str = str(emoji) if emoji else "🔹"
                        row_text.append(f"- {mark} {emoji_str} {pt.title()}")
                    type_lines.append("\n".join(row_text))
                embed.description = "\n".join(type_lines)

                if not self.current_types:
                    embed.description = self.config.get_no_selection_description("type") + "\n\n" + embed.description
                    #embed.add_field(**self.config.get_how_it_works_field("type"))

            footer_text = self.config.get_footer_text(status_message)
            embed.set_footer(
                text=footer_text,
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )

            return embed

        except Exception:
            print("Error in _create_embed:\n", traceback.format_exc())
            return self.config.get_error_embed("❌ Error", "Failed to render type selection interface.")

    async def select_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ Only the command author can use this interface.", ephemeral=True)

            self.current_types = set(interaction.data.get("values", []))
            collection = self.mongo.db[f"{self.collection_type}_types"]

            await collection.delete_many({"user_id": self.user_id})
            docs = [{"user_id": self.user_id, "type": t} for t in self.current_types]
            if docs:
                await collection.insert_many(docs)

            await self.refresh_view()

            status_msg = self.config.get_cleared_status("type") if not self.current_types else None
            embed = await self._create_embed(interaction, status_message=status_msg)
            await interaction.response.edit_message(embed=embed, view=self)
            self.message = interaction.message
        except Exception:
            print("Error in select_callback:\n", traceback.format_exc())
            await interaction.response.send_message("❌ An error occurred while updating your selection.", ephemeral=True)

    async def clear_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ Only the command author can clear selections.", ephemeral=True)

            self.current_types.clear()
            collection = self.mongo.db[f"{self.collection_type}_types"]
            await collection.delete_many({"user_id": self.user_id})

            await self.refresh_view()
            embed = await self._create_embed(interaction, status_message=self.config.get_cleared_status("type"))
            await interaction.response.edit_message(embed=embed, view=self)
            self.message = interaction.message
        except Exception:
            print("Error in clear_callback:\n", traceback.format_exc())
            await interaction.response.send_message("❌ An error occurred while clearing selections.", ephemeral=True)

    async def afk_toggle_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ Only the command author can use this feature.", ephemeral=True)

            user_id = self.user_id
            collection = self.mongo.db[f"{self.collection_type}_types"]
            afk_collection = self.afk_collection
            afk_data = await afk_collection.find_one({"user_id": user_id})
            current_data = list(self.current_types)

            if afk_data:
                # Turning AFK OFF - restore saved types
                self.current_types = set(afk_data.get("types", []))
                await afk_collection.delete_one({"user_id": user_id})
                await collection.delete_many({"user_id": user_id})
                await collection.insert_many([{"user_id": user_id, "type": t} for t in self.current_types])
                
                status_msg = self.config.get_afk_off_status(len(self.current_types), "type")
            else:
                # Turning AFK ON - save current types
                if not self.current_types:
                    return await interaction.response.send_message("❌ You need to select some types before enabling AFK mode.", ephemeral=True)

                await afk_collection.insert_one({"user_id": user_id, "types": current_data})
                await collection.delete_many({"user_id": user_id})
                self.current_types.clear()

                status_msg = self.config.get_afk_on_status(len(current_data), "type")

            await self.refresh_view()
            embed = await self._create_embed(interaction, status_message=status_msg)
            await interaction.response.edit_message(embed=embed, view=self)
            self.message = interaction.message
        except Exception:
            print("Error in afk_toggle_callback:\n", traceback.format_exc())
            await interaction.response.send_message("❌ Failed to toggle AFK mode.", ephemeral=True)

    async def help_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ Only the command author can view help.", ephemeral=True)

            embed = discord.Embed(
                title=self.config.get_help_title("type"),
                description=self.config.get_help_description("type"),
                color=0x3498DB
            )
            
            embed.add_field(**self.config.get_how_pings_work_field("type", self.bot.user.mention))
            
            embed.add_field(**self.config.get_interface_usage_field("type"))
            
            embed.add_field(**self.config.get_afk_benefits_field())
            
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            print("Error in help_callback:\n", traceback.format_exc())
            await interaction.response.send_message("❌ Error displaying help information.", ephemeral=True)

    async def on_timeout(self):
        try:
            user = await self.bot.fetch_user(self.user_id)
            for item in self.children:
                item.disabled = True
            if self.message:
                embed = await self._create_embed(status_message=self.config.get_timeout_status(), user=user)
                await self.message.edit(embed=embed, view=self)
            self.stop()
        except Exception:
            print("Error in on_timeout:\n", traceback.format_exc())

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command author can use these options.", ephemeral=True)
            return False
        return True

    def parse_type_input(self, user_input: str) -> set[str]:
        valid_types = {t.lower() for t in self.pokemon_types}
        parts = [p.strip().lower() for p in user_input.replace(',', ' ').split()]
        return {t for t in parts if t in valid_types}
  
class PokemonRegionSelect(discord.ui.View):
    def __init__(self, bot, user_id: int, collection_type: str, mongo_helper,
                 pokemon_regions: list[str], current_regions: list[str] | None = None, status=None):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.collection_type = collection_type
        self.mongo = mongo_helper
        self.pokemon_regions = [r for r in pokemon_regions if r.lower() != "hisui"]
        self.current_regions = set(r for r in (current_regions or []) if r.lower() != "hisui")
        self.status_message = status
        self.message = None
        self.config = TR_Embed_Config()
        self.afk_collection = self.mongo.db["afk_region_storage"]

        # Load emojis
        try:
            with open("data/commands/pokemon/pokemon_emojis/_pokemon_quest.json", "r", encoding="utf-8") as f:
                raw_emojis = json.load(f)
        except Exception:
            print("Error loading emoji JSON:\n", traceback.format_exc())
            raw_emojis = {}

        self.emojis = {}
        for key, raw in raw_emojis.items():
            try:
                parts = raw.strip('<>').split(':')
                if len(parts) == 3:
                    _, name, emoji_id = parts
                    self.emojis[key.lower()] = discord.PartialEmoji(name=name, id=int(emoji_id))
                else:
                    self.emojis[key.lower()] = raw
            except Exception:
                self.emojis[key.lower()] = raw

        # Initialize view
        self.clear_items()
        self.add_region_select(disabled=False)
        self.add_clear_button(disabled=False)
        self.add_afk_button(afk_on=False)
        self.add_help_button()

    def _get_emoji_by_name(self, name: str):
        return self.emojis.get(name.lower())

    def add_region_select(self, disabled=False):
        options = []
        for region in self.pokemon_regions:
            selected = region in self.current_regions
            emoji = self._get_emoji_by_name(region)
            options.append(discord.SelectOption(
                label=region.title(),
                value=region,
                emoji=emoji if isinstance(emoji, (discord.PartialEmoji, str)) else None,
                default=selected
            ))
        select = discord.ui.Select(
            placeholder="🌍 Select Pokémon Regions...",
            min_values=0,
            max_values=len(self.pokemon_regions),
            options=options,
            custom_id="pokemon_region_select",
            disabled=disabled
        )
        select.callback = self.select_callback
        self.add_item(select)

    def add_clear_button(self, disabled=False):
        clear_button = discord.ui.Button(
            label="Clear All",
            style=discord.ButtonStyle.danger,
            disabled=disabled,
            emoji="🗑️"
        )
        clear_button.callback = self.clear_callback
        self.add_item(clear_button)

    def add_help_button(self):
        help_button = discord.ui.Button(
            label="Help",
            style=discord.ButtonStyle.primary,
            emoji="❓"
        )
        help_button.callback = self.help_callback
        self.add_item(help_button)

    def add_afk_button(self, afk_on: bool):
        label = "AFK Mode (ON)" if afk_on else "AFK Mode (OFF)"
        style = discord.ButtonStyle.success if afk_on else discord.ButtonStyle.secondary
        emoji = "😴" if afk_on else "💤"
        afk_button = discord.ui.Button(label=label, style=style, emoji=emoji)
        afk_button.callback = self.afk_toggle_callback
        self.add_item(afk_button)

    async def refresh_view(self):
        try:
            afk_data = await self.afk_collection.find_one({"user_id": self.user_id})
            afk_on = bool(afk_data)
            self.clear_items()
            self.add_region_select(disabled=afk_on)
            self.add_clear_button(disabled=afk_on)
            self.add_afk_button(afk_on)
            self.add_help_button()
        except Exception:
            print("Error in refresh_view:\n", traceback.format_exc())

    async def _create_embed(self, ctx=None, status_message=None, user=None):
        try:
            if user is None:
                user = getattr(ctx, "user", None) or getattr(ctx, "author", None)

            afk_data = await self.afk_collection.find_one({"user_id": self.user_id})
            afk_on = bool(afk_data)

            title = self.config.get_title("region", is_afk=afk_on)
            color = self.config.afk_color if afk_on else self.config.primary_color
            embed = discord.Embed(title=title, color=color)

            if user and getattr(user, "avatar", None):
                embed.set_thumbnail(url=user.avatar.url)

            if afk_on:
                embed.description = self.config.get_afk_description("region")
                count = len(afk_data.get("regions", []))
                if count > 0:
                    embed.add_field(**self.config.get_afk_saved_field(count, "region"))
            else:
                lines = []
                sorted_regions = sorted(self.pokemon_regions)
                for i in range(0, len(sorted_regions), self.config.group_size):
                    row = sorted_regions[i:i + self.config.group_size]
                    row_text = []
                    for r in row:
                        selected = r in self.current_regions
                        mark = "`✅`" if selected else "`❌`"
                        emoji = self._get_emoji_by_name(r)
                        emoji_str = str(emoji) if emoji else "🔹"
                        row_text.append(f"- {mark} {emoji_str} {r.title()}")
                    lines.append("\n".join(row_text))
                embed.description = "\n".join(lines)

                if not self.current_regions:
                    embed.description = self.config.get_no_selection_description("region") + "\n\n" + embed.description
                    #embed.add_field(**self.config.get_how_it_works_field("region"))

            footer_text = self.config.get_footer_text(status_message or self.status_message)
            embed.set_footer(
                text=footer_text,
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )
            return embed
        except Exception:
            print("Error in _create_embed:\n", traceback.format_exc())
            return self.config.get_error_embed("❌ Error", "Failed to render region selection.")

    async def select_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ Only the command author can use this interface.", ephemeral=True)

            self.current_regions = {r for r in interaction.data.get("values", []) if r.lower() != "hisui"}
            collection = self.mongo.db[self.collection_type]

            await collection.update_one(
                {"user_id": self.user_id},
                {"$set": {"regions": list(self.current_regions)}},
                upsert=True
            )

            await self.refresh_view()
            status_msg = self.config.get_cleared_status("region") if not self.current_regions else None
            embed = await self._create_embed(interaction, status_message=status_msg)
            await interaction.response.edit_message(embed=embed, view=self)
            self.message = interaction.message
        except Exception:
            print("Error in select_callback:\n", traceback.format_exc())
            await interaction.response.send_message("❌ Failed to update selection.", ephemeral=True)

    async def clear_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ Only the command author can clear selections.", ephemeral=True)

            self.current_regions.clear()
            await self.mongo.db[self.collection_type].update_one(
                {"user_id": self.user_id}, {"$set": {"regions": []}}, upsert=True
            )
            await self.refresh_view()
            embed = await self._create_embed(interaction, status_message=self.config.get_cleared_status("region"))
            await interaction.response.edit_message(embed=embed, view=self)
            self.message = interaction.message
        except Exception:
            print("Error in clear_callback:\n", traceback.format_exc())
            await interaction.response.send_message("❌ An error occurred while clearing selections.", ephemeral=True)

    async def afk_toggle_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ Only the command author can toggle AFK.", ephemeral=True)

            afk_data = await self.afk_collection.find_one({"user_id": self.user_id})
            collection = self.mongo.db[self.collection_type]
            current_data = list(self.current_regions)

            if afk_data:
                # AFK OFF: restore
                self.current_regions = set(afk_data.get("regions", []))
                await self.afk_collection.delete_one({"user_id": self.user_id})
                await collection.update_one(
                    {"user_id": self.user_id}, {"$set": {"regions": list(self.current_regions)}}, upsert=True
                )
                status_msg = self.config.get_afk_off_status(len(self.current_regions), "region")
            else:
                # AFK ON: store current
                if not self.current_regions:
                    return await interaction.response.send_message("❌ Select regions before enabling AFK.", ephemeral=True)
                await self.afk_collection.insert_one({"user_id": self.user_id, "regions": current_data})
                await collection.update_one({"user_id": self.user_id}, {"$set": {"regions": []}}, upsert=True)
                self.current_regions.clear()
                status_msg = self.config.get_afk_on_status(len(current_data), "region")

            await self.refresh_view()
            embed = await self._create_embed(interaction, status_message=status_msg)
            await interaction.response.edit_message(embed=embed, view=self)
            self.message = interaction.message
        except Exception:
            print("Error in afk_toggle_callback:\n", traceback.format_exc())
            await interaction.response.send_message("❌ Failed to toggle AFK mode.", ephemeral=True)

    async def help_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ Only the command author can view help.", ephemeral=True)

            embed = discord.Embed(
                title=self.config.get_help_title("region"),
                description=self.config.get_help_description("region"),
                color=0x3498DB
            )
            embed.add_field(**self.config.get_how_pings_work_field("region", self.bot.user.mention))
            embed.add_field(**self.config.get_interface_usage_field("region"))
            embed.add_field(**self.config.get_afk_benefits_field())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            print("Error in help_callback:\n", traceback.format_exc())
            await interaction.response.send_message("❌ Error displaying help information.", ephemeral=True)

    async def on_timeout(self):
        try:
            user = await self.bot.fetch_user(self.user_id)
            for item in self.children:
                item.disabled = True
            if self.message:
                embed = await self._create_embed(status_message=self.config.get_timeout_status(), user=user)
                await self.message.edit(embed=embed, view=self)
            self.stop()
        except Exception:
            print("Error in on_timeout:\n", traceback.format_exc())

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command author can use this interface.", ephemeral=True)
            return False
        return True

    def parse_region_input(self, user_input: str) -> set[str]:
        valid_regions = {r.lower() for r in self.pokemon_regions}
        parts = [p.strip().lower() for p in user_input.replace(',', ' ').split()]
        return {r for r in parts if r in valid_regions and r != "hisui"}       