# quest.py

import traceback
import discord
from discord.ext import commands
from Data.const import Quest_Progress, error_custom_embed, primary_color

class Quest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Function to parse fraction input
    def parse_fraction(self, fraction_str):
        try:
            if "/" in fraction_str:
                parts = fraction_str.split("/")
                return int(parts[0]), int(parts[1])
            elif "," in fraction_str:
                parts = fraction_str.split(",")
                return int(parts[0]), int(parts[1])
            elif " " in fraction_str:
                parts = fraction_str.split(" ")
                return int(parts[0]), int(parts[1])
            else:
                return None
        except Exception as e:
            print(f"Error occurred while parsing fraction: {e}")
            traceback.print_exc()
            return None

    # Define the quest command
    @commands.command()
    async def quest(self, ctx, progress_str: str):
        try:
            fraction = self.parse_fraction(progress_str)
            if fraction:
                numerator, denominator = fraction
                if denominator != 0:
                    progress = numerator / denominator
                    if 0 <= progress <= 1:
                        progress_bar = await Quest_Progress.generate_progress_bar(progress, self.bot)  # Pass 'bot' parameter

                        # Add fraction to the end of the progress bar
                        progress_bar += f" `{numerator}/{denominator}`"

                        # Create an embed
                        embed = discord.Embed(title="Quest Progress", color=primary_color())
                        embed.add_field(name="Progress:", value=progress_bar, inline=False)

                        await ctx.send(embed=embed)
                    else:
                        await ctx.send("Invalid progress value. Progress should be between 0 and 1.")
                else:
                    await ctx.send("Invalid progress value. Denominator cannot be zero.")
            else:
                await ctx.send("Invalid input format. Please use one of the following formats: '1/3', '1 3', '1,3'.")
        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, ctx, e, title="Quest Error")

def setup(bot):
    bot.add_cog(Quest(bot))
