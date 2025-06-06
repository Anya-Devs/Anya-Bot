from imports.discord_imports import *
from utils.cogs.ticket import *

class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_data = Ticket_Dataset()

    def has_manage_role_or_perms(self, member):
        role = discord.utils.find(lambda r: r.name.lower() == "anya manager", member.roles)
        return role is not None or member.guild_permissions.manage_guild

    @commands.command(name="ticket")
    async def ticket_command(self, ctx,
                             action: Literal["create", "activate", "delete", "edit"],
                             param: Union[str, None] = None):
        if not self.has_manage_role_or_perms(ctx.author):
            return await ctx.send("❌ You lack permission to use this command.", delete_after=10)

        if action == "create":
            if not isinstance(param, TextChannel):
                return await ctx.send("Please mention a valid text channel.")
            await Ticket_View.TicketSetupView.start_setup(ctx, param)

        elif action == "activate":
            tickets = await self.ticket_data.load_all_tickets()
            if not tickets:
                return await ctx.send("No existing ticket configurations found.")
            await ctx.send("Select a ticket configuration to activate:",
                           view=Ticket_View.TicketActivateView(tickets, ctx.message.author.id))

        elif action == "delete":
            tickets = await self.ticket_data.load_all_tickets()
            if not tickets:
                return await ctx.send("No tickets available to delete.")
            await ctx.send("Select a ticket configuration to delete:",
                           view=Ticket_View.TicketDeleteView(tickets, ctx.message.author.id))

        elif action == "edit":
            if not param or "discord.com/channels/" not in param:
                return await ctx.send("Please provide a valid message link.")
            msg = await self.ticket_data.get_message_from_link(ctx, param)
            if not msg:
                return await ctx.send("Message not found.")
            await Ticket_View.TicketSetupView.start_edit(ctx, msg, self.ticket_data)

    @ticket_command.error
    async def ticket_error(self, ctx, error):
        embed = discord.Embed(
            title=":question: Not Quite...",
            description="You used the `ticket` command incorrectly.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Correct Format",
            value=(
                f"`{ctx.prefix}ticket create #channel`\n"
                f"`{ctx.prefix}ticket activate`\n"
                f"`{ctx.prefix}ticket delete`\n"
                f"`{ctx.prefix}ticket edit <message link>`"
            ),
            inline=False
        )
        embed.set_footer(text="Refer to each subcommand for required inputs.")
        await ctx.send(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(Ticket(bot))
