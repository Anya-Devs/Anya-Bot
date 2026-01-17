import csv
import re
from pathlib import Path



SPECIAL_NAMES_CSV = Path("data/commands/pokemon/pokemon_special_names.csv")


class PokemonSpecialNames:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.rare = set()
            cls._instance.regional = set()
            cls._instance._load()
        return cls._instance

    @classmethod
    def _load(cls):
        if not SPECIAL_NAMES_CSV.exists():
            print(f"CSV not found: {SPECIAL_NAMES_CSV}")
            return
        with open(SPECIAL_NAMES_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if rare := row.get("Rare Pokémon", "").strip().lower():
                    cls._instance.rare.add(rare)
                if regional := row.get("Regional Pokémon", "").strip().lower():
                    cls._instance.regional.add(regional)

    def is_rare(self, name: str) -> bool:
        return name.lower() in self.rare

    def is_regional(self, name: str) -> bool:
        return name.lower() in self.regional

    async def get_starboard_channel(self, guild_id):
        return await self.config_db.get_starboard_channel(guild_id)

    async def set_starboard_channel(self, guild_id, channel_id):
        await self.config_db.set_starboard_channel(guild_id, channel_id)

    def transform_name(self, name):
        variants = {
            "alolan": "-alola", "galarian": "-galar", "hisuian": "-hisui",
            "paldean": "-paldea", "mega": "-mega"
        }
        name_clean = re.sub(r"[^a-zA-Z\s]", "", name)
        lower = name_clean.lower()
        for key, suffix in variants.items():
            if key in lower:
                parts = name_clean.split()
                base = parts[1] if len(parts) > 1 else parts[0]
                return base.lower() + suffix, key
        return name_clean.lower(), None


def has_manager_role_or_manage_channel(ctx):
    return "Anya Manager" in [r.name for r in ctx.author.roles] or ctx.author.guild_permissions.manage_channels

