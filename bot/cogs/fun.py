from utils.cogs.fun import *; from imports.discord_imports import *; from data.commands.fun.emojis import *; from typing import Union, Literal

class Fun(commands.Cog):
    def __init__(self, bot): 
        self.bot = bot 
        self.fun_cmd = Fun_Commands()
        self._dynamic_commands = []
        self.action_commands_response_path ='data/commands/fun/action-response.json'
        self.create_action_commands()

    @commands.command(name='8ball')
    async def eight_ball(self, ctx, *, question): 
        await ctx.reply(f'**:8ball: | {ctx.author.display_name} asked:** *"{question}"*\n{blank_emoji} | **Answer:** {await self.fun_cmd.eight_ball()}', mention_author=False)

    def create_action_commands(self):
     actions = ['pat', 'cuddle', 'bite', 'kiss', 'lick', 'hug', 'cry', 'wave', 'slowclap', 'smug', 'dance', 'happy']
     for action in actions:
        async def action_fn(ctx, user: Union[discord.Member, Literal["everyone"]] = None, *, additional_text: str = ""):
            embed, msg = await self.fun_cmd.action_command(ctx, user or ctx.author, additional_text)
            await (ctx.reply(msg, mention_author=False) if embed is None else ctx.send(embed=embed))
        action_fn.__name__ = action
        command = commands.Command(action_fn)
        self._dynamic_commands.append(command)
        self.bot.add_command(command)
     self.add_missing_actions_to_json(actions)

    def add_missing_actions_to_json(self, actions):
        try:
            with open(self.action_commands_response_path, 'r+') as f:
                action_data = json.load(f)
                missing_actions = set(actions) - set(action_data["phrases"]["self"].keys())
                for missing_action in missing_actions:
                    action_data["phrases"]["self"][missing_action] = f"{missing_action}s themselves"
                    action_data["phrases"]["other"][missing_action] = f"{missing_action} {action_data['phrases']['other'].get(missing_action, '{target}')}"
                    action_data["phrases"]["everyone"][missing_action] = f"{missing_action} the whole server"
                f.seek(0)
                json.dump(action_data, f, indent=4)
                f.truncate()
        except FileNotFoundError:
            pass

    def get_commands(self): 
        return super().get_commands() + self._dynamic_commands

async def setup(bot):
    await bot.add_cog(Fun(bot))