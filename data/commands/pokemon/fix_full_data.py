import csv
import re
from pathlib import Path

csv_path = Path("data/commands/pokemon/pokemon_full_data.csv")
output_path = csv_path  # overwrite same file

def fix_description(desc: str, slug: str) -> str:
    if not desc:
        return desc

    # Lowercase for searching
    lowered = desc.lower()

    # Replace "pokemon" (case-insensitive) with "Pokémon"
    fixed = re.sub(r"\bpokemon\b", "Pokémon", lowered, flags=re.IGNORECASE)

    # Replace slug mentions with Title-case
    # Example: breloom -> Breloom
    fixed = re.sub(rf"\b{re.escape(slug.lower())}\b", slug.title(), fixed, flags=re.IGNORECASE)

    # Capitalize first character of sentence if lost
    if fixed and fixed[0].islower():
        fixed = fixed[0].upper() + fixed[1:]

    return fixed

def process_csv(path: Path):
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = row["slug"]
            row["description"] = fix_description(row["description"], slug)
            rows.append(row)

    # Write back with same header
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)

if __name__ == "__main__":
    process_csv(csv_path)
    print("Descriptions updated successfully ✅")
