import onnxruntime as ort
import numpy as np
import requests
from PIL import Image
import io, os, json

ONNX_PATH = os.path.join("data/events/poketwo_spawns/model/pokemon_cnn_v2.onnx")
LABELS_PATH = os.path.join("data/events/poketwo_spawns/model/labels_v2.json")
SAVE_PATH = os.path.join("data/commands/pokemon/pokemon_images")

class Prediction:
    def __init__(self, onnx_path=ONNX_PATH, labels_path=LABELS_PATH, save_path=SAVE_PATH):
        self.onnx_path, self.labels_path, self.save_path = onnx_path, labels_path, save_path
        self.class_names = self.load_class_names()
        sess_opts = ort.SessionOptions()
        sess_opts.intra_op_num_threads = 1
        sess_opts.inter_op_num_threads = 1
        available = ort.get_available_providers()
        preferred = ["CPUExecutionProvider"]
        providers = [p for p in preferred if p in available]
        if not providers:
            raise ValueError("No suitable ONNX providers available")
        self.ort_session = ort.InferenceSession(self.onnx_path, sess_options=sess_opts, providers=providers)

    def generate_labels_file_from_save_path(self):
        if not os.path.exists(self.save_path): 
            raise FileNotFoundError(f"SAVE_PATH not found: {self.save_path}")
        class_names = sorted([d for d in os.listdir(self.save_path) if os.path.isdir(os.path.join(self.save_path, d))])
        os.makedirs(os.path.dirname(self.labels_path), exist_ok=True)
        with open(self.labels_path, "w", encoding="utf-8") as f: 
            json.dump(class_names, f, indent=2)
        return class_names

    def load_class_names(self):
        if not os.path.exists(self.labels_path): 
            return self.generate_labels_file_from_save_path()
        with open(self.labels_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict): 
                return [data[k] for k in sorted(data, key=lambda x: int(x))]
            if isinstance(data, list): 
                return data
            raise ValueError("labels_v2.json must be a list or dict")

    def preprocess_image_from_url(self, url):
        with requests.get(url, stream=True, timeout=5) as r:
            r.raise_for_status()
            arr = np.frombuffer(r.raw.read(), np.uint8)
        image = Image.open(io.BytesIO(arr)).convert("RGB").resize((224, 224), Image.Resampling.BILINEAR)
        img = np.asarray(image, dtype=np.float32) / 255.0
        img -= [0.485, 0.456, 0.406]
        img /= [0.229, 0.224, 0.225]
        return np.expand_dims(np.transpose(img, (2, 0, 1)), 0)

    def predict(self, url):
        image = self.preprocess_image_from_url(url)
        inputs = {self.ort_session.get_inputs()[0].name: image}
        logits = self.ort_session.run(None, inputs)[0][0]
        idx = int(np.argmax(logits))
        prob = float(np.max(np.exp(logits - np.max(logits)) / np.exp(logits - np.max(logits)).sum()))
        name = self.class_names[idx] if idx < len(self.class_names) else f"unknown_{idx}"
        return name, f"{prob*100:.2f}%"

def main():
    try: 
        predictor = Prediction()
    except Exception as e: 
        return print(f"Initialization error: {e}")
    while True:
        url = input("Enter Pokémon image URL (or 'q' to quit): ").strip()
        if url.lower() == "q": 
            break
        try: 
            print("Predicted Pokémon:", *predictor.predict(url))
        except Exception as e: 
            print("Error:", e)

if __name__ == "__main__": 
    main()
