import os
import time
import cv2 as cv
import csv
import json
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import requests

class PokemonPredictor:
    def __init__(self, dataset_folder="dataset", csv_file="dataset.csv"):
        self.orb = cv.ORB_create(nfeatures=175)
        self.flann = cv.FlannBasedMatcher(dict(algorithm=6, table_number=6, key_size=9, multi_probe_level=1),
                                           dict(checks=1))
        self.executor = ThreadPoolExecutor(max_workers=25)
        self.cache = {}
        self.csv_file = csv_file
        self.dataset_folder = dataset_folder

        # Load dataset only once when code starts
        self.load_dataset()

    def load_dataset(self):
        print("Loading Images...")

        # Load from the saved matches folder
        saved_matches_folder = "saved_matches"
        if os.path.exists(saved_matches_folder):
            print("Loading saved matches from directory...")
            self.load_from_saved_matches(saved_matches_folder)

        if os.path.exists(self.csv_file):
            print("Loading dataset from CSV file...")
            self.load_from_csv()
        else:
            print("CSV file not found, loading images from dataset folder...")
            self.load_from_images()

    def load_from_saved_matches(self, saved_matches_folder):
        for filename in os.listdir(saved_matches_folder):
            path = os.path.join(saved_matches_folder, filename)
            if os.path.isfile(path):
                img = cv.imread(path)
                if img is not None:
                    gray_img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
                    keypoints, descriptors = self.orb.detectAndCompute(gray_img, None)
                    if descriptors is not None:
                        new_filename = filename.replace(".png", "_saved.png")
                        self.cache[new_filename] = (keypoints, descriptors)

    def load_from_csv(self):
        start_time = time.time()
        with open(self.csv_file, 'r') as file:
            reader = csv.reader(file)
            next(reader)
            for row in reader:
                filename, descriptors_str = row
                descriptors = np.array(json.loads(descriptors_str), dtype=np.uint8)
                self.cache[filename] = (None, descriptors)
        print(f"Dataset loaded from CSV in {time.time() - start_time:.2f} seconds")

    def load_from_images(self):
        start_time = time.time()
        with open(self.csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Filename', 'Descriptors'])

        for filename in os.listdir(self.dataset_folder):
            path = os.path.join(self.dataset_folder, filename.replace('_flipped', ''))
            if os.path.isfile(path):
                img = cv.imread(path)
                if img is not None:
                    gray_img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
                    keypoints, descriptors = self.orb.detectAndCompute(gray_img, None)
                    if descriptors is not None:
                        self.cache[filename] = (keypoints, descriptors)
                        with open(self.csv_file, 'a', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow([filename, descriptors.tolist()])

                        flipped_img = cv.flip(img, 1)
                        gray_flipped = cv.cvtColor(flipped_img, cv.COLOR_BGR2GRAY)
                        keypoints_flipped, descriptors_flipped = self.orb.detectAndCompute(gray_flipped, None)
                        if descriptors_flipped is not None:
                            flipped_filename = filename.replace(".png", "_flipped.png")
                            self.cache[flipped_filename] = (keypoints_flipped, descriptors_flipped)
                            with open(self.csv_file, 'a', newline='') as file:
                                writer = csv.writer(file)
                                writer.writerow([flipped_filename, descriptors_flipped.tolist()])

        print(f"Images loaded in {time.time() - start_time:.2f} seconds")

    def _match_image(self, kpB, desB, cache_item):
        filename, (kpA, desA) = cache_item
        if desA is not None and desB is not None and len(desA) > 2 and len(desB) > 2:
            try:
                desA = desA.astype(np.uint8)
                desB = desB.astype(np.uint8)

                matches = self.flann.knnMatch(desA, desB, k=2)
                good_matches = [m[0] for m in matches if len(m) == 2 and m[0].distance < 0.50 * m[1].distance]

                if len(good_matches) > 1:
                    accuracy = len(good_matches) / len(desA) * 100
                    return filename, accuracy
            except cv.error as e:
                print(f"Error in feature matching: {e}")
        return filename, 0

    def load_image_from_url(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            image = np.asarray(bytearray(response.content), dtype=np.uint8)
            img = cv.imdecode(image, cv.IMREAD_COLOR)
            return img
        except requests.RequestException as e:
            print(f"Error fetching image from URL: {e}")
            return None

    def predict_pokemon(self, img):
        best_match = None
        start_time = time.time()
        gray_img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        kpB, desB = self.orb.detectAndCompute(gray_img, None)

        if desB is not None:
            desB = desB.astype(np.uint8)

        if best_match is None:
            futures = [self.executor.submit(self._match_image, kpB, desB, item) for item in self.cache.items()]
            results = [future.result() for future in futures]
            best_match = max(results, key=lambda x: x[1] if x else 0, default=None)

        elapsed_time = round(time.time() - start_time, 2)

        if best_match:
            pokemon_img_path = os.path.join(self.dataset_folder, best_match[0])
            target_img = cv.imread(pokemon_img_path.replace('_flipped', ''))

            if target_img is not None:
                # Save the input image with the predicted Pokémon's name in the saved_matches folder
                output_dir = "saved_matches"
                os.makedirs(output_dir, exist_ok=True)
                predicted_pokemon = best_match[0].split("_flipped")[0].replace(".png", "")
                saved_image_path = os.path.join("saved_matches", f"{predicted_pokemon}_saved.png")
                cv.imwrite(saved_image_path, img)  # Save the input image here
                print(f"Saved input image to {saved_image_path}")

            else:
                print(f"Warning: Could not load image for {pokemon_img_path}")

            predicted_pokemon = best_match[0].split("_flipped")[0].replace(".png", "")
            accuracy = round(best_match[1], 2)
            return f"{predicted_pokemon.title()}: {accuracy}%", elapsed_time
        
        return "No Pokémon detected", elapsed_time

    def rename_saved_images(self):
        saved_matches_folder = "saved_matches"
        if not os.path.exists(saved_matches_folder):
            print("Saved matches folder does not exist.")
            return

        # List files in the saved_matches folder
        files = [f for f in os.listdir(saved_matches_folder) if f.endswith("_saved.png")]
        page_size = 5
        current_page = 0

        while True:
            # Calculate total pages
            total_pages = (len(files) + page_size - 1) // page_size
            start_index = current_page * page_size
            end_index = min(start_index + page_size, len(files))
            
            # Display current page of files
            print("\nSaved Pokémon Images (Page {} of {}):".format(current_page + 1, total_pages))
            for i in range(start_index, end_index):
                print(f"{i + 1}: {files[i]}")

            # Option to rename a file
            choice = input("\nEnter the number of the image to rename, 'next' for next page, 'prev' for previous page, or 'quit' to exit: ")
            if choice.lower() == 'quit':
                break
            elif choice.lower() == 'next':
                if current_page < total_pages - 1:
                    current_page += 1
                else:
                    print("You are already on the last page.")
            elif choice.lower() == 'prev':
                if current_page > 0:
                    current_page -= 1
                else:
                    print("You are already on the first page.")
            else:
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(files):
                        old_filename = files[index]
                        new_name = input("Enter the new Pokémon name (without _saved.png): ")
                        new_filename = f"{new_name}_saved.png"
                        new_path = os.path.join(saved_matches_folder, new_filename)

                        # Check if the new filename already exists
                        if not os.path.exists(new_path):
                            os.rename(os.path.join(saved_matches_folder, old_filename), new_path)
                            print(f"Renamed {old_filename} to {new_filename}")
                        else:
                            print(f"{new_filename} already exists. Please choose a different name.")
                    else:
                        print("Invalid number. Please try again.")
                except ValueError:
                    print("Please enter a valid number.")

# Example usage:
if __name__ == "__main__":
    predictor = PokemonPredictor()

    while True:
        user_input = input("Enter the URL of the image to scan, type 'update' to rename saved images, or 'quit' to exit: ")
        
        if user_input.lower() == 'quit':
            break
        elif user_input.lower() == 'update':
            predictor.rename_saved_images()
        else:
            test_image = predictor.load_image_from_url(user_input)
            if test_image is not None:
                result, time_taken = predictor.predict_pokemon(test_image)
                print(result)
            else:
                print("Could not load image from the provided URL.")
