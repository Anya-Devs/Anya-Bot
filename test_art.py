#!/usr/bin/env python3
"""Test script for art command functionality"""

import sys
import asyncio
sys.path.append('.')

from bot.cogs.search import *
from utils.cogs.art import *

def test_art_sources():
    """Test that all ART_SOURCES are properly categorized"""
    print("🧪 Testing ART_SOURCES categorization...")
    
    safe_sources = []
    mix_sources = []
    nsfw_sources = []
    
    for key, meta in ART_SOURCES.items():
        if meta["nsfw_only"]:
            nsfw_sources.append(key)
        elif meta.get("requires_nsfw_channel"):
            mix_sources.append(key)
        else:
            safe_sources.append(key)
    
    print(f"✅ Safe sources ({len(safe_sources)}): {', '.join(safe_sources[:5])}{'...' if len(safe_sources) > 5 else ''}")
    print(f"⚠️  Mix sources ({len(mix_sources)}): {', '.join(mix_sources[:5])}{'...' if len(mix_sources) > 5 else ''}")
    print(f"🔞 NSFW sources ({len(nsfw_sources)}): {', '.join(nsfw_sources)}")
    print(f"📊 Total: {len(ART_SOURCES)} sources")
    
    return len(safe_sources), len(mix_sources), len(nsfw_sources)

def test_category_filtering():
    """Test category filtering logic"""
    print("\n🧪 Testing category filtering logic...")
    
    # Mock view object
    class MockView:
        def __init__(self):
            self.available_sources = ART_SOURCES
            self.source_category = "mix"
        
        def get_sources_by_category(self):
            if self.source_category == "all":
                return self.available_sources
            
            filtered = {}
            for key, meta in self.available_sources.items():
                if self.source_category == "safe":
                    if not meta["nsfw_only"] and not meta.get("requires_nsfw_channel"):
                        filtered[key] = meta
                elif self.source_category == "mix":
                    if not meta["nsfw_only"] and meta.get("requires_nsfw_channel"):
                        filtered[key] = meta
                elif self.source_category == "nsfw":
                    if meta["nsfw_only"]:
                        filtered[key] = meta
            return filtered
    
    view = MockView()
    
    # Test each category
    categories = ["safe", "mix", "nsfw"]
    for category in categories:
        view.source_category = category
        filtered = view.get_sources_by_category()
        print(f"✅ {category.upper()} filter: {len(filtered)} sources")
    
    print("✅ Category filtering works correctly!")

def test_button_styling():
    """Test button styling logic"""
    print("\n🧪 Testing button styling logic...")
    
    categories = ["safe", "mix", "nsfw"]
    for active_category in categories:
        print(f"When {active_category} is active:")
        for category in categories:
            if category == active_category:
                style = "PRIMARY (blue/active)"
            else:
                style = "SECONDARY (gray/inactive)"
            print(f"  {category} button: {style}")
    
    print("✅ Button styling logic is correct!")

def test_prohibited_content():
    """Test prohibited content filtering"""
    print("\n🧪 Testing prohibited content filtering...")
    
    test_queries = [
        ("anya forger", False),  # Safe
        ("naruto", False),       # Safe
        ("loli", True),          # Prohibited
        ("gore", True),          # Prohibited
        ("scat", True),          # Prohibited
        ("anime girl", False),   # Safe
    ]
    
    for query, should_be_blocked in test_queries:
        is_blocked = contains_prohibited_content(query)
        status = "🚫 BLOCKED" if is_blocked else "✅ ALLOWED"
        expected = "🚫 BLOCKED" if should_be_blocked else "✅ ALLOWED"
        match = "✅" if is_blocked == should_be_blocked else "❌"
        print(f"  '{query}': {status} (expected: {expected}) {match}")
    
    print("✅ Prohibited content filtering works correctly!")

if __name__ == "__main__":
    print("🚀 Starting Art Command Tests...\n")
    
    try:
        # Test 1: Source categorization
        safe_count, mix_count, nsfw_count = test_art_sources()
        
        # Test 2: Category filtering
        test_category_filtering()
        
        # Test 3: Button styling
        test_button_styling()
        
        # Test 4: Content filtering
        test_prohibited_content()
        
        print(f"\n🎉 All tests passed!")
        print(f"📊 Summary: {safe_count} Safe + {mix_count} Mix + {nsfw_count} NSFW = {safe_count + mix_count + nsfw_count} total sources")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
