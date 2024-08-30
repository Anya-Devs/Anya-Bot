import os
import cv2
import numpy as np
import pandas as pd
import base64
import concurrent.futures
import time
from pathlib import Path
import io


class PokemonPredictor:
    def __init__(self, predict_folder="predict", dataset_folder="dataset", csv_file="image_data.csv"):
        # Initialize ORB with a reasonable number of features
        self.orb = cv2.ORB_create(nfeatures=170)  # Increased number of features

        # Configure FLANN with parameters for faster matching
        index_params = dict(algorithm=6, table_number=6, key_size=10, multi_probe_level=1)
        search_params = dict(checks=50)  # Increased checks for better matching
        self.flann = cv2.FlannBasedMatcher(index_params, search_params)

        # Thread pool executor for parallel processing
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        self.csv_file = csv_file
        self.cache = {}
        if not os.path.exists(self.csv_file):
            self.load_dataset(dataset_folder)
        else:
            self._load_csv_data()

    def load_dataset(self, dataset_folder, batch_size=10):
        self._clear_console()
        print("Loading Images...")
        start_time = time.time()

        image_paths = [entry.path for entry in os.scandir(dataset_folder) if entry.is_file()]

        total_images = len(image_paths)
        for i in range(0, total_images, batch_size):
            batch_paths = image_paths[i:i+batch_size]
            results = list(self.executor.map(self._process_image, batch_paths))

            rows = []
            for filename, result in zip(batch_paths, results):
                if result:
                    keypoints, descriptors = result
                    binary_image = self._convert_to_binary(filename)
                    encoded_image = self._encode_image(binary_image)

                    rows.append({
                        'filename': os.path.basename(filename),
                        'keypoints': self._encode_keypoints(keypoints),
                        'descriptors': self._encode_descriptors(descriptors),
                        'binary_image': encoded_image
                    })

                    # Process flipped image
                    flipped_img_path = self._flip_image(filename)
                    flipped_result = self._process_image(flipped_img_path)
                    if flipped_result is not None:
                        flipped_keypoints, flipped_descriptors = flipped_result
                        if flipped_keypoints is not None and flipped_descriptors is not None:
                            flipped_binary_image = self._convert_to_binary(flipped_img_path)
                            encoded_flipped_image = self._encode_image(flipped_binary_image)

                            rows.append({
                                'filename': os.path.basename(flipped_img_path),
                                'keypoints': self._encode_keypoints(flipped_keypoints),
                                'descriptors': self._encode_descriptors(flipped_descriptors),
                                'binary_image': encoded_flipped_image
                            })

            df = pd.DataFrame(rows)
            df.to_csv(self.csv_file, mode='a', header=not os.path.exists(self.csv_file), index=False)

            print(f"Processed batch {i//batch_size + 1} of {total_images//batch_size + 1}")

        self._clear_console()
        elapsed_time = round(time.time() - start_time, 2)
        print(f"Successfully loaded all images.\nTime Taken: {elapsed_time} sec")
    def _convert_to_binary(self, image_path):
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            _, binary_image = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary_image
        return None

    def _encode_image(self, image):
        _, buffer = cv2.imencode('.png', image)
        return base64.b64encode(buffer).decode('utf-8')

    def _encode_keypoints(self, keypoints):
        return ';'.join([f"{kp.pt[0]},{kp.pt[1]},{kp.size},{kp.angle},{kp.response},{kp.octave},{kp.class_id}" for kp in keypoints])

    def _encode_descriptors(self, descriptors):
        return base64.b64encode(descriptors).decode('utf-8')

    def _process_image(self, image_path):
        try:
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            img = cv2.GaussianBlur(img, (3, 3), 0)  # Slightly larger blur

            if img is not None:
                keypoints, descriptors = self.orb.detectAndCompute(img, None)
                return keypoints, descriptors
        except Exception as e:
            print(f"Error processing image {image_path}: {e}")
        return None

    def _decode_keypoints(self, keypoints_str):
        keypoints = []
        for kp_str in keypoints_str.split(';'):
            if kp_str:
                try:
                    x, y, size, angle, response, octave, class_id = map(float, kp_str.split(','))
                    keypoints.append(cv2.KeyPoint(x, y, size, angle, response, int(octave), int(class_id)))
                except ValueError as e:
                    print(f"Error decoding keypoint: {e}")
        return keypoints

    def _decode_descriptors(self, descriptors_str):
        descriptors = base64.b64decode(descriptors_str)
        return np.frombuffer(descriptors, dtype=np.uint8).reshape(-1, 32)

    def _load_csv_data(self):
        df = pd.read_csv(self.csv_file)
        for _, row in df.iterrows():
            filename = row['filename']
            keypoints = self._decode_keypoints(row['keypoints'])
            descriptors = self._decode_descriptors(row['descriptors'])
            binary_image = base64.b64decode(row['binary_image'])
            binary_image = cv2.imdecode(np.frombuffer(binary_image, np.uint8), cv2.IMREAD_GRAYSCALE)

            self.cache[filename] = (keypoints, descriptors, binary_image)

    def _match_image(self, kpB, desB, cache_item):
        filename, (kpA, desA, binA) = cache_item
        if desA is not None and desB is not None:
            # ORB feature matching
            matches = self.flann.knnMatch(desA, desB, k=2)
            good_matches = [m[0] for m in matches if len(m) == 2 and m[0].distance < 0.7 * m[1].distance]


            if len(good_matches) > 4:
                src_pts = np.float32([kpA[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kpB[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

                M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)  # Adjust RANSAC threshold

                if M is not None:
                    h, w = 50, 50  # Example dimensions, adjust based on your dataset
                    pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
                    dst = cv2.perspectiveTransform(pts, M)

                    if self._is_valid_match(dst):
                        accuracy = len(good_matches) / len(desA) * 100
                        return filename, len(good_matches), accuracy
        return None

    def _is_valid_match(self, dst):
        # Check if the found polygon is convex and large enough to be considered a valid match
        return cv2.isContourConvex(dst) and cv2.contourArea(dst) > 100

    def _flip_image(self, image_path):
        img = cv2.imread(image_path)
        if img is not None:
            flipped_img = cv2.flip(img, 1)  # Flip horizontally
            flipped_img_path = image_path.replace(".jpg", "_flipped.jpg")
            cv2.imwrite(flipped_img_path, flipped_img)
            return flipped_img_path
        return image_path

    def predict_pokemon(self, img):
        start_time = time.time()
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        kpB, desB = self.orb.detectAndCompute(gray_img, None)

        if not self.cache:
            self._load_csv_data()

        futures = [self.executor.submit(self._match_image, kpB, desB, item) for item in self.cache.items()]
        best_match = max((future.result() for future in concurrent.futures.as_completed(futures)), key=lambda x: x[1] if x else 0, default=None)

        elapsed_time = round(time.time() - start_time, 2)
        if best_match:
            predicted_pokemon = best_match[0].split(".png")[0].split("_flipped")[0]
            accuracy = round(best_match[2], 2)
            return (f"{predicted_pokemon}", elapsed_time)

        return "No Pokémon detected", elapsed_time

    def _clear_console(self):
        os.system("cls" if os.name == "nt" else "clear")
