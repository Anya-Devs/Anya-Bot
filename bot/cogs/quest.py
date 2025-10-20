import datetime, typing, traceback, json
from io import BytesIO


from data.local.const import *
from imports.discord_imports import *
from imports.log_imports import *
from utils.cogs.quest import *



import discord
from discord.ext import commands
import json
import logging
from io import BytesIO
from datetime import datetime
logger = logging.getLogger(__name__)

class Quest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        self.shop_file = "data/commands/quest/shop.json"
        self.shop_data = self.load_shop_data()

    def load_shop_data(self):
        try:
            with open(self.shop_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading shop data: {e}")
            return {}

    def get_tool_emoji(self, tool_name):
        """Fetches the emoji for a given tool name."""
        for category, items in self.shop_data.items():
            for item in items:
                if item["name"].lower() == tool_name.lower():
                    return item.get("emoji", "")
        return ""  

    @commands.command(name="redirect")
    async def redirect(self, ctx, *channel_mentions: discord.TextChannel):
        if not (
            ctx.author.guild_permissions.manage_channels
            or discord.utils.get(ctx.author.roles, name="Anya Manager")
        ):
            await ctx.reply(
                "You need the `Manage Channels` permission or the `Anya Manager` role to use this command.",
                mention_author=False,
            )
            return  

        try:
            guild_id = str(ctx.guild.id)
            channel_ids = [str(channel.id) for channel in channel_mentions]

            
            if await self.quest_data.store_channels_for_guild(guild_id, channel_ids):
                await ctx.reply(
                    f"Now redirecting missions to {', '.join([channel.mention for channel in channel_mentions])}",
                    mention_author=False,
                )
            else:
                await ctx.reply(
                    "Failed to store the channels. Please try again later.",
                    mention_author=False,
                )
        except Exception as e:
            logger.error(f"Error in setchannels command: {e}")
            await ctx.send("An error occurred while setting the channels.")

    @commands.group(name="quest", aliases=["q"], invoke_without_command=True)
    async def quest(self, ctx, args: str = None):
        """Main quest command."""
        logger.debug("Quest command invoked.")

        if args == "newbie":
            logger.debug("Starting newbie tutorial.")
            tutorial_mission = TutorialMission(self.bot)
            await tutorial_mission.wait_for_user_action(ctx)
            return

        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)

            user_exists = await self.quest_data.find_user_in_server(user_id, guild_id)

            if not user_exists:
                prompt_embed = await Quest_Prompt.get_embed(self.bot)
                await ctx.reply(
                    embed=prompt_embed,
                    view=Quest_Button(self.bot, ctx),
                    mention_author=False,
                )
                return

            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)

            if quests:
                view = Quest_View(self.bot, quests, ctx)
                embeds = await view.generate_messages()

                image_generator = ImageGenerator(
                    ctx,
                    text="Complete each quest to earn rewards. Click the location link to go to the corresponding channel."
                )

                img = image_generator.create_image()
                img_bytes = BytesIO()
                img.save(img_bytes, format="PNG")
                img_bytes.seek(0)

                image_generator.save_image(file_path="data/images/generated_image.png")
                file = discord.File("data/images/generated_image.png", filename="image.png")

                embeds.set_image(url=f"attachment://image.png")

                if len(quests) > 3:
                    await ctx.reply(embed=embeds, view=view, mention_author=False, file=file)
                else:
                    await ctx.reply(embed=embeds, mention_author=False, file=file)
            else:
                no_quest_message = "You currently don't have any quest."
                description = f"```ansi\n\u2753 \033[97m{no_quest_message}```"
                embed = discord.Embed(description=description, color=discord.Color.yellow())

                await ctx.reply(
                    embed=embed,
                    view=Quest_Button1(self.bot, ctx),
                    mention_author=False,
                )

        except Exception as e:
            error_message = "An error occurred while fetching quests."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await ctx.send(error_message)

    @quest.command(name="roles")
    async def quest_roles(self, ctx, *role_mentions: discord.Role):
        """Set or list roles that a target can get randomly."""
        if not (ctx.author.guild_permissions.manage_roles or discord.utils.get(ctx.author.roles, name="Anya Manager")):
            embed = discord.Embed(
                title="Permission Denied",
                description="You need the `Manage Roles` permission or the `Anya Manager` role to use this command.",
                color=discord.Color.red(),
                timestamp=datetime.now(),
            )
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
            await ctx.reply(embed=embed, mention_author=False)
            return

        guild_id = str(ctx.guild.id)

        # If no roles mentioned, display current roles
        if not role_mentions:
            current_roles = await self.quest_data.get_roles_for_guild(guild_id)
            if current_roles:
                roles_list = "\n".join([f"<@&{role_id}>" for role_id in current_roles])
            else:
                roles_list = (
                    "No roles have been set yet.\n\n"
                    "**Admins can set roles using the command below:**\n"
                    f"`{ctx.prefix}quest roles <@mention role1> <@mention role2> ... etc`"
                )

            embed = discord.Embed(
                description=f"```Grants the target user a random role from the list of available roles in the server.```\n**Current Set Roles:**\n{roles_list}",
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )
            embed.set_footer(text="Needed Tool: Key Chain Sheep", icon_url=self.bot.user.avatar.url)
            embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
            await ctx.reply(embed=embed, mention_author=False)
            return

        # Store new roles
        role_ids = [str(role.id) for role in role_mentions]
        await self.quest_data.store_roles_for_guild(guild_id, role_ids)

        embed = discord.Embed(
            title="Roles Set Successfully",
            description="Allows targets to get a random role.\n\nThe following roles have been set for this guild:",
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
        roles_list = "\n".join([role.mention for role in role_mentions])
        embed.add_field(name="Roles", value=roles_list, inline=False)

        await ctx.reply(embed=embed, mention_author=False)
    

    @commands.command(name="profile", aliases=["pf"])
    async def profile(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author

        user_id = member.id
        guild_id = ctx.guild.id
        user_id_str = str(user_id)
        guild_id_str = str(guild_id)

        user_exists = await self.quest_data.find_user_in_server(user_id_str, guild_id_str)
        if not user_exists:
            await ctx.reply(
                f"You need to start your quest first with `{ctx.prefix}quest` before viewing your profile.",
                mention_author=False
            )
            return

        try:
            balance = await self.quest_data.get_balance(user_id_str, guild_id_str)
        except AttributeError:
            # Fallback in case get_balance still fails due to NoneType
            balance = 0
            logger.warning(f"Balance fetch failed for user {user_id_str} in guild {guild_id_str}, defaulting to 0")

        db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
        server_collection = db["Servers"]
        doc = await server_collection.find_one({"guild_id": guild_id_str})
        if not doc:
            await ctx.reply("No server data found.")
            return

        member_data = doc.get("members", {}).get(user_id_str, {})
        profile = member_data.get("profile", {})
        age = profile.get("age", "Not set")
        sexuality = profile.get("sexuality", "Not set")
        bio = profile.get("bio", "No bio set.")
        stories = profile.get("stories", [])

        stella_points = balance  # Using the fetched balance

        view = ProfileView(ctx, member, age, sexuality, bio, stories, stella_points, self.quest_data)
        await view.start(ctx)

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx):
        try:
            guild_id = str(ctx.guild.id)
            user_id = str(ctx.author.id)

            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]

            user_data = await server_collection.find_one(
                {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}},
                {f"members.{user_id}.inventory"},
            )

            if not user_data:
                await ctx.reply(
                    f"{ctx.author.mention}, you need to start your quest first with `{ctx.prefix}quest` before viewing your inventory.",
                    mention_author=False,
                )
                return

            inventory = (
                user_data.get("members", {})
                .get(user_id, {})
                .get("inventory", {})
            )

            if not inventory:
                await ctx.reply(
                    f"{ctx.author.mention}, your inventory is empty! Start collecting items to see them here.",
                    mention_author=False,
                )
                return

            # Create inventory view with category selection
            inventory_view = InventoryView(self.quest_data, guild_id, user_id, ctx.author)
            await inventory_view.start(ctx)

        except Exception as e:
            await ctx.reply(
                f"An error occurred while fetching your inventory: {e}",
                mention_author=False,
            )
            logger.error(f"Error in inventory command: {e}")

    @commands.command(name="balance", aliases=["bal", "points", "stars","stp"])
    async def balance(
        self, ctx, method=None, amount: int = None, member: discord.Member = None
    ):
        guild_id = str(ctx.guild.id)
        target_member = member if member else ctx.author
        target_id = str(target_member.id)

        try:
            if method == "add":
                if ctx.author.id in [1030285330739363880, 1124389055598170182]:
                    await self.quest_data.add_balance(target_id, guild_id, amount)
                    amount_with_commas = "{:,}".format(amount)
                    await ctx.send(
                        f":white_check_mark: Successfully added {amount_with_commas} balance to {target_member.display_name}'s account."
                    )
                else:
                    await ctx.send(
                        "You don't have permission to use this command to add balance to other users."
                    )
            else:
                # View balance
                if target_id == str(ctx.author.id) and amount is None:
                    await self.quest_data.initialize_balance(target_id, guild_id)
                balance = await self.quest_data.get_balance(target_id, guild_id)
                balance_with_commas = "{:,}".format(balance)

                embed = discord.Embed(
                    description=f"-# {target_member.mention}'s balance",
                    timestamp=datetime.now(),
                )
                embed.set_thumbnail(url=target_member.avatar.url if target_member.avatar else target_member.default_avatar.url)
                embed.add_field(name="Stars", value=None, inline=True)
                embed.add_field(
                    name="Points", value=balance_with_commas, inline=True)
                embed.add_field(name="Class Ranking",
                                value=f"`#{None}`", inline=False)
                embed.set_footer(icon_url=self.bot.user.avatar.url)
                await ctx.reply(embed=embed, mention_author=False)

        except Exception as e:
            logger.error(f"An error occurred in the balance command: {e}")
            await ctx.send(
                "An error occurred while processing your request. Please try again later."
            )

    @commands.command(name="shop")
    async def shop(self, ctx):
        try:
            shop_data = self.read_shop_file(self.shop_file)
            view = ShopView(self.bot, shop_data)
            await view.start(ctx)
        except Exception as e:
            await ctx.send(f"An error occurred while processing the shop: {e}")

    @staticmethod
    def read_shop_file(filename):
        with open(filename, "r", encoding="utf-8") as file:
            shop_data = json.load(file)
        return shop_data


        
class Quest_Slash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        super().__init__()

    async def check_server_quest_limit(self, guild_id: int) -> bool:
        """
        Check if the server has reached its quest limit.
        """
        server_quest_count = await self.quest_data.get_server_quest_count(guild_id)
        server_quest_limit = await self.quest_data.get_quest_limit(guild_id)
        if server_quest_count >= server_quest_limit:
            return False
        return True

    quest_group = app_commands.Group(
        name="quest", description="Quest related commands")

    @quest_group.command(
        name="create",
        description="Create a new quest.",
    )
    @app_commands.describe(action="The action to perform for the quest.")
    @app_commands.describe(method="The method to use for the quest.")
    @app_commands.describe(content="The content for the quest.")
    @app_commands.choices(
        action=[
            discord.app_commands.Choice(name="send", value="send"),
            discord.app_commands.Choice(name="receive", value="receive"),
        ]
    )
    @app_commands.choices(
        method=[
            discord.app_commands.Choice(name="message", value="message"),
            discord.app_commands.Choice(name="reaction", value="reaction"),
            discord.app_commands.Choice(name="emoji", value="emoji"),
        ]
    )
    async def create_quest(
        self,
        interaction: discord.Interaction,
        action: discord.app_commands.Choice[str],
        method: discord.app_commands.Choice[str],
        channel: discord.TextChannel,
        content: str,
        times: typing.Optional[int] = 1,
    ) -> None:
        try:
            
            if any(mention in content for mention in ["<@", "<@&"]):
                await interaction.response.send_message(
                    "Content cannot contain user or role mentions.", ephemeral=True
                )
                return

            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            user = interaction.user

            
            quest_id = await self.quest_data.create_quest(
                guild_id,
                action.value,
                method.value,
                content,
                channel.id,
                times,
                0,
                interaction,
            )
            if quest_id is not None:
                
                embed = await QuestEmbed.create_quest_embed(
                    self.bot,
                    "Created",
                    quest_id,
                    action.value,
                    method.value,
                    channel,
                    times=times,
                    content=content,
                    user=user,
                )

                
                await interaction.response.send_message(embed=embed)
                logger.debug("Quest creation successful.")
            else:
                await interaction.response.send_message(
                    "Try doing `.quest`", ephemeral=True
                )
                logger.debug("Failed to create the quest.")

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, interaction, e, title="Quest Creation")

    @quest_group.command(
        name="delete",
        description="Delete a quest by its ID.",
    )
    async def delete_quest(
        self, interaction: discord.Interaction, quest_id: int
    ) -> None:
        try:
            guild_id = interaction.guild.id

            
            users_in_guild = await self.quest_data.find_users_in_server(guild_id)

            if not users_in_guild:
                await interaction.response.send_message(
                    "No users found in the server.", ephemeral=True
                )
                return

            quest_deleted = False

            for user_id in users_in_guild:
                
                quest_exists = await self.quest_data.find_users_with_quest(
                    guild_id, quest_id
                )
                if quest_exists:
                    
                    await self.quest_data.delete_quest(guild_id, quest_id)
                    quest_deleted = True

            if quest_deleted:
                await interaction.response.send_message(
                    f"The quest with ID {quest_id} has been deleted for all users who had it.",
                    ephemeral=True,
                ) 
            else:
                await interaction.response.send_message(
                    "The specified quest does not exist for any user.", ephemeral=True
                )

        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()
            await self.quest_data.handle_error(interaction, e, title="Quest Deletion")

    @quest_group.command(
        name="removeall",
        description="Remove all server quests from every member.",
    )
    async def remove_all_server_quests(self, interaction: discord.Interaction) -> None:
        try:
            guild_id = str(interaction.guild_id)

            
            await self.quest_data.remove_all_server_quests(guild_id)

            await interaction.response.send_message(
                "All server quests have been removed from every member.", ephemeral=True
            )
            logger.debug("All server quests removed successfully.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await self.quest_data.handle_error(
                interaction, e, title="Remove All Server Quests"
            )

    @quest_group.command(
        name="setlimit",
        description="Set the maximum number of quests a user can have.",
    )
    async def set_quest_limit(
        self, interaction: discord.Interaction, limit: int
    ) -> None:
        try:
            guild_id = str(interaction.guild_id)

            
            await self.quest_data.set_quest_limit(guild_id, limit)

            await interaction.response.send_message(
                f"Quest limit set to {limit} for this server.", ephemeral=True
            )
            logger.debug("Quest limit updated successfully.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(
                self.bot, interaction, e, title="Quest Limit Update"
            )

    @quest_group.command(
        name="serverquest",
        description="View all quests created for the server.",
    )
    async def view_all_server_quests(self, interaction: discord.Interaction) -> None:
        try:
            guild_id = str(interaction.guild_id)

            quests = await self.quest_data.server_quests(guild_id)

            embed = discord.Embed(
                title=f"All Server Quests for Server {guild_id}", color=0x7289DA
            )

            for quest_data in quests:
                embed.add_field(
                    name=f"Quest ID: {quest_data['quest_id']}",
                    value=f"**Action:** {quest_data['action']}\n"
                    f"**Method:** {quest_data['method']}\n"
                    f"**Content:** {quest_data['content']}\n"
                    f"**Channel ID:** {quest_data['channel_id']}\n"
                    f"**Times:** {quest_data['times']}\n"
                    f"**Reward:** {quest_data['reward']}\n",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)
            logger.debug("Viewed all server quests successfully.")

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await self.quest_data.handle_error(
                interaction, e, title="View All Server Quests"
            )





def setup(bot):

    bot.add_cog(Quest_Data(bot))
    bot.add_cog(Quest(bot))
    bot.add_cog(Quest_Slash(bot))
