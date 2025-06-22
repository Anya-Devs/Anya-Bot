import os, re, csv, json, asyncio, traceback
import aiofiles, aiohttp, requests, motor.motor_asyncio
import pandas as pd
from fuzzywuzzy import fuzz
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from imports.log_imports import *
from utils.subcogs.pokemon import *
from imports.discord_imports import *




class Pokemon_Commands:
    def __init__(self, bot):
        self.bot = bot
        self.flag_mapping = {
            "en": "🇬🇧", "fr": "🇫🇷", "es": "🇪🇸", "de": "🇩🇪", "it": "🇮🇹", "ja": "🇯🇵",
            "ko": "🇰🇷", "zh-Hans": "🇨🇳", "ru": "🇷🇺", "es-MX": "🇲🇽", "pt": "🇵🇹",
            "nl": "🇳🇱", "tr": "🇹🇷", "ar": "🇸🇦", "th": "🇹🇭", "vi": "🇻🇳", "pl": "🇵🇱",
            "sv": "🇸🇪", "da": "🇩🇰", "no": "🇳🇴", "fi": "🇫🇮", "el": "🇬🇷", "id": "🇮🇩",
            "ms": "🇲🇾", "fil": "🇵🇭", "hu": "🇭🇺", "cs": "🇨🇿", "sk": "🇸🇰", "ro": "🇷🇴",
            "uk": "🇺🇦", "hr": "🇭🇷", "bg": "🇧🇬", "et": "🇪🇪", "lv": "🇱🇻", "lt": "🇱🇹",
            "sl": "🇸🇮", "mt": "🇲🇹", "sq": "🇦🇱", "mk": "🇲🇰", "bs": "🇧🇦", "sr": "🇷🇸",
            "cy": "🇨🇾", "ga": "🇮🇪", "gd": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "kw": "🇰🇾", "br": "🇧🇷", "af": "🇿🇦",
            "xh": "🇿🇦", "zu": "🇿🇦", "tn": "🇿🇦", "st": "🇿🇦", "ss": "🇿🇦", "nr": "🇿🇦",
            "nso": "🇿🇦", "ts": "🇿🇦", "ve": "🇿🇦", "xog": "🇺🇬", "lg": "🇺🇬", "ak": "🇬🇭",
            "tw": "🇬🇭", "bm": "🇧🇫", "my": "🇲🇲", "km": "🇰🇭", "lo": "🇱🇦", "am": "🇪🇹",
            "ti": "🇪🇹", "om": "🇪🇹", "so": "🇸🇴", "sw": "🇰🇪", "rw": "🇷🇼", "yo": "🇳🇬",
            "ig": "🇳🇬", "ha": "🇳🇬", "bn": "🇧🇩", "pa": "🇮🇳", "gu": "🇮🇳", "or": "🇮🇳",
            "ta": "🇮🇳", "te": "🇮🇳", "kn": "🇮🇳", "ml": "🇮🇳", "si": "🇱🇰", "ne": "🇳🇵",
            "dz": "🇧🇹", "be": "🇧🇾", "kk": "🇰🇿", "uz": "🇺🇿", "ky": "🇰🇬"
        }
        self.region_mappings = {
            "Paldea": "<:Paldea:1212335178714980403>",
            "Sinnoh": "<:Sinnoh:1212335180459544607>",
            "Alola": "<:Alola:1212335185228472411>",
            "Kalos": "<:Kalos:1212335190656024608>",
            "Galar": "<:Galar:1212335192740470876>",
            "Pasio": "<:848495108667867139:1212335194628034560>",
            "Hoenn": "<:Hoenn:1212335197304004678>",
            "Unova": "<:Unova:1212335199095095306>",
            "Kanto": "<:Kanto:1212335202341363713>",
            "Johto": "<:Kanto:1212335202341363713>",
        }
        self.stat_name_mapping = {
            "hp": "Hp",
            "special-attack": "Sp. Atk",
            "special-defense": "Sp. Def",
        }

    async def send_pokemon_info(self, ctx, data,type, color):
        
        name = data["name"].capitalize()
        id = data["id"]
        types = [t["type"]["name"].capitalize() for t in data["types"]]
        pokemon_type_unformatted = types

        species_name = name.replace('-', ' ')
        base_url = "https://pokeapi.co/api/v2/pokemon-species/"
        
        if type == "mega":
            mega_url = f"https://pokeapi.co/api/v2/pokemon/{name.lower()}-mega"
            mega_response = requests.get(mega_url)
            if mega_response.status_code == 200:
                try:
                    mega_data = mega_response.json()
                    data_species = mega_response.json()
                except json.JSONDecodeError:
                    await ctx.send(f"Failed to parse JSON data for mega evolution of `{name}`.")
            else:
                await ctx.send(f"Mega evolution data not found for `{name}`.")
        else:
            url = f"{base_url}{name.lower()}/"
            response_species = requests.get(url)
            if response_species.status_code != 200:
                url = f"https://pokeapi.co/api/v2/pokemon-form/{name.lower()}/"
                form_response = requests.get(url)
                if form_response.status_code == 200:
                    data_species = form_response.json()
            else:
                data_species = response_species.json()

        pokemon_description = self.get_pokemon_description(id)
        region = self.get_pokemon_region(id)
        
        if type == "shiny":
            image_url = data["sprites"]["other"]["official-artwork"]["front_shiny"]
            image_thumb = data["sprites"]["versions"]["generation-v"]["black-white"]["animated"]["front_shiny"]
        elif type == "mega":
            mega_url = f"https://pokeapi.co/api/v2/pokemon/{name.lower()}-mega"
            mega_response = requests.get(mega_url)
            if mega_response.status_code == 200:
                try:
                    mega_data = mega_response.json()
                    data = mega_data
                    image_url = mega_data["sprites"]["other"]["official-artwork"]["front_default"]
                    image_thumb = mega_data["sprites"]["versions"]["generation-v"]["black-white"]["animated"]["front_default"]
                except json.JSONDecodeError:
                    await ctx.send(f"Failed to parse JSON data for mega evolution of `{name}`.")
            else:
                await ctx.send(f"Mega evolution data not found for `{name}`.")
        else:
            image_url = data["sprites"]["other"]["official-artwork"]["front_default"]
            image_thumb = data["sprites"]["versions"]["generation-v"]["black-white"]["animated"]["front_default"]

        height, weight = float(int(data["height"])) / 10, float(int(data["weight"])) / 10
        max_stat = 255

        def format_base_stats(stats, name_map, max_stat=255, bar_length=9, filled='▰', empty='▱'):
         def format_bar(value):
          filled_len = int(value / max_stat * bar_length)
          return filled * filled_len + empty * (bar_length - filled_len)
    
         return [
             f"{name_map.get(stat['stat']['name'], stat['stat']['name']).title().replace('Hp', 'Health'):<10} "
             f"{stat['base_stat']:>5} {format_bar(stat['base_stat'])}"
             for stat in stats
             ]
        
        base_stats = "\n".join(format_base_stats(data["stats"], self.stat_name_mapping))


        alternate_names = self.get_pokemon_alternate_names(data_species, species_name)
        
        if alternate_names:
            alt_names_info = {}
            for name, lang in alternate_names:
                key = name.lower()
                flag = self.flag_mapping.get(lang, None)
                if name.lower() != lang.lower() and flag is not None:
                    if key not in alt_names_info:
                        alt_names_info[key] = f"{flag} {name}"
            name_list = sorted(list(alt_names_info.values()), key=lambda x: x.split(" ")[-1])
            alt_names_str = "\n".join(name_list[:6])
        else:
            alt_names_str = "No alternate names available."

        type_chart = await self.get_type_chart()
        weaknesses, strengths = self.find_pokemon_weaknesses(data, type_chart)

        gender = self.get_pokemon_gender_ratio_display(data_species)
        rarity = self.determine_pokemon_category(data_species)

        if pokemon_description != " ":
            embed_title = f" #{id} — {species_name.title()}" if type != "shiny" else f" #{id} — ✨ {species_name.title()}"
            embed = discord.Embed(
                title=embed_title,
                description=f"\n{pokemon_description}\n",
                color=color,
            )
        else:
            embed_title = f" #{id} — {species_name.title()}" if type != "shiny" else f" #{id} — ✨ {species_name.title()}"
            embed = discord.Embed(
                title=embed_title,
                color=color,
            )

        pokemon_dex_name = embed_title
        embed.set_image(url=image_url)
        description = f"\n{pokemon_description}\n" if pokemon_description != " " else None

        
        wes = self.format_strengths_weaknesses(weaknesses, strengths)
        pokemon_type = self.format_pokemon_type(pokemon_type_unformatted)

        h_w = f"Height: {height:.2f} m\nWeight: {weight:.2f} kg"
        appearance = h_w
        
        if region:
            region = region.title()
            if region in self.region_mappings:
                region_emoji = self.region_mappings[region]
                embed.add_field(name="Region", value=f"{region_emoji} {region}", inline=True)
                region = f"{region_emoji} {region}"

        embed.add_field(name="Names", value=alt_names_str, inline=True)

        gender_differ = False
        if gender is not None:
            gender_differ = bool(gender != "♀️ Female only" or "♂️ Male only" or "Genderless")
            
        gender_info = None
        if image_thumb:
            if gender is not None and gender != "♂ 50% - ♀ 50%":
                embed.set_footer(icon_url=image_thumb, text=appearance + f"Gender: {gender}")
                gender_info = f"Gender: {gender}"
            else:
                embed.set_footer(icon_url=image_thumb, text=appearance)
        else:
            if type == "shiny":
                image_thumb = data["sprites"]["versions"]["generation-v"]["black-white"]["front_shiny"]
            else:
                image_thumb = data["sprites"]["versions"]["generation-v"]["black-white"]["front_default"]

            if image_thumb:
                if gender and rarity is not None and gender != "♂ 50% - ♀ 50%":
                    embed.set_footer(
                        icon_url=image_thumb,
                        text=f"Rarity: {rarity}\n\n{appearance}Gender: {gender}",
                    )
                    gender_info = f"Gender: {gender}"
                elif gender is not None and gender != "♂ 50% - ♀ 50%":
                    embed.set_footer(icon_url=image_thumb, text=f"{appearance}Gender: {gender}")
                    gender_info = f"Gender: {gender}"
                else:
                    embed.set_footer(icon_url=image_thumb, text=appearance)
            else:
                embed.set_footer(text=appearance)

        self.bot.add_view(Pokebuttons(alt_names_str, species_name))

        await ctx.reply(
            embed=embed,
            view=Pokebuttons(
                alt_names_str, species_name, base_stats, type, wes,
                pokemon_type, image_url, h_w, image_thumb,
                pokemon_dex_name, color, data, gender_differ, region,
                description, gender_info, self.bot
            ),
            mention_author=False,
        )

    def get_pokemon_description(self, pokemon_id, file_path="data/commands/pokemon/pokemon_description.csv"):
        with open(file_path, mode="r", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if row["id"] == str(pokemon_id):
                    return row["description"]
        return "Pokémon ID not found"

    def get_pokemon_region(self, pokemon_id, file_path="data/commands/pokemon/pokemon_description.csv"):
        try:
            with open(file_path, mode="r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    if row["id"] == str(pokemon_id):
                        return row["region"]
        except (FileNotFoundError, PermissionError, Exception):
            return None
        return None

    def get_pokemon_alternate_names(self, data_species, pokemon_name):
        try:
            if data_species:
                alternate_names = [(name["name"], name["language"]["name"]) for name in data_species["names"]]
                return alternate_names
            return None
        except KeyError:
            return None

    async def get_type_chart(self, max_retries=3):
        url = "https://pokeapi.co/api/v2/type"
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            type_chart = {}
                            types_data = (await response.json())["results"]
                            for type_data in types_data:
                                type_name = type_data["name"]
                                effectiveness_url = type_data["url"]
                                async with session.get(effectiveness_url) as effectiveness_response:
                                    if effectiveness_response.status == 200:
                                        damage_relations = (await effectiveness_response.json())["damage_relations"]
                                        type_chart[type_name] = {
                                            "double_damage_to": [],
                                            "half_damage_to": [],
                                            "no_damage_to": [],
                                            "double_damage_from": [],
                                            "half_damage_from": [],
                                            "no_damage_from": [],
                                        }
                                        for key, values in damage_relations.items():
                                            for value in values:
                                                type_chart[type_name][key].append(value["name"])
                            return type_chart
            except Exception:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
        return None

    def find_pokemon_weaknesses(self, pokemon_info, type_chart):
        if pokemon_info is None:
            return None, None
        types = [t["type"]["name"] for t in pokemon_info["types"]]
        weaknesses = set()
        strengths = set()
        for pokemon_type in types:
            weaknesses.update(type_chart.get(pokemon_type, {}).get("double_damage_from", []))
            strengths.update(type_chart.get(pokemon_type, {}).get("double_damage_to", []))
        weaknesses.discard("")
        weaknesses = {weakness.capitalize() for weakness in weaknesses}
        strengths = {strength.capitalize() for strength in strengths}
        return weaknesses, strengths

    def format_strengths_weaknesses(self, weaknesses, strengths):

     header_bullet = "□"
     branch_middle = "├─"
     branch_end = "└─"
     none_text = "None"
     def format_section(title, items):
        items = list(items)
        if not items:
            return f"{header_bullet} {title}\n{branch_end} {none_text}"
        if len(items) == 1:
            return f"{header_bullet} {title}\n{branch_end} {items[0]}"
        lines = [f"{branch_middle} {item}" for item in items[:-1]]
        lines.append(f"{branch_end} {items[-1]}")
        return f"{header_bullet} {title}\n" + "\n".join(lines)

     strengths_text = format_section("Strengths", strengths)
     weaknesses_text = format_section("Weaknesses", weaknesses)

     return f"{strengths_text}\n\n{weaknesses_text}"
    
    def format_pokemon_type(self, pokemon_type_unformatted):
     # Editable formatting config
     header_bullet = "□"
     branch_middle = "├─"
     branch_end = "└─"
     none_text = "None"

     types = list(pokemon_type_unformatted)
     if not types:
        types_formatted = f"{branch_end} {none_text}"
     elif len(types) == 1:
        types_formatted = f"{branch_end} {types[0]}"
     else:
        lines = [f"{branch_middle} {t}" for t in types[:-1]]
        lines.append(f"{branch_end} {types[-1]}")
        types_formatted = "\n".join(lines)

     return f"{header_bullet} Type\n{types_formatted}\n\n"







    def get_pokemon_gender_ratio_display(self, data_species):
        try:
            gender_rate = data_species["gender_rate"]
            if gender_rate == -1:
                return "Genderless"
            elif gender_rate == 0:
                return "♂️ Male only"
            else:
                female_ratio = (8 - gender_rate) / 8
                male_ratio = gender_rate / 8
                male_percentage = int(female_ratio * 100)
                female_percentage = int(male_ratio * 100)
                if female_percentage == 100:
                    return "♀️ Female only"
                elif male_percentage == 100:
                    return "♂️ Male only"
                return f"♂ {male_percentage}% - ♀ {female_percentage}%"
        except KeyError:
            return None

    def determine_pokemon_category(self, data_species):
        try:
            if data_species:
                if data_species["is_legendary"]:
                    return "Legendary"
                elif data_species["is_mythical"]:
                    return "Mythical"
                else:
                    flavor_text_entries = data_species["flavor_text_entries"]
                    english_flavor = next(
                        (entry["flavor_text"] for entry in flavor_text_entries 
                         if entry["language"]["name"] == "en"), None)
                    if english_flavor and "ultra beast" in english_flavor.lower():
                        return "Ultra Beast"
            return None
        except KeyError:
            return None





class PokeSelect(discord.ui.Select):
    def __init__(self, pokemon_forms, default_image_url, alt_names, pokemon_shiny, gender, bot, selected_index=None):
        self.bot = bot

        self.emoji_json_path = "data/commands/pokemon/pokemon_emojis.json"
        self.pokemon_csv_path = "data/commands/pokemon/pokemon_description.csv"
        
        self.pokemon_api_url = "https://pokeapi.co/api/v2/pokemon/"
        self.pokemon_form_api_url = "https://pokeapi.co/api/v2/pokemon-form/"

        self.emoji_mapping = self.load_emoji_mapping()
        self.pokemon_df = pd.read_csv(self.pokemon_csv_path)

        def is_base_form(form):
            return '-' not in form["name"] or all(x not in form["name"] for x in ["mega", "gmax", "alola", "galar", "hisui", "kalos"])

        pokemon_forms.sort(key=lambda f: (not is_base_form(f), f["name"]))

        self.selected_index = selected_index if selected_index is not None else 0
        
        self.form_urls = []

        options = []
        for index, form in enumerate(pokemon_forms):
            form_name = form["name"]
            formatted_name = self.format_pokemon_name(form_name)
            pokemon_id = self.get_pokemon_id(form_name)
            description = self.get_pokemon_description(pokemon_id['id'])

            emo = Pokemon_Emojis(bot=self.bot)
            emoji = emo.call_emoji(self.emoji_mapping, pokemon_id)

            form_url = f"{self.pokemon_api_url}{form_name.lower()}"
            self.form_urls.append(form_url)

            option = discord.SelectOption(
                label=formatted_name,
                value=form_url,
                description=f"{description[:54]}..." if len(description) > 1 else None,
                emoji=emoji,
                default=(index == self.selected_index)
            )
            options.append(option)

        super().__init__(
            options=options,
            placeholder=options[0].label if options else "Select a Pokémon form",
            custom_id="Select_Pokemon_Form",
            max_values=1,
            min_values=0
        )

        self.default_image_url = default_image_url
        self.alt_names = alt_names
        self.pokemon_type = pokemon_shiny
        self.gender = gender

        self.region_flag_mapping = RegionFlagMapping()
        self.region_mappings = self.region_flag_mapping.region_mappings
        self.flag_mapping = self.region_flag_mapping.flag_mapping

    def get_flag(self, lang):
        return self.flag_mapping.get(lang)
    
    def get_pokemon_id(self, form_name):
        url = f"{self.pokemon_api_url}{form_name.lower()}"
        response = requests.get(url)
        data = response.json()
        return {"id": data["id"], "slug": form_name.lower()}

    def format_pokemon_name(self, name):     
        special_forms = {
            "alola": "Alolan",
            "gmax": "Gigantamax",  
            "mega": "Mega",
            "galar": "Galarian",
            "hisui": "Hisuian",
            "kalos": "Kalosian",
        }

        if "-" in name:
            parts = name.split("-")
            formatted_parts = [special_forms.get(parts[1], parts[1].capitalize()), parts[0].capitalize()]
            formatted_name = " ".join(formatted_parts)
            return formatted_name
        else:
            return name.capitalize()

    def load_emoji_mapping(self):
        if os.path.exists(self.emoji_json_path):
            with open(self.emoji_json_path, "r") as f:
                return json.load(f)
        else:
            return {}

    @staticmethod
    def get_pokemon_description(pokemon_id, file_path="data/commands/pokemon/pokemon_description.csv"):
        try:
            with open(file_path, mode="r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    if row["id"] == str(pokemon_id):
                        return row["description"]
        except FileNotFoundError:
            return "File not found"
        except PermissionError:
            return "Permission denied"
        except Exception as e:
            print(f"An error occurred: {e}")
            return f"An error occurred: {e}"
        return "Pokémon ID not found"

    @staticmethod
    def get_pokemon_region(pokemon_id, file_path="data/commands/pokemon/pokemon_description.csv"):
        try:
            with open(file_path, mode="r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    if row["id"] == str(pokemon_id):
                        return row["region"]
        except FileNotFoundError:
            return None
        except PermissionError:
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None
        return None

    def get_alternate_names(self, pokemon_name):
        alternate_names = []
        form_endpoint = f"{self.pokemon_form_api_url}{pokemon_name}"
        try:
            response = requests.get(form_endpoint)
            response.raise_for_status()
            data = response.json()
            for name_data in data["names"]:
                lang = name_data["language"]["name"]
                name = name_data["name"]
                flag = self.flag_mapping.get(lang)
                if flag and name.lower() != lang.lower():
                    alternate_names.append((name, lang))
        except requests.exceptions.RequestException:
            species_endpoint = f"{self.pokemon_api_url}{pokemon_name}"
            try:
                response = requests.get(species_endpoint)
                response.raise_for_status()
                data = response.json()
                for name_data in data["names"]:
                    lang = name_data["language"]["name"]
                    name = name_data["name"]
                    flag = self.flag_mapping.get(lang)
                    if flag and name.lower() != lang.lower():
                        alternate_names.append((name, lang))
            except requests.exceptions.RequestException as e:
                print(f"Error fetching alternate names: {e}")
        return alternate_names

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_form_url = self.values[0]
            await interaction.response.defer()

            if selected_form_url in self.form_urls:
                new_index = self.form_urls.index(selected_form_url)
                self.selected_index = new_index

            response = requests.get(selected_form_url)

            if response.status_code == 200:
                data = response.json()
                official_artwork_url = None
                if "sprites" in data and "other" in data["sprites"]:
                    if "official-artwork" in data["sprites"]["other"]:
                        if self.pokemon_type == "shiny":
                            official_artwork_url = data["sprites"]["other"]["official-artwork"]["front_shiny"]
                            image_thumb = data["sprites"]["versions"]["generation-v"]["black-white"]["front_shiny"]
                        else:
                            official_artwork_url = data["sprites"]["other"]["official-artwork"]["front_default"]
                            image_thumb = data["sprites"]["versions"]["generation-v"]["black-white"]["front_default"]

                embed = interaction.message.embeds[0]
                if official_artwork_url:
                    embed.set_image(url=official_artwork_url)
                else:
                    embed.set_image(url=self.default_image_url)

                pokemon_data = requests.get(selected_form_url).json()
                if pokemon_data:
                    description = self.get_pokemon_description(pokemon_data["id"])
                    height, weight = (
                        float(int(pokemon_data["height"])) / 10,
                        float(int(pokemon_data["weight"])) / 10,
                    )
                    footer_text = (
                        f"Height: {height:.2f} m\nWeight: {weight:.2f} kg"
                        if self.gender is None
                        else f"Height: {height:.2f} m\nWeight: {weight:.2f} kg\t\t"
                        + self.gender
                    )
                    embed.title = (
                        f"#{pokemon_data['id']} — {pokemon_data['name'].replace('-', ' ').title()}"
                        if self.pokemon_type != "shiny"
                        else f"#{pokemon_data['id']} — ✨ {pokemon_data['name'].replace('-', ' ').title()}"
                    )
                    embed.description = description
                    if image_thumb:
                        embed.set_footer(icon_url=str(image_thumb), text=footer_text)
                    else:
                        embed.set_footer(text=footer_text)

                    names_field = next((field for field in embed.fields if field.name == "Names"), None)
                    if names_field:
                        embed.remove_field(embed.fields.index(names_field))

                    embed.clear_fields()

                    pokemon_region = self.get_pokemon_region(pokemon_data["id"])
                    if pokemon_region and pokemon_region in self.region_mappings:
                        region_emoji = self.region_mappings[pokemon_region]
                        embed.add_field(
                            name="Region",
                            value=f"{region_emoji} {pokemon_region.title()}",
                            inline=True,
                        )

                    if names_field:
                        alternate_names = self.get_alternate_names(pokemon_data["name"])
                        alt_names_info = {}
                        for name, lang in alternate_names:
                            key = name.lower()
                            flag = self.flag_mapping.get(lang, None)
                            if name.lower() != lang.lower() and flag is not None:
                                name_with_flag = f"{flag} {name}"
                                alt_names_info[key] = name_with_flag

                        sorted_names_by_length = dict(sorted(alt_names_info.items(), key=lambda item: len(item[1])))

                        if len(sorted_names_by_length) != len(alt_names_info):
                            sorted_names_by_name = dict(sorted(alt_names_info.items(), key=lambda item: item[1]))
                            name_list = sorted(list(sorted_names_by_name.values()))
                        else:
                            name_list = sorted(list(sorted_names_by_length.values()))

                        alt_names_str = "\n".join(name_list[:6])
                        embed.add_field(
                            name="Names", value=alt_names_str if len(alt_names_str) > 0 else self.alt_names, inline=True)

                view = discord.ui.View()
                
                new_select = PokeSelect(
                    pokemon_forms=[{"name": form_url.split("/")[-1]} for form_url in self.form_urls],
                    default_image_url=self.default_image_url,
                    alt_names=self.alt_names,
                    pokemon_shiny=self.pokemon_type,
                    gender=self.gender,
                    bot=self.bot,
                    selected_index=self.selected_index
                )
                
                view.add_item(new_select)
                
                await interaction.message.edit(embed=embed, view=view)
        except Exception as e:
            print(e)


class Pokebuttons(discord.ui.View):
    def __init__(
        self,
        alt_names_str=None,
        name=None,
        base_stats=None,
        type=None,
        wes=None,
        pokemon_type=None,
        image_url=None,
        h_w=None,
        image_thumb=None,
        pokemon_dex_name=None,
        color=None,
        pokemon_data=None,
        gender_differ=None,
        region=None,
        description=None,
        gender_info=None,
        bot=None
    ):
        super().__init__(timeout=None)
        self.alt_names_str = alt_names_str
        self.pokemon_name = name
        self.pokemon_shiny = type
        self.base_stats = base_stats
        self.s_and_w = wes
        self.pokemon_type = pokemon_type
        self.image_url = image_url
        self.height_and_weight = h_w
        self.image_thumb = image_thumb
        self.pokemon_dex_name = pokemon_dex_name
        self.color = color
        self.pokemon_data = pokemon_data
        self.gender_differ = gender_differ
        self.region = region
        self.description = description
        self.gender_info = gender_info
        self.bot = bot
        

        pokemon_forms = self.get_pokemon_forms()
        if pokemon_forms and len(pokemon_forms) > 1:
            self.add_item(
                PokeSelect(
                    pokemon_forms,
                    self.image_url,
                    self.alt_names_str,
                    self.pokemon_shiny,
                    self.gender_info,
                    self.bot
                )
            )

        self.POKEMON_DIR = "data/commands/pokemon"
        os.makedirs(self.POKEMON_DIR, exist_ok=True)
        self.POKEMON_IMAGES_FILE = os.path.join(
            self.POKEMON_DIR, "pokemon_images.txt"
        )
        if not os.path.exists(self.POKEMON_IMAGES_FILE):
            with open(self.POKEMON_IMAGES_FILE, "w") as file:
                file.write("")
        self.pokemon_images = self.load_pokemon_images()

        if self.check_pokemon_has_evolutions():
            self.evolves_button = discord.ui.Button(
                label="Evolutions",
                style=discord.ButtonStyle.gray,
                custom_id="Pokemon_Evolutions_Button",
                row=1
            )
            self.evolves_button.callback = self.show_evolutions_button
            self.add_item(self.evolves_button)

    def check_pokemon_has_evolutions(self):
        try:
            species_url = f"https://pokeapi.co/api/v2/pokemon-species/{self.pokemon_name.lower()}/"
            response = requests.get(species_url)
            if response.status_code != 200:
                return False
            species_data = response.json()
            evolution_chain_url = species_data.get("evolution_chain", {}).get("url")
            if not evolution_chain_url:
                return False
            
            chain_response = requests.get(evolution_chain_url)
            if chain_response.status_code != 200:
                return False
            evolution_chain_data = chain_response.json()
            chain = evolution_chain_data.get("chain")
            
            return self.has_evolutions_sync(chain)
        except Exception:
            return False

    def has_evolutions_sync(self, chain):
        queue = [chain]
        while queue:
            current = queue.pop(0)
            if current.get("evolves_to"):
                return True
            for evolution in current.get("evolves_to", []):
                queue.append(evolution)
        return False

    def get_pokemon_forms(self):
        url = f"https://pokeapi.co/api/v2/pokemon-species/{self.pokemon_name.lower()}"
        response = requests.get(url)
        if response.status_code == 200:
            forms = response.json().get("varieties", [])
            form_details = []
            for form in forms:
                form_name = form["pokemon"]["name"]
                form_url = f"https://pokeapi.co/api/v2/pokemon/{form_name.lower()}"
                form_details.append({"name": form_name, "url": form_url})
            return form_details
        return []

    def load_pokemon_images(self):
        pokemon_images = {}
        try:
            with open(self.POKEMON_IMAGES_FILE, "r") as file:
                for line in file:
                    pokemon_name, image_link = line.strip().split(":", 1)
                    pokemon_images[pokemon_name.lower()] = image_link.strip()
        except FileNotFoundError:
            print(f"Error: {self.POKEMON_IMAGES_FILE} not found")
        return pokemon_images

    async def on_button_click(self, interaction: discord.Interaction):
        selected_button_id = interaction.data["custom_id"]
        print(f"Selected button ID: {selected_button_id}")
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == selected_button_id:
                    child.style = discord.ButtonStyle.blurple
                else:
                    child.style = discord.ButtonStyle.blurple

        if selected_button_id == "Pokemon_Male_Button":
            await self.show_gender_image(interaction, "male")
        elif selected_button_id == "Pokemon_Female_Button":
            await self.show_gender_image(interaction, "female")

    async def show_gender_image(self, interaction: discord.Interaction, gender):
        if gender == "male":
            male_button = self.children[0]
            female_button = self.children[1]
        else:
            male_button = self.children[1]
            female_button = self.children[0]

        try:
            if gender == "male":
                image_url = self.pokemon_data["sprites"]["other"]["official-artwork"]["front_default"]
            else:
                pokemon_name_lower = self.pokemon_name.lower()
                if pokemon_name_lower in self.pokemon_images:
                    image_url = self.pokemon_images[pokemon_name_lower]
                else:
                    image_url = self.pokemon_images.get("front_female", None)

            embed = interaction.message.embeds[0]
            embed.set_image(url=image_url)
            await interaction.response.edit_message(embed=embed)

            male_button.style = discord.ButtonStyle.blurple
            female_button.style = discord.ButtonStyle.gray
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

    async def show_evolutions_button(self, interaction: discord.Interaction):
        try:
            await self.show_evolutions(interaction)
        except requests.exceptions.RequestException as e:
            await interaction.response.send_message(
                f"Error fetching Pokémon evolution chain: {str(e)}", ephemeral=True
            )

    async def show_evolutions(self, interaction: discord.Interaction):
        try:
            evolution_chain_data = await self.get_pokemon_evolution_chain(self.pokemon_name)
            if not evolution_chain_data:
                await interaction.response.send_message(
                    f"No evolution chain found for {self.pokemon_name.title()}.", ephemeral=True
                )
                return

            embeds = await self.display_evolution_chain(evolution_chain_data)
            await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)

            if len(embeds) > 10:
                await interaction.followup.send(embeds=embeds[10:], ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error fetching Pokémon evolution chain: {str(e)}", ephemeral=True)

    @staticmethod
    async def get_pokemon_evolution_chain(pokemon_name):
        async with aiohttp.ClientSession() as session:
            species_url = f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_name.lower()}/"
            async with session.get(species_url) as response:
                if response.status != 200:
                    return None
                species_data = await response.json()
                evolution_chain_url = species_data.get("evolution_chain", {}).get("url")
                if not evolution_chain_url:
                    return None
            async with session.get(evolution_chain_url) as response:
                if response.status != 200:
                    return None
                evolution_chain_data = await response.json()
                return evolution_chain_data.get("chain")

    async def display_evolution_chain(self, chain):
        embeds = []
        queue = [chain]
        final_forms = set()

        while queue:
            current_chain = queue.pop(0)
            species_name = current_chain["species"]["name"].title()

            if not current_chain.get("evolves_to"):
                final_forms.add(species_name)
                continue

            for evolution in current_chain["evolves_to"]:
                details = evolution["evolution_details"][0] if evolution["evolution_details"] else {}
                next_pokemon_name = evolution["species"]["name"].title()
                method = await self.determine_evolution_method(species_name, details, next_pokemon_name)

                if method:
                    embed = await self.create_pokemon_embed(species_name, method, next_pokemon_name)
                    embeds.append(embed)

                queue.append(evolution)

        for final_form in final_forms:
            embed = await self.create_pokemon_embed(final_form, "is the final form", final_form)
            embeds.append(embed)

        return embeds

    @staticmethod
    async def determine_evolution_method(current_pokemon, evolution_details, next_pokemon):
        trigger = evolution_details.get("trigger", {}).get("name")
        item = evolution_details.get("item")
        known_move_type = evolution_details.get("known_move_type")
        time_of_day = evolution_details.get("time_of_day")
        min_level = evolution_details.get("min_level")
        min_happiness = evolution_details.get("min_happiness")
        location = evolution_details.get("location")
        method = ""

        special_evolutions = {
            ("eevee", "leafeon"): "using a Leaf Stone",
            ("eevee", "glaceon"): "using an Ice Stone"
        }

        evolution_key = (current_pokemon.lower(), next_pokemon.lower())
        if evolution_key in special_evolutions:
            return special_evolutions[evolution_key]

        if trigger == "level-up":
            if location:
                location_name = location.get("name", "").replace("-", " ").title()
                if "moss" in location_name.lower() or "eterna forest" in location_name.lower():
                    method = "using a Leaf Stone"
                elif "ice" in location_name.lower() or "snowpoint" in location_name.lower():
                    method = "using an Ice Stone"
                else:
                    method = f"when leveled up at {location_name}"
            elif known_move_type:
                method = f"when leveled up while knowing a {known_move_type['name'].replace('-', ' ').title()} move"
            else:
                method = "when leveled up"
                if time_of_day:
                    method += f" at {time_of_day.title()} time"
                if min_level:
                    method += f" starting from level {min_level}"
                if min_happiness:
                    method += " while holding a Friendship Bracelet"
        elif trigger == "use-item":
            if item:
                method = f"using a {item['name'].replace('-', ' ').title()}"
        elif trigger == "trade":
            if item:
                method = f"when traded holding a {item['name'].replace('-', ' ').title()}"
            else:
                method = "when traded"
        
        return method

    async def create_pokemon_embed(self, current_pokemon, method, next_pokemon):
        embed = discord.Embed()
        sprite_url = f"https://pokemonshowdown.com/sprites/dex/{current_pokemon.lower()}.png"
        if self.pokemon_shiny:
            sprite_url = f"https://pokemonshowdown.com/sprites/dex-shiny/{current_pokemon.lower()}.png"
        embed.set_thumbnail(url=sprite_url)
        if current_pokemon == next_pokemon:
            embed.description = f"```{current_pokemon} is the final form.```"
        else:
            embed.description = f"```{current_pokemon} evolves into {next_pokemon} {method}```"
        return embed

    @discord.ui.button(
        label="Stats", style=discord.ButtonStyle.gray, custom_id="Pokemon_Stats", row=1
    )
    async def s_and_w(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = discord.Embed(color=self.color)
        embed.add_field(name="Base Stats", value=f"```py\n{self.base_stats}```", inline=False)
        strength_weakness = "```" + self.pokemon_type + self.s_and_w + "```"
        if self.pokemon_type != "shiny":
            image = f"https://pokemonshowdown.com/sprites/dex/{self.pokemon_name}.png"
        else:
            image = f"https://pokemonshowdown.com/sprites/dex-shiny/{self.pokemon_name}.png"
        if self.image_thumb is None:
            embed.set_footer(text=self.pokemon_dex_name)
        else:
            embed.set_footer(icon_url=self.image_thumb, text=self.pokemon_dex_name)
        #embed.set_thumbnail(url=self.image_url)
        thumbnail = self.image_url
        footer = self.image_thumb
        footer_text = self.pokemon_dex_name
        pokemon_data = self.pokemon_data
        color = self.color

        await button.response.send_message(
            embed=embed,
            view=Strength_weakness(
                color, strength_weakness, thumbnail, footer, footer_text, pokemon_data
            ),
            ephemeral=True,
        )



class RegionFlagMapping:
    def __init__(self):
        self.region_mappings = {
            "paldea": "<:Paldea:1212335178714980403>",
            "sinnoh": "<:Sinnoh:1212335180459544607>",
            "alola": "<:Alola:1212335185228472411>",
            "kalos": "<:Kalos:1212335190656024608>",
            "galar": "<:Galar:1212335192740470876>",
            "pasio": "<:848495108667867139:1212335194628034560>",
            "hoenn": "<:Hoenn:1212335197304004678>",
            "unova": "<:Unova:1212335199095095306>",
            "kanto": "<:Kanto:1212335202341363713>",
            "johto": "<:Johto:1212335202341363713>",
        }

        self.flag_mapping = {
            "en": "🇬🇧",
            "fr": "🇫🇷",
            "es": "🇪🇸",
            "de": "🇩🇪",
            "it": "🇮🇹",
            "ja": "🇯🇵",
            "ko": "🇰🇷",
            "zh-Hans": "🇨🇳",
            "ru": "🇷🇺",
            "es-MX": "🇲🇽",
            "pt": "🇵🇹",
            "nl": "🇳🇱",
            "tr": "🇹🇷",
            "ar": "🇸🇦",
            "th": "🇹🇭",
            "vi": "🇻🇳",
            "pl": "🇵🇱",
            "sv": "🇸🇪",
            "da": "🇩🇰",
            "no": "🇳🇴",
            "fi": "🇫🇮",
            "el": "🇬🇷",
            "id": "🇮🇩",
            "ms": "🇲🇾",
            "fil": "🇵🇭",
            "hu": "🇭🇺",
            "cs": "🇨🇿",
            "sk": "🇸🇰",
            "ro": "🇷🇴",
            "uk": "🇺🇦",
            "hr": "🇭🇷",
            "bg": "🇧🇬",
            "et": "🇪🇪",
            "lv": "🇱🇻",
            "lt": "🇱🇹",
            "sl": "🇸🇮",
            "mt": "🇲🇹",
            "sq": "🇦🇱",
            "mk": "🇲🇰",
            "bs": "🇧🇦",
            "sr": "🇷🇸",
            "cy": "🇨🇾",
            "ga": "🇮🇪",
            "gd": "🏴",
            "kw": "🇰🇾",
            "br": "🇧🇷",
            "af": "🇿🇦",
            "xh": "🇿🇦",
            "zu": "🇿🇦",
            "tn": "🇿🇦",
            "st": "🇿🇦",
            "ss": "🇿🇦",
            "nr": "🇿🇦",
            "nso": "🇿🇦",
            "ts": "🇿🇦",
            "ve": "🇿🇦",
            "xog": "🇺🇬",
            "lg": "🇺🇬",
            "ak": "🇬🇭",
            "tw": "🇬🇭",
            "bm": "🇧🇫",
            "my": "🇲🇲",
            "km": "🇰🇭",
            "lo": "🇱🇦",
            "am": "🇪🇹",
            "ti": "🇪🇹",
            "om": "🇪🇹",
            "so": "🇸🇴",
            "sw": "🇰🇪",
            "rw": "🇷🇼",
            "yo": "🇳🇬",
            "ig": "🇳🇬",
            "ha": "🇳🇬",
            "bn": "🇧🇩",
            "pa": "🇮🇳",
            "gu": "🇮🇳",
            "or": "🇮🇳",
            "ta": "🇮🇳",
            "te": "🇮🇳",
            "kn": "🇮🇳",
            "ml": "🇮🇳",
            "si": "🇱🇰",
            "ne": "🇳🇵",
            "dz": "🇧🇹",
            "ti": "🇪🇷",
            "be": "🇧🇾",
            "kk": "🇰🇿",
            "uz": "🇺🇿",
            "ky": "🇰🇬",
        }


class Strength_weakness(discord.ui.View):
    def __init__(
        self,
        color=None,
        strength_weakness_text=None,
        thumbnail_url=None,
        footer=None,
        footer_text=None,
        pokemon_data=None,
    ):
        super().__init__()
        self.color = color
        self.strength_weakness_text = strength_weakness_text
        self.thumbnail_url = thumbnail_url
        self.footer = footer
        self.footer_text = footer_text
        self.pokemon_data = pokemon_data
        self.pokemon_moveset_csv = "data/commands/pokemon/pokemon_moveset.csv"
        self.moves_api_base = "https://pokeapi.co/api/v2/move"
        self.pokemon_api_url = "https://pokeapi.co/api/v2/pokemon"
        self.semaphore = asyncio.Semaphore(10)

    @discord.ui.button(label="Type Details", style=discord.ButtonStyle.gray, custom_id="Pokemon_S_and_W_Button")
    async def strengths_and_weaknesses(self, button: discord.ui.Button, interaction: discord.Interaction):
        try:
            embed = discord.Embed(color=self.color, description=self.strength_weakness_text)
            if self.footer is None:
                embed.set_footer(text=self.footer_text)
            else:
                embed.set_footer(icon_url=self.footer, text=self.footer_text)
            await button.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            traceback.print_exc()
            await button.response.send_message(
                f"An error occurred displaying strengths/weaknesses:\n```{e}```",
                ephemeral=True
            )

    @discord.ui.button(label="Moveset", style=discord.ButtonStyle.gray, custom_id="Pokemon_Moveset_Button")
    async def moves_button(self, button, interaction):
        try:
            await button.response.defer(ephemeral=True)
            
            if os.path.exists(self.pokemon_moveset_csv) and os.path.getsize(self.pokemon_moveset_csv) > 0:
                moves_data = await self.get_pokemon_moves_from_csv(self.pokemon_data['name'])
                if moves_data:
                    embed = self.build_moves_embed(moves_data)
                    await button.followup.send(embed=embed, ephemeral=True)
                    return
            
            await button.followup.send("Downloading Pokémon movesets, this may take a few minutes...", ephemeral=True)
            await self.download_all_pokemon_movesets()

            moves_data = await self.get_pokemon_moves_api(self.pokemon_data['name'])
            if not moves_data:
                await button.followup.send(f"No moveset data found for {self.pokemon_data['name'].title()}.", ephemeral=True)
                return

            embed = self.build_moves_embed(moves_data)
            await button.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await button.followup.send(f"Error loading moveset:\n```{e}```", ephemeral=True)

    async def get_pokemon_moves_from_csv(self, pokemon_name):
        moves_data = {}
        try:
            with open(self.pokemon_moveset_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["pokemon"].lower() == pokemon_name.lower():
                        level = int(row.get("level", 1)) if row.get("level", "").isdigit() else 1
                        moves_data[level] = {
                            "name": row["name"],
                            "power": row["power"],
                            "accuracy": row["accuracy"],
                            "effect": row["effect"]
                        }
        except Exception as e:
            print(f"Error reading CSV for {pokemon_name}: {e}")
        return moves_data

    async def fetch_all_pokemon_names(self):
        names = []
        url = self.pokemon_api_url
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            while url:
                try:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            break
                        data = await resp.json()
                        names.extend([p["name"] for p in data["results"]])
                        url = data.get("next")
                except Exception as e:
                    print(f"Error fetching Pokemon names: {e}")
                    break
        return names

    async def fetch_pokemon_moves_async(self, session, pokemon_name):
        async with self.semaphore:
            try:
                url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name}"
                async with session.get(url, timeout=15) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    rows, move_tasks = [], []
                    for move in data.get("moves", []):
                        move_name = move["move"]["name"]
                        move_url = move["move"]["url"]
                        levels = [v["level_learned_at"] for v in move["version_group_details"] if v["level_learned_at"] > 0]
                        level = min(levels) if levels else 1
                        task = self.fetch_move_data_async(session, pokemon_name, move_name, move_url, level)
                        move_tasks.append(task)

                    batch_size = 5
                    for i in range(0, len(move_tasks), batch_size):
                        batch = move_tasks[i:i + batch_size]
                        batch_results = await asyncio.gather(*batch, return_exceptions=True)
                        for result in batch_results:
                            if isinstance(result, dict):
                                rows.append(result)
                        await asyncio.sleep(0.1)
                    return rows
            except Exception as e:
                print(f"Error fetching moves for {pokemon_name}: {e}")
                return []

    async def fetch_move_data_async(self, session, pokemon_name, move_name, move_url, level=1):
        try:
            async with session.get(move_url, timeout=10) as resp:
                if resp.status != 200:
                    return None
                move_data = await resp.json()
                effect = next(
                    (e["short_effect"] for e in move_data.get("effect_entries", []) if e["language"]["name"] == "en"),
                    "N/A"
                )
                return {
                    "pokemon": pokemon_name,
                    "name": move_name,
                    "power": move_data.get("power", "N/A"),
                    "accuracy": move_data.get("accuracy", "N/A"),
                    "effect": effect,
                    "level": level
                }
        except Exception:
            return None

    async def download_all_pokemon_movesets(self):
        path = os.path.dirname(self.pokemon_moveset_csv)
        os.makedirs(path, exist_ok=True)
        print("Fetching Pokemon names...")
        pokemon_names = await self.fetch_all_pokemon_names()
        print(f"Found {len(pokemon_names)} Pokemon")

        all_rows = []
        connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            batch_size = 50
            for i in range(0, len(pokemon_names), batch_size):
                batch = pokemon_names[i:i + batch_size]
                print(f"Processing batch {i//batch_size + 1}/{(len(pokemon_names) + batch_size - 1)//batch_size}")
                tasks = [self.fetch_pokemon_moves_async(session, name) for name in batch]
                batch_results = []
                for task in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc=f"Batch {i//batch_size + 1}"):
                    result = await task
                    batch_results.extend(result)
                all_rows.extend(batch_results)
                await asyncio.sleep(1)

        print(f"Writing {len(all_rows)} moves to CSV...")
        with open(self.pokemon_moveset_csv, "w", newline="", encoding="utf-8") as f:
            if all_rows:
                writer = csv.DictWriter(f, fieldnames=["pokemon", "name", "power", "accuracy", "effect", "level"])
                writer.writeheader()
                writer.writerows(all_rows)
        print("Download complete!")

    async def get_pokemon_moves_api(self, name):
        moves_data = {}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                url = f"https://pokeapi.co/api/v2/pokemon/{name.lower()}"
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return moves_data
                    data = await resp.json()
                    move_tasks = []
                    for move in data.get("moves", []):
                        levels = [v["level_learned_at"] for v in move["version_group_details"] if v["level_learned_at"] > 0]
                        if not levels:
                            continue
                        level = min(levels)
                        task = self.fetch_move_data_async(session, name, move["move"]["name"], move["move"]["url"], level)
                        move_tasks.append((level, task))

                    semaphore = asyncio.Semaphore(10)

                    async def fetch_with_semaphore(level, task):
                        async with semaphore:
                            result = await task
                            return level, result

                    results = await asyncio.gather(
                        *[fetch_with_semaphore(level, task) for level, task in move_tasks],
                        return_exceptions=True
                    )

                    for level, move_data in results:
                        if move_data:
                            moves_data[level] = move_data
        except Exception as e:
            print(f"Error fetching moves for {name}: {e}")
            traceback.print_exc()
        return moves_data

    def build_moves_embed(self, moves_data):
        embed = discord.Embed(
            title=f"{self.pokemon_data['name'].title().replace('-', ' ')} — Moveset",
            color=self.color
        )
        for level in sorted(moves_data.keys())[:25]:
            move = moves_data[level]
            effect = move['effect'][:97] + "..." if len(move['effect']) > 100 else move['effect']
            embed.add_field(
                name=f"{move['name'].title().replace('-', ' ')} | Lv. {level}",
                value = f"- Effect: {effect if effect else '—'}\n- Power: {move['power'] if move['power'] else '—'}\n- Accuracy: {move['accuracy'] if move['accuracy'] else '—'}",
                inline=True
            )
        if len(moves_data) > 25:
            embed.set_footer(text=f"Showing first 25 of {len(moves_data)} moves")
        embed.set_thumbnail(url=self.thumbnail_url)
        return embed
