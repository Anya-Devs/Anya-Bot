import discord
from discord.ext import commands

from utils.character_utils import build_character_embed_with_files, get_character_def
from utils.cogs.quest import Quest_Data

import time
import json
from pathlib import Path
import random


class CharacterView(discord.ui.View):
    def __init__(self, bot: commands.Bot, quest_data: Quest_Data, ctx: commands.Context, char_id: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.quest_data = quest_data
        self.ctx = ctx
        self.char_id = char_id

        self.message: discord.Message | None = None

        self.image_index: int = 0

        self.last_dialogue: str | None = None

        self.FEED_INTERVAL_SECONDS: int = 6 * 60 * 60

        self._rebuild_components()

    def _rebuild_components(self) -> None:
        self.clear_items()

        self.add_item(CharacterImageSelect(self))

        self.inv_btn = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Inventory",
            custom_id="character_inventory",
        )
        self.inv_btn.callback = self.inventory_callback
        self.add_item(self.inv_btn)

        self.feed_btn = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Feed",
            custom_id="character_feed",
        )
        self.feed_btn.callback = self.feed_callback
        self.add_item(self.feed_btn)

    async def _get_bucket(self, category_key: str) -> dict:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.{category_key}": 1},
            )
            return (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get(category_key, {})
            )
        except Exception:
            return {}

    async def _get_selected_character(self) -> str | None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.selected_character": 1},
            )
            bucket = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("selected_character", {})
            )
        except Exception:
            bucket = {}
        if isinstance(bucket, dict):
            for k, v in bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        return k
                except Exception:
                    continue
        return None

    async def _set_selected_character(self, char_id: str) -> None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.selected_character": 1},
            )
            bucket = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("selected_character", {})
            )
        except Exception:
            bucket = {}

        if isinstance(bucket, dict):
            for k, v in bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.selected_character", k, -int(v))
                except Exception:
                    continue
        await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.selected_character", char_id, 1)

    async def _get_equipped_item(self) -> str | None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.equipped_items": 1},
            )
            bucket = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("equipped_items", {})
            )
        except Exception:
            bucket = {}

        if isinstance(bucket, dict):
            for k, v in bucket.items():
                if k == self.char_id:
                    try:
                        return str(v) if v else None
                    except Exception:
                        return None
        return None

    async def _set_equipped_item(self, item_name: str | None) -> None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.inventory.sxf.equipped_items.{self.char_id}": item_name or ""}},
                upsert=True,
            )
        except Exception:
            return

    async def inventory_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This is not your character view.", ephemeral=True)

        items_bucket = await self._get_bucket("items")
        meals_bucket = await self._get_bucket("meals")
        chars_bucket = await self._get_bucket("characters")
        equipped = await self._get_equipped_item()
        selected_char = await self._get_selected_character()

        items = []
        if isinstance(items_bucket, dict):
            for k, v in items_bucket.items():
                if isinstance(v, int) and v > 0:
                    items.append((k, v))
        items.sort(key=lambda t: (t[0].lower(), -t[1]))

        meals = []
        if isinstance(meals_bucket, dict):
            for k, v in meals_bucket.items():
                if isinstance(v, int) and v > 0:
                    meals.append((k, v))
        meals.sort(key=lambda t: (t[0].lower(), -t[1]))

        owned_chars: list[tuple[str, int]] = []
        if isinstance(chars_bucket, dict):
            for k, v in chars_bucket.items():
                if isinstance(v, int) and v > 0:
                    owned_chars.append((k, v))
        owned_chars.sort(key=lambda t: (t[0].lower(), -t[1]))

        items_embed = discord.Embed(
            title="🎒 Inventory - Items",
            description=(
                "Select an item to equip it to this character.\n"
                + (f"Currently equipped: **{equipped}**" if equipped else "Currently equipped: **None**")
            ),
            color=discord.Color.blurple(),
        )
        if items:
            lines = [f"- **{name}** `x{qty}`" for name, qty in items[:20]]
            items_embed.add_field(name="Items", value="\n".join(lines), inline=False)
        else:
            items_embed.add_field(name="Items", value="No items.", inline=False)

        food_embed = discord.Embed(
            title="🍽️ Inventory - Food",
            description="Select a meal to feed (consumes 1).",
            color=discord.Color.green(),
        )
        if meals:
            lines = [f"- **{name}** `x{qty}`" for name, qty in meals[:20]]
            food_embed.add_field(name="Meals", value="\n".join(lines), inline=False)
        else:
            food_embed.add_field(name="Meals", value="No meals. Cook something first.", inline=False)

        inv_view = CharacterInventoryView(self, items=items, meals=meals, owned_chars=owned_chars, selected_char=selected_char)
        await interaction.response.send_message(
            embeds=[items_embed, food_embed],
            view=inv_view,
            ephemeral=True,
        )

    async def refresh_message(self) -> None:
        char_def = get_character_def(self.char_id)
        if not char_def:
            return

        hp, _max_hp = await self._get_hp()
        self.image_index = await self._get_selected_image_index()

        next_feed_ts, next_feed_in = await self._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=self.ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=self.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=next_feed_in,
            dialogue_footer=self.last_dialogue,
        )
        try:
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=self, attachments=[], files=files)
                except TypeError:
                    await self.message.edit(embed=embed, view=self)
        except Exception:
            return

    async def _get_selected_image_index(self) -> int:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        idx = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.selected_character_image", self.char_id)
        try:
            return max(0, int(idx or 0))
        except Exception:
            return 0

    async def _set_selected_image_index(self, idx: int) -> None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        current = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.selected_character_image", self.char_id)
        try:
            current = int(current or 0)
        except Exception:
            current = 0
        idx = max(0, int(idx))
        delta = idx - current
        if delta:
            await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.selected_character_image", self.char_id, delta)

    async def _get_hp(self) -> tuple[int, int]:
        char_def = get_character_def(self.char_id)
        if not char_def:
            return 0, 1

        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)

        max_hp = max(1, int(char_def.base_hp))
        stored = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.character_hp", self.char_id)
        hp = int(stored or max_hp)
        hp = max(0, min(hp, max_hp))
        return hp, max_hp

    async def _set_hp(self, hp: int):
        char_def = get_character_def(self.char_id)
        if not char_def:
            return

        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)

        max_hp = max(1, int(char_def.base_hp))
        hp = max(0, min(int(hp), max_hp))

        current = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.character_hp", self.char_id)
        current = int(current or max_hp)
        delta = hp - current
        if delta:
            await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.character_hp", self.char_id, delta)

    async def refresh(self, interaction: discord.Interaction):
        char_def = get_character_def(self.char_id)
        if not char_def:
            if interaction.response.is_done():
                return await interaction.followup.send("Character not found.", ephemeral=True)
            return await interaction.response.send_message("Character not found.", ephemeral=True)

        hp, _max_hp = await self._get_hp()
        self.image_index = await self._get_selected_image_index()
        next_feed_ts, next_feed_in = await self._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=self.ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=self.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=next_feed_in,
            dialogue_footer=self.last_dialogue,
        )

        if self.message and interaction.message and interaction.message.id != self.message.id:
            try:
                await self.message.edit(embed=embed, view=self, attachments=[], files=files)
            except TypeError:
                await self.message.edit(embed=embed, view=self)
            return
        if interaction.response.is_done():
            try:
                await interaction.edit_original_response(embed=embed, view=self, attachments=[], files=files)
            except TypeError:
                await interaction.edit_original_response(embed=embed, view=self)
        else:
            try:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[], files=files)
            except TypeError:
                await interaction.response.edit_message(embed=embed, view=self)

    async def feed_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This is not your character view.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        char_def = get_character_def(self.char_id)
        if not char_def:
            return await interaction.followup.send("Character not found.", ephemeral=True)

        next_feed_ts, _next_feed_in = await self._get_next_feed_info()
        if next_feed_ts is not None:
            now = int(time.time())
            if now < int(next_feed_ts):
                msg = await self._unique_not_hungry_dialogue(char_def)
                self.last_dialogue = msg
                await interaction.followup.send(
                    f"{char_def.emoji} **{self._display_name(char_def)}**: {msg}\n\nNext feed: <t:{int(next_feed_ts)}:R>",
                    ephemeral=True,
                )
                await self.refresh(interaction)
                return

        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)

        # Fetch the raw member inventory document to list meals (best-effort)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.meals": 1},
            )
            meal_bucket = (((doc or {}).get("members") or {}).get(user_id) or {}).get("inventory", {}).get("sxf", {}).get("meals", {})
        except Exception:
            meal_bucket = {}

        meal_name = None
        if isinstance(meal_bucket, dict):
            for k, v in meal_bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        meal_name = k
                        break
                except Exception:
                    continue

        if not meal_name:
            return await interaction.followup.send("You have no meals to feed. Cook something first.", ephemeral=True)

        removed = await self.quest_data.remove_item_from_inventory(guild_id, user_id, "sxf.meals", meal_name, 1)
        if not removed:
            return await interaction.followup.send("Failed to consume a meal. Try again.", ephemeral=True)

        hp, max_hp = await self._get_hp()
        new_hp = min(max_hp, hp + max(1, int(max_hp * 0.15)))
        await self._set_hp(new_hp)

        await self._set_last_feed_ts(int(time.time()))

        quality = self._meal_quality_from_name(meal_name)
        base_quality = self._meal_base_quality_from_name(meal_name)
        fed_msg = self._dialogue_fed_with_base(
            char_def,
            meal_name=meal_name,
            quality=quality,
            base_quality=base_quality,
        )
        self.last_dialogue = fed_msg
        await interaction.followup.send(
            f"{char_def.emoji} **{self._display_name(char_def)}**: {fed_msg}\n\nAte: **{meal_name}**",
            ephemeral=True,
        )

        await self.refresh(interaction)

    def _display_name(self, char_def) -> str:
        try:
            return str(getattr(char_def, "char_id", "Character")).replace("-", " ").title()
        except Exception:
            return "Character"

    def _load_dialogue_config(self) -> dict:
        try:
            p = Path("data/minigames/spy-x-family/character_dialogue.json")
            if not p.exists():
                return {}
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _dialogue_pool(self, char_def, key: str) -> list[str]:
        data = self._load_dialogue_config()
        cid = str(getattr(char_def, "char_id", "") or "")
        pool = []
        try:
            pool = (data.get(cid) or {}).get(key) or []
        except Exception:
            pool = []
        if not isinstance(pool, list) or not pool:
            try:
                pool = (data.get("_default") or {}).get(key) or []
            except Exception:
                pool = []
        return [str(x) for x in pool if isinstance(x, str) and x.strip()]

    def _render_dialogue_template(self, template: str, *, meal_name: str | None = None, quality: str | None = None) -> str:
        t = str(template or "").strip()
        if not t:
            return ""
        return (
            t.replace("{meal}", str(meal_name or "food"))
            .replace("{quality}", str((quality or "")).title() if quality else "")
            .strip()
        )

    def _meal_quality_from_name(self, meal_name: str) -> str | None:
        s = str(meal_name or "")
        for q in ("Perfect", "Great", "Good", "Bad", "Burnt"):
            if f"[{q}]" in s:
                return q.lower()
        return None

    def _meal_base_quality_from_name(self, meal_name: str) -> str | None:
        s = str(meal_name or "")
        if "|base:" not in s:
            return None
        # Expected format: "... [Perfect|base:good] ..."
        try:
            inside = s.split("[", 1)[-1].split("]", 1)[0]
            parts = [p.strip() for p in inside.split("|") if p.strip()]
            for p in parts:
                if p.lower().startswith("base:"):
                    v = p.split(":", 1)[-1].strip().lower()
                    return v or None
        except Exception:
            return None
        return None

    def _normalize_base_quality(self, base_quality: str | None) -> str | None:
        if not base_quality:
            return None
        b = str(base_quality).strip().lower()
        if not b:
            return None
        # Allow user-defined tiers. Provide a few common normalizations.
        if b in ("poor", "terrible", "trash"):
            return "poor"
        if b in ("okay", "ok", "average", "normal"):
            return "average"
        if b in ("good", "decent"):
            return "good"
        if b in ("great"):
            return "great"
        if b in ("excellent", "amazing", "premium"):
            return "excellent"
        # Unknown tier: keep as-is so JSON can define it.
        return b

    async def _unique_not_hungry_dialogue(self, char_def) -> str:
        pool = self._dialogue_pool(char_def, "not_hungry")
        if not pool:
            return "I'm not hungry right now."

        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        cid = str(getattr(char_def, "char_id", "") or "")

        used: list[int] = []
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.dialogue_used.not_hungry.{cid}": 1},
            )
            raw = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("dialogue_used", {})
                .get("not_hungry", {})
                .get(cid, [])
            )
            if isinstance(raw, list):
                used = [int(x) for x in raw if isinstance(x, int) or (isinstance(x, str) and str(x).isdigit())]
        except Exception:
            used = []

        used_set = {i for i in used if 0 <= i < len(pool)}
        remaining = [i for i in range(len(pool)) if i not in used_set]
        if not remaining:
            # reset once exhausted
            used_set = set()
            remaining = list(range(len(pool)))

        idx = remaining[0]
        used_set.add(idx)
        try:
            await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.inventory.sxf.dialogue_used.not_hungry.{cid}": sorted(list(used_set))}},
                upsert=True,
            )
        except Exception:
            pass

        return pool[idx]

    def _dialogue_not_hungry(self, char_def) -> str:
        pool = self._dialogue_pool(char_def, "not_hungry")
        return pool[0] if pool else "I'm not hungry right now."

    def _dialogue_fed(self, char_def, *, meal_name: str | None = None, quality: str | None = None) -> str:
        # Allow quality-based dialogue via JSON keys like fed_perfect/fed_great/etc.
        pool: list[str] = []
        if quality:
            pool = self._dialogue_pool(char_def, f"fed_{quality}")
        if not pool:
            pool = self._dialogue_pool(char_def, "fed")
        if not pool:
            return "Thanks!"
        chosen = random.choice(pool)
        return self._render_dialogue_template(chosen, meal_name=meal_name, quality=quality)

    def _dialogue_fed_with_base(self, char_def, *, meal_name: str | None = None, quality: str | None = None, base_quality: str | None = None) -> str:
        # Priority: cooked quality -> base quality -> generic fed.
        pool: list[str] = []
        if quality:
            pool = self._dialogue_pool(char_def, f"fed_{quality}")
        bq = self._normalize_base_quality(base_quality)
        if not pool and bq:
            pool = self._dialogue_pool(char_def, f"fed_base_{bq}")
        if not pool:
            pool = self._dialogue_pool(char_def, "fed")
        if not pool:
            return "Thanks!"
        chosen = random.choice(pool)
        # Use the cooked quality (if present) for {quality} placeholder, else base quality.
        q_for_tpl = quality or bq
        return self._render_dialogue_template(chosen, meal_name=meal_name, quality=q_for_tpl)

    async def _get_last_feed_ts(self) -> int | None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.last_feed_ts.{self.char_id}": 1},
            )
            ts = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("last_feed_ts", {})
                .get(self.char_id)
            )
        except Exception:
            ts = None
        try:
            if ts is None:
                return None
            return int(ts)
        except Exception:
            return None

    async def _set_last_feed_ts(self, ts: int) -> None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.inventory.sxf.last_feed_ts.{self.char_id}": int(ts)}},
                upsert=True,
            )
        except Exception:
            return

    async def _get_next_feed_info(self) -> tuple[int | None, str | None]:
        last = await self._get_last_feed_ts()
        if not last:
            return None, "Feed now"
        nxt = int(last) + int(self.FEED_INTERVAL_SECONDS)
        # Discord relative timestamp (<t:...:R>) is handled in embed builder.
        return nxt, None


class Character(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)

    async def _get_selected_character(self, guild_id: str, user_id: str) -> str | None:
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.selected_character": 1},
            )
            bucket = (((doc or {}).get("members") or {}).get(user_id) or {}).get("inventory", {}).get("sxf", {}).get("selected_character", {})
        except Exception:
            bucket = {}
        if isinstance(bucket, dict):
            for k, v in bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        return k
                except Exception:
                    continue
        return None

    async def _get_first_owned_character(self, guild_id: str, user_id: str) -> str | None:
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.characters": 1},
            )
            bucket = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("characters", {})
            )
        except Exception:
            bucket = {}

        if isinstance(bucket, dict):
            for k, v in bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        return k
                except Exception:
                    continue
        return None

    async def _resolve_active_character(self, guild_id: str, user_id: str) -> str | None:
        selected = await self._get_selected_character(guild_id, user_id)
        if selected:
            return selected
        return await self._get_first_owned_character(guild_id, user_id)

    async def _set_selected_character(self, guild_id: str, user_id: str, char_id: str) -> None:
        # Clear previous selection bucket by setting all existing keys to 0 (best-effort)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.selected_character": 1},
            )
            bucket = (((doc or {}).get("members") or {}).get(user_id) or {}).get("inventory", {}).get("sxf", {}).get("selected_character", {})
        except Exception:
            bucket = {}
        if isinstance(bucket, dict):
            for k, v in bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.selected_character", k, -int(v))
                except Exception:
                    continue

        await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.selected_character", char_id, 1)

    @commands.group(name="character", aliases=["char"], invoke_without_command=True)
    async def character(self, ctx: commands.Context):
        if not ctx.guild:
            return await ctx.reply("This command can only be used in a server.", mention_author=False)

        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        char_id = await self._resolve_active_character(guild_id, user_id)
        if not char_id:
            return await ctx.reply("You don't own any characters.", mention_author=False)

        owned = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.characters", char_id)
        if (owned or 0) <= 0:
            return await ctx.reply("You don't own any characters.", mention_author=False)

        char_def = get_character_def(char_id)
        if not char_def:
            return await ctx.reply("Character not found.", mention_author=False)

        max_hp = max(1, int(char_def.base_hp))
        stored_hp = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.character_hp", char_id)
        hp = int(stored_hp or max_hp)
        hp = max(0, min(hp, max_hp))

        view = CharacterView(self.bot, self.quest_data, ctx, char_id)
        view.image_index = await view._get_selected_image_index()

        next_feed_ts, next_feed_in = await view._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=view.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=next_feed_in,
        )
        msg = await ctx.reply(embed=embed, view=view, files=files, mention_author=False)
        view.message = msg

    @character.command(name="view")
    async def view_character(self, ctx: commands.Context):
        return await self.character(ctx)

    @commands.command(name="feed")
    async def feed(self, ctx: commands.Context):
        if not ctx.guild:
            return await ctx.reply("This command can only be used in a server.", mention_author=False)

        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        char_id = await self._resolve_active_character(guild_id, user_id)
        if not char_id:
            return await ctx.reply("You don't own any characters.", mention_author=False)

        owned = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.characters", char_id)
        if (owned or 0) <= 0:
            return await ctx.reply("You don't own that character.", mention_author=False)

        # Open the view and let the Feed button handle meal selection/consumption.
        char_def = get_character_def(char_id)
        if not char_def:
            return await ctx.reply("Character not found.", mention_author=False)

        max_hp = max(1, int(char_def.base_hp))
        stored_hp = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.character_hp", char_id)
        hp = int(stored_hp or max_hp)
        hp = max(0, min(hp, max_hp))

        view = CharacterView(self.bot, self.quest_data, ctx, char_id)
        view.image_index = await view._get_selected_image_index()

        next_feed_ts, next_feed_in = await view._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=view.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=next_feed_in,
        )
        msg = await ctx.reply(embed=embed, view=view, files=files, mention_author=False)
        view.message = msg


class CharacterImageSelect(discord.ui.Select):
    def __init__(self, parent_view: CharacterView):
        self.parent_view = parent_view
        char_def = get_character_def(parent_view.char_id)
        options = []
        if char_def and char_def.images:
            for i in range(min(25, len(char_def.images))):
                variant = None
                try:
                    if getattr(char_def, "image_variants", None) and i < len(char_def.image_variants):
                        variant = str(char_def.image_variants[i])
                except Exception:
                    variant = None
                label = (variant or f"Image {i + 1}")
                options.append(
                    discord.SelectOption(
                        label=label[:100],
                        value=str(i),
                        description=(f"Use {label}" if variant else f"Use variant #{i + 1}")[:100],
                    )
                )

        super().__init__(
            placeholder="Select character image...",
            options=options if options else [
                discord.SelectOption(label="No images", value="0", description="This character has no images")
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.ctx.author:
            return await interaction.response.send_message("This is not your character view.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        try:
            idx = int(self.values[0])
        except Exception:
            idx = 0

        await self.parent_view._set_selected_image_index(idx)
        await self.parent_view.refresh(interaction)


class CharacterInventoryView(discord.ui.View):
    def __init__(
        self,
        parent_view: CharacterView,
        items: list[tuple[str, int]],
        meals: list[tuple[str, int]],
        owned_chars: list[tuple[str, int]],
        selected_char: str | None,
    ):
        super().__init__(timeout=120)
        self.parent_view = parent_view
        self.items = items or []
        self.meals = meals or []
        self.owned_chars = owned_chars or []
        self.selected_char = selected_char

        if len(self.owned_chars) > 1:
            self.add_item(CharacterSelectSelect(self))

        self.add_item(CharacterEquipSelect(self))
        self.add_item(CharacterFoodSelect(self))


class CharacterSelectSelect(discord.ui.Select):
    def __init__(self, inv_view: CharacterInventoryView):
        self.inv_view = inv_view

        options = []
        for cid, _qty in (inv_view.owned_chars or [])[:25]:
            char_def = get_character_def(cid)
            emoji = (char_def.emoji if char_def else "👥")
            label = f"{emoji} {cid}"[:100]
            desc = "Currently selected" if cid == (inv_view.selected_char or inv_view.parent_view.char_id) else "Select this character"
            options.append(discord.SelectOption(label=label, value=cid, description=desc[:100]))

        super().__init__(placeholder="Character Select...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.inv_view.parent_view.ctx.author:
            return await interaction.response.send_message("This is not your inventory.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        cid = self.values[0]
        owned = await self.inv_view.parent_view.quest_data.get_user_inventory_count(
            str(self.inv_view.parent_view.ctx.guild.id),
            str(self.inv_view.parent_view.ctx.author.id),
            "sxf.characters",
            cid,
        )
        if (owned or 0) <= 0:
            return await interaction.followup.send("You don't own that character.", ephemeral=True)

        if not get_character_def(cid):
            return await interaction.followup.send("Character not found.", ephemeral=True)

        await self.inv_view.parent_view._set_selected_character(cid)
        self.inv_view.parent_view.char_id = cid
        self.inv_view.parent_view._rebuild_components()

        await interaction.followup.send(f"Selected character: `{cid}`", ephemeral=True)
        await self.inv_view.parent_view.refresh_message()


class CharacterEquipSelect(discord.ui.Select):
    def __init__(self, inv_view: CharacterInventoryView):
        self.inv_view = inv_view

        options = [discord.SelectOption(label="Unequip", value="__none__", description="Remove equipped item")]
        for name, qty in (inv_view.items or [])[:24]:
            options.append(
                discord.SelectOption(
                    label=str(name)[:100],
                    value=str(name),
                    description=f"x{qty}"[:100],
                )
            )

        super().__init__(placeholder="Equip item...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.inv_view.parent_view.ctx.author:
            return await interaction.response.send_message("This is not your inventory.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        val = self.values[0]
        item_name = None if val == "__none__" else val
        await self.inv_view.parent_view._set_equipped_item(item_name)

        await interaction.followup.send(
            f"Equipped: **{item_name or 'None'}**",
            ephemeral=True,
        )


class CharacterFoodSelect(discord.ui.Select):
    def __init__(self, inv_view: CharacterInventoryView):
        self.inv_view = inv_view

        options = []
        for name, qty in (inv_view.meals or [])[:25]:
            options.append(
                discord.SelectOption(
                    label=str(name)[:100],
                    value=str(name),
                    description=f"x{qty}"[:100],
                )
            )

        super().__init__(
            placeholder="Feed meal...",
            options=options if options else [
                discord.SelectOption(label="No meals", value="__none__", description="Cook something first")
            ],
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.inv_view.parent_view.ctx.author:
            return await interaction.response.send_message("This is not your inventory.", ephemeral=True)

        val = self.values[0]
        if val == "__none__":
            return await interaction.response.send_message("No meals available.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        guild_id = str(self.inv_view.parent_view.ctx.guild.id)
        user_id = str(self.inv_view.parent_view.ctx.author.id)

        removed = await self.inv_view.parent_view.quest_data.remove_item_from_inventory(
            guild_id, user_id, "sxf.meals", val, 1
        )
        if not removed:
            return await interaction.followup.send("Failed to consume that meal.", ephemeral=True)

        hp, max_hp = await self.inv_view.parent_view._get_hp()
        new_hp = min(max_hp, hp + max(1, int(max_hp * 0.15)))
        await self.inv_view.parent_view._set_hp(new_hp)

        await interaction.followup.send(f"Fed **{val}**. HP is now `{new_hp}/{max_hp}`.", ephemeral=True)

        try:
            await self.inv_view.parent_view.refresh_message()
        except Exception:
            pass


def setup(bot):
    bot.add_cog(Character(bot))
