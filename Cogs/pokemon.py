import os
import cv2 as cv
import numpy as np
import time
import aiohttp
import asyncio
import io
from sklearn.metrics.pairwise import cosine_similarity
import logging
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageSequence
from tqdm import tqdm  # Import tqdm for progress tracking
import mediapipe as mp

# Configure logging
logging.basicConfig(filename='pokemon_predictor.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class PokemonPredictor:
    def __init__(self, dataset_folder="pokemon_images", 
                 dataset_file="dataset.npy", max_workers=4, num_keypoints=100):
        self.flann = cv.FlannBasedMatcher(
            dict(algorithm=6, table_number=9, key_size=9, multi_probe_level=1), 
            dict(checks=1, fast=True)
        )
        self.cache = {}  # Store descriptors
        self.dataset_file = dataset_file
        self.dataset_folder = dataset_folder
        self.orb = cv.ORB_create(nfeatures=num_keypoints)  # Initialize ORB detector
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5)

    async def load_dataset(self):
        """Load the dataset from npy file or process the image folder asynchronously."""
        if os.path.exists(self.dataset_file):
            self.load_from_npy(self.dataset_file)
        else:
            await self.load_from_images()

    def load_from_npy(self, dataset_file):
        """Load precomputed descriptors from npy."""
        data = np.load(dataset_file, allow_pickle=True).item()
        self.cache = data
        logging.info(f"Loaded dataset from {dataset_file}. Total images: {len(data)}")

    async def load_from_images(self):
        """Process images in the folder using asyncio."""
        tasks = [
            self.process_image(os.path.join(self.dataset_folder, filename), filename)
            for filename in os.listdir(self.dataset_folder)
            if os.path.isfile(os.path.join(self.dataset_folder, filename))
        ]
        await asyncio.gather(*tasks)  # Gather all tasks and run them concurrently
        await self.save_dataset_concurrently()

    async def save_dataset_concurrently(self):
        """Save the dataset to npy file asynchronously."""
        if self.cache:  # Only save if there are descriptors
            try:
                await asyncio.to_thread(self.save_to_npy)
            except Exception as e:
                logging.error(f"Error saving dataset: {e}")
        else:
            logging.info("No descriptors to save.")

    def save_to_npy(self):
        """Actual function to save the cache to a npy file."""
        np.save(self.dataset_file, self.cache)
        logging.info(f"Saved dataset to {self.dataset_file}.")

    async def process_image(self, path, filename):
        """Process a single image asynchronously."""
        img = await asyncio.get_event_loop().run_in_executor(self.executor, cv.imread, path)
        if img is not None:
            gray_img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
            keypoints, descriptors = self.orb.detectAndCompute(gray_img, None)
            if descriptors is not None:
                self.cache[filename] = descriptors.astype(np.uint8)
                await self.cache_flipped_image(img, filename)

    async def cache_flipped_image(self, img, filename):
        """Cache the flipped version of the image and its descriptors."""
        flipped_img = cv.flip(img, 1)
        gray_flipped_img = cv.cvtColor(flipped_img, cv.COLOR_BGR2GRAY)
        keypoints, descriptors = self.orb.detectAndCompute(gray_flipped_img, None)
        if descriptors is not None:
            flipped_filename = filename.replace(".png", "_flipped.png")
            self.cache[flipped_filename] = descriptors.astype(np.uint8)

    async def load_image_from_url(self, url):
        """Asynchronously fetch and decode an image from a URL."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        img_data = await response.read()
                        img_array = np.asarray(bytearray(img_data), dtype=np.uint8)
                        return cv.imdecode(img_array, cv.IMREAD_COLOR)
                    else:
                        logging.error(f"Failed to fetch image, status code: {response.status}")
            except aiohttp.ClientError as e:
                logging.error(f"Error fetching image: {e}")
        return None

    async def load_gif_frames(self, url):
        """Load frames from a GIF URL."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        img_data = await response.read()
                        img_gif = Image.open(io.BytesIO(img_data))
                        frames = [np.array(frame.convert('RGB')) for frame in ImageSequence.Iterator(img_gif)]
                        return frames
                    else:
                        logging.error(f"Failed to fetch GIF, status code: {response.status}")
            except aiohttp.ClientError as e:
                logging.error(f"Error fetching GIF: {e}")
        return None

    async def cross_match(self, desB):
        """Match the descriptors with the dataset using FLANN."""
        if desB is None or desB.size == 0:
            logging.warning("No descriptors available for matching.")
            return None, 0.0

        best_match = None
        best_score = float('-inf')

        for filename, descriptor in self.cache.items():
            matches = self.flann.knnMatch(desB, descriptor, k=2)

            # Filter out good matches
            good_matches = []
            for match_pair in matches:
                # Ensure we have at least 2 matches in the pair
                if len(match_pair) >= 2:
                    m, n = match_pair  # Unpack the matches
                    # Compare distances and filter matches
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)

            score = len(good_matches)

            if score > best_score:
                best_score = score
                best_match = filename

        return best_match, best_score

    async def predict_pokemon(self, img):
        """Predict the closest matching Pokémon from the dataset using contour detection and feature extraction."""
        start_time = time.time()
        best_match = None
        highest_score = float('-inf')  # Initialize with very low similarity score
        frames_with_detections = []  # List to store frames with bounding boxes

        # Process as a list of frames (animated GIF) or as a static image
        if isinstance(img, list):
            preloaded_frames = img.copy()
            frame_count = len(preloaded_frames)

            # Use tqdm to track progress
            for frame_idx, img_np in tqdm(enumerate(preloaded_frames), total=frame_count, desc="Processing frames"):
                img_np = cv.cvtColor(img_np, cv.IMREAD_COLOR)  # Convert to BGR for OpenCV
                highest_score, best_match, processed_frame = await self.process_frame(img_np, frame_idx, highest_score, best_match)
                frames_with_detections.append(processed_frame)  # Store the processed frame with detections

        else:
            img_np = np.array(img)
            img_np = img_np.astype(np.uint8) if img_np.dtype != np.uint8 else img_np
            highest_score, best_match, processed_frame = await self.process_frame(img_np, 0, highest_score, best_match)
            frames_with_detections.append(processed_frame)  # Store the processed frame with detections

        logging.info(f"Processed image in {time.time() - start_time:.2f} seconds. Best match: {best_match} with score {highest_score}.")
        return best_match, time.time() - start_time, frames_with_detections  # Return processed frames

    async def process_frame(self, img_np, frame_idx, highest_score, best_match):
        """Process a single frame/image for prediction."""
        # Convert the image to grayscale
        #gray_img = cv.cvtColor(img_np, cv.COLOR_BGR2GRAY)

    
        # Apply Gaussian blur to reduce noise
        blurred_img = cv.GaussianBlur(img_np, (5, 5), 0)
    
        # Apply Canny edge detection to get outlines
        edged_img = cv.Canny(blurred_img, 50, 150)
    
        # Find contours in the edged image
        contours, _ = cv.findContours(edged_img, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

        # Create a blank image to draw the heat map
        heat_map = np.zeros_like(img_np, dtype=np.float32)

        if contours:
            # Filter out small contours
            large_contours = [cnt for cnt in contours if cv.contourArea(cnt) > 500]  # Adjust area threshold as needed

            if large_contours:
                # Sort contours by area and take the largest ones
                large_contours = sorted(large_contours, key=cv.contourArea, reverse=True)

                # Process each large contour
                for i in range(min(10, len(large_contours))):  # Limit to top 10 largest contours
                    cnt = large_contours[i]
                    x, y, w, h = cv.boundingRect(cnt)
                    roi = img_np[y:y + h, x:x + w]

                    # Convert ROI to grayscale for feature detection
                    gray_roi = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)

                    # Detect keypoints and compute descriptors
                    kp_roi, des_roi = self.orb.detectAndCompute(gray_roi, None)
                    if des_roi is not None and des_roi.shape[0] > 0:
                        # Compare with dataset
                        for name, des in self.cache.items():
                            if des.shape[0] > 0:
                                # Compute cosine similarity
                                similarity = cosine_similarity(des_roi.astype(np.float32), des.astype(np.float32))
                                score = np.max(similarity)

                                if score > highest_score:
                                    highest_score = score
                                    best_match = name

                    # Optional: Draw bounding box around detected Pokémon
                    cv.rectangle(img_np, (x, y), (x + w, y + h), (255, 0, 0), 2)  # Red bounding box

                    # Update the heat map with bounding box area
                    cv.rectangle(heat_map, (x, y), (x + w, y + h), (255, 255, 255), -1)  # White rectangle

        return highest_score, best_match, img_np  # Return updated frame

    async def save_gif_with_detections(self, frames):
        """Save the processed frames as a new GIF with bounding boxes."""
        save_path = 'detected_pokemon.gif'
        frames_to_save = [Image.fromarray(frame) for frame in frames]
        frames_to_save[0].save(save_path, save_all=True, append_images=frames_to_save[1:], loop=0)
        logging.info(f"Saved processed GIF with detections to {save_path}.")

async def main():
    predictor = PokemonPredictor()
    await predictor.load_dataset()

    while True:
        img_url = input("Enter an image URL (or type 'quit' to exit): ")
        if img_url.lower() == 'quit':
            break

        # Load GIF or static image
        if img_url.lower().endswith('.gif'):
            frames = await predictor.load_gif_frames(img_url)
            if frames:
                best_match, _, processed_frames = await predictor.predict_pokemon(frames)
                print(f"Best match for GIF: {best_match}")
                await predictor.save_gif_with_detections(processed_frames)

        else:
            img = await predictor.load_image_from_url(img_url)
            if img is not None:
                best_match, _, processed_frames = await predictor.predict_pokemon(img)
                print(f"Best match for image: {best_match}")

if __name__ == "__main__":
    asyncio.run(main())
