import os
import io
import cv2
import numpy as np
from PIL import Image
import logging
import traceback

from Imports.discord_imports import *
from Imports.log_imports import logger
from Data.const import error_custom_embed


from skimage.metrics import structural_similarity as ssim


import asyncio
import aiohttp

class PokemonPredictor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.image_folder = 'Data/pokemon_images'
        logger.info("Initializing PokemonPredictor...")
        
    @staticmethod
    async def fetch_pokemon_info(pokemon_name):
        url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    official_artwork_url = data['sprites']['other']['official-artwork']['front_default']
                    return official_artwork_url
                else:
                    return None

    async def download_all_images(self):
        pokemon_names = await self.fetch_all_pokemon_names()
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

        async with aiohttp.ClientSession() as session:
            for pokemon_name in pokemon_names:
                filename = f"{pokemon_name}.png"
                filepath = os.path.join(self.image_folder, filename)
                if not os.path.exists(filepath):
                    official_artwork_url = await self.fetch_pokemon_info(pokemon_name)
                    if official_artwork_url:
                        async with session.get(official_artwork_url) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                with open(filepath, 'wb') as f:
                                    f.write(image_data)
                                logger.info(f"Downloaded image for {pokemon_name}.")
                            else:
                                logger.error(f"Failed to download image for {pokemon_name}.")
                    else:
                        logger.error(f"Failed to fetch information for the Pokémon {pokemon_name}.")
                else:
                    logger.info(f"Image for {pokemon_name} already exists, skipping download.")
  
    def remove_srgb_profile(self, img_path):
        try:
            with Image.open(img_path) as img:
                img.save(img_path, icc_profile=None)
                logger.debug(f"Removed sRGB profile from {img_path}")
        except Exception as e:
            logger.error(f"Error removing sRGB profile: {e}")
            
    def ensure_correct_color_format(self, img):
     """
     Convert image to RGB format.
     """
     if img.shape[2] == 3:  # Check if the image has 3 color channels
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
     elif img.shape[2] == 4:  # Check if the image has 4 color channels (with alpha)
        return cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
     return img
    
    async def predict_pokemon(self, ctx, img, threshold=0.8):
        try:
            logger.debug("Predicting Pokémon from provided image...")
            async with ctx.typing():
                if not os.path.exists(self.image_folder):
                    os.makedirs(self.image_folder)

                pokemon_files = [f for f in os.listdir(self.image_folder) if os.path.isfile(os.path.join(self.image_folder, f))]
                logger.debug(f"Number of Pokémon images found: {len(pokemon_files)}")

                best_match = None
                highest_score = (float('-inf'), float('-inf'))  # Initialize with very low SSIM and MSE scores

                # Convert image to numpy array and ensure correct color format
                img_np = np.array(img)
                img_np = self.ensure_correct_color_format(img_np)
                # Convert image to uint8 depth if needed
                if img_np.dtype != np.uint8:
                    img_np = img_np.astype(np.uint8)

                # Convert image to PIL Image for comparison
                img_pil = Image.fromarray(img_np)

                # Convert image to binary for contour detection
                gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                _, binary_img = cv2.threshold(gray_img, 127, 255, cv2.THRESH_BINARY)

                # Find contours
                contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                # Initialize variables to store the largest contour's index and area
                largest_contour_idx = -1
                largest_contour_area = 0

                for idx, contour in enumerate(contours):
                    # Calculate contour area
                    contour_area = cv2.contourArea(contour)

                    # Check if contour area is greater than the current largest contour area
                    if contour_area > largest_contour_area:
                        largest_contour_idx = idx
                        largest_contour_area = contour_area

                # Only proceed if a valid contour is found
                if largest_contour_idx != -1:
                    x, y, w, h = cv2.boundingRect(contours[largest_contour_idx])

                    # Draw rectangle around the largest contour
                    cv2.rectangle(img_np, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    # Determine padding dynamically based on the dimensions of the bounding box
                    padding_x = min(w // 2, img_np.shape[1] - w)
                    padding_y = min(h // 2, img_np.shape[0] - h)

                    # Crop region of interest (ROI) from the original image with adaptive padding
                    roi = img_np[max(y - padding_y, 0):min(y + h + padding_y, img_np.shape[0]),
                                 max(x - padding_x, 0):min(x + w + padding_x, img_np.shape[1])]

                    orb = cv2.ORB_create()

                    # Compute keypoints and descriptors for the ROI
                    kp1, des1 = orb.detectAndCompute(roi, None)

                    for pokemon_file in pokemon_files:
                        pokemon_name, _ = os.path.splitext(pokemon_file)
                        stored_img_path = os.path.join(self.image_folder, pokemon_file)

                        # Ensure the stored_img_path is a file
                        if not os.path.isfile(stored_img_path):
                            logger.warning(f"Not a file: {stored_img_path}")
                            continue

                        # Remove sRGB profile
                        self.remove_srgb_profile(stored_img_path)

                        try:
                            stored_img = Image.open(stored_img_path)
                        except Exception as e:
                            logger.warning(f"Unable to read image: {stored_img_path}")
                            continue

                        # Calculate similarity between the input image and stored image
                        similarity_score = await self.calculate_similarity(img_pil, stored_img)
                        print(similarity_score)

                        # Update best match if criteria are met
                        try:
                            if isinstance(similarity_score, list):
                                if similarity_score[0] > highest_score[0] or (similarity_score[0] == highest_score[0] and similarity_score[2] < highest_score[2]):
                                    highest_score = tuple(similarity_score)
                                    best_match = pokemon_name
                            else:
                                logger.warning(f"Similarity score is not a tuple: {similarity_score}")
                        except Exception as e:
                            error_message = "An error occurred while predicting Pokémon."
                            logger.error(f"{error_message}: {e}")
                            traceback.print_exc()
                            await self.error_custom_embed(self.bot, ctx, error_message, title="Pokemon Prediction Error")

                        logger.debug(f"Comparing {pokemon_name} with similarity score: {similarity_score[0]:.2f}")

                    if best_match:
                        matched_img_path = os.path.join(self.image_folder, best_match + ".png")
                        matched_img = cv2.imread(matched_img_path)
                        matched_img = self.ensure_correct_color_format(matched_img)
                        resized_matched_img = cv2.resize(matched_img, (roi.shape[1], roi.shape[0]))

                        roi_path = 'Data/pokemon_images/detection/roi.png'
                        matched_img_path = 'Data/pokemon_images/detection/matched_img.png'
                        combined_img = np.hstack((roi, resized_matched_img))
                        combined_img_path = 'Data/pokemon_images/detection/combined_comparison.png'
                        detected_objects_path = "Data/pokemon_images/detection/detected_objects.png"

                        # Create necessary directories
                        os.makedirs(os.path.dirname(roi_path), exist_ok=True)

                        # Save the images
                        cv2.imwrite(roi_path, roi)
                        cv2.imwrite(matched_img_path, resized_matched_img)
                        cv2.imwrite(combined_img_path, combined_img)

                        # Send the combined image
                        await ctx.send(file=discord.File(combined_img_path))

                    # Save and send the detected objects image
                    cv2.imwrite(detected_objects_path, img_np)
                    await ctx.send(file=discord.File(detected_objects_path))

                    if highest_score[0] > threshold:
                        logger.info(f"Best match: {best_match} with score {highest_score[0]:.2f}")
                        await ctx.send(f"Best match: {best_match} with score {highest_score[0]:.2f}")
                    else:
                        logger.info("No good match found")
                        await ctx.send("No good match found")

                    return best_match, highest_score[0]
        except Exception as e:
            error_message = "An error occurred while predicting Pokémon."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await self.error_custom_embed(self.bot, ctx, error_message, title="Pokemon Prediction Error")
            return None, 0

    
    async def calculate_similarity(self, img1, img2, size=(256, 256)):
     try:
        # Resize images to the specified size
        img1_resized = img1.resize(size)
        img2_resized = img2.resize(size)

        # Convert images to grayscale
        img1_gray = img1_resized.convert('L')
        img2_gray = img2_resized.convert('L')

        # Convert images to numpy arrays
        img1_np = np.array(img1_gray)
        img2_np = np.array(img2_gray)

        # Calculate SSIM (Structural Similarity Index) for img1
        ssim_score_img1 = ssim(img1_np, img2_np)

        # Calculate SSIM (Structural Similarity Index) for img2
        ssim_score_img2 = ssim(img2_np, img1_np)

        # Calculate MSE (Mean Squared Error) for img1
        mse_score_img1 = np.mean((img1_np - img2_np) ** 2)

        # Calculate MSE (Mean Squared Error) for img2
        mse_score_img2 = np.mean((img2_np - img1_np) ** 2)

        return [ssim_score_img1, ssim_score_img2, mse_score_img1, mse_score_img2]
     except Exception as e:
        logger.error(f"Error calculating similarity: {e}")
        return [0, 0, 0, 0]

    
    @commands.command(name='predict')
    async def predict(self, ctx, url: str = None):
        # Initial message asking the user to provide an image or URL
        embed = discord.Embed(
            title="Predict Pokémon",
            description="Please send an image of the Pokémon to predict or provide a URL to the image.\n\nType `c` to cancel.",
            color=discord.Color.blue()
        )
        progress_message = await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            if url:
                # If URL is provided, download the image
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            img_bytes = await response.read()
                            img = Image.open(io.BytesIO(img_bytes))
                            img = img.resize((224, 224))
                            img = np.array(img.convert('RGB'))  # Convert to RGB
                            logger.debug("Image received and processed from URL.")
                        else:
                            await ctx.send("Failed to download image from the provided URL.")
                            logger.debug("Failed to download image from URL.")
                            return
            else:
                # Wait for user to send an image
                user_response = await self.bot.wait_for('message', timeout=120, check=check)

                if user_response.content.lower() == 'c':
                    await ctx.send("Operation cancelled.")
                    logger.debug("User cancelled the operation.")
                    return

                if user_response.attachments:
                    attachment = user_response.attachments[0]
                    if attachment.filename.endswith(('png', 'jpg', 'jpeg')):
                        img_bytes = await attachment.read()
                        img = Image.open(io.BytesIO(img_bytes))
                        img = img.resize((224, 224))
                        img = np.array(img.convert('RGB'))  # Convert to RGB
                        logger.debug("Image received and processed from attachment.")
                    else:
                        await ctx.send("Please attach a valid image file.")
                        logger.debug("Invalid image file attached.")
                        return
                else:
                    await ctx.send("Please attach an image.")
                    logger.debug("No valid image provided.")
                    return

            # Perform prediction
            predicted_pokemon, confidence_score = await self.predict_pokemon(ctx, img)

            # If prediction is successful, send success message with prediction result
            if predicted_pokemon:
                success_embed = discord.Embed(
                    title="Prediction Result",
                    description=f"The predicted Pokémon is: **{predicted_pokemon}** with a confidence score of **{confidence_score:.2%}**.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=success_embed)
                logger.info(f"Prediction result sent: {predicted_pokemon} with score {confidence_score:.2%}")
            else:
                # If prediction fails, send failure message
                failure_embed = discord.Embed(
                    title="Prediction Failed",
                    description="Failed to predict the Pokémon. Please try again with a different image.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=failure_embed)
                logger.error("Prediction failed.")

        except asyncio.TimeoutError:
            await ctx.send("Time's up. Operation cancelled.")
            logger.info("Timeout occurred. Operation cancelled.")

    @commands.command(name='add')
    async def add_pokemon(self, ctx, pokemon_name: str):
     logger.info(f"Attempting to add Pokémon: {pokemon_name}")
     filename = f"{pokemon_name}.png"
     filepath = os.path.join(self.image_folder, filename)
    
     try:
        # Create the directory if it doesn't exist
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

        if os.path.exists(filepath):
            await ctx.send(f"The Pokémon {pokemon_name} already exists in the database.")
            logger.debug(f"The Pokémon {pokemon_name} already exists in the database.")
            return

        official_artwork_url = await self.fetch_pokemon_info(pokemon_name)
        logger.debug(f"Official artwork URL for {pokemon_name}: {official_artwork_url}")
        
        if official_artwork_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(official_artwork_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        with open(filepath, 'wb') as f:
                            f.write(image_data)
                        await ctx.send(f"Added the Pokémon {pokemon_name} to the database.")
                        logger.info(f"Added the Pokémon {pokemon_name} to the database.")
                    else:
                        await ctx.send("Failed to download the image.")
                        logger.error("Failed to download the image.")
        else:
            await ctx.send(f"Failed to fetch information for the Pokémon {pokemon_name}.")
            logger.error(f"Failed to fetch information for the Pokémon {pokemon_name}.")
            
     except Exception as e:
        await ctx.send("An error occurred while adding the Pokémon. Please try again later.")
        logger.error(f"An error occurred while adding the Pokémon {pokemon_name}: {e}")

    
    @commands.command(name='all')
    async def download_images(self, ctx):
        await ctx.send("Starting download of all Pokémon images. This may take a while.")
        await self.download_all_images()
        await ctx.send("Completed download of all Pokémon images.")

def setup(bot):
    bot.add_cog(PokemonPredictor(bot))