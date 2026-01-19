"""
Test script to verify gacha rarity distribution
Simulates multiple 3-card draws and shows the rarity breakdown
"""

import random
from collections import Counter

# Rarity weights from const.py
GACHA_RARITY_TIERS = {
    "common": {"weight": 7500},
    "uncommon": {"weight": 1800},
    "rare": {"weight": 500},
    "epic": {"weight": 180},
    "legendary": {"weight": 20},
}

def get_random_rarity():
    """Get a random rarity based on weighted distribution"""
    total_weight = sum(tier["weight"] for tier in GACHA_RARITY_TIERS.values())
    rand = random.randint(1, total_weight)
    
    current = 0
    for rarity, data in GACHA_RARITY_TIERS.items():
        current += data["weight"]
        if rand <= current:
            return rarity
    
    return "common"

def simulate_draws(num_draws=1000):
    """Simulate multiple 3-card draws"""
    results = []
    
    print(f"🎴 Simulating {num_draws} three-card draws ({num_draws * 3} total cards)...\n")
    
    for i in range(num_draws):
        draw = [get_random_rarity() for _ in range(3)]
        results.extend(draw)
    
    # Count rarities
    counter = Counter(results)
    total = len(results)
    
    print("=" * 60)
    print("RARITY DISTRIBUTION RESULTS")
    print("=" * 60)
    
    rarity_order = ["legendary", "epic", "rare", "uncommon", "common"]
    
    for rarity in rarity_order:
        count = counter.get(rarity, 0)
        percentage = (count / total) * 100
        expected_weight = GACHA_RARITY_TIERS[rarity]["weight"]
        expected_percentage = (expected_weight / 10000) * 100
        
        # Visual bar
        bar_length = int(percentage * 2)
        bar = "█" * bar_length
        
        print(f"\n{rarity.upper():12} | {count:5} cards | {percentage:5.2f}% {bar}")
        print(f"{'':12} | Expected: {expected_percentage:5.2f}%")
    
    print("\n" + "=" * 60)
    print(f"Total cards drawn: {total:,}")
    print("=" * 60)
    
    # Show some example 3-card draws
    print("\n📋 Sample 3-card draws:")
    print("-" * 60)
    for i in range(5):
        draw = [get_random_rarity() for _ in range(3)]
        draw_str = " | ".join([f"{r:10}" for r in draw])
        print(f"Draw {i+1}: {draw_str}")
    
    print("\n" + "=" * 60)
    print("LEGENDARY DROP RATE ANALYSIS")
    print("=" * 60)
    legendary_count = counter.get("legendary", 0)
    if legendary_count > 0:
        avg_cards_per_legendary = total / legendary_count
        print(f"Legendary cards: {legendary_count}")
        print(f"Average: 1 legendary per {avg_cards_per_legendary:.1f} cards")
        print(f"Expected: 1 legendary per 500 cards (0.2%)")
    else:
        print("No legendary cards in this simulation!")
        print(f"Expected: ~{total/500:.1f} legendary cards in {total} draws")

if __name__ == "__main__":
    # Run simulation
    simulate_draws(1000)  # 1000 draws = 3000 cards
    
    print("\n\n💡 TIP: Run this script multiple times to see variance in results!")
    print("The more draws you simulate, the closer to expected percentages.")
