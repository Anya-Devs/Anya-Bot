import discord
from discord.ext import commands
import random, asyncio, io, os
from PIL import Image, ImageDraw, ImageFont
import aiohttp, motor.motor_asyncio
from datetime import datetime
from collections import deque

class Social_Data:
    def __init__(self, bot):
        uri = os.getenv("MONGO_URI")
        self.mongo = motor.motor_asyncio.AsyncIOMotorClient(uri)["Social"]
    
    async def get_rel(self, gid, uid):
        doc = await self.mongo.relationships.find_one({"guild_id": gid, "user_id": uid})
        return doc or {"partner": None, "parent": None, "children": [], "friends": []}
    
    async def set_partner(self, gid, uid, pid):
        now = datetime.utcnow()
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": uid}, {"$set": {"partner": pid, "married_at": now}}, upsert=True)
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": pid}, {"$set": {"partner": uid, "married_at": now}}, upsert=True)
    
    async def remove_partner(self, gid, uid):
        rel = await self.get_rel(gid, uid)
        pid = rel.get("partner")
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": uid}, {"$set": {"partner": None}})
        if pid: await self.mongo.relationships.update_one({"guild_id": gid, "user_id": pid}, {"$set": {"partner": None}})
        return pid
    
    async def adopt(self, gid, parent, child):
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": parent}, {"$addToSet": {"children": child}}, upsert=True)
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": child}, {"$set": {"parent": parent}}, upsert=True)
    
    async def disown(self, gid, parent, child):
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": parent}, {"$pull": {"children": child}})
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": child}, {"$set": {"parent": None}})
    
    async def emancipate(self, gid, child):
        rel = await self.get_rel(gid, child)
        pid = rel.get("parent")
        if pid: await self.mongo.relationships.update_one({"guild_id": gid, "user_id": pid}, {"$pull": {"children": child}})
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": child}, {"$set": {"parent": None}})
        return pid
    
    async def add_friend(self, gid, uid, fid):
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": uid}, {"$addToSet": {"friends": fid}}, upsert=True)
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": fid}, {"$addToSet": {"friends": uid}}, upsert=True)
    
    async def remove_friend(self, gid, uid, fid):
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": uid}, {"$pull": {"friends": fid}})
        await self.mongo.relationships.update_one({"guild_id": gid, "user_id": fid}, {"$pull": {"friends": uid}})
    
    async def get_family_size(self, gid, uid):
        visited, queue = set(), deque([uid])
        while queue:
            cur = queue.popleft()
            if cur in visited: continue
            visited.add(cur)
            rel = await self.get_rel(gid, cur)
            if rel.get("parent"): queue.append(rel["parent"])
            for c in rel.get("children", []): queue.append(c)
            if rel.get("partner"): queue.append(rel["partner"])
            for f in rel.get("friends", []): queue.append(f)
        return len(visited)
    
    async def maybe_change_iq(self, gid, uid):
        doc = await self.mongo.iq.find_one({"guild_id": gid, "user_id": uid})
        if not doc:
            iq = random.randint(50, 160)
            await self.mongo.iq.update_one({"guild_id": gid, "user_id": uid}, {"$set": {"iq": iq}}, upsert=True)
            return iq
        iq = doc.get("iq", 100)
        if random.random() < 0.05:
            iq = max(50, min(200, iq + random.randint(-10, 10)))
            await self.mongo.iq.update_one({"guild_id": gid, "user_id": uid}, {"$set": {"iq": iq}})
        return iq
    
    async def get_stat(self, gid, uid, stat_name, min_val=1, max_val=100):
        doc = await self.mongo.stats.find_one({"guild_id": gid, "user_id": uid})
        if not doc or stat_name not in doc:
            val = random.randint(min_val, max_val)
            await self.mongo.stats.update_one({"guild_id": gid, "user_id": uid}, {"$set": {stat_name: val}}, upsert=True)
            return val
        val = doc.get(stat_name, (min_val + max_val) // 2)
        if random.random() < 0.08:
            val = max(min_val, min(max_val, val + random.randint(-5, 5)))
            await self.mongo.stats.update_one({"guild_id": gid, "user_id": uid}, {"$set": {stat_name: val}})
        return val

class Social(commands.Cog):
    def __init__(self, bot):
        self.bot, self.data = bot, Social_Data(bot)

    async def _fetch_av(self, url, size=50):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=3)) as r:
                    if r.status == 200:
                        img = Image.open(io.BytesIO(await r.read())).convert("RGBA").resize((size, size))
                        mask = Image.new("L", (size, size), 0)
                        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
                        out = Image.new("RGBA", (size, size), (0,0,0,0))
                        out.paste(img, (0,0), mask)
                        return out
        except: pass
        return None

    def _draw_heart(self, draw, cx, cy, size, color, percentage=100):
        """Draw a proper heart shape centered at (cx, cy) with given size and optional fill percentage."""
        import math
        # Heart parametric equation points
        points = []
        for i in range(100):
            t = i * 2 * math.pi / 100
            # Heart parametric equations
            x = 16 * (math.sin(t) ** 3)
            y = -(13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))
            # Scale and translate
            px = cx + int(x * size / 32)
            py = cy + int(y * size / 32)
            
            # Only include points below the fill percentage
            if percentage >= 100:
                points.append((px, py))
            else:
                # Calculate if this point should be included based on percentage
                # Heart extends from top to bottom, we want to fill from bottom up
                heart_height = size * 1.85  # Approximate heart height
                bottom_y = cy + size * 0.95
                fill_y = bottom_y - (heart_height * percentage / 100)
                
                if py >= fill_y:
                    points.append((px, py))
        
        if points:
            draw.polygon(points, fill=color)
    
    def _ship_img(self, av1, av2, pct):
        # Larger canvas to fit full avatars and bigger heart
        img = Image.new("RGBA", (500, 200), (30, 30, 40, 255))
        draw = ImageDraw.Draw(img)
        
        avatar_size = 100
        # Position avatars with proper spacing
        for av, x in [(av1, 30), (av2, 370)]:
            if av:
                # Create circular mask for perfect circle
                mask = Image.new("L", (avatar_size, avatar_size), 0)
                ImageDraw.Draw(mask).ellipse([0, 0, avatar_size, avatar_size], fill=255)
                # Resize avatar to fit without cropping
                av = av.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                img.paste(av, (x, 30), mask)
            else:
                draw.ellipse([x, 30, x+avatar_size, 30+avatar_size], fill=(80, 80, 100))
        
        # Heart position and size (much bigger and centered)
        hx, hy, hs = 250, 75, 85  # center x, center y, size
        
        # Draw gray background heart (always 100% filled)
        gray_color = (60, 60, 70)
        self._draw_heart(draw, hx, hy, hs, gray_color, percentage=100)
        
        # Draw filled heart overlay based on percentage
        if pct > 0:
            # Color gradient based on percentage
            if pct >= 80:
                fill_color = (255, 50, 100)  # Hot pink/red
            elif pct >= 60:
                fill_color = (255, 100, 120)  # Pink
            elif pct >= 40:
                fill_color = (255, 150, 100)  # Peachy
            elif pct >= 20:
                fill_color = (200, 150, 100)  # Muted
            else:
                fill_color = (150, 100, 100)  # Dull
            
            # Draw filled heart with percentage (no mask that affects avatars)
            self._draw_heart(draw, hx, hy, hs, fill_color, percentage=pct)
        
        # Percentage text centered below heart
        try:
            from pathlib import Path
            font_path = Path("data/assets/fonts/Poppins-SemiBold.ttf")
            if font_path.exists():
                font = ImageFont.truetype(str(font_path), 22)
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        text = f"{pct}%"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text((hx - text_w // 2, hy + hs + 5), text, fill=(255, 255, 255), font=font)
        
        # Convert to RGB for saving
        rgb_img = Image.new("RGB", img.size, (30, 30, 40))
        rgb_img.paste(img, (0, 0), img)
        
        buf = io.BytesIO()
        rgb_img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    async def _tree_img(self, guild, uid, full=False):
        gid = str(guild.id)
        nodes, visited, queue = {}, set(), deque([(uid, 0)])
        while queue:
            cur, depth = queue.popleft()
            if cur in visited or abs(depth) > 4: continue
            visited.add(cur)
            rel = await self.data.get_rel(gid, cur)
            nodes[cur] = {"parent": rel.get("parent"), "children": rel.get("children", []), "partner": rel.get("partner") if full else None, "friends": rel.get("friends", []) if full else [], "depth": depth}
            if rel.get("parent") and rel["parent"] not in visited: queue.append((rel["parent"], depth - 1))
            for c in rel.get("children", []):
                if c not in visited: queue.append((c, depth + 1))
            if full and rel.get("partner") and rel["partner"] not in visited: queue.append((rel["partner"], depth))
            if full:
                for f in rel.get("friends", []):
                    if f not in visited: queue.append((f, depth))
        if not nodes: nodes[uid] = {"parent": None, "children": [], "partner": None, "friends": [], "depth": 0}
        depths = {}
        for nid, nd in nodes.items(): depths.setdefault(nd["depth"], []).append(nid)
        
        # Larger, cleaner layout
        nw, nh, hs, vs = 130, 80, 50, 70
        pos = {}
        for d, nlist in sorted(depths.items()):
            y = (d + 4) * (nh + vs)
            sx = -len(nlist) * (nw + hs) // 2
            for i, nid in enumerate(nlist): pos[nid] = (sx + i * (nw + hs), y)
        
        minx, maxx = min(p[0] for p in pos.values()) - nw, max(p[0] for p in pos.values()) + nw * 2
        miny, maxy = min(p[1] for p in pos.values()) - nh, max(p[1] for p in pos.values()) + nh * 2
        legend_h = 60
        w, h = max(500, maxx - minx + 100), max(400, maxy - miny + 100 + legend_h)
        ox, oy = -minx + 50, -miny + 50
        
        # Dark theme background
        img = Image.new("RGB", (w, h), (25, 28, 38))
        draw = ImageDraw.Draw(img)
        
        # Colors
        parent_line = (100, 180, 255)  # Blue for parent-child
        spouse_line = (255, 100, 150)  # Pink for spouse
        friend_line = (100, 255, 150)  # Green for friends
        card_bg = (40, 45, 60)
        card_border = (70, 80, 100)
        you_border = (139, 92, 246)  # Purple for "you"
        text_color = (255, 255, 255)
        
        # Draw relationship lines FIRST (behind cards)
        for nid, nd in nodes.items():
            x, y = pos[nid][0] + ox, pos[nid][1] + oy
            
            # Parent-child lines (blue, dashed effect with arrow)
            if nd.get("parent") and nd["parent"] in pos:
                px, py = pos[nd["parent"]][0] + ox, pos[nd["parent"]][1] + oy
                mid_y = (y + py + nh) // 2
                # Vertical from child up
                draw.line([(x + nw//2, y), (x + nw//2, mid_y)], fill=parent_line, width=3)
                # Horizontal connector
                draw.line([(x + nw//2, mid_y), (px + nw//2, mid_y)], fill=parent_line, width=3)
                # Vertical down to parent
                draw.line([(px + nw//2, mid_y), (px + nw//2, py + nh)], fill=parent_line, width=3)
            
            # Spouse lines (pink with heart indicator)
            if nd.get("partner") and nd["partner"] in pos and nid < nd["partner"]:
                px, py = pos[nd["partner"]][0] + ox, pos[nd["partner"]][1] + oy
                mid_x = (x + nw + px) // 2
                draw.line([(x + nw, y + nh//2), (px, py + nh//2)], fill=spouse_line, width=4)
                # Simple line indicator
                draw.text((mid_x - 2, y + nh//2 - 8), "—", fill=spouse_line)
            
            # Friend lines (green, dashed)
            if nd.get("friends"):
                for fid in nd["friends"]:
                    if fid in pos and nid < fid:
                        fx, fy = pos[fid][0] + ox, pos[fid][1] + oy
                        # Dashed line effect
                        x1, y1, x2, y2 = x + nw, y + nh//2, fx, fy + nh//2
                        dash_len = 8
                        total_len = ((x2-x1)**2 + (y2-y1)**2)**0.5
                        if total_len > 0:
                            num_dashes = int(total_len / (dash_len * 2))
                            for i in range(num_dashes):
                                t1 = i * 2 * dash_len / total_len
                                t2 = (i * 2 + 1) * dash_len / total_len
                                dx1, dy1 = int(x1 + t1 * (x2-x1)), int(y1 + t1 * (y2-y1))
                                dx2, dy2 = int(x1 + t2 * (x2-x1)), int(y1 + t2 * (y2-y1))
                                draw.line([(dx1, dy1), (dx2, dy2)], fill=friend_line, width=3)
        
        # Fetch avatars
        avs = {}
        for nid in nodes:
            m = guild.get_member(int(nid))
            if m and m.display_avatar: avs[nid] = await self._fetch_av(m.display_avatar.url, 45)
        
        # Draw cards
        for nid in nodes:
            x, y = pos[nid][0] + ox, pos[nid][1] + oy
            m = guild.get_member(int(nid))
            name = m.name[:14] if m else "User"
            is_target = nid == uid
            
            # Card with special border for target user
            border = you_border if is_target else card_border
            draw.rounded_rectangle([x, y, x + nw, y + nh], radius=10, fill=card_bg, outline=border, width=3 if is_target else 2)
            
            # "YOU" label for target
            if is_target:
                draw.rounded_rectangle([x + nw - 35, y - 8, x + nw + 5, y + 12], radius=6, fill=you_border)
                draw.text((x + nw - 30, y - 6), "YOU", fill=(255, 255, 255))
            
            # Avatar
            ax, ay = x + (nw - 45) // 2, y + 5
            if avs.get(nid): img.paste(avs[nid], (int(ax), int(ay)), avs[nid])
            else: draw.ellipse([ax, ay, ax + 45, ay + 45], fill=(80, 85, 100))
            
            # Name centered below avatar
            bbox = draw.textbbox((0, 0), name)
            tw = bbox[2] - bbox[0]
            draw.text((x + (nw - tw) // 2, y + 54), name, fill=text_color)
        
        # Legend at bottom
        ly = h - legend_h + 10
        draw.rounded_rectangle([20, ly - 5, w - 20, h - 10], radius=8, fill=(35, 40, 55))
        draw.text((30, ly + 5), "LEGEND:", fill=(180, 180, 200))
        
        # Parent-child legend
        draw.line([(110, ly + 15), (150, ly + 15)], fill=parent_line, width=3)
        draw.text((160, ly + 5), "Parent → Child", fill=parent_line)
        
        # Spouse legend
        draw.line([(290, ly + 15), (320, ly + 15)], fill=spouse_line, width=4)
        draw.text((325, ly + 5), "—", fill=spouse_line)
        draw.text((340, ly + 5), "Partner", fill=spouse_line)
        
        # Friend legend (dashed)
        for i in range(4):
            draw.line([(450 + i*10, ly + 15), (456 + i*10, ly + 15)], fill=friend_line, width=3)
        draw.text((500, ly + 5), "Friends", fill=friend_line)
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    @commands.command(name="ship")
    async def ship_cmd(self, ctx, u1: discord.Member, u2: discord.Member = None):
        u2 = u2 or ctx.author
        random.seed(int(u1.id) + int(u2.id))
        pct = random.randint(0, 100)
        random.seed()
        av1 = await self._fetch_av(u1.display_avatar.url, 100) if u1.display_avatar else None
        av2 = await self._fetch_av(u2.display_avatar.url, 100) if u2.display_avatar else None
        buf = self._ship_img(av1, av2, pct)
        n1, n2 = u1.display_name, u2.display_name
        ship_name = n1[:len(n1)//2] + n2[len(n2)//2:]
        rating = "Soulmates!" if pct >= 90 else "Great match!" if pct >= 70 else "Could work" if pct >= 50 else "Maybe..." if pct >= 30 else "Not meant to be"
        embed = discord.Embed(title=f"**{ship_name}**", description=f"{u1.mention} x {u2.mention}\n\n**{rating}**", color=discord.Color.from_rgb(255, 100, 150))
        embed.set_image(url="attachment://ship.png")
        await ctx.reply(embed=embed, file=discord.File(buf, "ship.png"), mention_author=False)

    @commands.command(name="marry", aliases=["propose"])
    async def propose_cmd(self, ctx, target: discord.Member):
        if target.id == ctx.author.id or target.bot: return await ctx.reply("Invalid target!", mention_author=False)
        gid, uid, tid = str(ctx.guild.id), str(ctx.author.id), str(target.id)
        if (await self.data.get_rel(gid, uid)).get("partner"): return await ctx.reply("You're already married!", mention_author=False)
        if (await self.data.get_rel(gid, tid)).get("partner"): return await ctx.reply(f"{target.display_name} is already married!", mention_author=False)
        view = ProposalView(self, ctx.author, target, gid)
        view.message = await ctx.send(embed=discord.Embed(title="Marriage Proposal", description=f"{ctx.author.mention} proposes to {target.mention}!", color=discord.Color.pink()), view=view)

    @commands.command(name="divorce")
    async def divorce_cmd(self, ctx, target: discord.Member = None):
        gid, uid = str(ctx.guild.id), str(ctx.author.id)
        pid = (await self.data.get_rel(gid, uid)).get("partner")
        if not pid: return await ctx.reply("You're not married!", mention_author=False)
        if target and str(target.id) != pid: return await ctx.reply("That's not your partner!", mention_author=False)
        await self.data.remove_partner(gid, uid)
        p = ctx.guild.get_member(int(pid))
        await ctx.reply(embed=discord.Embed(title="Divorce Finalized", description=f"{ctx.author.mention} divorced {p.display_name if p else 'partner'}.", color=discord.Color.dark_gray()), mention_author=False)

    @commands.command(name="adopt", aliases=["adoptchild"])
    async def adopt_cmd(self, ctx, target: discord.Member):
        if target.id == ctx.author.id or target.bot: return await ctx.reply("Invalid target!", mention_author=False)
        gid, uid, tid = str(ctx.guild.id), str(ctx.author.id), str(target.id)
        if (await self.data.get_rel(gid, tid)).get("parent"): return await ctx.reply(f"{target.display_name} already has a parent!", mention_author=False)
        if len((await self.data.get_rel(gid, uid)).get("children", [])) >= 10: return await ctx.reply("Max 10 children!", mention_author=False)
        view = AdoptView(self, ctx.author, target, gid)
        view.message = await ctx.send(embed=discord.Embed(title="Adoption Request", description=f"{ctx.author.mention} wants to adopt {target.mention}!", color=discord.Color.blue()), view=view)

    @commands.command(name="parentme", aliases=["makeparent", "getparent", "askparent"])
    async def makeparent_cmd(self, ctx, target: discord.Member):
        if target.id == ctx.author.id or target.bot: return await ctx.reply("Invalid target!", mention_author=False)
        gid, uid, tid = str(ctx.guild.id), str(ctx.author.id), str(target.id)
        if (await self.data.get_rel(gid, uid)).get("parent"): return await ctx.reply("You already have a parent!", mention_author=False)
        view = MakeParentView(self, ctx.author, target, gid)
        view.message = await ctx.send(embed=discord.Embed(title="Parent Request", description=f"{ctx.author.mention} asks {target.mention} to be their parent!", color=discord.Color.blue()), view=view)

    @commands.command(name="disown", aliases=["disownchild"])
    async def disown_cmd(self, ctx, target: discord.Member):
        gid, uid, tid = str(ctx.guild.id), str(ctx.author.id), str(target.id)
        if tid not in (await self.data.get_rel(gid, uid)).get("children", []): return await ctx.reply(f"{target.display_name} is not your child!", mention_author=False)
        await self.data.disown(gid, uid, tid)
        await ctx.reply(embed=discord.Embed(description=f"{ctx.author.mention} disowned {target.mention}.", color=discord.Color.dark_gray()), mention_author=False)

    @commands.command(name="runaway", aliases=["emancipate", "leavehome", "escape"])
    async def runaway_cmd(self, ctx, target: discord.Member = None):
        gid, uid = str(ctx.guild.id), str(ctx.author.id)
        pid = (await self.data.get_rel(gid, uid)).get("parent")
        if not pid: return await ctx.reply("You don't have a parent to runaway from!", mention_author=False)
        if target and str(target.id) != pid: return await ctx.reply("That's not your parent!", mention_author=False)
        await self.data.emancipate(gid, uid)
        p = ctx.guild.get_member(int(pid))
        runaway_messages = [
            f"{ctx.author.mention} packed their bags and ran away from home!",
            f"{ctx.author.mention} disappeared into the night...",
            f"{ctx.author.mention} decided it's time to find their own path!",
            f"{ctx.author.mention} broke free and started a new journey!",
        ]
        message = random.choice(runaway_messages)
        embed = discord.Embed(
            title="Runaway Success!",
            description=f"{message}\n\nThey're no longer under {p.display_name if p else 'parent'}'s care.",
            color=discord.Color.dark_gray()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="partner", aliases=["lover", "spouse", "marriage"])
    async def partner_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        pid = (await self.data.get_rel(str(ctx.guild.id), str(target.id))).get("partner")
        if pid:
            p = ctx.guild.get_member(int(pid))
            desc = f"{target.display_name}'s partner: {p.mention if p else f'<@{pid}>'}"
        else: desc = f"{target.display_name} is single."
        await ctx.reply(embed=discord.Embed(description=desc, color=discord.Color.pink()), mention_author=False)

    @commands.command(name="parent")
    async def parent_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        pid = (await self.data.get_rel(str(ctx.guild.id), str(target.id))).get("parent")
        if pid:
            p = ctx.guild.get_member(int(pid))
            desc = f"{target.display_name}'s parent: {p.mention if p else f'<@{pid}>'}"
        else: desc = f"{target.display_name} has no parent."
        await ctx.reply(embed=discord.Embed(description=desc, color=discord.Color.blue()), mention_author=False)

    @commands.command(name="relationship")
    async def relationship_cmd(self, ctx, u1: discord.Member, u2: discord.Member = None):
        u2 = u2 or ctx.author
        gid = str(ctx.guild.id)
        r1, r2 = await self.data.get_rel(gid, str(u1.id)), await self.data.get_rel(gid, str(u2.id))
        rels = []
        if r1.get("partner") == str(u2.id): rels.append("Partners")
        if r1.get("parent") == str(u2.id): rels.append(f"{u2.display_name} is {u1.display_name}'s parent")
        if r2.get("parent") == str(u1.id): rels.append(f"{u1.display_name} is {u2.display_name}'s parent")
        desc = "\n".join(rels) if rels else "No direct relationship."
        await ctx.reply(embed=discord.Embed(title=f"{u1.display_name} & {u2.display_name}", description=desc, color=discord.Color.purple()), mention_author=False)
    
    @commands.group(name="tree", aliases=['family'])
    async def tree(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        async with ctx.typing():
            buf = await self._tree_img(ctx.guild, str(target.id), full=True)
        embed = discord.Embed(title=f"{target.name}'s Family & Friends Tree", color=discord.Color.green())
        embed.set_image(url="attachment://tree.png")
        await ctx.reply(embed=embed, file=discord.File(buf, "tree.png"), mention_author=False)

    @tree.command(name="size")
    async def familysize_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        size = await self.data.get_family_size(str(ctx.guild.id), str(target.id))
        await ctx.reply(embed=discord.Embed(description=f"{target.display_name}'s family has **{size}** members.", color=discord.Color.purple()), mention_author=False)

    
    @commands.command(name="befriend", aliases=["addfriend"])
    async def befriend_cmd(self, ctx, target: discord.Member):
        if target.id == ctx.author.id or target.bot: return await ctx.reply("Invalid target!", mention_author=False)
        gid, uid, tid = str(ctx.guild.id), str(ctx.author.id), str(target.id)
        rel = await self.data.get_rel(gid, uid)
        if tid in rel.get("friends", []): return await ctx.reply(f"You're already friends with {target.display_name}!", mention_author=False)
        if len(rel.get("friends", [])) >= 20: return await ctx.reply("Max 20 friends!", mention_author=False)
        view = BefriendView(self, ctx.author, target, gid)
        view.message = await ctx.send(embed=discord.Embed(title="Friend Request", description=f"{ctx.author.mention} wants to be friends with {target.mention}!", color=discord.Color.green()), view=view)
    
    @commands.command(name="unfriend", aliases=["removefriend"])
    async def unfriend_cmd(self, ctx, target: discord.Member):
        gid, uid, tid = str(ctx.guild.id), str(ctx.author.id), str(target.id)
        rel = await self.data.get_rel(gid, uid)
        if tid not in rel.get("friends", []): return await ctx.reply(f"{target.display_name} is not your friend!", mention_author=False)
        await self.data.remove_friend(gid, uid, tid)
        await ctx.reply(embed=discord.Embed(description=f"{ctx.author.mention} unfriended {target.mention}.", color=discord.Color.dark_gray()), mention_author=False)
    
    @commands.command(name="friends", aliases=["friendlist"])
    async def friends_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        friends = (await self.data.get_rel(str(ctx.guild.id), str(target.id))).get("friends", [])
        if friends:
            friend_mentions = []
            for fid in friends[:20]:
                f = ctx.guild.get_member(int(fid))
                friend_mentions.append(f.mention if f else f"<@{fid}>")
            desc = "\n".join(friend_mentions)
        else:
            desc = f"{target.display_name} has no friends yet."
        embed = discord.Embed(title=f"{target.display_name}'s Friends ({len(friends)})", description=desc, color=discord.Color.green())
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.command(name="iq")
    async def iq_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        iq = await self.data.maybe_change_iq(str(ctx.guild.id), str(target.id))
        rating = "Genius" if iq >= 140 else "Very Smart" if iq >= 120 else "Above Average" if iq >= 110 else "Average" if iq >= 90 else "Below Average" if iq >= 70 else "Low"
        await ctx.reply(embed=discord.Embed(description=f"**{target.display_name}**'s IQ: **{iq}** ({rating})", color=discord.Color.blurple()), mention_author=False)
    
    @commands.command(name="strength", aliases=["str"])
    async def strength_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        strength = await self.data.get_stat(str(ctx.guild.id), str(target.id), "strength", 1, 100)
        rating = "Godlike" if strength >= 95 else "Superhuman" if strength >= 85 else "Very Strong" if strength >= 70 else "Strong" if strength >= 50 else "Average" if strength >= 30 else "Weak"
        await ctx.reply(embed=discord.Embed(description=f"💪 **{target.display_name}**'s Strength: **{strength}/100** ({rating})", color=discord.Color.red()), mention_author=False)
    
    @commands.command(name="speed", aliases=["spd"])
    async def speed_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        speed = await self.data.get_stat(str(ctx.guild.id), str(target.id), "speed", 1, 100)
        rating = "Lightning Fast" if speed >= 95 else "Very Fast" if speed >= 85 else "Fast" if speed >= 70 else "Quick" if speed >= 50 else "Average" if speed >= 30 else "Slow"
        await ctx.reply(embed=discord.Embed(description=f"⚡ **{target.display_name}**'s Speed: **{speed}/100** ({rating})", color=discord.Color.gold()), mention_author=False)
    
    @commands.command(name="charisma", aliases=["rizz"])
    async def charisma_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        charisma = await self.data.get_stat(str(ctx.guild.id), str(target.id), "charisma", 1, 100)
        rating = "Legendary Charm" if charisma >= 95 else "Very Charismatic" if charisma >= 85 else "Charismatic" if charisma >= 70 else "Charming" if charisma >= 50 else "Average" if charisma >= 30 else "Awkward"
        await ctx.reply(embed=discord.Embed(description=f"✨ **{target.display_name}**'s Charisma: **{charisma}/100** ({rating})", color=discord.Color.purple()), mention_author=False)
    
    @commands.command(name="luck", aliases=["lck"])
    async def luck_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        luck = await self.data.get_stat(str(ctx.guild.id), str(target.id), "luck", 1, 100)
        rating = "Blessed" if luck >= 95 else "Very Lucky" if luck >= 85 else "Lucky" if luck >= 70 else "Fortunate" if luck >= 50 else "Average" if luck >= 30 else "Unlucky"
        await ctx.reply(embed=discord.Embed(description=f"🍀 **{target.display_name}**'s Luck: **{luck}/100** ({rating})", color=discord.Color.green()), mention_author=False)
    
 

class ProposalView(discord.ui.View):
    def __init__(self, cog, proposer, target, gid):
        super().__init__(timeout=60)
        self.cog, self.proposer, self.target, self.gid, self.message = cog, proposer, target, gid, None
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, i, b):
        if i.user.id != self.target.id: return await i.response.send_message("Not for you!", ephemeral=True)
        await self.cog.data.set_partner(self.gid, str(self.proposer.id), str(self.target.id))
        await i.response.edit_message(embed=discord.Embed(title="Just Married!", description=f"{self.proposer.mention} and {self.target.mention} are married!", color=discord.Color.gold()), view=None)
        self.stop()
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, i, b):
        if i.user.id != self.target.id: return await i.response.send_message("Not for you!", ephemeral=True)
        await i.response.edit_message(embed=discord.Embed(title="Declined", description=f"{self.target.mention} declined.", color=discord.Color.dark_gray()), view=None)
        self.stop()
    async def on_timeout(self):
        if self.message:
            try: await self.message.edit(embed=discord.Embed(title="Expired", color=discord.Color.dark_gray()), view=None)
            except: pass

class AdoptView(discord.ui.View):
    def __init__(self, cog, parent, child, gid):
        super().__init__(timeout=60)
        self.cog, self.parent, self.child, self.gid, self.message = cog, parent, child, gid, None
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, i, b):
        if i.user.id != self.child.id: return await i.response.send_message("Not for you!", ephemeral=True)
        await self.cog.data.adopt(self.gid, str(self.parent.id), str(self.child.id))
        await i.response.edit_message(embed=discord.Embed(title="Adopted!", description=f"{self.parent.mention} adopted {self.child.mention}!", color=discord.Color.blue()), view=None)
        self.stop()
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, i, b):
        if i.user.id != self.child.id: return await i.response.send_message("Not for you!", ephemeral=True)
        await i.response.edit_message(embed=discord.Embed(title="Declined", color=discord.Color.dark_gray()), view=None)
        self.stop()
    async def on_timeout(self):
        if self.message:
            try: await self.message.edit(embed=discord.Embed(title="Expired", color=discord.Color.dark_gray()), view=None)
            except: pass

class MakeParentView(discord.ui.View):
    def __init__(self, cog, child, parent, gid):
        super().__init__(timeout=60)
        self.cog, self.child, self.parent, self.gid, self.message = cog, child, parent, gid, None
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, i, b):
        if i.user.id != self.parent.id: return await i.response.send_message("Not for you!", ephemeral=True)
        await self.cog.data.adopt(self.gid, str(self.parent.id), str(self.child.id))
        await i.response.edit_message(embed=discord.Embed(title="Parent Accepted!", description=f"{self.parent.mention} is now {self.child.mention}'s parent!", color=discord.Color.blue()), view=None)
        self.stop()
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, i, b):
        if i.user.id != self.parent.id: return await i.response.send_message("Not for you!", ephemeral=True)
        await i.response.edit_message(embed=discord.Embed(title="Declined", color=discord.Color.dark_gray()), view=None)
        self.stop()
    async def on_timeout(self):
        if self.message:
            try: await self.message.edit(embed=discord.Embed(title="Expired", color=discord.Color.dark_gray()), view=None)
            except: pass

class BefriendView(discord.ui.View):
    def __init__(self, cog, requester, target, gid):
        super().__init__(timeout=60)
        self.cog, self.requester, self.target, self.gid, self.message = cog, requester, target, gid, None
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, i, b):
        if i.user.id != self.target.id: return await i.response.send_message("Not for you!", ephemeral=True)
        await self.cog.data.add_friend(self.gid, str(self.requester.id), str(self.target.id))
        await i.response.edit_message(embed=discord.Embed(title="Friends!", description=f"{self.requester.mention} and {self.target.mention} are now friends!", color=discord.Color.green()), view=None)
        self.stop()
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, i, b):
        if i.user.id != self.target.id: return await i.response.send_message("Not for you!", ephemeral=True)
        await i.response.edit_message(embed=discord.Embed(title="Declined", color=discord.Color.dark_gray()), view=None)
        self.stop()
    async def on_timeout(self):
        if self.message:
            try: await self.message.edit(embed=discord.Embed(title="Expired", color=discord.Color.dark_gray()), view=None)
            except: pass

async def setup(bot): await bot.add_cog(Social(bot))
