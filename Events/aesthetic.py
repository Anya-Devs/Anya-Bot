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
from PIL import Image, ImageDraw, ImageFont
import textwrap

class Aesthetic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = 'aesthetics.fl'
        self.create_or_update_fl_file()
        self.font = ImageFont.truetype("arial.ttf", 20)  # Change to the path of your font file

    def create_or_update_fl_file(self):
        default_config = {
            "embeds": [
                {
                    "title": "{title}",
                    "description": ["{description}"],
                    "color": "{color}",
                    "image": {
                        "url": "{image_url}"
                    },
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
                    }
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

    async def create_pillow_image(self, embed_data):
        width, height = 600, 400  # Increased height for better readability
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)

        # Define vertical spacing
        margin = 10
        vertical_spacing = 30

        # Add title
        title = embed_data.get('title', '')
        draw.text((margin, margin), title, font=self.font, fill='black')

        # Add description
        description = "\n".join(embed_data.get('description', []))
        wrapped_description = textwrap.fill(description, width=70)
        y_position = margin + vertical_spacing
        draw.text((margin, y_position), wrapped_description, font=self.font, fill='black')

        # Add fields
        fields = embed_data.get('fields', [])
        for field in fields:
            field_name = field.get('name', '')
            field_value = field.get('value', '')
            wrapped_field_value = textwrap.fill(field_value, width=70)
            y_position += vertical_spacing + 20
            draw.text((margin, y_position), f"{field_name}:", font=self.font, fill='black')
            y_position += 20
            draw.text((margin, y_position), wrapped_field_value, font=self.font, fill='black')
        
        # Add footer
        footer_text = embed_data.get('footer', {}).get('text', '')
        y_position += vertical_spacing + 30
        draw.text((margin, y_position), footer_text, font=self.font, fill='black')

        # Save to a BytesIO object
        image_file = io.BytesIO()
        image.save(image_file, format='PNG')
        image_file.seek(0)
        return image_file

    async def process_and_send_embed(self, message, embed_data):
        try:
            # Load the existing configuration
            with open(self.config_file, 'r') as file:
                config = json.load(file)

            embed = discord.Embed(
                title=embed_data.get('title', config['embeds'][0].get('title')),
                description="\n".join(embed_data.get('description', config['embeds'][0].get('description'))),
                color=int(embed_data.get('color', config['embeds'][0].get('color')).lstrip('#'), 16)
            )

            # Set additional fields if available
            if 'thumbnail' in embed_data and embed_data['thumbnail'].get('url'):
                embed.set_thumbnail(url=embed_data['thumbnail']['url'])
            if 'footer' in embed_data:
                footer_text = embed_data['footer'].get('text', config['embeds'][0].get('footer', {}).get('text', ''))
                footer_icon_url = embed_data['footer'].get('icon_url', config['embeds'][0].get('footer', {}).get('icon_url', ''))
                embed.set_footer(text=footer_text, icon_url=footer_icon_url)
            if 'author' in embed_data:
                author_name = embed_data['author'].get('name', config['embeds'][0].get('author', {}).get('name', ''))
                author_icon_url = embed_data['author'].get('icon_url', config['embeds'][0].get('author', {}).get('icon_url', ''))
                embed.set_author(name=author_name, icon_url=author_icon_url)

            # Handle image URL
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
        description = embed.description or ""
        emoji_matches = re.findall(r':(\w+):', description)
        
        if emoji_matches:
            # Generate a placeholder image
            image_file = await self.create_pillow_image({
                "title": embed.title,
                "description": [description],
                "color": embed.color,
                "fields": [{'name': field.name, 'value': field.value} for field in embed.fields],
                "footer": {
                    "text": embed.footer.text if embed.footer else ''
                }
            })
            
            file = discord.File(fp=image_file, filename='embed_image.png')
            await message.channel.send(file=file)
        else:
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
                await self.process_and_send_embed(message, {
                    "title": embed.title,
                    "description": [field.value for field in embed.fields] + [embed.description or ''],
                    "color": f"{primary_color()}",
                    "image": {
                        "url": embed.image.url if embed.image.url else ''
                    },
                    "thumbnail": {
                        "url": embed.thumbnail.url if embed.thumbnail else ''
                    },
                    "footer": {
                        "text": embed.footer.text if embed.footer else '@Anya, Waka Waku',
                        "icon_url": embed.footer.icon_url if embed.footer else ''
                    },
                    "author": {
                        "name": embed.author.name if embed.author else '',
                        "icon_url": embed.author.icon_url if embed.author else ''
                    }
                })

    @commands.command(name="reload_aesthetic")
    async def reload_aesthetic(self, ctx):
        # Reload the file if needed
        self.create_or_update_fl_file()
        await ctx.send("Aesthetic settings reloaded.")

        
def setup(bot):
    bot.add_cog(Aesthetic(bot))
