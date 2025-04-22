import os, asyncio, aiohttp, base64, hashlib
from pathlib import Path
from datetime import datetime
from io import BytesIO
from collections import deque
from tqdm import tqdm 

import pickle
import cv2 as cv
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor



import cv2, numpy as np, requests
from PIL import Image, ImageSequence
from openai import AsyncOpenAI
from detectron2 import model_zoo
from detectron2.config import get_cfg
from detectron2.engine import DefaultPredictor
from detectron2.utils.visualizer import Visualizer, ColorMode
from detectron2.data import MetadataCatalog


from Imports.discord_imports import *
from Imports.log_imports import logger
from Data.const import error_custom_embed, primary_color

import queue





"""
class Detect():
    def __init__(self):
        self.p, self.c = self._init_mdl()
        self.ex = ThreadPoolExecutor(max_workers=4)

    def _init_mdl(self):
        c = get_cfg()
        c.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_101_FPN_3x.yaml"))
        c.MODEL.WEIGHTS = model_zoo.get_checkpoint_url("COCO-InstanceSegmentation/mask_rcnn_R_101_FPN_3x.yaml")
        c.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.3
        c.MODEL.ROI_HEADS.NMS_THRESH = 0.2
        c.MODEL.DEVICE = "cpu"
        return DefaultPredictor(c), c

    def _dl(self, url):
        try:
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            return BytesIO(r.content)
        except requests.RequestException:
            return None

    def _is_gif(self, d):
        try:
            return Image.open(d).format == 'GIF'
        except:
            return False

    def _filter_instances(self, instances):
        pred_classes = instances.pred_classes.cpu().numpy()
        scores = instances.scores.cpu().numpy()
        valid_indices = []
        for i, (cls, score) in enumerate(zip(pred_classes, scores)):
            if cls == 10:
                continue
            if score < 0.3:
                continue
            valid_indices.append(i)
        return instances[valid_indices] if valid_indices else None

    def _proc_img(self, d):
        img = Image.open(d).convert('RGB')
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        out = self.p(img_cv)
        md = MetadataCatalog.get(self.c.DATASETS.TRAIN[0])
        instances = out["instances"].to("cpu")
        filtered = self._filter_instances(instances)
        if filtered is None or len(filtered) == 0:
            filtered = instances[:0]
        v = Visualizer(img_cv[:, :, ::-1], metadata=md, scale=1.2, instance_mode=ColorMode.IMAGE)
        out_v = v.draw_instance_predictions(filtered)
        res = Image.fromarray(out_v.get_image())
        path = os.path.join("Data/commands/ai/images", "detected_output.jpg")
        os.makedirs("Data/commands/ai/images", exist_ok=True)
        res.save(path)
        return path

    def _proc_gif(self, d):
        gif = Image.open(d)
        frames = [f.convert('RGB') for f in ImageSequence.Iterator(gif)]
        frm_cnt = len(frames)
        batch_size = 10
        all_frames = []
        for i in tqdm(range(0, frm_cnt, batch_size), desc="Processing GIF frames", total=(frm_cnt // batch_size)):
            batch = frames[i:i + batch_size]
            processed_batch = self._proc_batch(batch)
            all_frames.extend(processed_batch)
        duration = gif.info.get('duration', 100)
        loop = gif.info.get('loop', 0)
        out_path = os.path.join("Data/commands/ai/images", "detected_output.gif")
        os.makedirs("Data/commands/ai/images", exist_ok=True)
        all_frames[0].save(
            out_path,
            save_all=True,
            append_images=all_frames[1:],
            duration=duration,
            loop=loop
        )
        return out_path

    def _proc_batch(self, batch):
        res = []
        md = MetadataCatalog.get(self.c.DATASETS.TRAIN[0])
        for frm in batch:
            frm_cv = cv2.cvtColor(np.array(frm), cv2.COLOR_RGB2BGR)
            out = self.p(frm_cv)
            instances = out["instances"].to("cpu")
            filtered = self._filter_instances(instances)
            if filtered is None or len(filtered) == 0:
                filtered = instances[:0]
            v = Visualizer(frm_cv[:, :, ::-1], metadata=md, scale=1.2, instance_mode=ColorMode.IMAGE)
            out_v = v.draw_instance_predictions(filtered)
            res.append(Image.fromarray(out_v.get_image()))
        return res
"""    


class Processor:
    def __init__(self, face_model, body_model):
        self.face_net = cv.dnn.readNetFromCaffe(*face_model)
        self.body_net = cv.dnn.readNetFromDarknet(*body_model)
        self.saved_faces_dir = "saved_faces"
        self.output_dir = "Data/commands/ai/images"  
        os.makedirs(self.saved_faces_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        self.saved_faces = self.load_saved_faces()

    def save_face_image(self, img_np, face_coords, face_index):
        x1, y1, x2, y2 = face_coords
        face_img = cv.resize(img_np[y1:y2, x1:x2], (128, 128))
        cv.imwrite(f"{self.saved_faces_dir}/face_{face_index}.jpg", face_img)
        return face_img

    def load_saved_faces(self):
        try:
            with open('saved_faces.pkl', 'rb') as f:
                return pickle.load(f)
        except FileNotFoundError:
            return []

    def save_faces_to_file(self):
        with open('saved_faces.pkl', 'wb') as f:
            pickle.dump(self.saved_faces, f)

    async def download_media(self, media_url, output_filename):
        response = await asyncio.to_thread(requests.get, media_url, stream=True)
        if response.status_code == 200:
            with open(output_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Media downloaded: {output_filename}")
        else:
            raise ValueError(f"Error downloading media: {media_url}")

    def process_frame(self, img_np):
        if img_np is None or img_np.size == 0:
            return img_np
        img_h, img_w = img_np.shape[:2]
        face_blob = cv.dnn.blobFromImage(img_np, 1.0, (300, 300), (104.0, 177.0, 123.0), swapRB=True)
        body_blob = cv.dnn.blobFromImage(img_np, 1.0 / 255.0, (416, 416), (0, 0, 0), swapRB=True)
        with ThreadPoolExecutor() as executor:
            face_detections, body_detections = executor.submit(self.face_net.setInput, face_blob), executor.submit(self.body_net.setInput, body_blob)
        face_coords = self.detect_face(face_detections.result(), img_w, img_h)
        body_coords = self.detect_body(body_detections.result(), img_w, img_h)
        if face_coords:
            cv.rectangle(img_np, face_coords[:2], face_coords[2:], (200, 0, 0), 2)
            cv.putText(img_np, f'Face: {face_coords[4]:.2f}', (face_coords[0], face_coords[1] - 10), cv.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        if body_coords:
            for coord in body_coords:
                cv.rectangle(img_np, coord[:2], coord[2:], (0, 0, 255), 2)
                cv.putText(img_np, 'Body', (coord[0], coord[1] - 10), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        self.save_faces_to_file()
        return img_np

    def detect_face(self, face_detections, img_w, img_h):
        if face_detections.shape[2] == 0:
            return None
        highest_confidence, best_face_coords = 0, None
        for i in range(face_detections.shape[2]):
            confidence = face_detections[0, 0, i, 2]
            if confidence > 0.15:
                if confidence > highest_confidence:
                    highest_confidence = confidence
                    x1, y1, x2, y2 = [int(face_detections[0, 0, i, j] * img_w if j % 2 == 0 else face_detections[0, 0, i, j] * img_h) for j in range(3, 7)]
                    best_face_coords = (x1, y1, x2, y2, confidence)
        return best_face_coords

    def detect_body(self, body_detections, img_w, img_h):
        detected_bodies = []
        if body_detections.size > 0:
            for detection in body_detections:
                if detection[4] >= 0.15:
                    center_x, center_y, width, height = map(int, (detection[0] * img_w, detection[1] * img_h, detection[2] * img_w, detection[3] * img_h))
                    x1, y1, x2, y2 = max(0, center_x - width // 2), max(0, center_y - height // 2), min(img_w, center_x + width // 2), min(img_h, center_y + height // 2)
                    aspect_ratio = height / width
                    if aspect_ratio >= 1.2:
                        detected_bodies.append((x1, y1, x2, y2))
        return detected_bodies













class Ai(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.OPENAI_KEY = os.getenv("OPENAI_KEY")
        self.HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
        self.queue = []  # Queue can be used for task handling
        
        if not self.OPENAI_KEY:
            raise ValueError("API key is not set in environment variables.")

        self.openai_client = AsyncOpenAI(
            api_key=self.OPENAI_KEY,
            base_url="https://api.naga.ac/v1",
        )
        self.image_gen = ImageGenerator()
        self.error_custom_embed = error_custom_embed
        #self.detect = Detect()  # Initialize Detect instance here
        self.detect.q = queue.Queue()

        self.detect.cache = {}  # Ensure cache exists as a dictionary        self.queue = []
        self.detect = Processor(face_model=('Data/commands/ai/detect/deploy.prototxt', 'Data/commands/ai/detect/res10_300x300_ssd_iter_140000.caffemodel'),
                                 body_model=('Data/commands/ai/detect/yolov4.cfg', 'Data/commands/ai/detect/yolov4.weights'))

    @commands.command()
    async def detect(self, ctx, url: str):
        output_filename = "Data/commands/ai/images/generated_media.jpg"  # Updated path for generated images
        try:
            await self.detect.download_media(url, output_filename)
            img = cv.imread(output_filename)
            processed_img = self.detect.process_frame(img)
            cv.imwrite(output_filename, processed_img)
            await ctx.send(file=discord.File(output_filename))  # Send processed media
        except ValueError as e:
            await ctx.send(f"Error: {e}")


    @commands.command(name="imagine", description="Generate an image", aliases=["i"])
    async def imagine(self, ctx: commands.Context, *, prompt: str):
     if ctx.author.id in self.queue:
        await ctx.send(f"{ctx.author.mention}, you're already in the process of generating an image. Please wait until it finishes.")
        return
    
     self.queue.append(ctx.author.id)
    
     try:
        async with ctx.typing():
            custom_prompt = f"{prompt}"
            output_path = await self.image_gen.generate_image_sync(custom_prompt)

            new_file = self.image_gen.output_dir / "1.png"
            if new_file.exists():
                new_file.unlink()
            if output_path == None:
                await ctx.reply("❌ Error generating prompt, please try again.")
                return
            output_path.rename(new_file)

            file = discord.File(str(new_file), filename="1.png")
            description = f"**Prompt:** ```{prompt}```"
            embed = discord.Embed(
                description=description,
                color=primary_color(),
                timestamp=datetime.now(),
                url="https://rajtech.me"
            )
            embed.set_image(url="attachment://1.png")
            embed.set_footer(
                icon_url=ctx.author.avatar, text=f"Requested by {ctx.author}"
            )

            await ctx.reply(embed=embed, file=file)
    
     except Exception as e:
        await ctx.send(f"An error occurred: {e}")
     finally:
        self.queue.remove(ctx.author.id)

    @commands.command(
        name="vision", description="Generate a vision-based response", aliases=["v"])
    async def vision_commmand(self, ctx, image_url: str = None):
        async def vision(image_link: str, prompt: str = " ") -> str:
            try:
                response = await self.openai_client.chat.completions.create(
                    model="gemini-2.0-flash-lite",  
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": image_link},
                                },
                            ],
                        }
                    ],
                )
                return response.choices[0].message.content
            except Exception as e:
                return f"Ouch! Something went wrong! {e}"

        try:
            prompt = "in a tone of innocent, and slightly naive (you are anya forger from spx x family : DO NOT TALK ABOUT PENUTS are make refrences to the show) describe the image you see and have turthful opionins"
            async with ctx.typing():
                message = await ctx.reply(
                    "> **Thinking ... :thought_balloon:**",
                    mention_author=False,
                )

                if not image_url:
                    if ctx.message.attachments:
                        image_url = ctx.message.attachments[0].url
                    elif ctx.message.reference:
                        ref_message = await ctx.channel.fetch_message(
                            ctx.message.reference.message_id
                        )
                        if ref_message.attachments:
                            image_url = ref_message.attachments[0].url
                        elif ref_message.embeds:
                            
                            embed = ref_message.embeds[0]
                            if embed.thumbnail and embed.thumbnail.url:
                                image_url = embed.thumbnail.url
                            elif embed.image and embed.image.url:
                                image_url = embed.image.url
                        else:
                            await message.edit(
                                content="No image URL found in the referenced message. Please provide an image URL or attach an image to your message."
                            )
                            return
                    elif ctx.message.embeds:
                        
                        embed = ctx.message.embeds[0]
                        if embed.thumbnail and embed.thumbnail.url:
                            image_url = embed.thumbnail.url
                        elif embed.image and embed.image.url:
                            image_url = embed.image.url
                    else:
                        await message.edit(
                            content="No image URL found. Please provide an image URL, attach an image to your message, or reply to a message with an image."
                        )
                        return

                logger.info(f"Image URL: {image_url}")
                logger.info(f"Prompt: {prompt}")

                response = await vision(image_url, prompt)
                embed = discord.Embed(
                    description=f"-# Asked by {ctx.author.mention}\n\n**Vision** - {response}",
                    color=primary_color(),
                )
                embed.set_thumbnail(url=image_url)
                embed.set_footer(
                    icon_url=self.bot.user.avatar,
                    text=f"Thanks for using {self.bot.user.name}",
                )
                await message.delete()
                await ctx.reply(embed=embed)
        except Exception as e:
            await message.edit(content=f"An error occurred: {e}")

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
                        
                        # Decode and save the image
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















"""
class ImageGenerator:
    def __init__(self, api_key: str):
        self.client = InferenceClient("cagliostrolab/animagine-xl-4.0", token=api_key)
        self.output_dir = Path("Data/commands/ai/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print("Using Hugging Face model via InferenceClient...")

    def generate_image_sync(self, prompt: str, width: int = 1344, height: int = 768) -> Path:
        try:
            print(f"Generating image for prompt: {prompt}")
            negative_prompt = "lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry, missing fingers, extra limbs, extra fingers, duplicate bodys, unfinished limbs"
            # Modify the parameters to match the model's requirements for size
            image = self.client.text_to_image(
                prompt,
                width=width,       # Pass width as a parameter to the model
                height=height,     # Pass height as a parameter to the model
                negative_prompt=negative_prompt
            )

            print(f"Image generated successfully with size {width}x{height}")
            
            # Save the image to the output directory
            output_path = self.output_dir / f"generated_image_{width}x{height}.png"
            image.save(output_path)
            print(f"Image saved at: {output_path}")
            return output_path

        except Exception as e:
            print(f"Error during image generation: {e}")
            raise e
  
"""

def setup(bot):
    bot.add_cog(Ai(bot))