import os, base64, asyncio, requests, concurrent, aiohttp, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import cv2 as cv
import numpy as np
from PIL import Image, ImageSequence
from tqdm import tqdm


class ImageGenerator:
    def __init__(self):
        self.output_dir = Path("Data/commands/ai/images")
        self.prompt_path = "Data/commands/ai/prompt.json"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.prompts = self.load_prompts()
        self.payload_config = self.load_payload_config()
        self.API_URL = os.getenv("Stable_Diffusion_API_URL")

    def load_prompts(self):
        prompt_file = Path(self.prompt_path)
        if prompt_file.exists():
            with open(prompt_file, 'r') as f:
                return json.load(f)

    def load_payload_config(self):
        payload_file = Path("Data/commands/ai/payload.json")
        if payload_file.exists():
            with open(payload_file, 'r') as f:
                return json.load(f)

    async def generate_image_sync(self, prompt: str, width: int = 1216, height: int = 768) -> Path:
        positive_prompt = f"{prompt}, {self.prompts['positive_prompt']}"
        negative_prompt = self.prompts['negative_prompt']
        sampler_name = self.payload_config['sampler_name']

        payload = {
            "prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "steps": self.payload_config['steps'],
            "cfg_scale": self.payload_config['cfg_scale'],
            "width": self.payload_config['width'],
            "height": self.payload_config['height'],
            "seed": self.payload_config['seed'],
            "style_preset": self.payload_config['style_preset'],
            "sampler_name": sampler_name,
            "override_settings": self.payload_config['override_settings']
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









































































