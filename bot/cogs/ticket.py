from imports.discord_imports import *
from utils.cogs.ticket import *

class Ticket(commands.Cog):
    def __init__(self, bot):  # fixed __init__ typo
        self.bot = bot
        self.ticket_data = Ticket_Dataset()  # create instance

        
    @commands.command(name="ticket")
    async def ticket_command(self, ctx,
                             action: Literal["create", "activate", "delete", "edit"],
                             param: Union[TextChannel, str] = None):
        if action == "create":
            if not isinstance(param, TextChannel):
                return await ctx.send("Please mention a valid text channel.")
            await Ticket_View.TicketSetupView.start_setup(ctx, param)
        elif action == "activate":
            tickets = await self.ticket_data.load_all_tickets()
            if not tickets:
                return await ctx.send("No existing ticket configurations found.")
            await ctx.send("Select a ticket configuration to activate:", view=Ticket_View.TicketActivateView(tickets))
        elif action == "delete":
            tickets = await self.ticket_data.load_all_tickets()
            if not tickets:
                return await ctx.send("No tickets available to delete.")
            await ctx.send("Select a ticket configuration to delete:", view=Ticket_View.TicketDeleteView(tickets))
        elif action == "edit":
            if not isinstance(param, str):
                return await ctx.send("Please provide a valid message link.")
            msg = await self.ticket_data.get_message_from_link(ctx, param)
            if not msg:
                return await ctx.send("Message not found.")
            await Ticket_View.TicketSetupView.start_edit(ctx, msg)

    @ticket_command.error
    async def ticket_error(self, ctx, error):
        await ctx.send(f"Error: {str(error)}")

async def setup(bot):
    await bot.add_cog(Ticket(bot))
