from utils.cogs.fun import *; from imports.discord_imports import *; from data.local.emojis import *; from typing import Union, Literal

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fun_cmd = Fun_Commands()
        self._dynamic_commands = []
        self._path = 'data/commands/fun/action-response.json'
        self._create_actions()

    @commands.command(name='8ball')
    async def eight_ball(self, ctx, *, question):
        ans = await self.fun_cmd.eight_ball()
        await ctx.reply(f'**:8ball: | {ctx.author.display_name} asked:** *"{question}"*\n{blank_emoji} | **Answer:** {ans}', mention_author=False)

    def _create_actions(self):
        actions = ['pat', 'cuddle', 'bite', 'kiss', 'lick', 'hug', 'cry', 'wave', 'slowclap', 'smug', 'dance', 'happy']
        for act in actions:
            async def cmd(ctx, user: Union[discord.Member, Literal["everyone"]] = None, *, txt=""):
                embed, msg = await self.fun_cmd.action_command(ctx, user or ctx.author, txt)
                await (ctx.reply(msg, mention_author=False) if not embed else ctx.send(embed=embed))
            cmd.__name__ = act
            command = commands.Command(cmd)
            self._dynamic_commands.append(command)
            self.bot.add_command(command)
        try:
            with open(self._path, 'r+') as f:
                data = json.load(f)
                s, o, e = data["phrases"]["self"], data["phrases"]["other"], data["phrases"]["everyone"]
                for a in actions:
                    s.setdefault(a, f"{a}s themselves")
                    o.setdefault(a, f"{a} {{target}}")
                    e.setdefault(a, f"{a} the whole server")
                f.seek(0); json.dump(data, f, indent=4); f.truncate()
        except FileNotFoundError:
            pass

    def get_commands(self):
        return super().get_commands() + self._dynamic_commands


async def setup(bot):
    await bot.add_cog(Fun(bot))