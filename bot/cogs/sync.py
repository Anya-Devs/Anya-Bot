import traceback
import asyncio
from typing import Optional, Literal
from discord.ext import commands
import discord

class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sync', hidden=True)
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        try:
            status_msg = await ctx.send(embed=discord.Embed(
                description="🔄 Starting global sync process...",
                color=discord.Color.blue()
            ))

            # Always perform global sync regardless of 'spec'
            try:
                synced_commands = await self.bot.tree.sync()
                total_synced_commands = len(synced_commands)
                await status_msg.edit(embed=discord.Embed(
                    description=f"✅ Global sync completed! Synced {total_synced_commands} commands globally.",
                    color=discord.Color.green()
                ))
            except Exception as e:
                await status_msg.edit(embed=discord.Embed(
                    description=f"❌ Global sync failed: {e}",
                    color=discord.Color.red()
                ))

        except Exception as e:
            print(f"[ERROR] An error occurred: {e}")
            traceback.print_exc()
            await ctx.send(embed=discord.Embed(description=f"An error occurred: {e}", color=discord.Color.red()))

    @sync.error
    async def sync_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing required arguments. Please check the command syntax.")
        else:
            await ctx.send(f"An error occurred: {error}")

def setup(bot):
    bot.add_cog(Sync(bot))
