#!/usr/bin/env python3
"""Test individual API sources to verify they work correctly"""

import sys
import asyncio
import aiohttp
import logging
sys.path.append('.')

from utils.cogs.art import *

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

async def test_single_source(source_name: str, source_class, query: str = "1girl", nsfw: bool = False):
    """Test a single art source"""
    print(f"\n🧪 Testing {source_name}...")
    
    try:
        async with aiohttp.ClientSession() as session:
            source = source_class(session)
            
            # Test with a simple query
            art_logger.info(f"Testing {source_name} with query: '{query}' nsfw={nsfw}")
            results = await source.search(query, limit=5, nsfw=nsfw, page=0)
            
            if results:
                print(f"✅ {source_name}: Found {len(results)} results")
                # Show first result details
                first = results[0]
                print(f"   Sample: {first.get('url', 'No URL')[:50]}...")
                print(f"   Tags: {', '.join(str(t) for t in first.get('tags', [])[:3])}")
                return True
            else:
                print(f"❌ {source_name}: No results returned")
                return False
                
    except Exception as e:
        print(f"❌ {source_name}: Error - {str(e)}")
        art_logger.error(f"{source_name} failed: {e}")
        return False

async def test_working_sources():
    """Test the sources that user mentioned are working"""
    working_sources = [
        ("yandere", Yandere),
        ("safebooru", Safebooru), 
        ("wallhaven", Wallhaven),
        ("xbooru_safe", XBooruSafe),
        ("hypnohub_safe", HypnohubSafe),
        ("e621", E621)
    ]
    
    print("🚀 Testing sources that should be working...")
    
    results = {}
    for source_name, source_class in working_sources:
        success = await test_single_source(source_name, source_class)
        results[source_name] = success
        await asyncio.sleep(1)  # Be nice to APIs
    
    print(f"\n📊 Working Sources Test Results:")
    working_count = 0
    for source_name, success in results.items():
        status = "✅ WORKING" if success else "❌ BROKEN"
        print(f"  {source_name}: {status}")
        if success:
            working_count += 1
    
    print(f"\n🎯 {working_count}/{len(working_sources)} sources are working")
    return results

async def test_all_sources():
    """Test all available sources"""
    print("\n🧪 Testing ALL art sources...")
    
    # Source classes with appropriate test queries
    # Many boorus use specific tag systems - "1girl" and "solo" are common tags
    source_tests = {
        "danbooru": (Danbooru, "1girl", False),
        "gelbooru": (Gelbooru, "1girl", False),
        "safebooru": (Safebooru, "1girl", False),
        "konachan": (Konachan, "landscape", False),
        "yandere": (Yandere, "landscape", False),
        "rule34": (Rule34, "1girl", True),  # NSFW only
        "zerochan": (Zerochan, "Anya Forger", False),
        "anime_pictures": (AnimePictures, "girl", False),
        "e621": (E621, "canine", True),  # NSFW only, furry tags
        "realbooru": (Realbooru, "woman", True),  # NSFW only
        "tbib": (TBIB, "1girl", False),
        "aibooru": (AIBooru, "1girl", False),
        "e926": (E926, "canine", False),  # SFW furry
        "konachan_safe": (KonachanSafe, "landscape", False),
        "wallhaven": (Wallhaven, "anime", False),
        "sankaku_safe": (SankakuSafe, "1girl", False),
        "xbooru_safe": (XBooruSafe, "1girl", False),
        "rule34_safe": (Rule34Safe, "1girl", False),
        "hypnohub_safe": (HypnohubSafe, "1girl", False),
        "booru_allthefallen": (BooruAllthefallen, "1girl", False),
        "sankaku": (Sankaku, "1girl", False),
    }
    
    results = {}
    working = []
    broken = []
    
    for source_name, (source_class, query, nsfw) in source_tests.items():
        if source_name in ART_SOURCES:  # Only test sources that are in ART_SOURCES
            success = await test_single_source(source_name, source_class, query, nsfw)
            results[source_name] = success
            if success:
                working.append(source_name)
            else:
                broken.append(source_name)
            await asyncio.sleep(1)  # Rate limiting
    
    print(f"\n📊 COMPLETE TEST RESULTS:")
    print(f"✅ Working ({len(working)}): {', '.join(working)}")
    print(f"❌ Broken ({len(broken)}): {', '.join(broken)}")
    print(f"📈 Success Rate: {len(working)}/{len(working)+len(broken)} ({len(working)/(len(working)+len(broken))*100:.1f}%)")
    
    return working, broken

async def main():
    print("🚀 Starting API Source Tests...\n")
    
    # First test the sources user mentioned should work
    working_results = await test_working_sources()
    
    # Then test all sources
    working, broken = await test_all_sources()
    
    print(f"\n🎉 Testing Complete!")
    print(f"📋 Summary:")
    print(f"  - Total sources tested: {len(working) + len(broken)}")
    print(f"  - Working sources: {len(working)}")
    print(f"  - Broken sources: {len(broken)}")
    
    if broken:
        print(f"\n🔧 Sources that need fixing:")
        for source in broken:
            print(f"  - {source}")

if __name__ == "__main__":
    asyncio.run(main())
