import os
import cv2 as cv
import numpy as np
import csv
import json
import requests
from concurrent.futures import ThreadPoolExecutor
import asyncio
import aiofiles
import matplotlib.pyplot as plt
import time  # Import time for measuring elapsed time

class PokemonPredictor:
    def __init__(self, dataset_folder='pokemon_images', output_folder='testing_output', dataset_file="_dataset.npy"):
        self.orb = cv.ORB_create(nfeatures=175)
        self.flann = cv.FlannBasedMatcher(dict(algorithm=6, table_number=6, key_size=9, multi_probe_level=1), 
                                          dict(checks=2))
        self.executor = ThreadPoolExecutor(max_workers=25)
        self.cache = {}
        self.output_folder = output_folder
        os.makedirs(self.output_folder, exist_ok=True)  # Create output folder if it doesn't exist
        self.dataset_file = dataset_file  # Change to use .npy
        asyncio.run(self.load_dataset(dataset_folder))

    async def load_dataset(self, dataset_folder):
        if os.path.exists(self.dataset_file):
            await self.load_from_npy(self.dataset_file)
        else:
            await self.load_from_images(dataset_folder)

    async def load_from_npy(self, dataset_file):
        data = np.load(dataset_file, allow_pickle=True).item()  # Load the .npy file
        for filename, (descriptors, bounding_box) in data.items():
            self.cache[filename] = (descriptors, bounding_box)

    async def load_from_images(self, dataset_folder):
        tasks = []
        for filename in os.listdir(dataset_folder):
            path = os.path.join(dataset_folder, filename)
            if os.path.isfile(path):
                tasks.append(self.process_image(path, filename))

        await asyncio.gather(*tasks)

        # Save the cache as .npy after processing
        np.save(self.dataset_file, self.cache)

    async def process_image(self, path, filename):
        # Use ThreadPoolExecutor to process images concurrently
        loop = asyncio.get_event_loop()
        img = await loop.run_in_executor(self.executor, cv.imread, path)
        
        if img is not None:
            keypoints, descriptors = await loop.run_in_executor(self.executor, self.orb.detectAndCompute, 
                                                               cv.cvtColor(img, cv.COLOR_BGR2GRAY), None)
            if descriptors is not None:
                bounding_box = await loop.run_in_executor(self.executor, self.calculate_bounding_box, keypoints)
                self.cache[filename] = (descriptors.astype(np.uint8), bounding_box)

                await self.cache_flipped_image(img, filename, bounding_box)

    async def cache_flipped_image(self, img, filename, bounding_box):
        # Use ThreadPoolExecutor for flipping and processing the image
        loop = asyncio.get_event_loop()
        flipped_img = await loop.run_in_executor(self.executor, cv.flip, img, 1)
        keypoints, descriptors = await loop.run_in_executor(self.executor, self.orb.detectAndCompute,
                                                           cv.cvtColor(flipped_img, cv.COLOR_BGR2GRAY), None)
        if descriptors is not None:
            flipped_filename = filename.replace(".png", "_flipped.png")
            self.cache[flipped_filename] = (descriptors.astype(np.uint8), bounding_box)

    def calculate_bounding_box(self, keypoints):
        points = np.array([kp.pt for kp in keypoints], dtype=np.int32)
        return cv.boundingRect(points)

    async def match(self, img, desB):
        def compute_matches(filename, desA, bounding_box):
            # Use a more robust feature matching algorithm (e.g., SIFT, SURF)
            matcher = cv.BFMatcher(cv.NORM_L2, crossCheck=True)
            matches = matcher.match(desA, desB)

            # Sort matches by distance
            matches = sorted(matches, key=lambda x: x.distance)

            # Select best matches based on a threshold
            num_matches = int(0.75 * len(matches))
            best_matches = matches[:num_matches]

            if len(best_matches) > 5:
                accuracy = len(best_matches) / len(desB) * 100
                return (filename, accuracy, bounding_box)
            return None

        futures = [self.executor.submit(compute_matches, filename, desA, bounding_box) 
                   for filename, (desA, bounding_box) in self.cache.items()]
        results = [future.result() for future in futures if future.result()]
        return max(results, key=lambda x: x[1], default=(None, 0, None))

    async def predict_pokemon(self, img):
        start_time = time.time()  # Start the timer for elapsed time
        gray_img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        kpB, desB = self.orb.detectAndCompute(gray_img, None)
        best_match = await self.match(img, desB)  # Await the async match function

        if best_match[0]:  # If there's a match
            predicted_pokemon, accuracy, bounding_box = best_match
            predicted_name = predicted_pokemon.split("_flipped")[0].replace(".png", "")
            
            # Remove background by isolating the Pokémon
            if bounding_box:
                mask = np.zeros_like(img)  # Create a mask of the same size as the input image
                cv.rectangle(mask, (bounding_box[0], bounding_box[1]),
                             (bounding_box[0] + bounding_box[2], bounding_box[1] + bounding_box[3]),
                             (255, 255, 255), -1)  # Fill the rectangle with white
                
                # Isolate the Pokémon
                isolated_pokemon = cv.bitwise_and(img, mask)

                # Optionally, convert isolated_pokemon to have an alpha channel for transparency
                b_channel, g_channel, r_channel = cv.split(isolated_pokemon)
                alpha_channel = np.ones(b_channel.shape, dtype=b_channel.dtype) * 255  # Create an alpha channel
                isolated_pokemon_rgba = cv.merge((b_channel, g_channel, r_channel, alpha_channel))

                # Save output image with isolated Pokémon
                output_image_path = os.path.join(self.output_folder, f"{predicted_name.title()}_result.png")
                cv.imwrite(output_image_path, isolated_pokemon_rgba)  # Save the isolated image

                plt.imshow(cv.cvtColor(isolated_pokemon_rgba, cv.COLOR_BGRA2RGBA))
                plt.title(f"Prediction: {predicted_name.title()} ({accuracy:.2f}%)")
                plt.axis('off')
                plt.show()

                elapsed_time = time.time() - start_time  # Calculate elapsed time
                return f"{predicted_name.title()}: {round(accuracy, 2)}%", isolated_pokemon_rgba, elapsed_time  # Return the modified image and elapsed time

    def load_image_from_url(self, url):
        try:
            img = np.asarray(bytearray(requests.get(url).content), dtype=np.uint8)
            return cv.imdecode(img, cv.IMREAD_COLOR)
        except requests.RequestException as e:
            print(f"Error fetching image from URL: {e}")
            return None

if __name__ == "__main__":
    predictor = PokemonPredictor()

    while True:
        image_url = input("Enter the URL of the image to scan, type 'quit' to exit: ")
        if image_url.lower() == 'quit':
            break
        img = predictor.load_image_from_url(image_url)
        if img is not None:
            prediction, result_img, elapsed_time = asyncio.run(predictor.predict_pokemon(img))
            print(prediction)
            print(f"Elapsed Time: {elapsed_time:.2f} seconds")
