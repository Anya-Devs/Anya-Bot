import traceback
from imports.discord_imports import *

class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sync', hidden=True)
    @commands.is_owner()
    async def sync(self, ctx: Context, spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        embed = discord.Embed(title="Command Sync Report", color=discord.Color.green())
        try:
            print(f"[DEBUG] Sync command called by {ctx.author} in guild {ctx.guild}")
            print(f"[DEBUG] Spec: {spec}")

            if spec == "^":
                guilds = [ctx.guild]
            else:
                guilds = self.bot.guilds

            total_synced_commands = 0
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

                    embed.add_field(
                        name=f"{guild.name} ({guild.id})",
                        value=f"✅ Synced {synced_count} commands.",
                        inline=False
                    )

                except discord.HTTPException as e:
                    error_message = f"❌ Error syncing: {e}"
                    print(f"[ERROR] Guild {guild.id}: {e}")
                    failed_guilds.append(guild)
                    embed.add_field(
                        name=f"{guild.name} ({guild.id})",
                        value=error_message,
                        inline=False
                    )

            embed.add_field(
                name="Summary",
                value=f"Total guilds attempted: {len(guilds)}\n"
                      f"Total commands synced: {total_synced_commands}\n"
                      f"Failed guilds: {', '.join(g.name for g in failed_guilds) if failed_guilds else 'None'}",
                inline=False
            )
            await ctx.send(embed=embed)

        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            print(f"[ERROR] {error_message}")
            traceback.print_exc()
            embed.color = discord.Color.red()
            embed.clear_fields()
            embed.add_field(name="Error", value=error_message, inline=False)
            await ctx.send(embed=embed)

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
