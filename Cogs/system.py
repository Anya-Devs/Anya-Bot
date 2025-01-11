import os
import gc
import json
import platform
import psutil
import subprocess
import time
import json
from datetime import datetime
from colorama import Fore, Style

from Imports.discord_imports import *
from Imports.log_imports import *
import Data.const as const 
from Data.const import primary_color, timestamp_gen


class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.memory_check.start()
        self.image_file = 'Data/commands/help/help_embed_images.json'


                                                                               

    async def get_latest_python_version(self):
        latest_version = subprocess.check_output(['python', '-c', 'import sys; print("{}.{}.{}".format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro))']).decode().strip()
        return latest_version

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{Fore.YELLOW}[System cog] Bot is ready.{Style.RESET_ALL}")

    @commands.command(name='ping')
    async def ping(self, ctx):
        try:
            python_version = platform.python_version()
            python_version_info = f"{python_version} {'Up to Date' if python_version >= await self.get_latest_python_version() else 'Outdated'}"

            system_info = f"{platform.system()} {platform.processor()}"
            
            threshold = 200
            lag = self.bot.latency * 1000
            pos_neg = f"{'+' if lag < threshold else '-'}"
            gateway_latency = f"{round(lag)}ms"
            
            cpu_usage_value = psutil.cpu_percent()
            mem_usage_value = psutil.virtual_memory().percent

            cpu_status = "Good" if cpu_usage_value < 80 else "Bad"
            mem_status = "Good" if mem_usage_value < 80 else "Bad"
            
            color =  discord.Color.green() if lag < threshold else discord.Color.red()

            embed = discord.Embed(title='', description=f"```diff\n{pos_neg} Pong: {gateway_latency}```", color=color, timestamp=datetime.now())
            embed.set_footer(text=f'Requested by {ctx.author}', icon_url=ctx.author.avatar)

                                                                                                                      
                                                                                                                         
                                                                                                       
                                                                                                               
                                                                                                                                                         

                                                            
            await ctx.reply(f"{ctx.message.author.mention}",embed=embed, mention_author=False)

        except Exception as e:
            await const.error_custom_embed(self.bot, ctx, e, title="Ping")
            logger.error(f"[System cog] Error occurred while sending ping embed: {e}")
   
    def cog_unload(self):
        logger.info(f"{Fore.RED}[System cog] Unloaded{Style.RESET_ALL}")
        
    @commands.command(name='uptime')
    async def uptime(self, ctx):
        """Shows how long the bot has been running."""
        bot_uptime = timestamp_gen(self.start_time)                                                                      


        embed = discord.Embed(
            title="How Long Has Bot Been Awake?",
            description=f"The bot was been running {bot_uptime}",
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.set_footer(text="Uptime", icon_url=self.bot.user.avatar)
        await ctx.reply(embed=embed, mention_author=False)     
        
    @tasks.loop(minutes=10)
    async def memory_check(self):
        """Periodically checks and optimizes memory usage."""
        await self.bot.wait_until_ready()
        self.optimize_memory()
        self.log_memory_usage()

    @memory_check.before_loop
    async def before_memory_check(self):
        await self.bot.wait_until_ready()

    def optimize_memory(self):
        """Optimize memory usage by clearing cache and running garbage collection."""
        # Force garbage collection
        collected = gc.collect()
        # Clear internal cache
        self.bot._connection.clear()
        print(f"Optimized memory. Garbage collected: {collected} objects.")

    def log_memory_usage(self):
        """Logs the bot's current memory usage."""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_usage = memory_info.rss / (1024 ** 2)  # Convert bytes to MB
        print(f"Current memory usage: {memory_usage:.2f} MB")

    @commands.command()
    @commands.is_owner()
    async def optimize(self, ctx):
        """Manually triggers memory optimization."""
        self.optimize_memory()
        memory_usage = self.get_memory_usage()
        await ctx.send(f"Memory optimization completed. Current usage: {memory_usage:.2f} MB")

    @commands.command()
    @commands.is_owner()
    async def memory_info(self, ctx):
        """Displays current memory usage statistics."""
        memory_usage = self.get_memory_usage()
        await ctx.send(f"Current memory usage: {memory_usage:.2f} MB")

    def get_memory_usage(self):
        """Returns the current memory usage of the bot."""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        return memory_info.rss / (1024 ** 2)  # Convert bytes to MB    
    
    @commands.command(name='credit')
    async def credit(self, ctx):
        try:
                                
            with open('Data/commands/system/credits.json', 'r') as f:
                credit_data = json.load(f)

                                                  
            embed = discord.Embed(
                title=f'{credit_data["title"]}',
                timestamp=datetime.now(),
                color=primary_color()
            )

                                  
            emoji = '<:ty:1285850367065587762>'
            reply = '<:reply:1285852466704809984>'
            image_url = 'https://static1.cbrimages.com/wordpress/wp-content/uploads/2022/11/Spy-x-family-ep-18-Loid-and-Anya-studying.jpg?q=50&fit=crop&w=1100&h=618&dpr=1.5'
            for developer in credit_data["developers"]:
                embed.add_field(name='', value=f'**{emoji} | {developer["name"]}**\n{reply} {developer["role"]}', inline=False)
                
            embed.set_image(url=image_url)
              
                        
            embed.set_footer(text='- w - thanks for using our bot')

                            
            await ctx.reply(embed=embed, mention_author=False)

        except Exception as e:
                                                              
            await ctx.send(f"An error occurred while trying to load the credits: {e}")


    @commands.command(name="set_image")
    async def set_image(self, ctx, cog_name: str):
        """Command to change the image URL of a specific cog. Accepts attachments or image URLs."""
        cog_name = cog_name.lower()

                               
        valid_cogs = ['anime', 'information', 'system', 'quest', 'ai', 'pokemon']
        if cog_name not in valid_cogs:
            await ctx.send(f"Invalid cog name. Valid cogs are: {', '.join(valid_cogs)}.")
            return

                              
        if len(ctx.message.attachments) > 0:
                                                          
            image_url = ctx.message.attachments[0].url
        elif len(ctx.message.content.split()) > 1:
                                                                                 
            image_url = ctx.message.content.split()[1]
        else:
            await ctx.send("No image URL or attachment found. Please attach an image or provide an image URL.")
            return
        
                                            
        if os.path.exists(self.image_file):
            with open(self.image_file, 'r') as f:
                help_embed = json.load(f)
        else:
            help_embed = {}

                                                    
        if cog_name not in help_embed:
            help_embed[cog_name] = {}

        help_embed[cog_name]['thumbnail_url'] = image_url

                                                      
        with open(self.image_file, 'w') as f:
            json.dump(help_embed, f, indent=4)

                                                             
        embed = discord.Embed(
            title=f"Thumbnail for `{cog_name}` Updated",
            description=f"The thumbnail for `{cog_name}` has been successfully updated!",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=image_url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="get_image")
    async def get_image(self, ctx, cog_name: str):
        """Command to retrieve the image URL of a specific cog."""
        cog_name = cog_name.lower()

                               
        valid_cogs = ['anime', 'information', 'system', 'quest', 'ai', 'pokemon']
        if cog_name not in valid_cogs:
            await ctx.send(f"Invalid cog name. Valid cogs are: {', '.join(valid_cogs)}.")
            return

                                                       
        if os.path.exists(self.image_file):
            with open(self.image_file, 'r') as f:
                help_embed = json.load(f)
        else:
            await ctx.send("No images have been set yet.")
            return
        
                                                                          
        if cog_name in help_embed and 'thumbnail_url' in help_embed[cog_name]:
            image_url = help_embed[cog_name]['thumbnail_url']
                                                               
            embed = discord.Embed(
                title=f"Thumbnail for `{cog_name}`",
                description=f"The current thumbnail for `{cog_name}` is:",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=image_url)
            await ctx.reply(embed=embed, mention_author=False)
        else:
            await ctx.reply(embed=embed, mention_author=False)



def setup(bot):
    bot.add_cog(System(bot))
