import os
import json
import aiohttp
import io
from discord.ext import commands
import discord
from Data.const import error_custom_embed, sdxl, primary_color
import aiohttp
import json
import io
import re
from Cogs.pokemon import *
from PIL import Image, ImageDraw, ImageFont
import textwrap

import json
import re
import aiohttp
import discord
from discord.ext import commands
import io

class Aesthetic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = 'aesthetics.fl'
        self.create_or_update_fl_file()
        self.predictor = PokemonPredictor()
        self.footer_icon_pokemon = 'https://play.pokemonshowdown.com/sprites/gen6/'
    
    def create_or_update_fl_file(self):
        default_config = {
            "embeds": [
                {
                    "title": "{title}",
                    "description": ["{description}"],
                    "color": "{color}",
                    "thumbnail": {
                        "url": "{thumbnail_url}"
                    },
                    "footer": {
                        "text": "{footer_text}",
                        "icon_url": "{footer_icon_url}"
                    },
                    "author": {
                        "name": "{author_name}",
                        "icon_url": "{author_icon_url}"
                    },
                    "fields": [
                        {
                            "name": "{field_name}",
                            "value": "{field_value}",
                            "inline": "{field_inline}"  # Optional field to specify if the field should be inline
                        }
                    ]
                }
            ]
        }

        with open(self.config_file, 'w') as file:
            json.dump(default_config, file, indent=2)

    async def download_image(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        return None
        except Exception as e:
            print(f"Failed to download image: {str(e)}")
            return None

    def parse_pokemon_data(self, description):
        pokemon_list = []
        for line in description:
            match = re.match(r'`(\d+)`\s+.*?>([^<]+)<.*?>([^<]+)<.*?>(.*?)<.*?(\d+)\s+.*?(\d+\.\d+)%', line)
            if match:
                pokemon = {
                    'id': match.group(1),
                    'name': match.group(2).strip(),
                    'gender': match.group(3).strip(),
                    'nickname': match.group(4).strip(),
                    'level': match.group(5).strip(),
                    'iv': match.group(6).strip(),
                    'favorite': '❤️' in line
                }
                pokemon_list.append(pokemon)
        return pokemon_list
    
    def remove_emojis(self, text):
        """Remove emoji placeholders from text."""
        emoji_pattern = re.compile(r'<:_:\d+>|<a?:(?:\w+):\d+>')
        return emoji_pattern.sub('', text).strip()

    async def process_and_send_embed(self, message, embed_data):
        try:
            # Load the existing configuration
            with open(self.config_file, 'r') as file:
                config = json.load(file)

            embed = discord.Embed(
                title=embed_data.get('title', config['embeds'][0].get('title')),
                description=self.remove_emojis("\n".join(embed_data.get('description', config['embeds'][0].get('description')))),
                color=int(embed_data.get('color', config['embeds'][0].get('color')).lstrip('#'), 16)
            )

            # Set additional fields if available
            if 'thumbnail' in embed_data and embed_data['thumbnail'].get('url'):
                embed.set_thumbnail(url=embed_data['thumbnail']['url'])
            if 'footer' in embed_data:
                footer_text = self.remove_emojis(embed_data['footer'].get('text', config['embeds'][0].get('footer', {}).get('text', '')))
                footer_icon_url = embed_data['footer'].get('icon_url', config['embeds'][0].get('footer', {}).get('icon_url', ''))
                embed.set_footer(text=footer_text, icon_url=footer_icon_url)
            if 'author' in embed_data:
                author_name = self.remove_emojis(embed_data['author'].get('name', config['embeds'][0].get('author', {}).get('name', '')))
                author_icon_url = embed_data['author'].get('icon_url', config['embeds'][0].get('author', {}).get('icon_url', ''))
                embed.set_author(name=author_name, icon_url=author_icon_url)

            # Process fields
            fields = embed_data.get('fields', [])
            for field in fields:
                name = self.remove_emojis(field.get('name', ''))
                value = self.remove_emojis(field.get('value', ''))
                inline = field.get('inline', False)  # Default to False if not specified
                embed.add_field(name=name, value=value, inline=inline)

            # Handle images if available
            if 'image' in embed_data and embed_data['image'].get('url'):
                image_data = await self.download_image(embed_data['image']['url'])
                if image_data:
                    image_file = io.BytesIO(image_data)
                    image_file.seek(0)
                    file = discord.File(fp=image_file, filename='image.png')
                    embed.set_image(url='attachment://image.png')
                    await message.channel.send(embed=embed, file=file)
                else:
                    await message.channel.send(embed=embed)
            else:
                # Handle emojis if no image is present
                await self.handle_embeds_without_images(embed, message)

            # Delete the original message
            await message.delete()

        except Exception as e:
            await message.channel.send(f"An error occurred: {str(e)}")

    async def handle_embeds_without_images(self, embed, message):
        # Check if the embed description contains emojis
        description = self.remove_emojis(embed.description or "")
        
        # Create a new embed if needed
        new_embed = discord.Embed(
            title=embed.title,
            description=description,
            color=embed.color
        )
        new_embed.set_thumbnail(url=embed.thumbnail.url if embed.thumbnail else '')
        new_embed.set_footer(text=embed.footer.text if embed.footer else '', icon_url=embed.footer.icon_url if embed.footer else '')
        new_embed.set_author(name=embed.author.name if embed.author else '', icon_url=embed.author.icon_url if embed.author else '')
        await message.channel.send(embed=new_embed)

    @commands.Cog.listener()
    async def on_message(self, message):
     # Specify the author ID to target
     target_author_id = 716390085896962058
    
     if message.author.id == target_author_id:
        # Fetch embed data from the message
        for embed in message.embeds:
            if "Guess the pokémon" in embed.description:
                image_url = embed.image.url
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as response:
                        if response.status == 200:
                            img_bytes = await response.read()
                            img = Image.open(io.BytesIO(img_bytes))
                            img = np.array(img.convert('RGB'))  # Convert to numpy array

                            # Use the predictor to predict the Pokémon
                            prediction, time_taken = self.predictor.predict_pokemon(img)

                            # Update the embed to include the prediction in the footer
                            await self.process_and_send_embed(message, {
                                "title": embed.title,
                                "description": [self.remove_emojis(field.value) for field in embed.fields] + [self.remove_emojis(embed.description or '')],
                                "color": f"{primary_color()}",
                                "image": {
                                    "url": embed.image.url if embed.image.url else ''
                                },
                                "thumbnail": {
                                    "url": embed.thumbnail.url if embed.thumbnail else ''
                                },
                                "footer": {
                                    "text": f'{embed.footer.text if embed.footer else f"{prediction}"}',
                                    "icon_url": embed.footer.icon_url if embed.footer else f'{self.footer_icon_pokemon}.png'
                                },
                                "author": {
                                    "name": embed.author.name if embed.author else '',
                                    "icon_url": embed.author.icon_url if embed.author else ''
                                },
                                "fields": [{'name': field.name, 'value': self.remove_emojis(field.value), 'inline': field.inline} for field in embed.fields]
                            })
                        else:
                            await message.channel.send(f"Failed to download image. Status code: {response.status}", reference=message)


    @commands.command(name="reload_aesthetic")
    async def reload_aesthetic(self, ctx):
        # Reload the file if needed
        self.create_or_update_fl_file()
        await ctx.send("Aesthetic settings reloaded.")
        
def setup(bot):
    bot.add_cog(Aesthetic(bot))
