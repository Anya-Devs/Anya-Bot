# Standard library _imports
import json
import csv
import time
import os
import io
import logging
import random
from typing import List, Tuple, Optional
from urllib.request import urlopen

# Third-party library _imports
import cv2
import cv2 as cv
import numpy as np
import aiohttp
import requests
from PIL import Image


# Concurrent and multiprocessing _imports
from concurrent import *
from concurrent.futures import ThreadPoolExecutor


# Custom _imports
from _imports.discord_imports import *
from discord.ext import tasks
from _imports.log_imports import logger
from data.const import error_custom_embed, primary_color


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


class PokemonPredictor:
    def __init__(
        self,
        dataset_folder="data/pokemon/pokemon_images",
        csv_file="data/pokemon/dataset.csv",
        approx_file="data/pokemon/pokemon_aprox.csv",
    ):
        self.orb = cv.ORB_create(nfeatures=175)
        self.flann = cv.FlannBasedMatcher(
            dict(algorithm=6, table_number=6, key_size=9, multi_probe_level=1),
            dict(checks=1),
        )
        self.executor = ThreadPoolExecutor(max_workers=25)
        self.cache = {}
        self.csv_file = csv_file
        self.dataset_folder = dataset_folder

        # Load dataset only once when code starts
        self.load_dataset()

    def load_dataset(self):
        print("Loading Images...")
        if os.path.exists(self.csv_file):
            print("Loading dataset from CSV file...")
            self.load_from_csv()
        else:
            print("CSV file not found, loading images from dataset folder...")
            self.load_from_images()

    def load_from_csv(self):
        start_time = time.time()
        with open(self.csv_file, "r") as file:
            reader = csv.reader(file)
            next(reader)
            for row in reader:
                filename, descriptors_str = row
                descriptors = np.array(json.loads(
                    descriptors_str), dtype=np.uint8)
                self.cache[filename] = (None, descriptors)
        print(
            f"Dataset loaded from CSV in {time.time() - start_time:.2f} seconds")

    def load_from_images(self):
        start_time = time.time()
        with open(self.csv_file, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Filename", "Descriptors"])

        for filename in os.listdir(self.dataset_folder):
            path = os.path.join(self.dataset_folder, filename)
            if os.path.isfile(path):
                img = cv.imread(path)
                if img is not None:
                    gray_img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
                    keypoints, descriptors = self.orb.detectAndCompute(
                        gray_img, None)
                    if descriptors is not None:
                        self.cache[filename] = (keypoints, descriptors)
                        with open(self.csv_file, "a", newline="") as file:
                            writer = csv.writer(file)
                            writer.writerow([filename, descriptors.tolist()])

                        flipped_img = cv.flip(img, 1)
                        gray_flipped = cv.cvtColor(
                            flipped_img, cv.COLOR_BGR2GRAY)
                        keypoints_flipped, descriptors_flipped = (
                            self.orb.detectAndCompute(gray_flipped, None)
                        )
                        if descriptors_flipped is not None:
                            flipped_filename = filename.replace(
                                ".png", "_flipped.png")
                            self.cache[flipped_filename] = (
                                keypoints_flipped,
                                descriptors_flipped,
                            )
                            with open(self.csv_file, "a", newline="") as file:
                                writer = csv.writer(file)
                                writer.writerow(
                                    [flipped_filename, descriptors_flipped.tolist()]
                                )

        print(f"Images loaded in {time.time() - start_time:.2f} seconds")

    @staticmethod
    def _find_image_inside_image(img, template):
        img_gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        template_gray = cv.cvtColor(template, cv.COLOR_BGR2GRAY)

        # Check if template is larger than the input image
        if (
            template_gray.shape[0] > img_gray.shape[0]
            or template_gray.shape[1] > img_gray.shape[1]
        ):
            return None, None  # Skip matching if the template is larger

        # Match template
        res = cv.matchTemplate(img_gray, template_gray, cv.TM_CCOEFF_NORMED)
        threshold = 0.8
        loc = np.where(res >= threshold)

        # Check if any matching locations are found
        if loc[0].size > 0:
            # Get dimensions of the template
            h, w = template_gray.shape
            for pt in zip(*loc[::-1]):  # Switch columns and rows
                bottom_right = (pt[0] + w, pt[1] + h)
                return [
                    pt[0],
                    pt[1],
                    bottom_right[0],
                    bottom_right[1],
                ], os.path.basename(template)

        return None, None

    def predict_pokemon(self, img):
        start_time = time.time()
        gray_img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        kpB, desB = self.orb.detectAndCompute(gray_img, None)

        if desB is not None:
            desB = desB.astype(np.uint8)

        results = []

        # Load images from dataset.csv
        for filename, (_, desA) in self.cache.items():
            if (
                desA is not None
                and desB is not None
                and len(desA) > 2
                and len(desB) > 2
            ):
                # Perform matching using FLANN
                matches = self.flann.knnMatch(desA, desB, k=2)
                good_matches = [
                    m[0]
                    for m in matches
                    if len(m) == 2 and m[0].distance < 0.50 * m[1].distance
                ]

                if len(good_matches) > 1:
                    accuracy = len(good_matches) / len(desA) * 100
                    results.append((filename, accuracy))

        # Find the best match based on results
        if results:
            best_match = max(results, key=lambda x: x[1])
            pokemon_img_path = os.path.join(self.dataset_folder, best_match[0])
            target_img = cv.imread(pokemon_img_path)

            if target_img is not None:
                # Detect Pokémon by finding the image inside the input image
                detection_box, filename = self._find_image_inside_image(
                    img, target_img)

                # Check if a detection box is returned
                if detection_box is not None:
                    # Draw bounding box around detected Pokémon
                    x1, y1, x2, y2 = detection_box
                    cv.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    print(f"Bounding box: {(x1, y1, x2, y2)}")

                    predicted_pokemon = filename.split("_flipped")[0].replace(
                        ".png", ""
                    )
                    return f"{predicted_pokemon.title()}: 100%", round(
                        time.time() - start_time, 2
                    )
                else:
                    print(
                        f"Warning: No detection found for {pokemon_img_path}")
                    predicted_pokemon = (
                        pokemon_img_path.split("_flipped")[0]
                        .replace(".png", "")
                        .replace(f"{self.dataset_folder}", "")
                    )
                    return f"{predicted_pokemon.title()}: 100%", round(
                        time.time() - start_time, 2
                    )

            else:
                print(f"Warning: Could not load image for {pokemon_img_path}")
                predicted_pokemon = (
                    pokemon_img_path.split("_flipped")[0]
                    .replace(".png", "")
                    .replace(f"{self.dataset_folder}", "")
                )
                return f"{predicted_pokemon.title()}: 100%", round(
                    time.time() - start_time, 2
                )

        return "No Pokémon detected", round(time.time() - start_time, 2)

    @staticmethod
    def load_image_from_url(url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            image = np.asarray(bytearray(response.content), dtype=np.uint8)
            img = cv.imdecode(image, cv.IMREAD_COLOR)
            return img
        except requests.RequestException as e:
            print(f"Error fetching image from URL: {e}")
            return None


class Pokemon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.author_id = 716390085896962058
        self.predictor = PokemonPredictor()
        self.primary_color = primary_color
        self.error_custom_embed = error_custom_embed
        self.local_color_memory = []  # Binary local color comparator memory
        self.pokemon_api_url = "https://pokeapi.co/api/v2/pokemon"
        self.pokemon_info_url = "https://pokeapi.co/api/v2/pokemon/{}/"

    async def fetch_all_pokemon_names(self):
        pokemon_names = []
        url = self.pokemon_api_url
        while url:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for result in data["results"]:
                            pokemon_names.append(result["name"])
                        url = data.get("next")
                    else:
                        logger.error("Failed to fetch Pokémon names.")
                        break
        return pokemon_names

    async def fetch_pokemon_info(self, pokemon_name):
        url = self.pokemon_info_url.format(pokemon_name.lower())
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["sprites"]["other"]["official-artwork"]["front_default"]
                else:
                    logger.error(f"Failed to fetch info for {pokemon_name}.")
                    return None

    async def download_all_images(self, max_concurrent_tasks=10):
        pokemon_names = await self.fetch_all_pokemon_names()
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

        async with aiohttp.ClientSession() as session:
            tasks = []
            semaphore = asyncio.Semaphore(max_concurrent_tasks)
            for pokemon_name in pokemon_names:
                tasks.append(self.download_image(
                    session, pokemon_name, semaphore))
            await asyncio.gather(*tasks)

    async def download_image(self, session, pokemon_name, semaphore):
        async with semaphore:
            filename = f"{pokemon_name.lower()}.png"
            filepath = os.path.join(self.image_folder, filename)
            if not os.path.exists(filepath):
                official_artwork_url = await self.fetch_pokemon_info(pokemon_name)
                if official_artwork_url:
                    try:
                        async with session.get(official_artwork_url) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                async with aiofiles.open(filepath, "wb") as f:
                                    await f.write(image_data)
                                logger.info(
                                    f"Downloaded image for {pokemon_name}.")
                            else:
                                logger.error(
                                    f"Failed to download image for {pokemon_name}."
                                )
                    except Exception as e:
                        logger.error(
                            f"Error downloading image for {pokemon_name}: {e}")
                else:
                    logger.error(
                        f"Failed to fetch information for {pokemon_name}.")
            else:
                logger.info(
                    f"Image for {pokemon_name} already exists, skipping download."
                )

    @staticmethod
    def remove_srgb_profile(img_path):
        try:
            with Image.open(img_path) as img:
                img.save(img_path, icc_profile=None)
                logger.debug(f"Removed sRGB profile from {img_path}")
        except Exception as e:
            logger.error(f"Error removing sRGB profile: {e}")

    @staticmethod
    def ensure_correct_color_format(img):
        """
        Convert image to RGB format.
        """
        if img.shape[2] == 3:  # Check if the image has 3 color channels
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # Check if the image has 4 color channels (with alpha)
        elif img.shape[2] == 4:
            return cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        return img

    @staticmethod
    def download_file(url, filename):
        response = urlopen(url)
        with open(filename, "wb") as f:
            f.write(response.read())

    @commands.command(name="predict")
    # 1 use per 24 hours per user
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def predict(self, ctx, *, arg=None):
        image_url = None

        if arg:
            image_url = arg
        elif ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        elif ctx.message.reference:
            reference_message = await ctx.channel.fetch_message(
                ctx.message.reference.message_id
            )
            if reference_message.attachments:
                image_url = reference_message.attachments[0].url
            elif reference_message.embeds:
                embed = reference_message.embeds[0]
                if embed.image:
                    image_url = embed.image.url

        if image_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        img_bytes = await response.read()
                        img = Image.open(io.BytesIO(img_bytes))
                        # Convert to numpy array
                        img = np.array(img.convert("RGB"))

                        # Use the predictor to predict the Pokémon
                        prediction, time_taken = self.predictor.predict_pokemon(
                            img)
                        await ctx.reply(prediction, mention_author=False)
                    else:
                        await ctx.reply(
                            f"Failed to download image. Status code: {response.status}",
                            mention_author=False,
                        )
        else:
            await ctx.send("No image found to predict.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.author_id and message.embeds:
            embed = message.embeds[0]
            if embed.description and "Guess the pokémon" in embed.description:
                image_url = embed.image.url
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as response:
                        if response.status == 200:
                            img_bytes = await response.read()
                            img = Image.open(io.BytesIO(img_bytes))
                            # Convert to numpy array
                            img = np.array(img.convert("RGB"))

                            # Use the predictor to predict the Pokémon
                            prediction, time_taken = self.predictor.predict_pokemon(
                                img)
                            await message.channel.send(prediction, reference=message)
                        else:
                            await message.channel.send(
                                f"Failed to download image. Status code: {response.status}",
                                reference=message,
                            )

    @commands.command(
        help="Displays Pokemon dex information.", aliases=["pokdex", "dex", "d", "p"]
    )
    async def pokemon(self, ctx, *, args=None, form=None):
        # Get the primary color of the bot's icon
        primary_color = self.primary_color()
        async with ctx.typing():
            is_shiny = False
            is_form = False
            is_mega = None

            if not args:
                pokemon_id = random.randint(1, 1021)
            elif args.lower() == "shiny":
                is_shiny = True
                pokemon_id = random.randint(1, 1021)
            else:
                args = args.lower().replace(" ", "-").replace("shiny-", "shiny ")
                is_shiny = args.startswith("shiny ")
                is_form = form is not None

                args = args.replace("shiny ", "")
                pokemon_id = args

           
            pokemon_folder_path = "data/commands/pokemon"
            os.makedirs(pokemon_folder_path, exist_ok=True)
            file_path = os.path.join(pokemon_folder_path, "pokemon.json")

            if not os.path.exists(file_path):
                with open(file_path, "w") as file:
                    file.write("{}") 

            pokemon_data = {}

            if os.path.exists(file_path):
                with open(file_path, "r") as file:
                    pokemon_data = json.load(file)

                if str(pokemon_id) in pokemon_data:
                    existing_data = pokemon_data[str(pokemon_id)]
                    return await self.send_pokemon_info(
                        ctx,
                        existing_data,
                        type="mega" if is_mega else "shiny" if is_shiny else None,
                        color=primary_color,
                    )

            if is_form:
                url = f"https://pokeapi.co/api/v2/pokemon-form/{pokemon_id}-{form}"
            else:
                url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"

            response = requests.get(url)
            if response.status_code != 200:
                if is_form:
                    return await ctx.send(f"Form data not found for `{pokemon_id}`.")
                else:
                    return await ctx.send(f"Pokemon `{pokemon_id}` not found.")

            try:
                data = response.json()
                if is_form:
                    await self.send_form_pokemon(ctx, data)
                else:
                    await self.send_pokemon_info(
                        ctx,
                        data,
                        type="mega" if is_mega else "shiny" if is_shiny else None,
                        color=primary_color,
                    )

                # Save or update JSON data in the Pokemon folder
                pokemon_data[str(pokemon_id)] = data

                with open(file_path, "w") as file:
                    json.dump(pokemon_data, file)

            except json.JSONDecodeError:
                if isinstance(pokemon_id, int):
                    await ctx.send(f"Failed to parse JSON data for `{pokemon_id}`.")

    async def send_pokemon_info(self, ctx, data, type, color):
        name = data["name"].capitalize()
        id = data["id"]

        types = [t["type"]["name"].capitalize() for t in data["types"]]
        pokemon_type_unformatted = types

        formatted_types = "\n".join(types)

        abilities = [a["ability"]["name"].capitalize()
                     for a in data["abilities"]]

        pokemon_name = name
        base_url = "https://pokeapi.co/api/v2/pokemon-species/"
        if type == "mega":
            print("Getting Mega Evolution")
            mega_url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}-mega"
            mega_response = requests.get(mega_url)
            print(requests.get(mega_url))
            if mega_response.status_code == 200:
                try:
                    mega_data = mega_response.json()
                    data_species = mega_response.json()  # Corrected line

                except json.JSONDecodeError:
                    await ctx.send(
                        f"Failed to parse JSON data for mega evolution of `{pokemon_name}`."
                    )
            else:
                await ctx.send(f"Mega evolution data not found for `{pokemon_name}`.")
        else:
            print("Getting Basic Pokemon")
            url = f"{base_url}{pokemon_name.lower()}/"
            response_species = requests.get(url)
            if response_species.status_code != 200:
                # Fetch form data if species data not found
                url = f"https://pokeapi.co/api/v2/pokemon-form/{pokemon_name.lower()}/"
                form_response = requests.get(url)
                if form_response.status_code == 200:
                    data_species = form_response.json()
            else:
                data_species = response_species.json()

        if type == "mega":
            print(f"Pokemon {name} is mega")

        async def title_case_except_all_caps(text):
            words = text.split()
            result = []

            for word in words:
                if word.isupper():
                    result.append(word.title())
                else:
                    result.append(word)

            return " ".join(result)

        async def get_pokemon_info(data_species, pokemon_name):
            try:
                flavor = data_species["flavor_text_entries"][0]["flavor_text"]
                english_flavor = next(
                    (
                        entry["flavor_text"]
                        for entry in data_species["flavor_text_entries"]
                        if entry["language"]["name"] == "en"
                    ),
                    None,
                )

                if english_flavor:
                    flavor = english_flavor
                    formatted_flavor = " ".join(flavor.split())
                    formatted_description = await capitalize_sentences(formatted_flavor)

                    word_replacements = {
                        "POKéMON": "Pokémon",
                        "POKé BALL": "Poké Ball",
                        # Add more replacements as needed
                    }

                    formatted_description = await replace_words(
                        formatted_description, word_replacements
                    )

                    return formatted_description
                else:
                    await find_pokemon_description(pokemon_name)
            except Exception as e:
                await find_pokemon_description(pokemon_name)
                print(f"Error: An unexpected error occurred - {e}")

        async def find_pokemon_description(pokemon_name):
            POKEMON_DIR = "data/pokemon"
            os.makedirs(POKEMON_DIR, exist_ok=True)
            POKEMON_DESCRIPTION_FILE = os.path.join(
                POKEMON_DIR, "pokemon_descriptions.txt"
            )

            if not os.path.exists(POKEMON_DESCRIPTION_FILE):
                with open(POKEMON_DESCRIPTION_FILE, "w") as file:
                    file.write("")  # Creating an empty text file
            with open(POKEMON_DESCRIPTION_FILE, "r") as file:
                pokemon_name = pokemon_name.lower()
                print(pokemon_name)
                for line in file:
                    # Split the line into Pokemon name and description
                    pokemon, description = line.strip().split(":", 1)

                    # Check if the current line's Pokemon name matches the requested name
                    if pokemon.strip() == pokemon_name:
                        print(f"{pokemon.strip()} : {description.strip()}")
                        return description.strip()

                    else:
                        return None

            # If the Pokemon name is not found, return None
            return None

        async def replace_words(text, replacements):
            for old_word, new_word in replacements.items():
                text = text.replace(old_word, new_word)
            return text

        async def capitalize_sentences(text):
            sentences = text.split(".")
            capitalized_sentences = ". ".join(
                sentence.strip().capitalize()
                for sentence in sentences
                if sentence.strip()
            )
            return capitalized_sentences

        def get_pokemon_description(
            pokemon_id, file_path="data/pokemon/pokemon_description.csv"
        ):
            with open(file_path, mode="r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)

                for row in reader:
                    if row["id"] == str(pokemon_id):
                        return row["description"]

            return "Pokémon ID not found"

        pokemon_description = get_pokemon_description(
            id
        )  # await get_pokemon_info(data_species,name) or await find_pokemon_description(pokemon_name) or " "

        species_url = data["species"]["url"]
        species_data = requests.get(species_url).json()
        species_name = species_data["name"]
        # Fetch the Pokémon's characteristic
        characteristic_id = id  # You can use the Pokémon's ID as the characteristic ID
        characteristic_url = (
            f"https://pokeapi.co/api/v2/characteristic/{characteristic_id}/"
        )
        characteristic_response = requests.get(characteristic_url)

        if characteristic_response.status_code == 200:
            characteristic_data = characteristic_response.json()
            # Get the English description
            for description in characteristic_data["descriptions"]:
                if description["language"]["name"] == "en":
                    characteristic_description = description["description"]
                    break
                else:
                    characteristic_description = "No English description available"

        else:
            characteristic_description = "Characteristic data not found"

        if type == "shiny":
            image_url = data["sprites"]["other"]["official-artwork"]["front_shiny"]
            image_thumb = data["sprites"]["versions"]["generation-v"]["black-white"][
                "animated"
            ]["front_shiny"]
        elif type == "mega":
            print("Getting Mega Evolution")
            mega_url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}-mega"
            mega_response = requests.get(mega_url)
            print(requests.get(mega_url))
            if mega_response.status_code == 200:
                try:
                    mega_data = mega_response.json()
                    # Redefine data for mega evolution
                    data = mega_data
                    image_url = mega_data["sprites"]["other"]["official-artwork"][
                        "front_default"
                    ]
                    image_thumb = mega_data["sprites"]["versions"]["generation-v"][
                        "black-white"
                    ]["animated"]["front_default"]
                except json.JSONDecodeError:
                    await ctx.send(
                        f"Failed to parse JSON data for mega evolution of `{pokemon_name}`."
                    )
            else:
                await ctx.send(f"Mega evolution data not found for `{pokemon_name}`.")
        else:
            image_url = data["sprites"]["other"]["official-artwork"]["front_default"]
            image_thumb = data["sprites"]["versions"]["generation-v"]["black-white"][
                "animated"
            ]["front_default"]

        height, weight = (
            float(int(data["height"])) / 10,
            float(int(data["weight"])) / 10,
        )
        max_stat = 255
        bar_length = 13  # Length of the level bar
        fixed_bar_length = 13

        # Mapping for renaming
        stat_name_mapping = {
            "hp": "Hp",
            "special-attack": "Sp. Atk",
            "special-defense": "Sp. Def",
        }

        # Bar types
        bar_symbols = {
            0: {
                "front": "<:__:1194757522041618572>",
                "mid": "<:__:1194758504490205364>",
                "end": "<:__:1194758898721239040>",
            },
            1: {
                "front": "<:__:1194759037024206859>",
                "mid": "<:__:1194759109401133136>",
                "end": "<:__:1194759199071141999>",
            },
        }
        # Fixed length for all bars
        # Generate base_stats with modified names and level bars
        base_stats = [
            f"{str(stat_name_mapping.get(stat['stat']['name'], stat['stat']['name']).title()).replace('Hp', 'Health'):<10} {str(stat['base_stat']):>5} {'▒' * int(stat['base_stat'] / max_stat * bar_length)}{'░' * (bar_length - int(stat['base_stat'] / max_stat * bar_length))}"
            for stat in data["stats"]
        ]
        formatted_base_stats = "\n".join(base_stats)

        _base_stats = [
            f"**{str(stat_name_mapping.get(stat['stat']['name'], stat['stat']['name']).title()).replace('Hp', 'HP')}:** {str(stat['base_stat'])}"
            for stat in data["stats"]
        ]
        basic_base_stats = "\n".join(_base_stats)

        mot = ctx.guild.get_member(ctx.bot.user.id)
        # color = mot.color

        # Define the function to get alternate names
        def get_pokemon_alternate_names(data_species, pokemon_name):
            try:
                if data_species:
                    alternate_names = [
                        (name["name"], name["language"]["name"])
                        for name in data_species["names"]
                    ]
                    return alternate_names
                else:
                    print(f"Error: Unable to retrieve data for {pokemon_name}")
                    return None
            except KeyError:
                return None  # or handle the missing key case accordingly

        def get_pokemon_species_data(name):
            response = requests.get(
                f"https://pokeapi.co/api/v2/pokemon-species/{name.lower()}"
            )
            if response.status_code == 200:
                species_data = response.json()
                return species_data
            else:
                return None

        def get_pokemon_region(
            pokemon_id, file_path="data/pokemon/pokemon_description.csv"
        ):
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

        region = get_pokemon_region(id) or None

        language_codes = ["ja", "ja", "ja", "en", "de", "fr"]
        # Define a mapping between language codes and flag emojis
        flag_mapping = {
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
            "gd": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
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

        # Fetch alternative names from the PokeAPI
        alternate_names = get_pokemon_alternate_names(
            data_species, species_name)

        desired_pokemon = name  # Replace with the desired Pokémon name

        if alternate_names:
            alt_names_info = {}

            for name, lang in alternate_names:
                # Create a unique key for each name
                key = name.lower()

                flag = flag_mapping.get(
                    lang, None
                )  # Get the flag for the language, or None if not found

                # Check if the Pokemon name is the same as the language name, and skip it
                if name.lower() != lang.lower() and flag is not None:
                    if key not in alt_names_info:
                        alt_names_info[key] = f"{flag} {name}"

            # Extract the unique names with their flags
            name_list = sorted(
                list(alt_names_info.values()), key=lambda x: x.split(" ")[-1]
            )

            # Join the results with newline characters
            alt_names_str = "\n".join(name_list[:6])

        else:
            alt_names_str = "No alternate names available."
            print(alt_names_str)

        def organize_pokemon_names_by_region(pokemon_name):
            region = get_pokemon_region(data_species, pokemon_name)

            if region:
                result = f"Region: {region.capitalize()}\n"

                # Fetch alternative names from the PokeAPI
                alternate_names = get_pokemon_alternate_names(
                    data_species, pokemon_name
                )

                if alternate_names:
                    alt_names_info = {}

                    for name, lang in alternate_names:
                        key = name.lower()

                        flag = flag_mapping.get(lang, None)
                        if key not in alt_names_info and flag is not None:
                            alt_names_info[key] = f"{flag} {name.capitalize()}"

                    name_list = sorted(
                        list(alt_names_info.values()),
                        key=lambda x: x.split(" ")[1],
                        reverse=True,
                    )
                    alt_names_str = "\n".join(f"`{name_list}`")

                    result += alt_names_str
                else:
                    result += "No alternate names available."
            else:
                result = "Region information not available."

            return result

        p = organize_pokemon_names_by_region(name)
        print(p)

        async def get_type_chart(max_retries=3):
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

                                    async with session.get(
                                        effectiveness_url
                                    ) as effectiveness_response:
                                        if effectiveness_response.status == 200:
                                            damage_relations = (
                                                await effectiveness_response.json()
                                            )["damage_relations"]
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
                                                    type_chart[type_name][key].append(
                                                        value["name"]
                                                    )

                                return type_chart
                            else:
                                # Handle other HTTP response codes if needed
                                print(
                                    f"Error: HTTP request failed with status code {response.status}"
                                )
                                return None
                except aiohttp.ClientError as e:
                    print(f"Error: aiohttp client error - {e}")
                except Exception as e:
                    print(f"Error: An unexpected error occurred - {e}")

                # If the attempt is not the last one, wait for a while before retrying
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

        def find_pokemon_weaknesses(pokemon_info, type_chart):
            if pokemon_info is None:
                print("Failed to retrieve Pokemon info.")
                return None, None

            types = [t["type"]["name"] for t in pokemon_info["types"]]

            weaknesses = set()
            strengths = set()

            for pokemon_type in types:
                weaknesses.update(
                    type_chart.get(pokemon_type, {}).get(
                        "double_damage_from", [])
                )
                strengths.update(
                    type_chart.get(pokemon_type, {}).get(
                        "double_damage_to", [])
                )

            weaknesses.discard("")

            # Capitalize the output
            weaknesses = {weakness.capitalize() for weakness in weaknesses}
            strengths = {strength.capitalize() for strength in strengths}

            return weaknesses, strengths

        type_chart = await get_type_chart()

        def get_pokemon_spawn_rate(pokemon_id):
            url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}/encounters"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"Error: {response.status_code}")
                return None

        spawn_data = get_pokemon_spawn_rate(id)

        def get_pokemon_gender_ratio_display(data_species):
            try:
                # Extract gender data
                gender_rate = data_species["gender_rate"]

                # Gender rate is an integer representing the likelihood of a Pokemon being female
                # -1: Genderless
                # 0: Always male
                # 1-7: Female ratio (e.g., 1 = 12.5% female, 2 = 25% female, etc.)
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

                    # Create a string representing the gender ratio with Discord markdown

                    # <:male:1212308647984635986> {male_percentage}% - <:female:1212308708151787550> {female_percentage}%
                    # ♂ {male_percentage}% - ♀ {female_percentage}%
                    gender_ratio_display = (
                        f"♂ {male_percentage}% - ♀ {female_percentage}%"
                    )

                    return gender_ratio_display
            except KeyError:
                return None  # or handle the missing key case accordingly

        gender = get_pokemon_gender_ratio_display(data_species) or None

        def determine_pokemon_category(data_species):
            try:
                pokemon_info = data_species

                if pokemon_info:
                    if pokemon_info["is_legendary"]:
                        return "Legendary"
                    elif pokemon_info["is_mythical"]:
                        return f"Mythical"
                    else:
                        flavor_text_entries = pokemon_info["flavor_text_entries"]
                        english_flavor = next(
                            (
                                entry["flavor_text"]
                                for entry in flavor_text_entries
                                if entry["language"]["name"] == "en"
                            ),
                            None,
                        )
                        if english_flavor and "ultra beast" in english_flavor.lower():
                            return f"Ultra Beast"
                        else:
                            return None
                else:
                    return None
            except KeyError:
                return None  # or handle the missing key case accordingly

        rarity = determine_pokemon_category(data_species) or None

        if pokemon_description != " ":
            embed = discord.Embed(
                title=(
                    f" #{id} — {species_name.title()}"
                    if type != "shiny"
                    else f" #{id} — ✨ {species_name.title()}"
                ),
                description=f"\n{pokemon_description}\n",
                color=color,
            )  # Blue color
        else:
            embed = discord.Embed(
                title=(
                    f" #{id} — {species_name.title()}"
                    if type != "shiny"
                    else f" #{id} — ✨ {species_name.title()}"
                ),
                color=color,
            )

        pokemon_dex_name = (
            f" #{id} — {species_name.title()}"
            if type != "shiny"
            else f" #{id} — ✨ {species_name.title()}"
        )
        embed.set_image(url=image_url)
        description = (
            f"\n{pokemon_description}\n" if pokemon_description != " " else None
        )

        # Information about the Pokémon itself

        """
      [Gender] [Apperence]
     
      [Rarity] [Region]    [Names] 
     
     
      [Names]

    
     """
        type_chart = await get_type_chart()
        pokemon_info = data
        weaknesses, strengths = find_pokemon_weaknesses(
            pokemon_info, type_chart)
        label_width = max(len("Type"), len("Weaknesses"), len("Strengths"))

        result = "● Strengths\n" "{2}" "{3}\n\n" "● Weaknesses\n" "{4}" "{5}"
        weaknesses = list(weaknesses)
        strengths = list(strengths)

        if len(weaknesses) == 1:
            weaknesses_formatted = f"╚ {weaknesses[0]}"
        else:
            weaknesses_formatted = "\n".join(
                [f"╠ {weakness}" for weakness in weaknesses[:-1]]
            ) + (f"\n╚ {weaknesses[-1]}" if weaknesses else "╚ None")
        if len(strengths) == 1:
            strengths_formatted = f"╚ {strengths[0]}"
        else:
            strengths_formatted = "\n".join(
                [f"╠ {strength}" for strength in strengths[:-1]]
            ) + (f"\n╚ {strengths[-1]}" if strengths else "╚ None")
        wes = result.format("", "", strengths_formatted,
                            "", weaknesses_formatted, "")

        pokemon_type_result = "● Type\n" "{2}\n\n"
        if len(pokemon_type_unformatted) == 1:
            pokemon_types_formatted = f"╚ {pokemon_type_unformatted[0]}"
        else:
            pokemon_types_formatted = "\n".join(
                [f"╠ {types}" for types in pokemon_type_unformatted[:-1]]
            ) + (
                f"\n╚ {pokemon_type_unformatted[-1]}"
                if pokemon_type_unformatted
                else "╚ None"
            )

        pokemon_type = pokemon_type_result.format(
            "", "", pokemon_types_formatted)
        print(pokemon_type)

        """" Weakness stuff  """
        weaknesses, _ = find_pokemon_weaknesses(pokemon_info, type_chart)

        result = "{0}"

        weaknesses_formatted = (
            "\n".join(
                [
                    f"    {i}. {weakness}"
                    for i, weakness in enumerate(weaknesses, start=1)
                ]
            )
            if weaknesses
            else "None"
        )

        output_weak = result.format(weaknesses_formatted)
        print(output_weak)

        """" Strengths stuff  """
        _, strengths = find_pokemon_weaknesses(pokemon_info, type_chart)

        result = "{0}"

        strengths_formatted = (
            "\n".join(
                [
                    f"    {i}. {strength}"
                    for i, strength in enumerate(strengths, start=1)
                ]
            )
            if strengths
            else "None"
        )

        output_strength = result.format(strengths_formatted)
        print(output_strength)

        s_and_w = wes

        # Define the mappings
        region_mappings = {
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
        if region:
            region = region.title()
        else:
            region = None

        appearance_info = [
            f"**Height:** {height:.2f} m",
            f"**Weight:** {weight:.2f} kg",
        ]
        appearance = "\n".join(appearance_info)

        # embed.add_field(name='Type', value=f"{formatted_types}", inline=True)

        if region is not None:
            if region in region_mappings:
                region_emoji = region_mappings[region]
                embed.add_field(
                    name="Region", value=f"{region_emoji} {region}", inline=True
                )
                region = f"{region_emoji} {region}" or region

        embed.add_field(name="Names", value=alt_names_str, inline=True)

        if gender is not None:
            gender_differ = bool(
                gender != "♀️ Female only" or "♂️ Male only" or "Genderless"
            )
        else:
            gender_differ = False

        spawn_data = get_pokemon_spawn_rate(id)

        # embed.add_field(name='', value=f"```Type: {formatted_types}```",inline=False)
        base_stats = formatted_base_stats

        # Include alternate names

        appearance = (
            f"Height: {height:.2f} m\nWeight: {weight:.2f} kg\t\t"
            if gender is not None and gender != "♂ 50% - ♀ 50%"
            else f"Height: {height:.2f} m\nWeight: {weight:.2f} kg"
        )

        gender_info = None

        if image_thumb:
            embed.set_footer(icon_url=image_thumb, text=appearance)
            gender_info = None
            if gender is not None and gender != "♂ 50% - ♀ 50%":
                embed.set_footer(
                    icon_url=image_thumb, text=appearance + f"Gender: {gender}"
                )
                appearance_footer = embed.set_footer(
                    icon_url=image_thumb, text=appearance + f"Gender: {gender}"
                )
                gender_info = f"Gender: {gender}"

        else:
            if type == "shiny":
                image_thumb = data["sprites"]["versions"]["generation-v"][
                    "black-white"
                ]["front_shiny"]
            else:
                image_thumb = data["sprites"]["versions"]["generation-v"][
                    "black-white"
                ]["front_default"]

            if image_thumb:
                embed.set_footer(icon_url=image_thumb, text=appearance)
            else:
                image_thumb = None
                embed.set_footer(text=appearance)

            if gender and rarity is not None and gender != "♂ 50% - ♀ 50%":
                embed.set_footer(
                    icon_url=image_thumb,
                    text=f"Rarity: {rarity}\n\n" +
                    appearance + f"Gender: {gender}",
                )
                appearance_footer = embed.set_footer(
                    icon_url=image_thumb,
                    text=f"Rarity: {rarity}\n\n" +
                    appearance + f"Gender: {gender}",
                )
                gender_info = f"Gender: {gender}"

            elif gender is not None and gender != "♂ 50% - ♀ 50%":
                embed.set_footer(
                    icon_url=image_thumb, text=appearance + f"Gender: {gender}"
                )
                appearance_footer = embed.set_footer(
                    icon_url=image_thumb, text=appearance + f"Gender: {gender}"
                )
                gender_info = f"Gender: {gender}"

        h_w = f"Height: {height:.2f} m\nWeight: {weight:.2f} kg"
        print("is_shiny: ", type)
        self.bot.add_view(Pokebuttons(alt_names_str, species_name))

        await ctx.reply(
            embed=embed,
            view=Pokebuttons(
                alt_names_str,
                species_name,
                formatted_base_stats,
                type,
                wes,
                pokemon_type,
                base_stats,
                image_url,
                h_w,
                image_thumb,
                pokemon_dex_name,
                color,
                data,
                gender_differ,
                region,
                description,
                gender_info,
            ),
            mention_author=False,
        )


class Pokebuttons(discord.ui.View):
    def __init__(
        self,
        alt_names_str=None,
        name=None,
        formatted_base_stats=None,
        type=None,
        wes=None,
        pokemon_type=None,
        base_stats=None,
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
    ):
        super().__init__(timeout=None)
        self.alt_names_str = alt_names_str
        self.pokemon_name = name
        self.pokemon_shiny = type
        self.formatted_base_stats = formatted_base_stats
        self.s_and_w = wes
        self.pokemon_type = pokemon_type
        self.base_stats = base_stats
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

        # Add PokeSelect to the view
        pokemon_forms = self.get_pokemon_forms()

        if pokemon_forms and len(pokemon_forms) > 1:
            self.add_item(
                PokeSelect(
                    pokemon_forms,
                    self.image_url,
                    self.alt_names_str,
                    self.pokemon_shiny,
                    self.gender_info,
                )
            )

        # Assuming the file path to the Pokemon directory
        self.POKEMON_DIR = "data/pokemon"
        os.makedirs(self.POKEMON_DIR, exist_ok=True)
        self.POKEMON_IMAGES_FILE = os.path.join(
            self.POKEMON_DIR, "pokemon_images.txt")

        if not os.path.exists(self.POKEMON_IMAGES_FILE):
            with open(self.POKEMON_IMAGES_FILE, "w") as file:
                file.write("")  # Creating an empty text file

        # Load Pokémon images from the file
        self.pokemon_images = self.load_pokemon_images()

    def get_pokemon_forms(self):
        url = f"https://pokeapi.co/api/v2/pokemon-species/{self.pokemon_name.lower()}"
        print(f"Requesting forms for {self.pokemon_name} from URL: {url}")
        response = requests.get(url)
        print(f"Response status code: {response.status_code}")
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
                    pokemon_images[self.pokemon_name.lower()
                                   ] = image_link.strip()
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
            # Assuming male button is the first child
            male_button = self.children[0]
            female_button = self.children[
                1
            ]  # Assuming female button is the second child
        else:
            # Assuming male button is the second child
            male_button = self.children[1]
            female_button = self.children[
                0
            ]  # Assuming female button is the first child

        try:
            print(f"Male Button ID: {male_button.custom_id}")
            print(f"Female Button ID: {female_button.custom_id}")

            if gender == "male":
                image_url = self.pokemon_data["sprites"]["other"]["official-artwork"][
                    "front_default"
                ]
                print(image_url)
            else:
                # Check if the Pokémon name exists in the loaded images dictionary
                pokemon_name_lower = self.pokemon_name.lower()
                if pokemon_name_lower in self.pokemon_images:
                    image_url = self.pokemon_images[pokemon_name_lower]
                else:
                    image_url = self.pokemon_images["front_female"]

            embed = interaction.message.embeds[0]
            embed.set_image(url=image_url)
            await interaction.response.edit_message(embed=embed)

            # Change button colors
            male_button.style = discord.ButtonStyle.blurple
            female_button.style = discord.ButtonStyle.gray

            print("Button colors changed successfully.")

        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

    @discord.ui.button(
        label="Evolves",
        style=discord.ButtonStyle.gray,
        custom_id="Pokemon_Evolutions_Button",
        row=1,
    )
    async def show_evolutions_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        # Fetch and display evolution chain when button is clicked
        try:
            await self.show_evolutions(button)
        except requests.exceptions.RequestException as e:
            await interaction.response.send_message(
                f"Error fetching Pokémon evolution chain: {str(e)}", ephemeral=True
            )

    async def show_evolutions(self, interaction: discord.Interaction):
        try:
            # Fetch Pokémon evolution chain data
            evolution_chain_data = await self.get_pokemon_evolution_chain(
                self.pokemon_name
            )

            if not evolution_chain_data:
                await interaction.response.send_message(
                    f"No evolution chain found for {self.pokemon_name.title()}.",
                    ephemeral=True,
                )
                # Disable the button if no evolution chain found
                self.disabled = True
                await interaction.message.edit(view=self.view)
                return

            # Display the evolution chain
            embeds = await self.display_evolution_chain(evolution_chain_data)
            await interaction.response.send_message(embeds=embeds, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"Error fetching Pokémon evolution chain: {str(e)}", ephemeral=True
            )

    @staticmethod
    async def get_pokemon_evolution_chain(pokemon_name):
        async with aiohttp.ClientSession() as session:
            species_url = (
                f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_name.lower()}/"
            )
            async with session.get(species_url) as response:
                if response.status != 200:
                    raise Exception(
                        f"Error fetching species data for {pokemon_name}")

                species_data = await response.json()
                evolution_chain_url = species_data.get(
                    "evolution_chain", {}).get("url")

                if not evolution_chain_url:
                    raise Exception(
                        f"No evolution chain found for {pokemon_name}")

            async with session.get(evolution_chain_url) as response:
                if response.status != 200:
                    raise Exception(
                        f"Error fetching evolution chain data for {pokemon_name}"
                    )

                evolution_chain_data = await response.json()
                return evolution_chain_data.get("chain")

    async def display_evolution_chain(self, chain):
        embeds = []
        queue = [chain]
        final_forms = set()  # To keep track of Pokémon that are final forms

        while queue:
            current_chain = queue.pop(0)
            species_name = current_chain["species"]["name"].title()

            # Check if this is a final form
            if not current_chain.get("evolves_to"):
                final_forms.add(species_name)
                continue

            for evolution in current_chain["evolves_to"]:
                details = evolution["evolution_details"][0]
                next_pokemon_name = evolution["species"]["name"].title()
                method = await self.determine_evolution_method(
                    species_name, details, next_pokemon_name
                )

                if method:
                    embed = await self.create_pokemon_embed(
                        species_name, method, next_pokemon_name
                    )
                    embeds.append(embed)

                # Add the next evolution stage to the queue
                queue.append(evolution)

        # Handle final forms
        if final_forms:
            for final_form in final_forms:
                embed = await self.create_pokemon_embed(
                    final_form, "is the final form", final_form
                )
                embeds.append(embed)

        return embeds

    @staticmethod
    async def determine_evolution_method(
        current_pokemon, evolution_details, next_pokemon
    ):
        trigger = evolution_details.get("trigger", {}).get("name")
        item = evolution_details.get("item")
        known_move_type = evolution_details.get("known_move_type")
        time_of_day = evolution_details.get("time_of_day")
        min_level = evolution_details.get("min_level")
        min_happiness = evolution_details.get("min_happiness")
        method = ""

        if trigger == "level-up":
            # Handle leveling up with specific conditions
            if known_move_type:
                method += f"when leveled up while knowing a {known_move_type['name'].replace('-', ' ').title()} move"
            else:
                method = f"when leveled up"
                if time_of_day:
                    method += f" at {time_of_day.title()} time"
                if min_level:
                    method += f" starting from level {min_level}"
                if min_happiness:
                    method += " while holding a Friendship Bracelet"
        elif trigger == "use-item":
            # Handle evolution using a specific item
            if item:
                method = f"using a {item['name'].replace('-', ' ').title()}"
        elif trigger == "trade":
            # Handle trade evolution with or without an item
            if item:
                method = (
                    f"when traded holding a {item['name'].replace('-', ' ').title()}"
                )
            else:
                method = f"when traded"

        return method

    async def create_pokemon_embed(self, current_pokemon, method, next_pokemon):
        embed = discord.Embed()
        sprite_url = (
            f"https://pokemonshowdown.com/sprites/dex/{current_pokemon.lower()}.png"
        )
        print("create_pokemon_embed: ", self.pokemon_type)
        if self.pokemon_shiny:
            sprite_url = f"https://pokemonshowdown.com/sprites/dex-shiny/{current_pokemon.lower()}.png"

        embed.set_thumbnail(url=sprite_url)

        if current_pokemon == next_pokemon:
            # If the Pokémon evolves into itself (final form)
            embed.description = f"{current_pokemon} is the final form."
        else:
            # Normal evolution description
            embed.description = (
                f"{current_pokemon} evolves into {next_pokemon} {method}"
            )

        return embed

    @discord.ui.button(
        label="Stats", style=discord.ButtonStyle.gray, custom_id="Pokemon_Stats", row=1
    )
    async def s_and_w(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        embed = discord.Embed(color=self.color)
        embed.add_field(
            name="Base Stats", value=f"```py\n{self.base_stats}```", inline=False
        )
        # embed.add_field(name=" ", value="```" + self.pokemon_type + self.s_and_w + "```", inline=False)
        strength_weakness = "```" + self.pokemon_type + self.s_and_w + "```"
        if self.pokemon_type != "shiny":
            image = f"https://pokemonshowdown.com/sprites/dex/{self.pokemon_name}.png"
        else:
            image = (
                f"https://pokemonshowdown.com/sprites/dex-shiny/{self.pokemon_name}.png"
            )
        # embed.(url=self.image_url)
        if self.image_thumb is None:
            embed.set_footer(text=self.pokemon_dex_name)
        else:
            embed.set_footer(icon_url=self.image_thumb,
                             text=self.pokemon_dex_name)

        embed.set_thumbnail(url=self.image_url)

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


class PokeSelect(discord.ui.Select):
    def __init__(
        self, pokemon_forms, default_image_url, alt_names, pokemon_shiny, gender
    ):
        options = []
        for index, form in enumerate(pokemon_forms):
            form_name = form["name"]
            form_url = f"https://pokeapi.co/api/v2/pokemon/{form_name.lower()}"
            options.append(discord.SelectOption(
                label=form_name, value=form_url))
        super().__init__(
            placeholder="Form", options=options, custom_id="Select_Pokemon_Form"
        )
        self.default_image_url = default_image_url
        self.alt_names = alt_names
        self.pokemon_type = pokemon_shiny
        self.gender = gender

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

    def get_flag(self, lang):
        return self.flag_mapping.get(lang)

    @staticmethod
    def get_pokemon_description(
        pokemon_id, file_path="data/pokemon/pokemon_description.csv"
    ):
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
    def get_pokemon_region(
        pokemon_id, file_path="data/pokemon/pokemon_description.csv"
    ):
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
        form_endpoint = f"https://pokeapi.co/api/v2/pokemon-form/{pokemon_name}"
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
            species_endpoint = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name}"
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
        await interaction.response.defer()
        selected_form_url = self.values[0]
        response = requests.get(selected_form_url)

        if response.status_code == 200:
            data = response.json()
            official_artwork_url = None
            if "sprites" in data and "other" in data["sprites"]:
                if "official-artwork" in data["sprites"]["other"]:
                    if self.pokemon_type == "shiny":
                        official_artwork_url = data["sprites"]["other"][
                            "official-artwork"
                        ]["front_shiny"]
                        image_thumb = data["sprites"]["versions"]["generation-v"][
                            "black-white"
                        ]["front_shiny"]
                    else:
                        official_artwork_url = data["sprites"]["other"][
                            "official-artwork"
                        ]["front_default"]
                        image_thumb = data["sprites"]["versions"]["generation-v"][
                            "black-white"
                        ]["front_default"]

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
                    embed.set_footer(icon_url=str(
                        image_thumb), text=footer_text)
                else:
                    embed.set_footer(text=footer_text)

                # Remove previous Names field if it exists
                names_field = next(
                    (field for field in embed.fields if field.name == "Names"), None
                )
                if names_field:
                    embed.remove_field(embed.fields.index(names_field))

                embed.clear_fields()  # Clear Fields

                # Add Region field
                pokemon_region = self.get_pokemon_region(pokemon_data["id"])
                if pokemon_region and pokemon_region in self.region_mappings:
                    region_emoji = self.region_mappings[pokemon_region]
                    embed.add_field(
                        name="Region",
                        value=f"{region_emoji} {pokemon_region.title()}",
                        inline=True,
                    )

                # Add alternate names
                if names_field:
                    alternate_names = self.get_alternate_names(
                        pokemon_data["name"])
                    alt_names_info = {}
                    for name, lang in alternate_names:
                        key = name.lower()
                        flag = self.flag_mapping.get(lang, None)
                        if name.lower() != lang.lower() and flag is not None:
                            name_with_flag = f"{flag} {name}"
                            alt_names_info[key] = name_with_flag

                    sorted_names_by_length = dict(
                        sorted(alt_names_info.items(),
                               key=lambda item: len(item[1]))
                    )

                    if len(sorted_names_by_length) != len(alt_names_info):
                        sorted_names_by_name = dict(
                            sorted(alt_names_info.items(),
                                   key=lambda item: item[1])
                        )
                        name_list = sorted(list(sorted_names_by_name.values()))
                    else:
                        name_list = sorted(
                            list(sorted_names_by_length.values()))

                    alt_names_str = "\n".join(name_list[:6])
                    embed.add_field(
                        name="Names", value=alt_names_str, inline=True)

            await interaction.message.edit(embed=embed)
        else:
            await interaction.response.send_message(
                "Error fetching data for the selected form.", ephemeral=True
            )


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

    @discord.ui.button(
        label="S/W", style=discord.ButtonStyle.gray, custom_id="Pokemon_S_and_W_Button"
    )
    async def strengths_and_weaknesses(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        try:
            embed = discord.Embed(color=self.color)
            embed.add_field(
                name=" ", value=self.strength_weakness_text, inline=False)

            if self.footer is None:
                embed.set_footer(text=self.footer_text)
            else:
                embed.set_footer(icon_url=self.footer, text=self.footer_text)
            embed.set_thumbnail(url=self.thumbnail_url)

            await button.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await button.response.send_message(e, ephemeral=True)

            print(e)
            return

    @discord.ui.button(
        label="Moveset",
        style=discord.ButtonStyle.gray,
        custom_id="Pokemon_Moveset_Button",
    )
    async def moves_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await button.response.defer()
        await self.show_moves(button)

    async def show_moves(self, interaction: discord.Interaction):
        try:
            moves_data = await self.get_pokemon_moves()
            embed = discord.Embed(
                title=f"{self.pokemon_data['name'].title().replace('-', ' ')}'s — Moveset",
                color=self.color,
            )

            for level, move_info in sorted(moves_data.items()):
                move_name = move_info["name"].title().replace("-", " ")
                move_power = move_info["power"]
                move_accuracy = move_info["accuracy"]
                move_effect = move_info["effect"]

                embed.add_field(
                    name=f"(Level {level}) : {move_name}",
                    value=f"`Power:` **{move_power}**\n`Accuracy:` **{move_accuracy}**\n> ```Effect: {move_effect}```",
                    inline=True,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except requests.exceptions.RequestException as e:
            await interaction.followup.send(
                f"Error fetching moves data: {str(e)}", ephemeral=True
            )
        except IndexError:
            await interaction.followup.send(
                "Error: Move data is incomplete or unavailable.", ephemeral=True
            )

    async def get_pokemon_moves(self):
        moves_data = {}
        moves = self.pokemon_data.get("moves", [])
        for move in moves:
            move_name = move["move"]["name"]
            level = [
                version_group_details["level_learned_at"]
                for version_group_details in move["version_group_details"]
            ]
            if level:
                move_url = move["move"]["url"]
                move_data = await self.fetch_move_details(move_url)
                move_power = move_data.get("power", "N/A")
                move_accuracy = move_data.get("accuracy", "N/A")
                move_effect_entries = move_data.get("effect_entries", [])
                move_effect = (
                    move_effect_entries[0]["short_effect"]
                    if move_effect_entries
                    else "N/A"
                )
                moves_data.setdefault(
                    level[0],
                    {
                        "name": move_name,
                        "power": move_power,
                        "accuracy": move_accuracy,
                        "effect": move_effect,
                    },
                )
        return moves_data

    @staticmethod
    async def fetch_move_details(move_url):
        response = requests.get(move_url)
        if response.status_code == 200:
            move_data = response.json()
            return move_data

        return {}


def setup(bot):
    bot.add_cog(Pokemon(bot))
