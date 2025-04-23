import os, base64, asyncio, requests, concurrent
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import cv2 as cv
import numpy as np
import aiohttp
from PIL import Image, ImageSequence
from tqdm import tqdm


class Processor:
    def __init__(self, face_model, body_model):
        self.face_net = cv.dnn.readNetFromCaffe(*face_model)
        self.body_net = cv.dnn.readNetFromDarknet(*body_model)
        self.output_dir = "Data/commands/ai/images"
        os.makedirs(self.output_dir, exist_ok=True)

    async def process_media(self, media_url):
        try:
            media_type = await asyncio.to_thread(self.detect_media_type, media_url)
            print(f"Detected media type: {media_type}")

            output_filename = f"{self.output_dir}/temp.{media_type if media_type != 'image' else 'jpg'}"
            await self.download_media(media_url, output_filename)

            if media_type == 'image':
                return await self.process_image(output_filename)
            elif media_type == 'gif':
                return await self.load_and_process_gif(output_filename)

        except Exception as e:
            print(f"Error processing media: {e}")

    async def download_media(self, media_url, output_filename):
        response = await asyncio.to_thread(requests.get, media_url, stream=True)
        if response.status_code == 200:
            with open(output_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Media downloaded: {output_filename}")
        else:
            raise ValueError(f"Error downloading media: {media_url}")

    async def load_and_process_gif(self, gif_path):
        gif = Image.open(gif_path)
        frames = []
        durations = []

        try:
            while True:
                frame = gif.convert("RGB")
                frame_np = np.array(frame)
                if frame_np is None or frame_np.size == 0:
                    continue
                frame_bgr = cv.cvtColor(frame_np, cv.COLOR_RGB2BGR)
                frames.append(frame_bgr)
                durations.append(gif.info.get('duration', 100))
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass

        return await self.process_gif(frames, durations)

    async def process_gif(self, frames, durations):
        processed_frames = []
        for frame in tqdm(frames, desc="Drawing on frames", unit="frame"):
            processed_frame = await asyncio.to_thread(self.process_frame, frame)
            processed_frames.append(processed_frame)
        await self.save_gif_with_detections(processed_frames, durations)
        return processed_frames, durations

    async def save_gif_with_detections(self, frames, durations):
        processed_frames = []
        for frame in tqdm(frames, desc="Saving frames", unit="frame"):
            rgb_frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            pil_frame = Image.fromarray(rgb_frame).convert("P", palette=Image.ADAPTIVE, dither=Image.NONE)
            processed_frames.append(pil_frame)

        output_gif = f"{self.output_dir}/processed_media.gif"
        processed_frames[0].save(
            output_gif,
            save_all=True,
            append_images=processed_frames[1:],
            loop=0,
            duration=durations,
            optimize=False
        )

    async def process_image(self, image_path):
        img_np = cv.imread(image_path)
        if img_np is None:
            raise ValueError(f"Failed to load image: {image_path}")
        return self.process_frame(img_np)

    def process_frame(self, img_np):
        try:
            if img_np is None or img_np.size == 0:
                return img_np

            if len(img_np.shape) == 2:  # Grayscale
                img_np = cv.cvtColor(img_np, cv.COLOR_GRAY2BGR)

            img_h, img_w = img_np.shape[:2]

            face_blob = cv.dnn.blobFromImage(img_np, 1.0, (300, 300), (104.0, 177.0, 123.0), swapRB=True, crop=False)
            body_blob = cv.dnn.blobFromImage(img_np, 1.0 / 255.0, (416, 416), (0, 0, 0), swapRB=True, crop=False)

            with concurrent.futures.ThreadPoolExecutor() as executor:
                executor.submit(self.face_net.setInput, face_blob).result()
                executor.submit(self.body_net.setInput, body_blob).result()
                face_detections = self.face_net.forward()
                body_detections = self.body_net.forward()

            if face_detections is None or face_detections.shape[2] == 0:
                face_detections = np.array([])

            highest_confidence = 0
            best_face_coords = None
            if face_detections.size > 0:
                for i in range(face_detections.shape[2]):
                    confidence = face_detections[0, 0, i, 2]
                    if confidence > 0.15 and confidence > highest_confidence:
                        highest_confidence = confidence
                        x1 = int(face_detections[0, 0, i, 3] * img_w)
                        y1 = int(face_detections[0, 0, i, 4] * img_h)
                        x2 = int(face_detections[0, 0, i, 5] * img_w)
                        y2 = int(face_detections[0, 0, i, 6] * img_h)
                        best_face_coords = (x1, y1, x2, y2)

            if best_face_coords:
                x1, y1, x2, y2 = best_face_coords
                cv.rectangle(img_np, (x1, y1), (x2, y2), (200, 0, 0), 2)
                cv.putText(img_np, f'Face: {highest_confidence:.2f}', (x1, y1 - 10),
                           cv.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            detected_bodies = []
            if body_detections is not None and body_detections.size > 0:
                for detection in body_detections:
                    confidence = detection[4]
                    if confidence >= 0.15:
                        center_x = int(detection[0] * img_w)
                        center_y = int(detection[1] * img_h)
                        width = int(detection[2] * img_w)
                        height = int(detection[3] * img_h)
                        x1, y1 = max(0, center_x - width // 2), max(0, center_y - height // 2)
                        x2, y2 = min(img_w, center_x + width // 2), min(img_h, center_y + height // 2)
                        if height / width >= 1.2:
                            detected_bodies.append((x1, y1, x2, y2))

            nms_indices = cv.dnn.NMSBoxes([box for box in detected_bodies], [1] * len(detected_bodies), 0.5, 0.4)
            if len(nms_indices) > 0:
                for i in nms_indices.flatten():
                    x1, y1, x2, y2 = detected_bodies[i]
                    cv.rectangle(img_np, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv.putText(img_np, 'Body', (x1, y1 - 10), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

            self.save_faces_to_file()
            return img_np

        except cv.error as e:
            print(f"OpenCV error in process_frame: {e}")
        except Exception as e:
            print(f"Unexpected error in process_frame: {e}")
        return img_np

    def save_faces_to_file(self):
        pass 
    
    def detect_media_type(self, media_url):
        if any(media_url.lower().endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
            return 'image'
        elif media_url.lower().endswith('.gif'):
            return 'gif'
        elif media_url.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            return 'video'
        return 'unknown'
class ImageGenerator:
    def __init__(self):
        """Initialize the image generator with API settings."""
        self.output_dir = Path("Data/commands/ai/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        #print("Using Stable Diffusion API via aiohttp...")
        self.API_URL  = os.getenv("Stable_Diffusion_API_URL")

    async def generate_image_sync(self, prompt: str, width: int = 1216, height: int = 768) -> Path:
        negative_prompt = "(bad-artist:1.5), watermark, text, error, blurry, jpeg artifacts, cropped, signature, username, artist name, (bad score:1.5), (bad quality:1.5), lowres, noisy, distorted, poorly drawn, out of focus, (uncanny:1.5), (robotic appearance:1.5), (unnatural pose:1.5), stiff posture, (incorrect anatomy:1.5), (bad hands:1.3), malformed hands, (incorrect head placement:1.5), uneven features, (bad clothing:1.5), wrinkled clothing, ill-fitting clothes, (unfinished details:1.5), (bad lighting), logo, artist logo, extra limbs, extra digit, extra legs, extra arms, disfigured, missing arms, extra fingers, fused fingers, missing fingers, unclear eyes, blur, (abstract background:1.5), (messy background:1.5), (unrealistic background:1.5), (chaotic background:1.5), (blurry background:1.5), (low quality background:1.5), (distracting background:1.5), (bad limbs:1.5), (disproportionate limbs:1.5), (unnatural limb position:1.5), (wrong limb count:1.5), (malformed limbs:1.5), (missing limbs:1.5), (incorrect limb anatomy:1.5), (unattractive)"
        payload = {
        "prompt": f"{prompt}, masterpiece, (best quality), (high resolution), (8K), absurdres, amazing image, perfect skin, (best clothing), (expressive personality)",
        "negative_prompt": negative_prompt,
        "steps": 50,  
        "cfg_scale": 7,  
        "width": width,
        "height": height,
        "seed": -1,  
        "style_preset": "Anim4gine", 
        "sampler_name": "DPM++ 2M Karras",
        "override_settings": {
         "sd_model_checkpoint": "animagine-xl-4.0",
           }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.API_URL, json=payload) as response:
                    if response.status == 200:
                        r = await response.json()
                        image_data = base64.b64decode(r['images'][0])
                        output_path = self.output_dir / f"generated_image_{width}x{height}.png"
                        with open(output_path, 'wb') as f:
                            f.write(image_data)

                        print(f"✅ Image successfully generated and saved as '{output_path}'")
                        return output_path
                    else:
                        print(f"❌ Error: {response.status}, {await response.text()}")
                        return None
        except aiohttp.ClientError as e:
            print(f"❌ Request failed: {str(e)}")
            return None







