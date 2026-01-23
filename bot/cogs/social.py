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
        return doc or {"partner": None, "parent": None, "children": []}
    
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

    def _ship_img(self, av1, av2, pct):
        img = Image.new("RGB", (400, 150), (30, 30, 40))
        draw = ImageDraw.Draw(img)
        for av, x in [(av1, 30), (av2, 270)]:
            if av:
                mask = Image.new("L", (100, 100), 0)
                ImageDraw.Draw(mask).ellipse([0, 0, 100, 100], fill=255)
                av = av.resize((100, 100))
                img.paste(av, (x, 25), mask)
            else:
                draw.ellipse([x, 25, x+100, 125], fill=(80, 80, 100))
        hx, hy, hs = 165, 35, 70
        r = hs // 4
        draw.ellipse([hx, hy, hx+hs//2, hy+hs//2], fill=(60, 60, 70))
        draw.ellipse([hx+hs//2, hy, hx+hs, hy+hs//2], fill=(60, 60, 70))
        draw.polygon([(hx, hy+r), (hx+hs, hy+r), (hx+hs//2, hy+hs)], fill=(60, 60, 70))
        if pct > 0:
            for py in range(hy + hs - int(hs * pct / 100), hy + hs):
                for px in range(hx, hx + hs):
                    try:
                        if img.getpixel((px, py)) == (60, 60, 70): img.putpixel((px, py), (255, 50, 80))
                    except: pass
        draw.text((hx + 25, hy + hs + 5), f"{pct}%", fill=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
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
            nodes[cur] = {"parent": rel.get("parent"), "children": rel.get("children", []), "partner": rel.get("partner") if full else None, "depth": depth}
            if rel.get("parent") and rel["parent"] not in visited: queue.append((rel["parent"], depth - 1))
            for c in rel.get("children", []):
                if c not in visited: queue.append((c, depth + 1))
            if full and rel.get("partner") and rel["partner"] not in visited: queue.append((rel["partner"], depth))
        if not nodes: nodes[uid] = {"parent": None, "children": [], "partner": None, "depth": 0}
        depths = {}
        for nid, nd in nodes.items(): depths.setdefault(nd["depth"], []).append(nid)
        nw, nh, hs, vs, pos = 110, 70, 30, 50, {}
        for d, nlist in sorted(depths.items()):
            y, tw, sx = (d + 4) * (nh + vs), len(nlist) * (nw + hs), -len(nlist) * (nw + hs) // 2
            for i, nid in enumerate(nlist): pos[nid] = (sx + i * (nw + hs), y)
        minx, maxx = min(p[0] for p in pos.values()) - nw, max(p[0] for p in pos.values()) + nw * 2
        miny, maxy = min(p[1] for p in pos.values()) - nh, max(p[1] for p in pos.values()) + nh * 2
        w, h, ox, oy = max(400, maxx - minx + 80), max(300, maxy - miny + 80), -minx + 40, -miny + 40
        img = Image.new("RGB", (w, h), (250, 250, 255))
        draw = ImageDraw.Draw(img)
        for nid, nd in nodes.items():
            x, y = pos[nid][0] + ox, pos[nid][1] + oy
            if nd.get("parent") and nd["parent"] in pos:
                px, py = pos[nd["parent"]][0] + ox, pos[nd["parent"]][1] + oy
                mid = (y + py + nh) // 2
                draw.line([(x + nw//2, y), (x + nw//2, mid)], fill=(100, 100, 100), width=2)
                draw.line([(x + nw//2, mid), (px + nw//2, mid)], fill=(100, 100, 100), width=2)
                draw.line([(px + nw//2, mid), (px + nw//2, py + nh)], fill=(100, 100, 100), width=2)
            if nd.get("partner") and nd["partner"] in pos and nid < nd["partner"]:
                px, py = pos[nd["partner"]][0] + ox, pos[nd["partner"]][1] + oy
                draw.line([(x + nw, y + nh//2), (px, py + nh//2)], fill=(255, 100, 100), width=3)
        avs = {}
        for nid in nodes:
            m = guild.get_member(int(nid))
            if m and m.display_avatar: avs[nid] = await self._fetch_av(m.display_avatar.url, 40)
        for nid in nodes:
            x, y = pos[nid][0] + ox, pos[nid][1] + oy
            m = guild.get_member(int(nid))
            name = m.display_name[:12] if m else "User"
            draw.rounded_rectangle([x, y, x + nw, y + nh], radius=6, fill=(220, 220, 240), outline=(100, 100, 120), width=2)
            ax, ay = x + (nw - 40) // 2, y + 3
            if avs.get(nid): img.paste(avs[nid], (int(ax), int(ay)), avs[nid])
            else: draw.ellipse([ax, ay, ax + 40, ay + 40], fill=(180, 180, 200))
            draw.text((x + 5, y + 48), name, fill=(40, 40, 50))
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

    @commands.command(name="propose")
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

    @commands.command(name="adopt")
    async def adopt_cmd(self, ctx, target: discord.Member):
        if target.id == ctx.author.id or target.bot: return await ctx.reply("Invalid target!", mention_author=False)
        gid, uid, tid = str(ctx.guild.id), str(ctx.author.id), str(target.id)
        if (await self.data.get_rel(gid, tid)).get("parent"): return await ctx.reply(f"{target.display_name} already has a parent!", mention_author=False)
        if len((await self.data.get_rel(gid, uid)).get("children", [])) >= 10: return await ctx.reply("Max 10 children!", mention_author=False)
        view = AdoptView(self, ctx.author, target, gid)
        view.message = await ctx.send(embed=discord.Embed(title="Adoption Request", description=f"{ctx.author.mention} wants to adopt {target.mention}!", color=discord.Color.blue()), view=view)

    @commands.command(name="makeparent")
    async def makeparent_cmd(self, ctx, target: discord.Member):
        if target.id == ctx.author.id or target.bot: return await ctx.reply("Invalid target!", mention_author=False)
        gid, uid, tid = str(ctx.guild.id), str(ctx.author.id), str(target.id)
        if (await self.data.get_rel(gid, uid)).get("parent"): return await ctx.reply("You already have a parent!", mention_author=False)
        view = MakeParentView(self, ctx.author, target, gid)
        view.message = await ctx.send(embed=discord.Embed(title="Parent Request", description=f"{ctx.author.mention} asks {target.mention} to be their parent!", color=discord.Color.blue()), view=view)

    @commands.command(name="disown")
    async def disown_cmd(self, ctx, target: discord.Member):
        gid, uid, tid = str(ctx.guild.id), str(ctx.author.id), str(target.id)
        if tid not in (await self.data.get_rel(gid, uid)).get("children", []): return await ctx.reply(f"{target.display_name} is not your child!", mention_author=False)
        await self.data.disown(gid, uid, tid)
        await ctx.reply(embed=discord.Embed(description=f"{ctx.author.mention} disowned {target.mention}.", color=discord.Color.dark_gray()), mention_author=False)

    @commands.command(name="emancipate")
    async def emancipate_cmd(self, ctx, target: discord.Member = None):
        gid, uid = str(ctx.guild.id), str(ctx.author.id)
        pid = (await self.data.get_rel(gid, uid)).get("parent")
        if not pid: return await ctx.reply("You don't have a parent!", mention_author=False)
        if target and str(target.id) != pid: return await ctx.reply("That's not your parent!", mention_author=False)
        await self.data.emancipate(gid, uid)
        p = ctx.guild.get_member(int(pid))
        await ctx.reply(embed=discord.Embed(description=f"{ctx.author.mention} ran away from {p.display_name if p else 'parent'}.", color=discord.Color.dark_gray()), mention_author=False)

    @commands.command(name="partner")
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

    @commands.command(name="familysize")
    async def familysize_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        size = await self.data.get_family_size(str(ctx.guild.id), str(target.id))
        await ctx.reply(embed=discord.Embed(description=f"{target.display_name}'s family has **{size}** members.", color=discord.Color.purple()), mention_author=False)

    @commands.command(name="tree")
    async def tree_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        async with ctx.typing():
            buf = await self._tree_img(ctx.guild, str(target.id), full=False)
        embed = discord.Embed(title=f"{target.display_name}'s Family Tree", color=discord.Color.green())
        embed.set_image(url="attachment://tree.png")
        await ctx.reply(embed=embed, file=discord.File(buf, "tree.png"), mention_author=False)

    @commands.command(name="stupidtree")
    async def stupidtree_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        async with ctx.typing():
            buf = await self._tree_img(ctx.guild, str(target.id), full=True)
        embed = discord.Embed(title=f"{target.display_name}'s Full Family Tree", description="Blood + Marriage", color=discord.Color.orange())
        embed.set_image(url="attachment://tree.png")
        await ctx.reply(embed=embed, file=discord.File(buf, "tree.png"), mention_author=False)

    @commands.command(name="iq")
    async def iq_cmd(self, ctx, target: discord.Member = None):
        target = target or ctx.author
        iq = await self.data.maybe_change_iq(str(ctx.guild.id), str(target.id))
        await ctx.reply(embed=discord.Embed(description=f"**{target.display_name}**'s IQ is **{iq}**", color=discord.Color.blurple()), mention_author=False)

    @commands.command(name="treefile")
    async def treefile_cmd(self, ctx, target: discord.Member = None):
        """Export family tree as GEDCOM file"""
        target = target or ctx.author
        gid, uid = str(ctx.guild.id), str(target.id)
        
        # Build family data
        nodes, visited, queue = {}, set(), deque([uid])
        while queue:
            cur = queue.popleft()
            if cur in visited: continue
            visited.add(cur)
            rel = await self.data.get_rel(gid, cur)
            nodes[cur] = rel
            if rel.get("parent") and rel["parent"] not in visited: queue.append(rel["parent"])
            for c in rel.get("children", []):
                if c not in visited: queue.append(c)
            if rel.get("partner") and rel["partner"] not in visited: queue.append(rel["partner"])
        
        # Generate GEDCOM
        lines = ["0 HEAD", "1 SOUR AnyaBot", "1 GEDC", "2 VERS 5.5.1", "1 CHAR UTF-8", "0 @SUB@ SUBM", "1 NAME AnyaBot"]
        
        # Individuals
        for uid in nodes:
            m = ctx.guild.get_member(int(uid))
            name = m.display_name if m else f"User_{uid[:8]}"
            lines.append(f"0 @I{uid}@ INDI")
            lines.append(f"1 NAME {name}")
        
        # Families
        fam_id = 1
        processed = set()
        for uid, rel in nodes.items():
            if rel.get("partner") and uid < rel["partner"]:
                pid = rel["partner"]
                lines.append(f"0 @F{fam_id}@ FAM")
                lines.append(f"1 HUSB @I{uid}@")
                lines.append(f"1 WIFE @I{pid}@")
                # Add children of this couple
                for cid in rel.get("children", []):
                    lines.append(f"1 CHIL @I{cid}@")
                fam_id += 1
        
        lines.append("0 TRLR")
        
        content = "\n".join(lines)
        buf = io.BytesIO(content.encode("utf-8"))
        buf.seek(0)
        
        await ctx.reply(f"Family tree for {target.display_name}", file=discord.File(buf, f"{target.display_name}_family.ged"), mention_author=False)

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

async def setup(bot): await bot.add_cog(Social(bot))
