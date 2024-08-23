import concurrent.futures
import threading
import time
import cv2
import os
import io
import pickle
import aiohttp
import numpy as np
from PIL import Image
from discord.ext import commands
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])

class PokemonPredictor:
    def __init__(self, predict_folder="predict", dataset_folder="dataset"):
        # Initialize ORB with a reasonable number of features
        self.orb = cv2.ORB_create(nfeatures=170)

        # Configure FLANN with parameters for faster matching
        index_params = dict(algorithm=6, table_number=6, key_size=10, multi_probe_level=1)
        search_params = dict(checks=10)
        self.flann = cv2.FlannBasedMatcher(index_params, search_params)

        # Thread pool executor for parallel processing
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        self.cache = {}
        self.load_dataset(dataset_folder)

    def load_dataset(self, dataset_folder):
        self._clear_console()
        print("Loading Images...")
        start_time = time.time()

        # Faster directory traversal using os.scandir
        image_paths = [entry.path for entry in os.scandir(dataset_folder) if entry.is_file()]

        results = list(self.executor.map(self._process_image, image_paths))
        for filename, result in zip(os.scandir(dataset_folder), results):
            if result:
                self.cache[filename.name] = result

        self._clear_console()
        elapsed_time = round(time.time() - start_time, 2)
        print(f"Successfully loaded all images.\nTime Taken: {elapsed_time} sec")

    def _process_image(self, image_path):
        img = cv2.imread(image_path)
        if img is not None:
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            keypoints, descriptors = self.orb.detectAndCompute(gray_img, None)
            return img, keypoints, descriptors
        return None

    def _match_image(self, kpB, desB, cache_item):
        filename, (imgA, kpA, desA) = cache_item
        if desA is not None and desB is not None:
            # ORB feature matching
            matches = self.flann.knnMatch(desA, desB, k=2)
            good_matches = [m[0] for m in matches if len(m) == 2 and m[0].distance < 0.75 * m[1].distance]

            if len(good_matches) > 4:
                # Extract location of good matches
                src_pts = np.float32([kpA[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kpB[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

                # Calculate homography
                M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

                if M is not None:
                    h, w = imgA.shape[:2]
                    pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
                    dst = cv2.perspectiveTransform(pts, M)

                    if self._is_valid_match(dst):
                        accuracy = len(good_matches) / len(desA) * 100
                        return filename, len(good_matches), accuracy
        return None

    def _is_valid_match(self, dst):
        # Check if the found polygon is convex and large enough to be considered a valid match
        return cv2.isContourConvex(dst) and cv2.contourArea(dst) > 100

    def predict_pokemon(self, img):
        start_time = time.time()
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        kpB, desB = self.orb.detectAndCompute(gray_img, None)

        futures = [self.executor.submit(self._match_image, kpB, desB, item) for item in self.cache.items()]
        best_match = max((future.result() for future in concurrent.futures.as_completed(futures)), key=lambda x: x[1] if x else 0, default=None)

        elapsed_time = round(time.time() - start_time, 2)
        if best_match:
            predicted_pokemon = best_match[0].split(".png")[0].split("_flipped")[0]
            accuracy = round(best_match[2], 2)
            return f"```<@716390085896962058> {predicted_pokemon.title()}```\n⏱️ {elapsed_time}s\n🎯 {accuracy}%", elapsed_time

        return "No Pokémon detected", elapsed_time

    def _clear_console(self):
        os.system("cls" if os.name == "nt" else "clear")













class PokemonBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.author_id = 716390085896962058
        self.predictor = PokemonPredictor()

    @commands.command(name='predict')
    async def predict(self, ctx, *, arg=None):
        image_url = None

        if arg:
            image_url = arg
        elif ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        elif ctx.message.reference:
            reference_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
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
                        img = np.array(img.convert('RGB'))  # Convert to numpy array

                        # Use the predictor to predict the Pokémon
                        prediction, time_taken = self.predictor.predict_pokemon(img)
                        await ctx.reply(prediction, mention_author=False)
                    else:
                        await ctx.reply(f"Failed to download image. Status code: {response.status}", mention_author=False)
        else:
            await ctx.send("No image found to predict.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.author_id and message.embeds:
            embed = message.embeds[0]
            if embed.description and 'Guess the pokémon' in embed.description:
                image_url = embed.image.url
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as response:
                        if response.status == 200:
                            img_bytes = await response.read()
                            img = Image.open(io.BytesIO(img_bytes))
                            img = np.array(img.convert('RGB'))  # Convert to numpy array

                            # Use the predictor to predict the Pokémon
                            prediction, time_taken = self.predictor.predict_pokemon(img)
                            await message.channel.send(prediction, reference=message)
                        else:
                            await message.channel.send(f"Failed to download image. Status code: {response.status}", reference=message)


def setup(bot):
    bot.add_cog(PokemonBot(bot))
