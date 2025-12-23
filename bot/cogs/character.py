from imports.discord_imports import *
from imports.log_imports import *


from utils.character_utils import build_character_embed_with_files, get_character_def
from utils.cogs.quest import Quest_Data

import time
import json
from pathlib import Path
import random

_REPO_ROOT = Path(__file__).resolve().parents[2]


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

        self.FEED_INTERVAL_SECONDS: int = 6 * 60 * 60  # 6 hours

        self._rebuild_components()

    def _rebuild_components(self) -> None:
        self.clear_items()
        self.add_item(CharacterImageSelect(self))
        self.add_item(InventoryButton())

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

        # Fallback if format_character_name is not available
        def format_character_name(cid: str) -> str:
            return cid.replace("-", " ").title()

        current_char = get_character_def(selected_char or self.char_id)
        char_emoji = current_char.emoji if current_char else ""
        char_name = format_character_name(selected_char or self.char_id)

        items_embed = discord.Embed(
            title=f"🎒 {char_emoji} {char_name}'s Inventory",
            description=(
                f"**{char_emoji} {char_name}**\n"
                f"*{current_char.flavor_text if current_char else ''}*\n\n"
                f"Use the buttons below to manage your inventory.\n"
                f"Currently equipped: **{equipped or 'None'}**"
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

        hp, _ = await self._get_hp()
        self.image_index = await self._get_selected_image_index()

        next_feed_ts, _ = await self._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=self.ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=self.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=None,
            dialogue_footer=self.last_dialogue,
        )
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self, attachments=[], files=files)
            except TypeError:
                await self.message.edit(embed=embed, view=self)

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
                await interaction.followup.send("Character not found.", ephemeral=True)
            else:
                await interaction.response.send_message("Character not found.", ephemeral=True)
            return

        hp, _ = await self._get_hp()
        self.image_index = await self._get_selected_image_index()
        next_feed_ts, _ = await self._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=self.ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=self.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=None,
            dialogue_footer=self.last_dialogue,
        )

        if self.message and interaction.message and interaction.message.id != self.message.id:
            try:
                await self.message.edit(embed=embed, view=self, attachments=[], files=files)
            except TypeError:
                await self.message.edit(embed=embed, view=self)
            return

        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self, attachments=[], files=files)
            else:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[], files=files)
        except TypeError:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)

    async def feed_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This is not your character view.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        char_def = get_character_def(self.char_id)
        if not char_def:
            return await interaction.followup.send("Character not found.", ephemeral=True)

        next_feed_ts, _ = await self._get_next_feed_info()
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
            p = _REPO_ROOT / "data" / "commands" / "minigames" / "spy-x-family" / "character_dialogue.json"
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

    def _dialogue_fed_with_base(self, char_def, *, meal_name: str | None = None, quality: str | None = None, base_quality: str | None = None) -> str:
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
            return int(ts) if ts is not None else None
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
        nxt = int(last) + self.FEED_INTERVAL_SECONDS
        return nxt, None


# Fixed buttons using proper discord.ui.Button subclasses
class InventoryButton(discord.ui.Button['CharacterView']):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Inventory",
            custom_id="character_inventory",
        )
        self._logger = logging.getLogger("bot.InventoryButton")
        self._logger.setLevel(logging.DEBUG)  # ensure all logs show
        # Optionally add console handler if not already present
        if not self._logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
            ch.setFormatter(formatter)
            self._logger.addHandler(ch)

    def _log_ctx(
        self,
        level,
        msg: str,
        interaction: Optional[discord.Interaction] = None,
        **extra,
    ):
        ctx = {}
        if interaction:
            ctx.update({
                "user_id": getattr(interaction.user, "id", None),
                "guild_id": getattr(interaction.guild, "id", None),
                "channel_id": getattr(interaction.channel, "id", None),
                "interaction_id": interaction.id,
                "response_done": interaction.response.is_done(),
            })
        ctx.update(extra)
        log_msg = f"{msg} | Context: {ctx}"
        print(log_msg)  # print for immediate visibility
        self._logger.log(level, msg, extra={"ctx": ctx})

    async def callback(self, interaction: discord.Interaction):
        # ---- View validation ----
        if not getattr(self, "view", None) or not hasattr(self.view, "inventory_callback"):
            self._log_ctx(
                logging.ERROR,
                "InventoryButton misconfigured: missing view or inventory_callback",
                interaction,
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⚠️ This button is not properly configured.",
                    ephemeral=True,
                )
            return

        view: CharacterView = self.view  # type: ignore

        if not getattr(view, "ctx", None) or not getattr(view.ctx, "author", None):
            self._log_ctx(
                logging.ERROR,
                "CharacterView missing ctx or ctx.author",
                interaction,
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⚠️ Configuration error. Please try again later.",
                    ephemeral=True,
                )
            return

        # ---- Ownership check ----
        if interaction.user != view.ctx.author:
            self._log_ctx(
                logging.INFO,
                "User attempted to interact with another user's character view",
                interaction,
                owner_id=view.ctx.author.id,
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ This is not your character view.",
                    ephemeral=True,
                )
            return

        # ---- Execute callback ----
        self._log_ctx(
            logging.DEBUG,
            "Executing inventory callback",
            interaction,
        )

        try:
            await view.inventory_callback(interaction)

        except discord.NotFound:
            self._log_ctx(
                logging.WARNING,
                "Interaction no longer valid (message/component not found)",
                interaction,
            )

        except discord.Forbidden:
            self._log_ctx(
                logging.ERROR,
                "Forbidden: missing permissions to respond",
                interaction,
            )
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        "❌ I don’t have permission to do that here.",
                        ephemeral=True,
                    )
                except Exception as e:
                    print("Failed to send Forbidden error message:", e)
                    traceback.print_exc()
                    self._logger.exception("Failed to send Forbidden error message")

        except Exception as e:
            print("Unexpected error in inventory callback:", e)
            traceback.print_exc()
            self._logger.exception(
                "Unhandled exception during inventory callback",
                extra={
                    "ctx": {
                        "user_id": interaction.user.id,
                        "guild_id": getattr(interaction.guild, "id", None),
                        "interaction_id": interaction.id,
                    }
                },
            )
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        "⚠️ An unexpected error occurred. Please try again.",
                        ephemeral=True,
                    )
                except Exception as send_error:
                    print("Failed to send fallback error message:", send_error)
                    traceback.print_exc()
                    self._logger.exception("Failed to send fallback error message")



class FeedButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Feed",
            custom_id="character_feed",
        )

    async def callback(self, interaction: discord.Interaction):
        view: CharacterView = self.view  # type: ignore
        if interaction.user != view.ctx.author:
            return await interaction.response.send_message("This is not your character view.", ephemeral=True)
        await view.feed_callback(interaction)


class CharacterImageSelect(discord.ui.Select):
    def __init__(self, parent_view: CharacterView):
        self.parent_view = parent_view
        char_def = get_character_def(parent_view.char_id)
        options = []
        if char_def and getattr(char_def, "images", None):
            for i in range(min(25, len(char_def.images))):
                variant = None
                try:
                    if getattr(char_def, "image_variants", None) and i < len(char_def.image_variants):
                        variant = str(char_def.image_variants[i])
                except Exception:
                    variant = None
                label = variant or f"Image {i + 1}"
                options.append(
                    discord.SelectOption(
                        label=label[:100],
                        value=str(i),
                        description=(f"Use {label}" if variant else f"Use variant #{i + 1}")[:100],
                    )
                )

        super().__init__(
            placeholder="Select character image...",
            options=options or [discord.SelectOption(label="No images", value="0", description="This character has no images")],
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

        next_feed_ts, _ = await view._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=view.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=None,
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

        char_def = get_character_def(char_id)
        if not char_def:
            return await ctx.reply("Character not found.", mention_author=False)

        max_hp = max(1, int(char_def.base_hp))
        stored_hp = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.character_hp", char_id)
        hp = int(stored_hp or max_hp)
        hp = max(0, min(hp, max_hp))

        view = CharacterView(self.bot, self.quest_data, ctx, char_id)
        view.image_index = await view._get_selected_image_index()

        next_feed_ts, _ = await view._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=view.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=None,
        )
        msg = await ctx.reply(embed=embed, view=view, files=files, mention_author=False)
        view.message = msg


# Remaining classes (unchanged from your original code)
class CharacterSelect(discord.ui.Select):
    def __init__(self, inv_view: 'CharacterInventoryView'):
        self.inv_view = inv_view
        
        options = []
        for char_id, _ in inv_view.owned_chars:
            char_def = get_character_def(char_id)
            if not char_def:
                continue
                
            char_name = ' '.join(word.capitalize() for word in char_id.split('-'))
            emoji = char_def.emoji if char_def.emoji else ""
            
            label = f"{char_name}"[:100]
            
            is_selected = char_id == inv_view.selected_char
            
            options.append(discord.SelectOption(
                label=label,
                value=char_id,
                description=char_def.flavor_text[:100] if char_def and char_def.flavor_text else "No description",
                default=is_selected
            ))
        
        super().__init__(
            placeholder="Select a character...",
            options=options[:25],
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.inv_view.ctx.author:
            return await interaction.response.send_message("This is not your inventory.", ephemeral=True)
        
        selected_char = self.values[0]
        if selected_char == self.inv_view.selected_char:
            return await interaction.response.defer()
        
        self.inv_view.selected_char = selected_char
        self.inv_view.parent_view.char_id = selected_char
        
        await self.inv_view.parent_view.refresh_message()
        
        char_def = get_character_def(selected_char)
        char_name = ' '.join(word.capitalize() for word in selected_char.split('-'))
        emoji = char_def.emoji if char_def and char_def.emoji else ""
        await interaction.response.send_message(
            f"Selected character: {emoji} **{char_name}**",
            ephemeral=True
        )


class NavigationButton(discord.ui.Button):
    def __init__(self, label: str, style: discord.ButtonStyle, row: int = 0):
        super().__init__(label=label, style=style, row=row)
        self.label = label
    
    async def callback(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
                
            if interaction.user != self.view.ctx.author:
                return await interaction.followup.send("This is not your inventory.", ephemeral=True)
            
            view = discord.ui.View(timeout=180)
            
            try:
                if self.label == "Characters":
                    if len(self.view.owned_chars) > 1:
                        view.add_item(CharacterSelectSelect(self.view))
                        message = "Select a character:"
                    else:
                        return await interaction.followup.send("You only have one character.", ephemeral=True)
                elif self.label == "Items":
                    view.add_item(CharacterEquipSelect(self.view))
                    message = "Select an item to equip:"
                elif self.label == "Meals":
                    view.add_item(CharacterFoodSelect(self.view))
                    message = "Select a meal to feed:"
                else:
                    return await interaction.followup.send("Unknown action.", ephemeral=True)
                
                await interaction.followup.send(message, view=view, ephemeral=True)
                
            except Exception as e:
                print(f"[ERROR] Error in {self.label} button: {str(e)}")
                await interaction.followup.send(
                    "An error occurred while processing your request. Please try again.", 
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"[CRITICAL] Unhandled error in NavigationButton: {str(e)}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "⚠️ An unexpected error occurred. Please try again.", 
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "⚠️ An unexpected error occurred. Please try again.", 
                        ephemeral=True
                    )
            except:
                pass


class CharacterInventoryView(discord.ui.View):
    def __init__(
        self,
        parent_view: CharacterView,
        items: list[tuple[str, int]],
        meals: list[tuple[str, int]],
        owned_chars: list[tuple[str, int]],
        selected_char: str | None = None,
    ):
        super().__init__(timeout=180)
        self.parent_view = parent_view
        self.items = items
        self.meals = meals
        self.owned_chars = owned_chars
        self.selected_char = selected_char or parent_view.char_id
        self.quest_data = parent_view.quest_data
        self.ctx = parent_view.ctx
        self.bot = parent_view.bot
        self._add_components()
        
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        try:
            if hasattr(self, 'message'):
                await self.message.edit(view=self)
        except:
            pass

    def _add_components(self):
        # Navigation buttons in row 0 (max 5 items per row)
        self.add_item(NavigationButton("Characters", discord.ButtonStyle.primary, row=0))
        self.add_item(NavigationButton("Items", discord.ButtonStyle.secondary, row=0))
        self.add_item(NavigationButton("Meals", discord.ButtonStyle.success, row=0))


class CharacterSelectSelect(discord.ui.Select):
    def __init__(self, inv_view: CharacterInventoryView):
        self.inv_view = inv_view

        options = []
        for cid, _qty in (inv_view.owned_chars or [])[:25]:
            char_def = get_character_def(cid)
            if not char_def:
                continue
                
            char_name = ' '.join(word.capitalize() for word in cid.split('-'))
            emoji = char_def.emoji if char_def.emoji else "❔"
            
            label = f"{char_name}"[:100]
            
            is_selected = cid == (inv_view.selected_char or inv_view.parent_view.char_id)
            if is_selected:
                inv_view.selected_char = cid
                
            options.append(discord.SelectOption(
                label=label,
                value=cid,
                emoji=emoji,
                description="Currently selected" if is_selected else "Click to select"
            ))

        placeholder = "Select a character..."
        if inv_view.selected_char:
            char_def = get_character_def(inv_view.selected_char)
            if char_def:
                placeholder = f"Current: {inv_view.selected_char.replace('-', ' ').title()}"

        super().__init__(placeholder=placeholder, options=options, row=0)

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

        # Set the selected character and update the parent view
        await self.inv_view.parent_view._set_selected_character(cid)
        self.inv_view.parent_view.char_id = cid
        
        # Reset image index to 0 for the new character
        self.inv_view.parent_view.image_index = 0
        await self.inv_view.parent_view._set_selected_image_index(0)
        
        # Rebuild components to reflect the new character
        self.inv_view.parent_view._rebuild_components()

        # Instantly refresh the main character embed with new character and image
        await self.inv_view.parent_view.refresh_message()

        char_def = get_character_def(cid)
        char_name = ' '.join(word.capitalize() for word in cid.split('-'))
        emoji = char_def.emoji if char_def and char_def.emoji else ""
        await interaction.followup.send(f"Selected character: {emoji} **{char_name}**", ephemeral=True)


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
            options=options or [
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