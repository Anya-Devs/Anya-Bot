
import os
import asyncio
import aiohttp
import asyncio
import base64
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI  

#from huggingface_hub import InferenceClient unsued


from Imports.discord_imports import *
from Imports.log_imports import logger
from Data.const import error_custom_embed, primary_color


class Ai(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.OPENAI_KEY = os.getenv("OPENAI_KEY")
        self.HUGGINGFACE_API_KEY =  os.getenv("HUGGINGFACE_API_KEY")
        self.queue = []  

        if not self.OPENAI_KEY:
            raise ValueError("API key is not set in environment variables.")

        self.openai_client = AsyncOpenAI(
            api_key=self.OPENAI_KEY,
            base_url="https://api.naga.ac/v1",
        )
        self.image_gen = ImageGenerator()  
        self.error_custom_embed = error_custom_embed

   
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
