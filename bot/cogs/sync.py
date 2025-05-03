import traceback
from imports.discord_imports import *

class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sync', hidden=True)
    @commands.guild_only()
    @commands.is_owner()
    async def sync(self, ctx: Context, spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        try:
            print(f"[DEBUG] Sync command called by {ctx.author} in guild {ctx.guild}")
            print(f"[DEBUG] Spec: {spec}")

            
            if spec == "^":
                guilds = [ctx.guild]
            else:
                guilds = self.bot.guilds

            total_synced_commands = 0
            total_guilds = len(guilds)
            failed_guilds = []

            for guild in guilds:
                try:
                    print(f"[DEBUG] Syncing commands for guild: {guild.name} (ID: {guild.id})")

                    if spec == "~":
                        
                        synced_commands = await self.bot.tree.sync(guild=guild)
                    elif spec == "*":
                        
                        await self.bot.tree.copy_global_to(guild=guild)
                        
                        synced_commands = await self.bot.tree.sync(guild=guild)
                    else:
                        
                        synced_commands = await self.bot.tree.sync()

                    synced_count = len(synced_commands)
                    total_synced_commands += synced_count

                    
                    message = f"Synced {synced_count} commands in guild: {guild.name} (ID: {guild.id})."
                    await ctx.send(embed=discord.Embed(description=message, color=discord.Color.green()))

                except discord.HTTPException as e:
                    error_message = f"Error syncing guild {guild.id}: {e}"
                    print(f"[ERROR] {error_message}")
                    failed_guilds.append(guild)
                    await ctx.send(embed=discord.Embed(description=error_message, color=discord.Color.red()))

            
            success_message = f"Successfully synced commands in {total_guilds} guild(s). Total commands synced: {total_synced_commands}."
            await ctx.send(embed=discord.Embed(description=success_message, color=discord.Color.green()))

            if failed_guilds:
                failed_message = f"Failed to sync commands in the following guilds: {', '.join(guild.name for guild in failed_guilds)}."
                await ctx.send(embed=discord.Embed(description=failed_message, color=discord.Color.red()))

        except Exception as e:
            error_message = f"An error occurred: {e}"
            print(f"[ERROR] {error_message}")
            traceback.print_exc()
            await ctx.send(embed=discord.Embed(description=error_message, color=discord.Color.red()))

    @sync.error
    async def sync_error(self, ctx: Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing required arguments. Please check the command syntax.")
        else:
            await ctx.send(f"An error occurred: {error}")

def setup(bot):
    bot.add_cog(Sync(bot))