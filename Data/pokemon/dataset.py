import sqlite3
import pickle
import cv2
import os
import time
import concurrent.futures
import os
import time
import cv2
import pickle
import concurrent.futures
import sqlite3


import sqlite3
import cv2
import pickle
import os
import time
import concurrent.futures


class Dataset:
    def __init__(
        self,
        db_file="Data/pokemon/pokemon_images.db",
        processed_file="Data/pokemon/processed_pokemon_images.db",
        batch_size=5,
        image_folder="Data/pokemon/pokemon_images",
    ):
        self.db_file = db_file
        self.processed_file = processed_file
        self.batch_size = batch_size
        self.image_folder = image_folder
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.orb = cv2.ORB_create(nfeatures=170)
        index_params = dict(
            algorithm=6, table_number=6, key_size=12, multi_probe_level=10, tree=6
        )
        search_params = dict(checks=2)
        self.flann = cv2.FlannBasedMatcher(index_params, search_params)
        self.cache = {}

        # Initialize the database
        if not os.path.exists(self.db_file):
            print(f"Initializing database at {self.db_file}...")
            self._init_db()
        else:
            print("Database file found. Loading existing data in batches...")
            self.load_from_existing_db_in_batches()

        if not os.path.exists(self.processed_file):
            print(
                f"Initializing processed entries database at {self.processed_file}..."
            )
            self._init_processed_db()

    def _db_connect(self, db_name):
        return sqlite3.connect(db_name)

    def _init_db(self):
        conn = self._db_connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE,
                flipped_filename TEXT UNIQUE,
                keypoints BLOB,
                descriptors BLOB,
                flipped_keypoints BLOB,
                flipped_descriptors BLOB
            )
        """
        )
        conn.commit()
        conn.close()

    def _init_processed_db(self):
        conn = self._db_connect(self.processed_file)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed (
                filename TEXT PRIMARY KEY
            )
        """
        )
        conn.commit()
        conn.close()

    def load_dataset(self, dataset_folder=None):
        if dataset_folder is None:
            dataset_folder = self.image_folder

        self._clear_console()
        print(f"Loading Images from {dataset_folder}...")
        start_time = time.time()
        image_paths = [
            entry.path for entry in os.scandir(dataset_folder) if entry.is_file()
        ]
        total_images = len(image_paths)

        if total_images == 0:
            print(f"No images found in {dataset_folder}.")
            return

        conn = self._db_connect(self.db_file)
        cursor = conn.cursor()

        for i in range(0, total_images, self.batch_size):
            batch_paths = image_paths[i: i + self.batch_size]
            results = list(self.executor.map(self._process_image, batch_paths))
            for filename, result in zip(batch_paths, results):
                if result:
                    keypoints, descriptors = result
                    flipped_img = cv2.flip(cv2.imread(filename), 1)
                    flipped_gray_img = cv2.cvtColor(
                        flipped_img, cv2.COLOR_BGR2GRAY)
                    flipped_keypoints, flipped_descriptors = self.orb.detectAndCompute(
                        flipped_gray_img, None
                    )
                    flipped_filename = f"{os.path.basename(filename)}_flipped"

                    # Serialize keypoints
                    keypoints_serialized = pickle.dumps(
                        self.serialize_keypoints(keypoints)
                    )
                    descriptors_serialized = pickle.dumps(descriptors)
                    flipped_keypoints_serialized = pickle.dumps(
                        self.serialize_keypoints(flipped_keypoints)
                    )
                    flipped_descriptors_serialized = pickle.dumps(
                        flipped_descriptors)

                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO images (filename, flipped_filename, keypoints, descriptors, flipped_keypoints, flipped_descriptors)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            os.path.basename(filename),
                            flipped_filename,
                            keypoints_serialized,
                            descriptors_serialized,
                            flipped_keypoints_serialized,
                            flipped_descriptors_serialized,
                        ),
                    )

            conn.commit()
            print(
                f"Processed batch {i//self.batch_size + 1} of {total_images//self.batch_size + 1}"
            )

        conn.close()
        self._clear_console()
        elapsed_time = round(time.time() - start_time, 2)
        print(
            f"Successfully loaded all images.\nTime Taken: {elapsed_time} sec")

    def load_from_existing_db_in_batches(self):
        """Load data from the existing database in batches and track processed entries."""
        conn = self._db_connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM images")
        total_records = cursor.fetchone()[0]

        print(f"Total records in database: {total_records}")

        # Open processed entries database
        processed_conn = self._db_connect(self.processed_file)
        processed_cursor = processed_conn.cursor()

        # Check if the table exists
        try:
            processed_cursor.execute("SELECT filename FROM processed")
            processed_entries = {row[0] for row in processed_cursor.fetchall()}
        except sqlite3.OperationalError as e:
            print(f"Error querying processed table: {e}")
            processed_entries = set()

        start_time = time.time()
        for i in range(0, total_records, self.batch_size):
            cursor.execute(
                """
                SELECT filename, keypoints, descriptors, flipped_keypoints, flipped_descriptors 
                FROM images 
                LIMIT ? OFFSET ?
            """,
                (self.batch_size, i),
            )
            items = cursor.fetchall()

            for item in items:
                filename = item[0]
                if filename not in processed_entries:
                    self.cache[filename] = (
                        pickle.loads(item[1]),
                        pickle.loads(item[2]),
                        pickle.loads(item[3]),
                        pickle.loads(item[4]),
                    )
                    # Mark as processed
                    processed_cursor.execute(
                        "INSERT OR IGNORE INTO processed (filename) VALUES (?)",
                        (filename,),
                    )

            processed_conn.commit()
            print(
                f"Loaded batch {i//self.batch_size + 1} of {total_records//self.batch_size + 1}"
            )

        conn.close()
        processed_conn.close()
        elapsed_time = round(time.time() - start_time, 2)
        print(
            f"Successfully loaded data from database.\nTime Taken: {elapsed_time} sec"
        )

    def _process_image(self, image_path):
        try:
            img = cv2.imread(image_path)
            if img is not None:
                gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                keypoints, descriptors = self.orb.detectAndCompute(
                    gray_img, None)
                return keypoints, descriptors
        except Exception as e:
            print(f"Error processing image {image_path}: {e}")
        return None

    def serialize_keypoints(self, keypoints):
        """Convert cv2.KeyPoint objects to a serializable format."""
        return [
            {
                "pt": kp.pt,
                "size": kp.size,
                "angle": kp.angle,
                "response": kp.response,
                "octave": kp.octave,
                "class_id": kp.class_id,
            }
            for kp in keypoints
        ]

    def deserialize_keypoints(self, serialized_keypoints):
        """Convert serialized keypoints back to cv2.KeyPoint objects."""
        return [
            cv2.KeyPoint(
                kp["pt"][0],
                kp["pt"][1],
                kp["size"],
                kp["angle"],
                kp["response"],
                kp["octave"],
                kp["class_id"],
            )
            for kp in serialized_keypoints
        ]

    def _clear_console(self):
        os.system("cls" if os.name == "nt" else "clear")

    def _get_cache_items(self):
        if not self.cache:
            conn = self._db_connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT filename, keypoints, descriptors, flipped_keypoints, flipped_descriptors FROM images"
            )
            items = cursor.fetchall()
            conn.close()
            self.cache = {
                item[0]: (
                    pickle.loads(item[1]),
                    pickle.loads(item[2]),
                    pickle.loads(item[3]),
                    pickle.loads(item[4]),
                )
                for item in items
            }
        return self.cache.items()
