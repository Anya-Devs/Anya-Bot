from Imports.discord_imports import *
class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sync', hidden=True)
    @commands.is_owner()
    @commands.guild_only()
    async def sync(self, ctx: Context, guilds: Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
        try:
            # Get the current guild
            guild = ctx.guild

            # Initialize the counter for synced commands
            synced_commands_count = 0

            if not guilds:
                if spec == "~":
                    # Sync global commands to the current guild
                    synced_commands = await self.bot.tree.sync(guild=guild)
                    synced_commands_count += len(synced_commands)
                elif spec == "*":
                    # Copy global commands to the current guild
                    self.bot.tree.copy_global_to(guild=guild)
                    # Sync global commands to the current guild
                    synced_commands = await self.bot.tree.sync(guild=guild)
                    synced_commands_count += len(synced_commands)
                elif spec == "^":
                    # Clear all existing commands in the current guild
                    self.bot.tree.clear_commands(guild=guild)
                    # Sync global commands to the current guild
                    await self.bot.tree.sync(guild=guild)
                else:
                    # Sync global commands to the current guild
                    synced_commands = await self.bot.tree.sync(guild=guild)
                    synced_commands_count += len(synced_commands)

                # Send feedback to the user about the synchronization result
                message = f"Synced {synced_commands_count} app tree commands {'globally' if spec is None else 'to the current guild'}."
                embed = discord.Embed(description=message)
                await ctx.send(embed=embed)
                return

            # Sync commands for multiple guilds
            for guild_obj in guilds:
                try:
                    # Sync global commands to the current guild
                    synced_commands = await self.bot.tree.sync(guild=guild_obj)
                    synced_commands_count += len(synced_commands)
                except discord.HTTPException as e:
                    # Log the error
                    print(f"Error syncing guild {guild_obj.id}: {e}")

            # Send feedback to the user about the synchronization result for multiple guilds
            message = f"Synced the app tree to {synced_commands_count}/{len(guilds)} guilds."
            embed = discord.Embed(description=message)
            await ctx.send(embed=embed)
        except Exception as e:
            # Handle any unexpected errors
            print(f"An error occurred during app tree synchronization: {e}")
            traceback.print_exc()
            await ctx.send(f"An error occurred during app tree synchronization: {e}")

    @sync.error
    async def sync_error(self, ctx, error):
        # Handle command errors
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing required arguments. Please check the command syntax.")
        else:
            await ctx.send(f"An error occurred: {error}")

def setup(bot):
    bot.add_cog(Sync(bot))
