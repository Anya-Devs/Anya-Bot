import traceback
import asyncio
from typing import Optional, Literal
from discord.ext import commands
import discord

class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sync', hidden=True)
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        try:
            status_msg = await ctx.send(embed=discord.Embed(
                description="🔄 Starting sync process...",
                color=discord.Color.blue()
            ))

            if spec == "^":
                guilds = [ctx.guild]
            else:
                guilds = self.bot.guilds

            total_guilds = len(guilds)
            failed_guilds = []
            total_synced_commands = 0

            if spec is None:
                try:
                    synced_commands = await self.bot.tree.sync()
                    total_synced_commands = len(synced_commands)
                    await status_msg.edit(embed=discord.Embed(
                        description=f"✅ Global sync completed! Synced {total_synced_commands} commands across all {total_guilds} guilds.",
                        color=discord.Color.green()
                    ))
                    return
                except Exception as e:
                    await status_msg.edit(embed=discord.Embed(
                        description=f"❌ Global sync failed: {e}",
                        color=discord.Color.red()
                    ))
                    return

            # Create all tasks immediately
            tasks = []
            for guild in guilds:
                if spec == "~":
                    tasks.append(asyncio.create_task(self._sync_guild_only(guild)))
                elif spec == "*":
                    tasks.append(asyncio.create_task(self._sync_with_global_copy(guild)))
                else:
                    tasks.append(asyncio.create_task(self._sync_global()))

            processed = 0

            # Use as_completed to update progress as tasks finish
            for completed_task in asyncio.as_completed(tasks):
                try:
                    result = await completed_task
                    total_synced_commands += result
                except Exception as e:
                    failed_guilds.append(str(e))
                    print(f"[ERROR] Sync failed: {e}")
                    traceback.print_exc()
                processed += 1

                progress = (processed / total_guilds) * 100
                await status_msg.edit(embed=discord.Embed(
                    description=f"🔄 Syncing... {processed}/{total_guilds} guilds ({progress:.1f}%)",
                    color=discord.Color.blue()
                ))

            if failed_guilds:
                failed_names = failed_guilds[:5]
                if len(failed_guilds) > 5:
                    failed_names.append(f"... and {len(failed_guilds) - 5} more")
                await status_msg.edit(embed=discord.Embed(
                    title="Sync Completed with Errors",
                    description=(
                        f"✅ Successfully synced {total_guilds - len(failed_guilds)} guilds\n"
                        f"❌ Failed to sync {len(failed_guilds)} guilds\n"
                        f"📊 Total commands synced: {total_synced_commands}\n\n"
                        f"Failed guilds/errors: {', '.join(failed_names)}"
                    ),
                    color=discord.Color.orange()
                ))
            else:
                await status_msg.edit(embed=discord.Embed(
                    title="Sync Completed Successfully",
                    description=(
                        f"✅ Successfully synced commands in all {total_guilds} guilds\n"
                        f"📊 Total commands synced: {total_synced_commands}"
                    ),
                    color=discord.Color.green()
                ))

        except Exception as e:
            print(f"[ERROR] An error occurred: {e}")
            traceback.print_exc()
            await ctx.send(embed=discord.Embed(description=f"An error occurred: {e}", color=discord.Color.red()))

    async def _sync_guild_only(self, guild):
        synced_commands = await self.bot.tree.sync(guild=guild)
        return len(synced_commands)

    async def _sync_with_global_copy(self, guild):
        await self.bot.tree.copy_global_to(guild=guild)
        synced_commands = await self.bot.tree.sync(guild=guild)
        return len(synced_commands)

    async def _sync_global(self):
        synced_commands = await self.bot.tree.sync()
        return len(synced_commands)

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
