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

from urllib.request import urlopen, urlretrieve
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
    
    def download_file(self, url, filename):
        response = urlopen(url)
        with open(filename, 'wb') as f:
            f.write(response.read())

    
    async def predict_pokemon(self, ctx, img, threshold=0.8):
     try:
        logger.debug("Predicting Pokémon from provided image...")
        async with ctx.typing():
            if not os.path.exists(self.image_folder):
                os.makedirs(self.image_folder)

            pokemon_files = [f for f in os.listdir(self.image_folder) if os.path.isfile(os.path.join(self.image_folder, f))]
            logger.debug(f"Number of Pokémon images found: {len(pokemon_files)}")
            
            matches_list = []

            best_match = None
            highest_score = (float('-inf'), float('-inf'), '')  # Initialize with very low similarity score and empty name

            # Convert image to numpy array and ensure correct color format
            img_np = np.array(img)
            img_np = self.ensure_correct_color_format(img_np)
            # Convert image to uint8 depth if needed
            if img_np.dtype != np.uint8:
                img_np = img_np.astype(np.uint8)

            # Convert image to grayscale for contour detection
            gray_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

            # Apply GaussianBlur to reduce noise and improve contour detection
            blurred_img = cv2.GaussianBlur(gray_img, (5, 5), 0)

            # Apply Canny edge detector
            edged_img = cv2.Canny(blurred_img, 50, 150)

            # Dilate the edges to close gaps
            dilated_img = cv2.dilate(edged_img, None, iterations=2)

            # Find contours
            contours, _ = cv2.findContours(dilated_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

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

                # Draw rectangle around the largest contour (for visualization)
                cv2.rectangle(img_np, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Determine padding dynamically based on the dimensions of the bounding box
                padding_x = min(w // 2, img_np.shape[1] - w)
                padding_y = min(h // 2, img_np.shape[0] - h)

                # Crop region of interest (ROI) from the original image with adaptive padding
                roi = img_np[max(y - padding_y, 0):min(y + h + padding_y, img_np.shape[0]),
                             max(x - padding_x, 0):min(x + w + padding_x, img_np.shape[1])]

                # Use ORB (Oriented FAST and Rotated BRIEF) for keypoint and descriptor computation
                orb = cv2.ORB_create()

                # Compute keypoints and descriptors for the ROI
                kp1, des1 = orb.detectAndCompute(roi, None)

                # Iterate over stored Pokemon images for comparison
                for pokemon_file in pokemon_files:
                    pokemon_name, _ = os.path.splitext(pokemon_file)
                    stored_img_path = os.path.join(self.image_folder, pokemon_file)

                    # Ensure the stored_img_path is a file
                    if not os.path.isfile(stored_img_path):
                        logger.warning(f"Not a file: {stored_img_path}")
                        continue

                    try:
                        stored_img = cv2.imread(stored_img_path, cv2.IMREAD_UNCHANGED)
                        stored_img = self.ensure_correct_color_format(stored_img)
                        stored_img_gray = cv2.cvtColor(stored_img, cv2.COLOR_RGB2GRAY)

                        # Compute keypoints and descriptors for the stored image
                        kp2, des2 = orb.detectAndCompute(stored_img_gray, None)

                        # Match descriptors using BFMatcher (Brute Force Matcher)
                        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                        matches = bf.match(des1, des2)

                        # Sort matches by distance
                        matches = sorted(matches, key=lambda x: x.distance)

                        # Calculate similarity score based on matches
                        similarity_score = len(matches) / len(kp1) if kp1 else 0

                        # Calculate contour-based similarity score
                        contour_similarity = await self.calculate_similarity(roi, stored_img)

                        # Combine similarity scores (for example, averaging or another method)
                        combined_similarity = (similarity_score + contour_similarity[0]) / 2

                        # Update best match if criteria are met
                        if combined_similarity > highest_score[0]:
                            highest_score = (combined_similarity, len(matches), pokemon_name)
                            best_match = pokemon_name

                        logger.debug(f"Comparing {pokemon_name} with combined similarity score: {combined_similarity:.2f}")
                        matches_list.append((pokemon_name, combined_similarity))

                    except Exception as e:
                        logger.warning(f"Unable to process image: {stored_img_path}. Error: {e}")
                        continue

                # Visualize and save comparison images (optional)
                if best_match:
                    matched_img_path = os.path.join(self.image_folder, best_match + ".png")
                    matched_img = cv2.imread(matched_img_path, cv2.IMREAD_UNCHANGED)
                    matched_img = self.ensure_correct_color_format(matched_img)
                    resized_matched_img = cv2.resize(matched_img, (roi.shape[1], roi.shape[0]))

                    # Paths for saving images
                    roi_path = 'Data/pokemon_images/detection/roi.png'
                    matched_img_path = 'Data/pokemon_images/detection/matched_img.png'
                    combined_img_path = 'Data/pokemon_images/detection/combined_comparison.png'
                    detected_objects_path = "Data/pokemon_images/detection/detected_objects.png"

                    # Create necessary directories if they don't exist
                    os.makedirs(os.path.dirname(roi_path), exist_ok=True)

                    # Save the images
                    cv2.imwrite(roi_path, roi)
                    cv2.imwrite(matched_img_path, resized_matched_img)
                    combined_img = np.hstack((roi, resized_matched_img))
                    cv2.imwrite(combined_img_path, combined_img)

                    # Send the combined image (assuming Discord bot context)
                    await ctx.send(file=discord.File(combined_img_path))

                # Save and send the detected objects image (for visualization)
                cv2.imwrite(detected_objects_path, img_np)
                await ctx.send(file=discord.File(detected_objects_path))

                # Provide result based on threshold
                matches_list_sorted = sorted(matches_list, key=lambda x: x[1], reverse=True)
                embed = discord.Embed(title="Best Match", description=f"The best match found is {best_match}")
                embed.add_field(name="Combined Similarity", value=f"{highest_score[0]:.2f}", inline=False)

                for index, match in enumerate(matches_list_sorted):
                    if index >= 6:
                        break

                    pokemon_name, similarity_score = match
                    embed.add_field(name=f"{pokemon_name}", value=f"Similarity: {similarity_score:.2f}", inline=True)

                await ctx.send(embed=embed)

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

        
        
    async def calculate_similarity(self, img1, img2, size=(256, 256), num_sections=4):
        try:
            # Function to calculate color histogram similarity
            def calculate_color_histogram_similarity(hist1, hist2):
                # Use histogram intersection for comparison
                similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_INTERSECT)
                return similarity
            
            # Resize images to the specified size
            img1_resized = cv2.resize(np.array(img1), size)
            img2_resized = cv2.resize(np.array(img2), size)
            
            # Convert images to RGB (assuming they are BGR due to cv2)
            img1_rgb = cv2.cvtColor(img1_resized, cv2.COLOR_BGR2RGB)
            img2_rgb = cv2.cvtColor(img2_resized, cv2.COLOR_BGR2RGB)
            
            # Split images into sections
            height1, width1, _ = img1_rgb.shape
            height2, width2, _ = img2_rgb.shape
            
            section_height = height1 // num_sections
            section_width = width1 // num_sections
            
            # Initialize a list to store section similarities
            section_similarities = []
            
            # Iterate through sections
            for i in range(num_sections):
                for j in range(num_sections):
                    # Calculate section boundaries for both images
                    start_row1 = i * section_height
                    end_row1 = (i + 1) * section_height
                    start_col1 = j * section_width
                    end_col1 = (j + 1) * section_width
                    
                    start_row2 = i * (height2 // num_sections)
                    end_row2 = (i + 1) * (height2 // num_sections)
                    start_col2 = j * (width2 // num_sections)
                    end_col2 = (j + 1) * (width2 // num_sections)
                    
                    # Extract sections from both images
                    section_img1 = img1_rgb[start_row1:end_row1, start_col1:end_col1, :]
                    section_img2 = img2_rgb[start_row2:end_row2, start_col2:end_col2, :]
                    
                    # Calculate color histograms for the sections
                    hist_img1 = cv2.calcHist([section_img1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                    hist_img2 = cv2.calcHist([section_img2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                    
                    # Normalize histograms
                    cv2.normalize(hist_img1, hist_img1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
                    cv2.normalize(hist_img2, hist_img2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
                    
                    # Calculate similarity between color histograms
                    section_similarity = calculate_color_histogram_similarity(hist_img1, hist_img2)
                    section_similarities.append(section_similarity)
            
            # Calculate overall similarity as the average of section similarities
            overall_similarity = np.mean(section_similarities)
            
            # Round overall_similarity to 4 decimal places
            rounded_similarity = round(overall_similarity, 4)
            
            # Return overall similarity as a list (for consistency with previous implementation)
            return [rounded_similarity]
        
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return [0.0]  # Return default similarity in case of errors
    
    
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
