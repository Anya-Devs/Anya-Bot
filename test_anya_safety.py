"""
Test script to verify Anya (Spy x Family) image safety across all sources
Run this to get image URLs from all sources for manual verification
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from utils.cogs.game.draw.multisearch import MultiSourceImageSearch


async def test_anya_images():
    """Test Anya (Spy x Family) image search across all sources"""
    
    print("=" * 80)
    print("ANYA (SPY X FAMILY) - SAFETY TEST")
    print("Testing all image sources with maximum safety filters")
    print("=" * 80)
    print()
    
    # Initialize the search system
    searcher = MultiSourceImageSearch()
    
    # Character tag for Anya from Spy x Family
    character_tag = "anya_(spy_x_family)"
    
    print(f"🔍 Searching for: {character_tag}")
    print(f"📊 Safety Level: MAXIMUM (All-Ages)")
    print(f"🛡️ Filters: 150+ blocked tags, strict ratings only")
    print()
    print("-" * 80)
    
    # Test each source individually
    sources = [
        ("Safebooru.org", searcher._search_safebooru_org),
        ("Konachan.net", searcher._search_konachan),
        ("Danbooru", searcher._search_danbooru_safe_only)
    ]
    
    all_results = []
    
    for source_name, search_func in sources:
        print(f"\n📌 Testing {source_name}...")
        print("-" * 80)
        
        try:
            # Get raw results
            raw_results = await search_func(character_tag, page=1, limit=10)
            
            # Process results based on source
            if source_name == "Safebooru.org":
                processed = searcher._process_safebooru_results(raw_results)
            elif source_name == "Konachan.net":
                processed = searcher._process_konachan_results(raw_results)
            elif source_name == "Danbooru":
                processed = searcher._process_danbooru_safe_results(raw_results)
            else:
                processed = []
            
            print(f"✅ Found {len(processed)} safe images from {source_name}")
            
            if processed:
                print(f"\n🖼️  Sample images from {source_name}:")
                for i, img in enumerate(processed[:5], 1):  # Show first 5
                    print(f"\n  [{i}] ID: {img.get('id')}")
                    print(f"      URL: {img.get('url')}")
                    print(f"      Preview: {img.get('preview_url')}")
                    print(f"      Tags: {', '.join(img.get('tags', [])[:8])}")
                    print(f"      Score: {img.get('score')}")
                    print(f"      Size: {img.get('width')}x{img.get('height')}")
                
                all_results.extend(processed[:5])
            else:
                print(f"⚠️  No images passed safety filters from {source_name}")
            
        except Exception as e:
            print(f"❌ Error testing {source_name}: {e}")
    
    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print(f"Total safe images found: {len(all_results)}")
    print()
    
    # Test the full search_all_sources method
    print("\n🔄 Testing combined search (search_all_sources)...")
    print("-" * 80)
    
    try:
        combined_results, total_available = await searcher.search_all_sources(
            character_tag, 
            page=1, 
            limit=20
        )
        
        print(f"✅ Combined search returned {len(combined_results)} images")
        print(f"📊 Total available across all sources: {total_available}")
        print()
        
        if combined_results:
            print("🖼️  COMBINED RESULTS (First 10 for verification):")
            print()
            
            for i, img in enumerate(combined_results[:10], 1):
                print(f"[{i}] Source: {img.get('source')}")
                print(f"    URL: {img.get('url')}")
                print(f"    Preview: {img.get('preview_url')}")
                print(f"    Tags: {', '.join(img.get('tags', [])[:8])}")
                print(f"    Score: {img.get('score')} | Size: {img.get('width')}x{img.get('height')}")
                print()
        
    except Exception as e:
        print(f"❌ Error in combined search: {e}")
    
    print("=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)
    print()
    print("📝 VERIFICATION INSTRUCTIONS:")
    print("1. Copy the URLs above")
    print("2. Paste them into Discord or your browser")
    print("3. Verify that ALL images are:")
    print("   - Wholesome and family-friendly")
    print("   - Fully clothed characters")
    print("   - No suggestive poses or angles")
    print("   - No inappropriate content")
    print()
    print("⚠️  If you find ANY inappropriate images, report them immediately!")
    print()
    
    # Close the session
    await searcher.close()


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_anya_images())