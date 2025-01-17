import os
import logging
from pathlib import Path
import asyncio

from Imports.discord_imports import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileSender(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.token = os.getenv('TOKEN')
        self.owner_id = 1030285330739363880  

    @commands.command(hidden=True)
    @commands.is_owner()  
    async def sendfile(self, ctx, directory: str = "."):
        """List available files and send the selected file from the local filesystem to the user's DM."""
        if ctx.author.id != self.owner_id:
            await ctx.send("You are not authorized to use this command.")
            return
        
        try:
            
            file_paths = self.list_files(directory)
            if not file_paths:
                await ctx.send("No files found in the specified directory.")
                return

            
            file_list_content = "\n".join(f"{idx + 1}: {file_path}" for idx, file_path in enumerate(file_paths))
            file_list_path = Path("file_list.txt")
            
            
            with open(file_list_path, "w") as file_list:
                file_list.write(file_list_content)

            
            user = await self.bot.fetch_user(self.owner_id)  
            await user.send(file=discord.File(file_list_path))

            
            await ctx.send("Please check your DM for the list of files and reply with the number of the file you want to send.")

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

            try:
                response = await self.bot.wait_for('message', timeout=60.0, check=check)
                file_number = int(response.content) - 1

                if 0 <= file_number < len(file_paths):
                    file_path = file_paths[file_number]
                    await self.send_file_to_user(user, file_path)
                else:
                    await ctx.send("Invalid file number selected.")
            except asyncio.TimeoutError:
                await ctx.send("You took too long to respond. Please try again.")

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            await ctx.send(f"An error occurred: {e}")

    @staticmethod
    def list_files(search_path: str = ".") -> list:
        """List all file paths in the given directory and its subdirectories, ignoring package and cache files."""
        file_paths = []
        ignore_patterns = [
            ".local/lib/python",
            "site-packages",
            "cache",
            "tmp",
            ".cache",
            ".tmp"
        ]

        
        directories_to_process = [search_path]

        while directories_to_process:
            current_directory = directories_to_process.pop(0)

            
            if any(ignore_pattern in current_directory for ignore_pattern in ignore_patterns):
                continue

            
            try:
                with os.scandir(current_directory) as it:
                    for entry in it:
                        if entry.is_file() and not any(pattern in entry.path for pattern in ignore_patterns):
                            file_paths.append(entry.path)
                        elif entry.is_dir():
                            if not any(pattern in entry.path for pattern in ignore_patterns):
                                directories_to_process.append(entry.path)
            except PermissionError:
                logger.warning(f"Permission denied for directory: {current_directory}")

        return file_paths

    @staticmethod
    async def send_file_to_user(user: discord.User, file_path: str):
        """Send a file to the specified user via DM, handling size limitations."""
        try:
            filename = os.path.basename(file_path)
            output_path = Path(file_path)
            max_file_size = 8 * 1024 * 1024  

            if output_path.stat().st_size <= max_file_size:
                
                with open(file_path, 'rb') as f:
                    await user.send(file=discord.File(fp=f, filename=filename))
            else:
                
                with open(file_path, 'rb') as f:
                    chunk_number = 1
                    while chunk := f.read(max_file_size):
                        chunk_filename = f"{filename}.part{chunk_number}"
                        await user.send(file=discord.File(fp=chunk, filename=chunk_filename))
                        chunk_number += 1

            await user.send("File sent successfully!")

        except Exception as e:
            logger.error(f"An error occurred while sending the file: {e}")
            await user.send(f"An error occurred while sending the file: {e}")

async def setup(bot):
    await bot.add_cog(FileSender(bot))
