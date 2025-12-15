import json
from dataclasses import dataclass
from typing import Any

import discord

from data.local.const import Quest_Progress


@dataclass(frozen=True)
class CharacterDefinition:
    char_id: str
    emoji: str
    base_hp: int
    attack: int
    defense: int
    speed: int
    attack_speed: int
    crit_rate: int
    evasion: int
    images: list[str]
    flavor_text: str
    fighting_ability: str
    food_ability: str
    cooking_difficulty: str


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def load_sxf_characters(path: str = "data/minigames/spy-x-family/characters.json") -> dict[str, dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return raw
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return {}


def get_character_def(char_id: str, path: str = "data/minigames/spy-x-family/characters.json") -> CharacterDefinition | None:
    if not char_id:
        return None

    chars = load_sxf_characters(path)
    data = chars.get(char_id)
    if not isinstance(data, dict):
        return None

    imgs = data.get("images")
    images: list[str] = []
    if isinstance(imgs, list):
        images = [str(u) for u in imgs if isinstance(u, str) and u.strip()]

    return CharacterDefinition(
        char_id=char_id,
        emoji=str(data.get("emoji") or "👤"),
        base_hp=_safe_int(data.get("Hp"), 100),
        attack=_safe_int(data.get("Attack"), 0),
        defense=_safe_int(data.get("Def"), 0),
        speed=_safe_int(data.get("Speed"), 0),
        attack_speed=_safe_int(data.get("AttackSpeed"), 0),
        crit_rate=_safe_int(data.get("CritRate"), 0),
        evasion=_safe_int(data.get("Evasion"), 0),
        images=images,
        flavor_text=str(data.get("flavor-text") or ""),
        fighting_ability=str(data.get("fighting-ability") or ""),
        food_ability=str(data.get("food-ability") or ""),
        cooking_difficulty=str(data.get("cooking-difficulty") or "normal"),
    )


async def render_hp_bar(current_hp: int, max_hp: int, bot: discord.Client) -> str:
    max_hp = max(1, int(max_hp))
    current_hp = max(0, min(int(current_hp), max_hp))
    progress = current_hp / max_hp
    return await Quest_Progress.generate_progress_bar(progress, bot)


async def build_character_embed(
    *,
    bot: discord.Client,
    user: discord.abc.User,
    char_def: CharacterDefinition,
    current_hp: int,
    author_avatar_url: str | None = None,
    image_index: int = 0,
) -> discord.Embed:
    max_hp = max(1, int(char_def.base_hp))
    hp = max(0, min(int(current_hp), max_hp))

    bar = await render_hp_bar(hp, max_hp, bot)
    pct = int((hp / max_hp) * 100)

    embed = discord.Embed(
        title=f"{char_def.emoji} {char_def.char_id}",
        description=(char_def.flavor_text or "").strip()[:4000],
        color=discord.Color.from_rgb(255, 182, 193),
    )

    # Thumbnail should be the requester (ctx author)
    if author_avatar_url:
        embed.set_thumbnail(url=author_avatar_url)
    else:
        try:
            if getattr(user, "avatar", None):
                embed.set_thumbnail(url=user.avatar.url)
        except Exception:
            pass

    # Character art should be the embed image; choose one of the available images
    if char_def.images:
        idx = max(0, min(int(image_index), len(char_def.images) - 1))
        embed.set_image(url=char_def.images[idx])

    embed.add_field(
        name="Health",
        value=f"`{hp}/{max_hp}` {bar} `{pct}%`",
        inline=False,
    )

    stats_lines = [
        f"⚔️ ATK: **{char_def.attack}**",
        f"🛡️ DEF: **{char_def.defense}**",
        f"💨 SPD: **{char_def.speed}**",
        f"🗡️ ATK SPD: **{char_def.attack_speed}**",
        f"🎯 CRIT: **{char_def.crit_rate}%**",
        f"🌀 EVA: **{char_def.evasion}%**",
    ]
    embed.add_field(name="Stats", value="\n".join(stats_lines), inline=False)

    if char_def.fighting_ability:
        embed.add_field(name="Fighting Ability", value=char_def.fighting_ability[:1024], inline=False)
    if char_def.food_ability:
        embed.add_field(name="Food Ability", value=char_def.food_ability[:1024], inline=False)

    embed.set_footer(text=f"Requested by {getattr(user, 'display_name', getattr(user, 'name', 'User'))}")
    return embed
