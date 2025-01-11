# Standard Libraries
import os
import asyncio
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI  # Assuming AsyncOpenAI is the correct import

from huggingface_hub import InferenceClient

# Local Imports
from Imports.discord_imports import *
from Imports.log_imports import logger
from Data.const import error_custom_embed, primary_color






class Ai(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("api_key")

        if not self.api_key:
            raise ValueError("API key is not set in environment variables.")

        self.openai_client =  AsyncOpenAI(api_key = 'ng-YgkaT8abn2sWaqZRUmVPzs07BdtrE', base_url = "https://api.naga.ac/v1")
        self.api_key = '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'

        self.image_gen =  ImageGenerator("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")  # Instantiate your ImageGenerator class

        self.huggingface_url = 'https://api-inference.huggingface.co/models/cagliostrolab/animagine-xl-3.1'
        self.vision_model_file = 'Data/commands/ai/vision_model.txt'
        self.options = VisionModelOptions(self.vision_model_file)
        self.error_custom_embed = error_custom_embed

        # Load vision model from file or set default if file does not exist
        self.vision_model = self.load_vision_model(self.vision_model_file)

    def load_vision_model(self, file_path: str) -> str:
        """
        Load vision model identifier from a file or create the file with the default model if it does not exist.
        """
        path = Path(file_path)
        default_model = 'gpt-4-turbo'  # Default model

        try:
            if path.exists():
                with open(file_path, 'r') as file:
                    model_id = file.read().strip()
                    if model_id in self.options.models:
                        return model_id

            # If file doesn't exist or model is invalid, create the file with the default model
            self.save_vision_model(file_path, default_model)
            return default_model

        except IOError as e:
            print(f"Error loading vision model: {e}")
            # Fallback to default model in case of any file operation error
            return default_model

    def save_vision_model(self, file_path: str, model_id: str):
        """
        Save vision model identifier to a file.
        """
        if model_id not in self.options.models:
            raise ValueError(f"Invalid model ID: {model_id}")

        try:
            with open(file_path, 'w') as file:
                file.write(model_id)
        except IOError as e:
            print(f"Error saving vision model: {e}")
            
    @commands.command(name='vision_model', aliases=['vm'], description="Change the vision model identifier or show the current model",hidden=True)
    async def set_vision_model(self, ctx: commands.Context, model_id: str = None):
        """Command to change the vision model and update the text file. Show current model if no ID is provided."""
        file_path = self.vision_model_file
        vision_options = VisionModelOptions(file_path)

        if model_id:
            if model_id.isdigit():
                # Handle user selection by number
                index = int(model_id) - 1
                if 0 <= index < len(vision_options.models):
                    selected_model = vision_options.models[index]
                    vision_options.save_model(selected_model)
                    self.vision_model = selected_model
                    await ctx.send(f"Vision model updated to: {selected_model}")
                else:
                    await ctx.send("Invalid number. Please choose a valid number from the list.")
            else:
                # Update vision model by model ID
                if vision_options.is_valid_model(model_id):
                    vision_options.save_model(model_id)
                    self.vision_model = model_id
                    await ctx.send(f"Vision model updated to: {model_id}")
                else:
                    await ctx.send("Invalid model ID. Please provide a valid model ID.")
        else:
            # Show current vision model
            current_model = self.vision_model
            model_list_message = vision_options.get_model_message()
            await ctx.send(f"Current vision model: {current_model}\n\n```{model_list_message}```")

            def check(msg):
                return msg.author == ctx.author and msg.channel == ctx.channel and msg.content.isdigit()

            try:
                response = await self.bot.wait_for('message', timeout=60.0, check=check)
                model_number = int(response.content) - 1
                if 0 <= model_number < len(vision_options.models):
                    selected_model = vision_options.models[model_number]
                    vision_options.save_model(selected_model)
                    self.vision_model = selected_model
                    await ctx.send(f"Vision model updated to: {selected_model}")
                else:
                    await ctx.send("Invalid number. Please choose a valid number from the list.")
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. Please try the command again.")
            except ValueError:
                await ctx.send("Invalid input. Please respond with a number.")
                
                

    @commands.command(name='imagine', description="Generate an image", aliases=['i'])
    async def imagine(self, ctx: commands.Context, *, prompt: str):
        try:
            async with ctx.typing():
                message = await ctx.reply('> **Please wait while I generate your prompt...**', mention_author=False)

                # Generate image using the generate_image method
                image_path = await self.image_gen.generate_image(prompt)

                if image_path:
                    image_file = discord.File(image_path, filename="generated_image.png")
                    description = f'**Prompt:** ```{prompt}```'
                    embed = discord.Embed(description=description, color=discord.Color.blurple(), timestamp=datetime.now())
                    embed.set_image(url="attachment://generated_image.png")
                    embed.set_footer(icon_url=ctx.author.avatar, text=f'Requested by {ctx.author}')
                    
                    await message.delete()
                    await ctx.reply(embed=embed, file=image_file)
                else:
                    await ctx.reply("Failed to generate image after multiple attempts.")
        
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(name='vision', description="Generate a vision-based response", aliases=['v'])
    async def vision_command(self, ctx, image_url: str = None):
         async def vision(image_link: str, prompt: str = ' ') -> str:
          try:
            response = await self.openai_client.chat.completions.create(
                model= 'gemini-1.5-pro', #self.vision_model,
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

          prompt = ('Speak in childlike wonder and innocence, use alittle bit of childlike grammar like a 6 year old. Read the images mind like a telapath. Have the vocab and personality of Anya Forger form spy x family thus make her your persona. Be logical')
          async with ctx.typing():
            message = await ctx.reply('> **Please wait while I analyze the image...**', mention_author=False)

            if not image_url:
                if ctx.message.attachments:
                    image_url = ctx.message.attachments[0].url
                elif ctx.message.reference:
                    ref_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                    if ref_message.attachments:
                        image_url = ref_message.attachments[0].url
                    elif ref_message.embeds:
                        # Extract image URL from the embed's thumbnail or image
                        embed = ref_message.embeds[0]
                        if embed.thumbnail and embed.thumbnail.url:
                            image_url = embed.thumbnail.url
                        elif embed.image and embed.image.url:
                            image_url = embed.image.url
                    else:
                        await message.edit(content="No image URL found in the referenced message. Please provide an image URL or attach an image to your message.")
                        return
                elif ctx.message.embeds:
                    # Extract image URL from the embed's thumbnail or image
                    embed = ctx.message.embeds[0]
                    if embed.thumbnail and embed.thumbnail.url:
                        image_url = embed.thumbnail.url
                    elif embed.image and embed.image.url:
                        image_url = embed.image.url
                else:
                    await message.edit(content="No image URL found. Please provide an image URL, attach an image to your message, or reply to a message with an image.")
                    return

            logger.info(f"Image URL: {image_url}")
            logger.info(f"Prompt: {prompt}")

            response = await vision(image_url, prompt)
            embed = discord.Embed(description=f'-# Asked by {ctx.author.mention}\n\n**Vision** - {response}', color=primary_color())
            embed.set_thumbnail(url=image_url)
            embed.set_footer(icon_url=self.bot.user.avatar, text=f'Thanks for using {self.bot.user.name}')
            await message.delete()
            await ctx.reply(embed=embed)
         except Exception as e:
          await message.edit(content=f"An error occurred: {e}")

            
            

class ImageGenerator:
    def __init__(self, api_key: str):
        # Use Hugging Face InferenceClient for faster image generation
        self.client = InferenceClient("ehristoforu/dalle-3-xl-v2", token=api_key)
        self.output_dir = Path("Data/commands/ai/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print("Using Hugging Face model via InferenceClient...")

    def generate_image_sync(self, prompt: str, width: int = 1344, height: int = 768) -> Path:
        """Generates an image synchronously using Hugging Face InferenceClient."""
        try:
            print(f"Generating image for prompt: {prompt}")
            negative_prompt = "longbody, lowres, bad anatomy, bad hands, missing fingers, pubic hair, extra digit, fewer digits, cropped, worst quality, low quality, very displeasing"


            # Send the prompt to the Hugging Face API for image generation
            image = self.client.text_to_image(prompt)  
            
            print(image)
            # Save the image to the output directory
            output_path = self.output_dir / f"generated_image.png"
            image.save(output_path)
            print(f"Image saved at: {output_path}")
            return output_path
        
        except Exception as e:
            print(f"Error during image generation: {e}")
            raise e

    async def generate_image(self, prompt: str) -> str:
        """Generates an image asynchronously."""
        try:
            output_path = await asyncio.to_thread(self.generate_image_sync, prompt)
            return str(output_path)
        except Exception as e:
            print(f"Failed to generate image: {e}")
            raise Exception(f"Failed to generate image: {e}")
        
class VisionModelOptions:
    """Class to manage vision model options."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.models: List[str] = [
            'gemini-1.5-pro-exp',
            'gemini-1.5-pro',
            'gemini-1.5-pro-exp-0801',
            'gemini-1.5-pro-latest', 'gemini-1.5-flash-latest', 'gpt-4o',
            'gpt-4o-2024-05-13', 'gpt-4o-mini', 'gpt-4o-mini-2024-07-18',
            'gpt-4-turbo', 'gpt-4-turbo-2024-04-09', 'gpt-4-turbo-preview',
            'gpt-4-0125-preview', 'gpt-4-1106-preview', 'gpt-4', 'gpt-4-0613',
            'llama-3-70b-instruct', 'llama-3-8b-instruct', 'mixtral-8x22b-instruct',
            'command-r-plus', 'command-r', 'codestral', 'codestral-2405',
            'mistral-large', 'mistral-large-2402', 'mistral-next', 'mistral-small',
            'mistral-small-2402', 'gpt-3.5-turbo', 'gpt-3.5-turbo-0125',
            'gpt-3.5-turbo-1106', 'claude-3.5-sonnet', 'claude-3.5-sonnet-20240620',
            'claude-3-opus', 'claude-3-opus-20240229', 'claude-3-sonnet',
            'claude-3-sonnet-20240229', 'claude-3-haiku', 'claude-3-haiku-20240307',
            'claude-2.1', 'claude-instant', 'gemini-pro', 'gemini-pro-vision',
            'llama-2-70b-chat', 'llama-2-13b-chat', 'llama-2-7b-chat',
            'mistral-7b-instruct', 'mixtral-8x7b-instruct', 'stable-diffusion-3-large'
        ]
        self.current_model = self.load_model()

    def load_model(self) -> str:
        """Load the current vision model identifier from a file."""
        if Path(self.file_path).exists():
            with open(self.file_path, 'r') as file:
                model_id = file.read().strip()
                if model_id in self.models:
                    return model_id
        return self.models[0]  # Default to the first model in the list if file not found or invalid

    def save_model(self, model_id: str):
        """Save the vision model identifier to a file."""
        if model_id in self.models:
            with open(self.file_path, 'w') as file:
                file.write(model_id)
            self.current_model = model_id
        else:
            raise ValueError(f"Invalid model ID: {model_id}")

    def get_model_list(self) -> List[str]:
        """Return the list of available vision models."""
        return self.models

    def is_valid_model(self, model_id: str) -> bool:
        """Check if the provided model ID is valid."""
        return model_id in self.models

    def get_model_embed(self) -> discord.Embed:
        """Generate an embed displaying the list of models with their positions."""
        embed = discord.Embed(title="Select Vision Model", description="Choose a vision model by replying with the number corresponding to the model.", color=0x00ff00)
        for i, model in enumerate(self.models):
            embed.add_field(name=f"{i + 1}. {model}", value='\u200b', inline=False)
        return embed       
    
    def get_model_message(self) -> str:
        """Generate a message displaying the list of models with their positions."""
        message = "Select Vision Model:\n"
        for i, model in enumerate(self.models):
            message += f"{i + 1}. {model}\n"
        message += "Reply with the number corresponding to the model."
        return message
            
      
        
def setup(bot):
    bot.add_cog(Ai(bot))
