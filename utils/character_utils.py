import json
from pathlib import Path
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
    image_variants: list[str]
    flavor_text: str
    fighting_ability: str
    food_ability: str
    cooking_difficulty: str


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def format_character_name(char_id: str) -> str:
    name = str(char_id or "").strip().replace("-", " ")
    if not name:
        return "Character"
    return " ".join(part[:1].upper() + part[1:].lower() if part else "" for part in name.split())


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
    image_variants: list[str] = []
    
    if isinstance(imgs, str) and imgs.strip():
        # New format: direct path string
        images.append(imgs.strip())
        image_variants.append("default")
    elif isinstance(imgs, list):
        # Legacy list format (for backward compatibility)
        images = [str(u) for u in imgs if isinstance(u, str) and u.strip()]
        image_variants = [f"Image {i + 1}" for i in range(len(images))]
    elif isinstance(imgs, dict):
        # Legacy dict format (for backward compatibility)
        for k, v in imgs.items():
            if not isinstance(k, str) or not isinstance(v, str) or not v.strip():
                continue
            key = k.strip()
            if key.lower() == "defualt":
                key = "default"
            
            # Check if the path is a directory
            v_path = Path(v.strip())
            if v_path.is_dir():
                images.append(str(v_path))
                image_variants.append(key)
            else:
                image_variants.append(key)
                images.append(v.strip())

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
        image_variants=image_variants,
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
    image_index: int = 0,
) -> discord.Embed:
    embed, _files = await build_character_embed_with_files(
        bot=bot,
        user=user,
        char_def=char_def,
        current_hp=current_hp,
        image_index=image_index,
    )
    return embed


def _resolve_image_source(image: str, *, fallback_name: str) -> tuple[str | None, discord.File | None]:
    if not image:
        return None, None

    img = str(image).strip()
    if not img:
        return None, None

    if img.startswith("http://") or img.startswith("https://"):
        return img, None

    p = Path(img)
    if not p.is_absolute():
        p = Path.cwd() / p

    if p.exists() and p.is_file():
        suffix = p.suffix or ""
        safe = "".join(ch for ch in str(fallback_name) if ch.isalnum() or ch in ("-", "_"))
        filename = f"{safe}{suffix}" if safe else p.name
        return f"attachment://{filename}", discord.File(fp=str(p), filename=filename)

    # If it isn't a URL and doesn't exist as a file, don't set an invalid embed image.
    return None, None


async def build_character_embed_with_files(
    *,
    bot: discord.Client,
    user: discord.abc.User,
    char_def: CharacterDefinition,
    current_hp: int,
    image_index: int = 0,
    next_feed_ts: int | None = None,
    next_feed_in: str | None = None,
    dialogue_footer: str | None = None,
) -> tuple[discord.Embed, list[discord.File]]:
    files: list[discord.File] = []
    max_hp = max(1, int(char_def.base_hp))
    hp = max(0, min(int(current_hp), max_hp))

    bar = await render_hp_bar(hp, max_hp, bot)
    pct = int((hp / max_hp) * 100)

    display_name = format_character_name(char_def.char_id)
    desc = (char_def.flavor_text or "").strip()

    abilities_lines: list[str] = []
    if (char_def.fighting_ability or "").strip():
        abilities_lines.append(f"> **Fighting Ability:** {str(char_def.fighting_ability).strip()}")
    if (char_def.food_ability or "").strip():
        abilities_lines.append(f"> **Food Ability:** {str(char_def.food_ability).strip()}")
    if abilities_lines:
        desc = (desc + "\n\n" if desc else "") + "\n".join(abilities_lines)

    embed = discord.Embed(
        title=f"{char_def.emoji} {display_name}",
        description=desc[:4000],
        color=discord.Color.from_rgb(255, 182, 193),
    )

    try:
        icon_url = None
        if getattr(user, "avatar", None):
            icon_url = user.avatar.url
        embed.set_author(name=getattr(user, "display_name", getattr(user, "name", "User")), icon_url=icon_url)
    except Exception:
        pass

    # Character art should be the embed image; choose one of the available images
    if char_def.images:
        idx = max(0, min(int(image_index), len(char_def.images) - 1))
        image_path = char_def.images[idx]
        
        # Check if the image path is a directory
        if image_path and Path(image_path).is_dir():
            # Get all image files from the directory
            image_files = [f for f in Path(image_path).glob('*') 
                         if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif']]
            if image_files:
                # Sort files for consistent ordering
                image_files.sort()
                # Use the first image in the directory
                image_path = str(image_files[0])
        
        if image_path:
            fallback_name = f"{char_def.char_id}"
            if idx < len(char_def.image_variants):
                fallback_name += f"_{char_def.image_variants[idx]}"
            
            url, f = _resolve_image_source(
                image_path,
                fallback_name=fallback_name,
            )
            if url:
                embed.set_image(url=url)
            if f:
                files.append(f)

    embed.add_field(
        name="Health",
        value=f"`{hp}/{max_hp}` {bar} `{pct}%`",
        inline=False,
    )

    stats_lines = [
        f"> ⚔️ ATK: **{char_def.attack}**",
        f"> 🛡️ DEF: **{char_def.defense}**",
        f"> 💨 SPD: **{char_def.speed}**",
        f"> 🗡️ ATK SPD: **{char_def.attack_speed}**",
        f"> 🎯 CRIT: **{char_def.crit_rate}%**",
        f"> 🌀 EVA: **{char_def.evasion}%**",
    ]

    if next_feed_ts is not None or next_feed_in:
        when = f"<t:{int(next_feed_ts)}:R>" if next_feed_ts is not None else "soon"
        extra = f" ({next_feed_in})" if next_feed_in else ""
        stats_lines.append(f"> 🍽️ Next feed: **{when}**{extra}")

    embed.add_field(name="Stats", value="\n".join(stats_lines), inline=False)

    if dialogue_footer:
        try:
            who = format_character_name(char_def.char_id)
            embed.set_footer(text=f"{who}: {str(dialogue_footer).strip()[:200]}")
        except Exception:
            pass

    return embed, files
