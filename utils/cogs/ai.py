import os, base64, asyncio, requests, concurrent, aiohttp, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor






class Image:
    class ImageGenerator:
        def __init__(self):
            self.output_dir = Path("data/commands/ai/images")
            self.prompt_path = "data/commands/ai/prompt.json"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.prompts = self.load_prompts()
            self.payload_config = self.load_payload_config()
            self.API_URL = os.getenv("Stable_Diffusion_API_URL")

        def load_prompts(self):
            p = Path(self.prompt_path)
            if p.exists():
                with open(p, 'r') as f:
                    return json.load(f)

        def load_payload_config(self):
            p = Path("data/commands/ai/payload.json")
            if p.exists():
                with open(p, 'r') as f:
                    return json.load(f)

        async def generate_image_sync(self, prompt: str, width: int = 1216, height: int = 768):
            pos = f"{prompt}, {self.prompts['positive_prompt']}"
            neg = self.prompts['negative_prompt']
            sampler = self.payload_config['sampler_name']

            payload = {
                "prompt": pos or "",
                "negative_prompt": neg or "",
                "steps": self.payload_config.get("steps", 20),
                "cfg_scale": self.payload_config.get("cfg_scale", 7.0),
                "width": self.payload_config.get("width", 512),
                "height": self.payload_config.get("height", 512),
                "seed": self.payload_config.get("seed", -1),
                "style_preset": self.payload_config.get("style_preset", "none"),
                "sampler_name": sampler or "Euler",
                "override_settings": self.payload_config.get("override_settings", {})
            }

            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(self.API_URL, json=payload) as r:
                        if r.status == 200:
                            data = await r.json()
                            img = base64.b64decode(data['images'][0])
                            out_path = self.output_dir / f"generated_image_{width}x{height}.png"
                            with open(out_path, 'wb') as f:
                                f.write(img)

                            config_dump = (
                                json.dumps(self.prompts, indent=2) + "\n\n" +
                                json.dumps(self.payload_config, indent=2)
                            )
                            return out_path, config_dump
                        else:
                            print(f"❌ Error: {r.status}, {await r.text()}")
                            return None, None
            except aiohttp.ClientError as e:
                print(f"❌ Request failed: {str(e)}")
                return None, None



class Vision:
  
  @staticmethod
  async def _generate_vision_response(cog, url: str, prompt: str = " "):
        try:
            res = await cog.openai_client.chat.completions.create(
                model="gemini-2.0-flash-lite",
                messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}]}]
            )
            return res.choices[0].message.content
        except Exception as e:
            return VISION_ERROR.format(error=e)




class Ai_Text:
    IMAGINE_ALREADY_IN_QUEUE = "{}, you're already in the process of generating an image. Please wait until it finishes."
    ERROR_GENERATING_PROMPT = "❌ Error generating prompt, please try again."
    NO_IMAGE_URL_FOUND = "No image URL found. Please provide an image URL, attach an image to your message, or reply to a message with an image."
    THINKING_MESSAGE = "> **Thinking ... :thought_balloon:**"
    ERROR_OCCURED = "An error occurred: {e}"
    REQUESTED_BY = "Requested by {ctx.author}"
    VISION_RESPONSE = "-# Asked by {ctx.author.mention}\n\n**Vision** - {response}"
    VISION_THANKS = "Thanks for using {self.bot.user.name}"
    VISION_PROMPT = "in a tone of innocent, and slightly naive (you are anya forger from spx x family : DO NOT TALK ABOUT PENUTS are make refrences to the show) describe the image you see and have turthful opionins"





























































