"""
Smart Tag Discovery System V2 - ULTRA AGGRESSIVE Tag Finding
Fetches ALL possible tags, uses multiple name variations, low thresholds,
and parallel discovery for maximum coverage.
"""

import aiohttp
import asyncio
import re
import logging
from typing import List, Dict, Optional, Set
from urllib.parse import quote_plus
from difflib import SequenceMatcher
import json

logger = logging.getLogger(__name__)

# Comprehensive character name to booru tag mapping
# Format: "Character Name" -> "correct_booru_tag"
CHARACTER_TAG_MAP = {
    # === NARUTO / NARUTO SHIPPUDEN ===
    "itachi uchiha": "uchiha_itachi",
    "uchiha itachi": "uchiha_itachi",
    "sasuke uchiha": "uchiha_sasuke",
    "uchiha sasuke": "uchiha_sasuke",
    "naruto uzumaki": "uzumaki_naruto",
    "uzumaki naruto": "uzumaki_naruto",
    "sakura haruno": "haruno_sakura",
    "haruno sakura": "haruno_sakura",
    "kakashi hatake": "hatake_kakashi",
    "hatake kakashi": "hatake_kakashi",
    "hinata hyuga": "hyuuga_hinata",
    "hyuga hinata": "hyuuga_hinata",
    "gaara": "gaara",
    "rock lee": "rock_lee",
    "neji hyuga": "hyuuga_neji",
    "shikamaru nara": "nara_shikamaru",
    "temari": "temari",
    "tsunade": "tsunade_(naruto)",
    "jiraiya": "jiraiya",
    "orochimaru": "orochimaru",
    "madara uchiha": "uchiha_madara",
    "obito uchiha": "uchiha_obito",
    "minato namikaze": "namikaze_minato",
    "kushina uzumaki": "uzumaki_kushina",
    "pain": "pain_(naruto)",
    "konan": "konan",
    
    # === MY HERO ACADEMIA ===
    "izuku midoriya": "midoriya_izuku",
    "deku": "midoriya_izuku",
    "katsuki bakugo": "bakugou_katsuki",
    "bakugo": "bakugou_katsuki",
    "shoto todoroki": "todoroki_shouto",
    "todoroki": "todoroki_shouto",
    "ochako uraraka": "uraraka_ochako",
    "uraraka": "uraraka_ochako",
    "momo yaoyorozu": "yaoyorozu_momo",
    "tsuyu asui": "asui_tsuyu",
    "all might": "all_might",
    
    # === ATTACK ON TITAN ===
    "eren yeager": "eren_yeager",
    "eren jaeger": "eren_yeager",
    "mikasa ackerman": "mikasa_ackerman",
    "levi ackerman": "levi_(shingeki_no_kyojin)",
    "levi": "levi_(shingeki_no_kyojin)",
    "armin arlert": "armin_arlert",
    "historia reiss": "historia_reiss",
    "sasha braus": "sasha_braus",
    "annie leonhart": "annie_leonhart",
    "reiner braun": "reiner_braun",
    
    # === DEMON SLAYER ===
    "tanjiro kamado": "kamado_tanjirou",
    "nezuko kamado": "kamado_nezuko",
    "zenitsu agatsuma": "agatsuma_zenitsu",
    "inosuke hashibira": "hashibira_inosuke",
    "giyu tomioka": "tomioka_giyuu",
    "shinobu kocho": "kochou_shinobu",
    "mitsuri kanroji": "kanroji_mitsuri",
    "kyojuro rengoku": "rengoku_kyoujurou",
    
    # === JUJUTSU KAISEN ===
    "yuji itadori": "itadori_yuuji",
    "megumi fushiguro": "fushiguro_megumi",
    "nobara kugisaki": "kugisaki_nobara",
    "satoru gojo": "gojou_satoru",
    "gojo": "gojou_satoru",
    "maki zenin": "zenin_maki",
    "toge inumaki": "inumaki_toge",
    "yuta okkotsu": "okkotsu_yuuta",
    
    # === SPY X FAMILY ===
    "anya forger": "anya_(spy_x_family)",
    "anya": "anya_(spy_x_family)",
    "loid forger": "loid_forger",
    "yor forger": "yor_forger",
    "yor briar": "yor_forger",
    "damian desmond": "damian_desmond",
    "becky blackbell": "becky_blackbell",
    
    # === ONE PIECE ===
    "monkey d luffy": "monkey_d._luffy",
    "luffy": "monkey_d._luffy",
    "roronoa zoro": "roronoa_zoro",
    "zoro": "roronoa_zoro",
    "nami": "nami_(one_piece)",
    "sanji": "sanji",
    "nico robin": "nico_robin",
    "robin": "nico_robin",
    "tony tony chopper": "tony_tony_chopper",
    "chopper": "tony_tony_chopper",
    "trafalgar law": "trafalgar_law",
    "law": "trafalgar_law",
    "portgas d ace": "portgas_d._ace",
    "ace": "portgas_d._ace",
    
    # === CHAINSAW MAN ===
    "denji": "denji_(chainsaw_man)",
    "power": "power_(chainsaw_man)",
    "makima": "makima_(chainsaw_man)",
    "aki hayakawa": "aki_hayakawa",
    "kobeni higashiyama": "higashiyama_kobeni",
    
    # === RE:ZERO ===
    "subaru natsuki": "natsuki_subaru",
    "emilia": "emilia_(re:zero)",
    "rem": "rem_(re:zero)",
    "ram": "ram_(re:zero)",
    "beatrice": "beatrice_(re:zero)",
    
    # === FATE SERIES ===
    "saber": "saber_(fate)",
    "artoria pendragon": "artoria_pendragon_(fate)",
    "rin tohsaka": "tohsaka_rin",
    "archer": "archer_(fate/stay_night)",
    "gilgamesh": "gilgamesh_(fate)",
    "ishtar": "ishtar_(fate)",
    "ereshkigal": "ereshkigal_(fate)",
    "jeanne d'arc": "jeanne_d'arc_(fate)",
    "mash kyrielight": "mash_kyrielight",
    
    # === GENSHIN IMPACT ===
    "raiden shogun": "raiden_shogun",
    "ei": "raiden_shogun",
    "yae miko": "yae_miko",
    "hu tao": "hu_tao_(genshin_impact)",
    "ganyu": "ganyu_(genshin_impact)",
    "keqing": "keqing_(genshin_impact)",
    "zhongli": "zhongli_(genshin_impact)",
    "venti": "venti_(genshin_impact)",
    "nahida": "nahida_(genshin_impact)",
    "furina": "furina_(genshin_impact)",
    "neuvillette": "neuvillette_(genshin_impact)",
}


class SmartTagDiscovery:
    """Ultra-aggressive tag discovery - finds EVERY possible matching tag"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.tag_cache: Dict[str, Dict[str, List[str]]] = {}
        
    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=15, connect=8)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={'User-Agent': 'AnyaBot/3.0 (Discord Bot; Ultra Tag Discovery)'}
            )
        return self.session
    
    def _normalize(self, name: str) -> str:
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', '_', normalized)
        return normalized
    
    def _generate_all_variations(self, character_name: str, series_name: str = None) -> List[str]:
        """Generate ALL possible name variations for maximum tag matching"""
        variations = set()
        
        # PRIORITY 1: Check CHARACTER_TAG_MAP for exact match
        char_lower = character_name.lower().strip()
        if char_lower in CHARACTER_TAG_MAP:
            exact_tag = CHARACTER_TAG_MAP[char_lower]
            variations.add(exact_tag)
            logger.info(f"[TagDiscovery] Found exact mapping: '{character_name}' -> '{exact_tag}'")
            # Add the exact tag as PRIMARY, but still generate variations as fallback
        
        base = self._normalize(character_name)
        variations.add(base)
        
        parts = base.split('_')
        
        # Add first name only (CRITICAL for Safebooru/Danbooru format)
        if len(parts) >= 1:
            variations.add(parts[0])
        
        if len(parts) >= 2:
            variations.add(f"{parts[0]}_{parts[1]}")
            variations.add(f"{parts[1]}_{parts[0]}")  # Japanese name order
            variations.add(parts[1])
            
        if len(parts) >= 3:
            variations.add(f"{parts[0]}_{parts[1]}_{parts[2]}")
            variations.add(f"{parts[2]}_{parts[0]}_{parts[1]}")
            variations.add(f"{parts[0]}_{parts[2]}")
            variations.add(f"{parts[1]}_{parts[2]}")
        
        # CRITICAL: Add series-disambiguated first name (Danbooru/Safebooru standard)
        if series_name:
            series_norm = self._normalize(series_name)
            # First name + series is the most common format
            if parts:
                variations.add(f"{parts[0]}_({series_norm})")
            # Also add full variations with series
            for v in list(variations):
                if '(' not in v:  # Don't double-add series
                    variations.add(f"{v}_({series_norm})")
        
        return list(variations)
    
    def _similarity(self, s1: str, s2: str) -> float:
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
    
    def _score_tag(self, tag: str, char_name: str, series_name: str = None, count: int = 0) -> float:
        score = 0.0
        tag_lower = tag.lower()
        char_norm = self._normalize(char_name)
        
        # Extract first name from character name for comparison
        char_first = char_norm.split('_')[0] if '_' in char_norm else char_norm
        
        # Extract tag base (without series parenthetical)
        tag_base = re.sub(r'\([^)]+\)$', '', tag_lower).strip('_')
        tag_first = tag_base.split('_')[0] if '_' in tag_base else tag_base
        
        # CRITICAL: Prefer first_name_(series) format over full_name_(series)
        if series_name:
            series_norm = self._normalize(series_name)
            match = re.search(r'\(([^)]+)\)$', tag_lower)
            if match:
                tag_series = match.group(1)
                # Exact match: first_name_(series)
                if tag_first == char_first and (series_norm in tag_series or tag_series in series_norm):
                    score += 1000  # HIGHEST priority
                # Full name match with series
                elif tag_base == char_norm and (series_norm in tag_series or tag_series in series_norm):
                    score += 800
                # Series match bonus
                elif series_norm in tag_series or tag_series in series_norm:
                    score += 400
                    series_sim = self._similarity(tag_series, series_norm)
                    score += series_sim * 200
        
        # Name matching
        if tag_lower == char_norm:
            score += 500
        elif tag_first == char_first:
            score += 300  # First name match is good
        elif tag_lower.startswith(char_norm):
            score += 200
        elif char_norm in tag_lower:
            score += 100
        
        # Similarity bonus
        score += self._similarity(tag_base, char_norm) * 80
        
        # Popularity bonus
        if count > 5000:
            score += 100
        elif count > 1000:
            score += 60
        elif count > 100:
            score += 30
        elif count > 10:
            score += 10
        
        return score

    async def _fetch_tags_safebooru(self, search_term: str) -> List[Dict]:
        session = await self.get_session()
        tags = []
        try:
            params = {
                'page': 'dapi', 's': 'tag', 'q': 'index', 'json': '1',
                'name_pattern': f'{search_term}%', 'orderby': 'count', 'limit': 100
            }
            async with session.get('https://safebooru.org/index.php', params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        tags = [{'name': t.get('name', ''), 'count': int(t.get('count', 0))} for t in data]
                        logger.info(f"[DEBUG TAGS] Safebooru API returned {len(tags)} tags for '{search_term}%'")
                        for tag in tags[:5]:
                            logger.debug(f"[DEBUG TAGS] Safebooru tag: '{tag['name']}' (count: {tag['count']})")
        except Exception as e:
            logger.error(f"[TagDiscovery] Safebooru error: {e}")
        return tags

    async def _fetch_tags_danbooru(self, search_term: str) -> List[Dict]:
        session = await self.get_session()
        tags = []
        try:
            params = {
                'search[name_matches]': f'{search_term}*',
                'search[category]': '4', 'search[order]': 'count', 'limit': 100
            }
            async with session.get('https://danbooru.donmai.us/tags.json', params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        tags = [{'name': t.get('name', ''), 'count': t.get('post_count', 0)} for t in data]
        except Exception as e:
            logger.debug(f"[TagDiscovery] Danbooru error: {e}")
        return tags

    async def _fetch_tags_gelbooru(self, search_term: str) -> List[Dict]:
        session = await self.get_session()
        tags = []
        try:
            params = {
                'page': 'dapi', 's': 'tag', 'q': 'index', 'json': '1',
                'name_pattern': f'{search_term}%', 'orderby': 'count', 'limit': 100
            }
            async with session.get('https://gelbooru.com/index.php', params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tag_list = data.get('tag', []) if isinstance(data, dict) else data
                    if isinstance(tag_list, list):
                        tags = [{'name': t.get('name', ''), 'count': int(t.get('count', 0))} for t in tag_list]
        except Exception as e:
            logger.debug(f"[TagDiscovery] Gelbooru error: {e}")
        return tags

    async def _fetch_tags_yandere(self, search_term: str) -> List[Dict]:
        session = await self.get_session()
        tags = []
        try:
            params = {'name': f'{search_term}*', 'order': 'count', 'limit': 100}
            async with session.get('https://yande.re/tag.json', params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        tags = [{'name': t.get('name', ''), 'count': t.get('count', 0)} for t in data]
        except Exception as e:
            logger.debug(f"[TagDiscovery] Yande.re error: {e}")
        return tags

    async def _fetch_tags_konachan(self, search_term: str) -> List[Dict]:
        session = await self.get_session()
        tags = []
        try:
            params = {'name': f'{search_term}*', 'order': 'count', 'limit': 100}
            async with session.get('https://konachan.net/tag.json', params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        tags = [{'name': t.get('name', ''), 'count': t.get('count', 0)} for t in data]
        except Exception as e:
            logger.debug(f"[TagDiscovery] Konachan error: {e}")
        return tags

    async def discover_best_tags(self, character_name: str, series_name: str = None) -> Dict[str, List[str]]:
        """Discover ALL matching tags for each source using ALL name variations."""
        cache_key = f"{self._normalize(character_name)}_{self._normalize(series_name or 'none')}"
        if cache_key in self.tag_cache:
            return self.tag_cache[cache_key]
        
        variations = self._generate_all_variations(character_name, series_name)
        logger.info(f"[DEBUG TAGS] Generated {len(variations)} variations: {variations}")
        
        source_fetchers = {
            'safebooru': self._fetch_tags_safebooru,
            'danbooru': self._fetch_tags_danbooru,
            'gelbooru': self._fetch_tags_gelbooru,
            'yandere': self._fetch_tags_yandere,
            'konachan': self._fetch_tags_konachan,
        }
        
        all_tasks = []
        task_info = []
        
        for source, fetcher in source_fetchers.items():
            for var in variations:
                all_tasks.append(fetcher(var))
                task_info.append((source, var))
        
        results = await asyncio.gather(*all_tasks, return_exceptions=True)
        
        source_tags: Dict[str, Dict[str, int]] = {s: {} for s in source_fetchers}
        
        for (source, var), result in zip(task_info, results):
            if isinstance(result, list):
                logger.info(f"[DEBUG TAGS] {source} - Found {len(result)} tags for '{var}'")
                for tag_data in result:
                    name = tag_data.get('name', '')
                    count = tag_data.get('count', 0)
                    if name:
                        if name not in source_tags[source] or source_tags[source][name] < count:
                            source_tags[source][name] = count
                            logger.debug(f"[DEBUG TAGS] {source} - Tag: '{name}', count: {count}")
        
        discovered: Dict[str, List[str]] = {}
        
        for source, tags_dict in source_tags.items():
            scored = []
            for tag, count in tags_dict.items():
                score = self._score_tag(tag, character_name, series_name, count)
                if score >= 50:
                    scored.append((tag, score, count))
            
            scored.sort(key=lambda x: x[1], reverse=True)
            best_tags = [t[0] for t in scored[:5]]
            
            if best_tags:
                discovered[source] = best_tags
                logger.info(f"[TagDiscovery] {source}: {best_tags}")
        
        fallback = self._normalize(character_name)
        if series_name:
            fallback = f"{fallback}_({self._normalize(series_name)})"
        
        for source in source_fetchers:
            if source not in discovered or not discovered[source]:
                discovered[source] = [fallback]
        
        best_overall = discovered.get('safebooru', [fallback])
        discovered['tbib'] = best_overall
        discovered['anime_pictures'] = best_overall
        
        self.tag_cache[cache_key] = discovered
        return discovered

    async def discover_all_tags(self, character_name: str, series_name: str = None) -> Dict[str, str]:
        """Compatibility wrapper - returns single best tag per source"""
        multi_tags = await self.discover_best_tags(character_name, series_name)
        return {source: tags[0] if tags else '' for source, tags in multi_tags.items()}

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


_instance: Optional[SmartTagDiscovery] = None

def get_tag_discovery() -> SmartTagDiscovery:
    global _instance
    if _instance is None:
        _instance = SmartTagDiscovery()
    return _instance
