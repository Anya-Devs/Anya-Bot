"""
Cover Art System Setup Script
Creates or updates a single character in MongoDB (no bundled sample data).
"""

import argparse
import asyncio
import os
from datetime import datetime
from typing import Any, Dict

from motor.motor_asyncio import AsyncIOMotorClient


def normalize_key(raw: str) -> str:
    return str(raw or "").strip().lower().replace(" ", "_")


def build_character_doc(data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    char_id = normalize_key(data["id"] if "id" in data else data["name"])
    return {
        "_id": char_id,
        "name": data["name"],
        "series": data.get("series", "Unknown"),
        "description": data.get("description", ""),
        "rarity": data.get("rarity", "C"),
        "default_image": data.get("default_image"),
        "aliases": data.get("aliases", []),
        "tags": data.get("tags", []),
        "created_at": now,
        "updated_at": now,
    }


async def upsert_character(data: Dict[str, Any]):
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017/")
    client = AsyncIOMotorClient(mongo_url)
    db = client["anya_bot"]
    characters_collection = db["characters"]

    doc = build_character_doc(data)
    _id = doc["_id"]

    print(f"🔄 Upserting character: {doc['name']} ({_id})")
    await characters_collection.update_one({"_id": _id}, {"$set": doc}, upsert=True)

    await characters_collection.create_index("name")
    await characters_collection.create_index("series")
    await characters_collection.create_index("rarity")

    print("✅ Character upserted.")
    print(f"  • ID: {_id}")
    print(f"  • Name: {doc['name']}")
    print(f"  • Series: {doc['series']}")
    print(f"  • Rarity: {doc['rarity']}")

    await client.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Insert/update a single character for cover art."
    )
    parser.add_argument("--name", required=True, help="Character name (required)")
    parser.add_argument("--series", default="Unknown", help="Series name")
    parser.add_argument("--rarity", default="C", choices=["C", "R", "SR", "SSR"], help="Rarity")
    parser.add_argument("--description", default="", help="Description")
    parser.add_argument("--default-image", dest="default_image", default=None, help="Default image URL")
    parser.add_argument("--aliases", nargs="*", default=[], help="Aliases (space-separated)")
    parser.add_argument("--tags", nargs="*", default=[], help="Tags (space-separated)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    payload = {
        "name": args.name,
        "series": args.series,
        "rarity": args.rarity,
        "description": args.description,
        "default_image": args.default_image,
        "aliases": args.aliases,
        "tags": args.tags,
    }
    asyncio.run(upsert_character(payload))
