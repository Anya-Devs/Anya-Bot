"""                   commands                   """
# 8ball, bite, blush, builtdifferent, cry, cuddle, dance, gayrate, handhold, happy,
# hug, iq, kiss, lick, nervous, pat, pinch, poke, pp, simprate, slap,
# slowclap, smile, smug, slot, strength, waifurate, wave, wink

import aiofiles, random
from imports.discord_imports import *



class Fun_Commands:
    def __init__(self):
        self._8ball_file = "data/commands/fun/8ball-responses.txt"
    
    async def eight_ball(self):
        async with aiofiles.open(self._8ball_file, mode="r") as file:
            responses = await file.readlines()
        response = random.choice([line.strip() for line in responses if line.strip()])
        return response