#!/usr/bin/env python3
"""
Parse Telegram HTML export into posts.json for the astronomy archive site.
Uses only Python stdlib (html.parser).

v2: Properly merges joined messages, extracts videos, and handles GIF animations.
"""

import json
import re
import os
from html.parser import HTMLParser
from datetime import datetime

# ── Topic taxonomy with keyword matching ──────────────────────
TAXONOMY = {
    "solar_system": {
        "label": "🪐 Солнечная система",
        "children": {
            "planets": {
                "label": "Планеты",
                "keywords": [
                    "меркурий", "венера", "земля", "марс", "юпитер",
                    "сатурн", "уран", "нептун", "планет"
                ]
            },
            "dwarf_planets": {
                "label": "Карликовые планеты",
                "keywords": ["плутон", "церера", "эрида", "хаумеа", "макемаке", "карликов"]
            },
            "moons": {
                "label": "Спутники",
                "keywords": [
                    "титания", "энцелад", "ио ", "титан ", "луна", "спутник",
                    "ганимед", "каллисто", "европа", "тритон", "оберон",
                    "миранда", "ариэль", "умбриэль", "харон", "фобос", "деймос"
                ]
            },
            "comets_asteroids": {
                "label": "Кометы и астероиды",
                "keywords": ["комет", "астероид", "метеор", "болид"]
            },
            "sun": {
                "label": "Солнце",
                "keywords": ["солнц", "солнеч", "корональн", "протуберанц", "вспышк"]
            }
        }
    },
    "deep_space": {
        "label": "🌌 Глубокий космос",
        "children": {
            "nebulae": {
                "label": "Туманности",
                "keywords": ["туманност", "эмиссионн", "отражательн", "планетарн"]
            },
            "galaxies": {
                "label": "Галактики",
                "keywords": ["галактик", "млечн", "андромед"]
            },
            "stars": {
                "label": "Звёзды",
                "keywords": ["звезд", "звёзд", "сверхнов", "нейтрон", "пульсар", "белый карлик", "красный гигант", "красный карлик"]
            },
            "black_holes": {
                "label": "Чёрные дыры",
                "keywords": ["чёрн", "черн", "дыр", "горизонт событий", "сингулярност"]
            }
        }
    },
    "space_exploration": {
        "label": "🚀 Космонавтика",
        "children": {
            "missions": {
                "label": "Миссии",
                "keywords": [
                    "миссия", "миссии", "зонд", "аппарат", "кассини", "вояджер",
                    "новые горизонты", "джуно", "марсоход", "ровер", "луноход",
                    "посадочный модуль"
                ]
            },
            "astronauts": {
                "label": "Космонавты и история",
                "keywords": [
                    "гагарин", "космонавт", "астронавт", "мкс", "космическ станц",
                    "аполлон", "шаттл", "союз", "spacex", "наса", "роскосмос"
                ]
            },
            "telescopes": {
                "label": "Телескопы",
                "keywords": ["телескоп", "хаббл", "уэбб", "джеймс уэбб", "jwst", "hubble"]
            }
        }
    },
    "events": {
        "label": "🌍 Астрономические события",
        "children": {
            "events": {
                "label": "События",
                "keywords": [
                    "затмение", "противостояние", "парад планет",
                    "метеорный поток", "суперлун", "равноденств",
                    "солнцестояни"
                ]
            }
        }
    }
}


def classify_post(text_lower, post_id=None):
    """Return list of {category, subcategory} for matching topics with refined rules and overrides."""
    # Curated manual overrides for static archive posts to ensure 100% correct taxonomy
    OVERRIDES = {
        "message414930": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}, {"category": "space_exploration", "subcategory": "missions"}],
        "message418238": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message439600": [{"category": "space_exploration", "subcategory": "astronauts"}],
        "message457274": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message461445": [{"category": "solar_system", "subcategory": "planets"}],
        "message465960": [{"category": "solar_system", "subcategory": "planets"}, {"category": "space_exploration", "subcategory": "telescopes"}],
        "message480499": [{"category": "solar_system", "subcategory": "dwarf_planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message525588": [{"category": "solar_system", "subcategory": "planets"}],
        "message530465": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}, {"category": "space_exploration", "subcategory": "missions"}],
        "message560921": [{"category": "deep_space", "subcategory": "stars"}],
        "message570852": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message593812": [{"category": "deep_space", "subcategory": "nebulae"}],
        "message595458": [{"category": "space_exploration", "subcategory": "astronauts"}],
        "message595716": [{"category": "solar_system", "subcategory": "moons"}, {"category": "space_exploration", "subcategory": "missions"}, {"category": "space_exploration", "subcategory": "astronauts"}],
        "message602109": [{"category": "solar_system", "subcategory": "moons"}, {"category": "space_exploration", "subcategory": "astronauts"}],
        "message616034": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message650948": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "comets_asteroids"}],
        "message663568": [{"category": "deep_space", "subcategory": "stars"}],
        "message668141": [{"category": "events", "subcategory": "events"}],
        "message676818": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message678580": [{"category": "solar_system", "subcategory": "comets_asteroids"}],
        "message680331": [{"category": "solar_system", "subcategory": "comets_asteroids"}],
        "message683535": [{"category": "deep_space", "subcategory": "galaxies"}],
        "message694716": [{"category": "events", "subcategory": "events"}],
        "message697060": [{"category": "solar_system", "subcategory": "comets_asteroids"}],
        "message758828": [{"category": "events", "subcategory": "events"}],
        "message780078": [{"category": "solar_system", "subcategory": "moons"}],
        "message798377": [{"category": "solar_system", "subcategory": "comets_asteroids"}],
        "message802602": [{"category": "deep_space", "subcategory": "nebulae"}],
        "message817530": [{"category": "solar_system", "subcategory": "comets_asteroids"}],
        "message885834": [{"category": "solar_system", "subcategory": "dwarf_planets"}],
        "message911130": [{"category": "space_exploration", "subcategory": "telescopes"}],
        "message914969": [{"category": "events", "subcategory": "events"}],
        "message919904": [{"category": "solar_system", "subcategory": "planets"}, {"category": "space_exploration", "subcategory": "missions"}],
        "message932380": [{"category": "solar_system", "subcategory": "planets"}],
        "message982107": [{"category": "deep_space", "subcategory": "nebulae"}],
        "message986893": [{"category": "space_exploration", "subcategory": "telescopes"}],
        "message1000440": [{"category": "events", "subcategory": "events"}],
        "message1030624": [{"category": "deep_space", "subcategory": "stars"}],
        "message1037738": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message1068294": [{"category": "solar_system", "subcategory": "planets"}, {"category": "space_exploration", "subcategory": "missions"}],
        "message1070072": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message1071534": [],
        "message1084129": [{"category": "solar_system", "subcategory": "planets"}],
        "message1098518": [{"category": "events", "subcategory": "events"}],
        "message1098912": [{"category": "deep_space", "subcategory": "nebulae"}, {"category": "space_exploration", "subcategory": "telescopes"}],
        "message1139616": [{"category": "deep_space", "subcategory": "stars"}],
        "message1141369": [{"category": "solar_system", "subcategory": "dwarf_planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message1145390": [{"category": "solar_system", "subcategory": "dwarf_planets"}],
        "message1146317": [{"category": "deep_space", "subcategory": "galaxies"}],
        "message1166779": [{"category": "solar_system", "subcategory": "moons"}, {"category": "events", "subcategory": "events"}],
        "message1173823": [{"category": "deep_space", "subcategory": "black_holes"}],
        "message1193340": [{"category": "events", "subcategory": "events"}],
        "message1210162": [{"category": "solar_system", "subcategory": "planets"}],
        "message1220956": [{"category": "solar_system", "subcategory": "planets"}],
        "message1236445": [{"category": "solar_system", "subcategory": "planets"}],
        "message1246078": [{"category": "solar_system", "subcategory": "comets_asteroids"}],
        "message1257591": [],
        "message1270319": [{"category": "events", "subcategory": "events"}],
        "message1291721": [{"category": "deep_space", "subcategory": "galaxies"}],
        "message1303150": [{"category": "solar_system", "subcategory": "planets"}],
        "message1322081": [{"category": "solar_system", "subcategory": "planets"}],
        "message1364106": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message1364138": [{"category": "solar_system", "subcategory": "planets"}],
        "message1383227": [{"category": "events", "subcategory": "events"}],
        "message1387730": [{"category": "events", "subcategory": "events"}],
        "message1390305": [{"category": "solar_system", "subcategory": "planets"}],
        "message1393785": [{"category": "events", "subcategory": "events"}],
        "message1394135": [{"category": "deep_space", "subcategory": "stars"}],
        "message1445364": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message1445578": [{"category": "deep_space", "subcategory": "nebulae"}],
        "message1445974": [{"category": "deep_space", "subcategory": "galaxies"}],
        "message1446910": [{"category": "deep_space", "subcategory": "galaxies"}],
        "message1452366": [{"category": "deep_space", "subcategory": "galaxies"}],
        "message1453388": [{"category": "deep_space", "subcategory": "galaxies"}],
        "message1457205": [{"category": "deep_space", "subcategory": "nebulae"}, {"category": "deep_space", "subcategory": "stars"}, {"category": "space_exploration", "subcategory": "telescopes"}],
        "message1457964": [{"category": "space_exploration", "subcategory": "missions"}, {"category": "space_exploration", "subcategory": "astronauts"}],
        # ── New posts from ChatExport_2026-06-07 ──
        "message1470923": [{"category": "deep_space", "subcategory": "galaxies"}],
        "message1479696": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message1489925": [{"category": "deep_space", "subcategory": "stars"}],
        "message1492469": [{"category": "events", "subcategory": "events"}],
        "message1497327": [{"category": "solar_system", "subcategory": "planets"}],
        "message1503180": [{"category": "solar_system", "subcategory": "planets"}, {"category": "solar_system", "subcategory": "moons"}],
        "message1506276": [{"category": "deep_space", "subcategory": "galaxies"}],
        "message1507591": [{"category": "space_exploration", "subcategory": "missions"}, {"category": "space_exploration", "subcategory": "astronauts"}],
        "message1530023": [{"category": "solar_system", "subcategory": "planets"}],
        "message1540694": [{"category": "events", "subcategory": "events"}],
        "message1546488": [{"category": "deep_space", "subcategory": "nebulae"}],
        "message1563567": [{"category": "events", "subcategory": "events"}],
        "message1564795": [{"category": "deep_space", "subcategory": "nebulae"}, {"category": "deep_space", "subcategory": "stars"}],
        "message1565766": [{"category": "solar_system", "subcategory": "sun"}],
        "message1565907": [{"category": "solar_system", "subcategory": "comets_asteroids"}],
    }

    if post_id in OVERRIDES:
        return OVERRIDES[post_id]

    import re
    topics = []
    
    # 1. Galaxies
    if re.search(r'(галактик|млечн|андромед)', text_lower):
        topics.append({"category": "deep_space", "subcategory": "galaxies"})
        
    # 2. Nebulae
    has_nebulae = False
    if "туманност" in text_lower:
        has_nebulae = True
    elif "эмиссионн" in text_lower or "планетарн" in text_lower:
        has_nebulae = True
    elif "отражательн" in text_lower and not "отражательная способность" in text_lower and not "отражательную способность" in text_lower:
        has_nebulae = True
        
    if has_nebulae:
        topics.append({"category": "deep_space", "subcategory": "nebulae"})
        
    # 3. Black holes
    has_black_hole = False
    if "горизонт событий" in text_lower or "сингулярност" in text_lower:
        has_black_hole = True
    elif re.search(r'\b(черн|чёрн)[а-я]*\s+дыр', text_lower):
        has_black_hole = True
    elif "сверхмассивн" in text_lower and "дыр" in text_lower:
        has_black_hole = True
        
    if has_black_hole:
        topics.append({"category": "deep_space", "subcategory": "black_holes"})
        
    # 4. Stars
    has_stars = False
    if re.search(r'(сверхнов|нейтронн|пульсар|карлик)', text_lower):
        has_stars = True
    elif "звездное скоплен" in text_lower or "звёздное скоплен" in text_lower:
        has_stars = True
    elif "звездное образован" in text_lower or "звёздообразован" in text_lower or "звездообразован" in text_lower:
        has_stars = True
    else:
        # Match звезд/звёзд but NOT созвезди and NOT звездочк
        zve_count = len(re.findall(r'звезд|звёзд', text_lower))
        soz_count = len(re.findall(r'созвезди', text_lower))
        star_metaphor_count = len(re.findall(r'звездочк|звёздочк', text_lower))
        if zve_count > (soz_count + star_metaphor_count):
            has_stars = True
            
    if has_stars:
        topics.append({"category": "deep_space", "subcategory": "stars"})
        
    # 5. Sun
    has_sun = False
    if re.search(r'(корональн|протуберанц|вспышк)', text_lower) and not "сверхнов" in text_lower:
        has_sun = True
    elif re.search(r'\b(солнц[еауо]|солнеч)', text_lower):
        # Exclude: "подсолнух", "Солнечной системы", "солнечного света", "солнечные лучи", "от Солнца", etc.
        clean_text = text_lower
        clean_text = clean_text.replace("подсолнух", "")
        clean_text = clean_text.replace("солнцестоян", "")
        clean_text = re.sub(r'солнечн[аяыеоиу]?[^\s]*\s+систем[аыеоу]?[^\s]*', '', clean_text)
        clean_text = re.sub(r'солнечн[аяыеоиу]?[^\s]*\s+свет[а-я]*', '', clean_text)
        clean_text = re.sub(r'солнечн[аяыеоиу]?[^\s]*\s+луч[а-я]*', '', clean_text)
        clean_text = re.sub(r'солнечн[аяыеоиу]?[^\s]*\s+сут[а-я]*', '', clean_text)
        
        # Exclude comparisons
        clean_text = re.sub(r'масс[аыуо]?[^\s]*\s+солнца', '', clean_text)
        clean_text = re.sub(r'больше\s+чем\s+у\s+солнца', '', clean_text)
        clean_text = re.sub(r'раз\s+больше\s+солнца', '', clean_text)
        clean_text = re.sub(r'температур[а-я]*\s+солнца', '', clean_text)
        clean_text = re.sub(r'вроде\s+солнца', '', clean_text)
        clean_text = re.sub(r'типа\s+солнца', '', clean_text)
        clean_text = re.sub(r'подобно\s+солнцу', '', clean_text)
        
        # Exclude distance/location
        clean_text = re.sub(r'удалённости\s+от\s+солнца', '', clean_text)
        clean_text = re.sub(r'расстояни[яеи]?\s+от\s+солнца', '', clean_text)
        clean_text = re.sub(r'планет[а-я]*\s+от\s+солнца', '', clean_text)
        clean_text = re.sub(r'дальн[а-я]*\s+от\s+солнца', '', clean_text)
        clean_text = re.sub(r'перв[а-я]*\s+от\s+солнца', '', clean_text)
        clean_text = re.sub(r'ближайш[а-я]*\s+к\s+солнцу', '', clean_text)
        clean_text = re.sub(r'обращения\s+вокруг\s+солнца', '', clean_text)
        clean_text = re.sub(r'вращения\s+вокруг\s+солнца', '', clean_text)
        clean_text = re.sub(r'захода\s+солнца', '', clean_text)
        clean_text = re.sub(r'восход[а-я]*\s+солнца', '', clean_text)
        clean_text = re.sub(r'заслони[а-я]*\s+солнце', '', clean_text)
        clean_text = re.sub(r'обращён[а-я]*\s+к\s+солнцу', '', clean_text)
        clean_text = re.sub(r'повернут[а-я]*\s+к\s+солнцу', '', clean_text)
        clean_text = re.sub(r'обращен[а-я]*\s+к\s+солнцу', '', clean_text)
        clean_text = re.sub(r'солнечн[а-я]*\s+вет(е|р)[а-я]*', '', clean_text)
        clean_text = re.sub(r'обраща[а-я]*\s+вокруг\s+солнца', '', clean_text)
        clean_text = re.sub(r'враща[а-я]*\s+вокруг\s+солнца', '', clean_text)
        
        if re.search(r'\b(солнц[еауо]|солнеч)', clean_text):
            has_sun = True
            
    if has_sun:
        topics.append({"category": "solar_system", "subcategory": "sun"})
        
    # 6. Planets
    has_planets = False
    planets_pattern = r'\b(меркури[йяеюме]|венер[аыеуо]|земл[яеиюо]|[зЗ]емл[яеиюо]|марс[аеуо]?|юпитер[аеуо]?|сатурн[аеуо]?|уран[аеуо]?|нептун[аеуо]?)\b'
    if re.search(planets_pattern, text_lower):
        has_planets = True
    elif re.search(r'\bпланет[аыеуо]?\b', text_lower):
        pla_count = len(re.findall(r'\bпланет', text_lower))
        plan_neb_count = len(re.findall(r'планетарн', text_lower))
        if pla_count > plan_neb_count:
            has_planets = True
            
    if has_planets:
        topics.append({"category": "solar_system", "subcategory": "planets"})
        
    # 7. Dwarf Planets
    dwarf_planets_pattern = r'\b(плутон[аеуо]?|церер[аыеуо]|эрид[аыеуо]|хауме[аыеуо]|макемаке)\b'
    clean_dwarf = text_lower
    clean_dwarf = re.sub(r'орбит[а-я]*\s+плутона', '', clean_dwarf)
    if re.search(dwarf_planets_pattern, clean_dwarf) or "карликов" in clean_dwarf:
        topics.append({"category": "solar_system", "subcategory": "dwarf_planets"})
        
    # 8. Moons
    moons_pattern = r'\b(титани[яиею]|энцелад[аеуо]?|ио|титан[аеуо]?|лун[аыеуои]|[лЛ]ун[аыеуои]|спутник[иаовеу]?|ганимед[аеуо]?|каллисто|европ[аыеуо]|тритон[аеуо]?|оберон[аеуо]?|миранд[аыеуо]|ариэль|умбриэль|харон[аеуо]?|фобос[аеуо]?|деймос[аеуо]?)\b'
    if re.search(moons_pattern, text_lower):
        moons_count = len(re.findall(moons_pattern, text_lower))
        art_count = len(re.findall(r'искусственн[а-я]*\s+спутник', text_lower))
        if moons_count > art_count:
            topics.append({"category": "solar_system", "subcategory": "moons"})
        
    # 9. Comets and Asteroids
    if re.search(r'(комет[а-я]*|астероид[a-я]*|метеор[а-я]*|болид[а-я]*)', text_lower):
        topics.append({"category": "solar_system", "subcategory": "comets_asteroids"})
        
    # 10. Missions
    if re.search(r'(мисси[яи]|зонд[а-я]*|космическ[а-я]* аппарат[а-я]*|кассини|вояджер|новые горизонты|джуно|юнона|марсоход[а-я]*|ровер[а-я]*|луноход[а-я]*|посадочный модуль|артемид[а-я]*|пионер|магеллан[а-я]*|паркер|parker)', text_lower):
        topics.append({"category": "space_exploration", "subcategory": "missions"})
        
    # 11. Astronauts
    has_astronauts = False
    if re.search(r'(гагарин[а-я]*|космонавт[а-я]*|астронавт[а-я]*|мкс|шаттл[а-я]*|spacex|наса|роскосмос|аполлон[а-я]*)', text_lower):
        has_astronauts = True
    elif "станци" in text_lower and "космическ" in text_lower:
        has_astronauts = True
    elif "союз" in text_lower and not ("астрономическ" in text_lower or "международн" in text_lower):
        has_astronauts = True
        
    if has_astronauts:
        topics.append({"category": "space_exploration", "subcategory": "astronauts"})
        
    # 12. Telescopes
    if re.search(r'(телескоп[а-я]*|хаббл[а-я]*|уэбб[а-я]*|jwst|hubble|обсерватор[а-я]*)', text_lower):
        topics.append({"category": "space_exploration", "subcategory": "telescopes"})
        
    # 13. Events
    if re.search(r'(затмени[еяи]|противостояни[еяи]|парад планет|метеорный поток|суперлун[иье][а-я]*|равноденств[iи]е[а-я]*|солнцестояни[еяи]|полнолун[иье][а-я]*|новолун[иье][а-я]*|микролун[иье][а-я]*|астрокалендарь|календарь)', text_lower):
        topics.append({"category": "events", "subcategory": "events"})
        
    return topics


def html_to_text(html_str):
    """Strip tags and decode entities for search indexing."""
    text = re.sub(r'<br\s*/?>', '\n', html_str)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    text = text.replace('&quot;', '"').replace('&#039;', "'")
    return text.strip()


def clean_author(name):
    """Normalize author names to merge aliases and strip timestamps."""
    if not name:
        return ""
    # Normalize xxhezme variants
    if name.lower().startswith("xxhezme"):
        return "xxhezme"
    # Remove trailing date/time (e.g. "  06.02.2025 13:33:52")
    name = re.sub(r"\s+\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2}", "", name)
    return name.strip()


# ── Parse the big HTML file ───────────────────────────────────
class TelegramParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.posts = []
        self.current_post = None
        self.current_date_section = ""

        # State tracking
        self._in_message = False
        self._is_joined = False
        self._in_from_name = False
        self._in_date = False
        self._in_text = False
        self._in_reaction = False
        self._in_emoji = False
        self._in_count = False
        self._in_service = False
        self._in_service_body = False
        self._in_video_duration = False

        self._text_depth = 0
        self._text_buffer = ""
        self._from_buffer = ""
        self._date_title = ""
        self._date_time = ""
        self._service_buffer = ""
        self._current_emoji = ""
        self._current_reaction_count = ""
        self._video_duration_buffer = ""

        self._current_reactions = []
        self._pending_images = []
        self._pending_videos = []
        self._message_id = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "").split()

        # Detect service messages (date separators)
        if tag == "div" and "message" in classes and "service" in classes:
            self._in_service = True
            self._service_buffer = ""
            return

        if self._in_service and tag == "div" and "body" in classes and "details" in classes:
            self._in_service_body = True
            return

        # Detect message div
        if tag == "div" and "message" in classes and "default" in classes:
            self._in_message = True
            self._is_joined = "joined" in classes
            self._message_id = attrs_dict.get("id", "")

            if not self._is_joined:
                # Flush previous post, start a new one
                self._flush_post()
                self.current_post = {
                    "id": self._message_id,
                    "author": "",
                    "date": "",
                    "dateISO": "",
                    "html": "",
                    "text": "",
                    "images": [],
                    "videos": [],
                    "reactions": [],
                    "topics": []
                }
                self._pending_images = []
                self._pending_videos = []
                self._current_reactions = []
            # For joined messages, we keep self.current_post as-is (merge into it)
            return

        if not self._in_message or not self.current_post:
            return

        # Author
        if tag == "div" and "from_name" in classes:
            self._in_from_name = True
            self._from_buffer = ""
            return

        # Date
        if tag == "div" and "date" in classes and "details" in classes:
            self._in_date = True
            self._date_title = attrs_dict.get("title", "")
            self._date_time = ""
            return

        # Text content
        if tag == "div" and "text" in classes:
            self._in_text = True
            self._text_depth = 1
            self._text_buffer = ""
            return

        if self._in_text:
            self._text_depth += 1 if tag == "div" else 0
            if tag == "br":
                self._text_buffer += "<br>"
            elif tag == "blockquote":
                self._text_buffer += "<blockquote>"
            elif tag in ("strong", "em", "b", "i"):
                self._text_buffer += f"<{tag}>"
            elif tag == "a" and "href" in attrs_dict:
                href = attrs_dict["href"]
                if "sticker" not in href:
                    self._text_buffer += f'<a href="{href}">'
            elif tag == "span" and "spoiler" in classes:
                self._text_buffer += '<span class="spoiler">'
            return

        # Images (photo_wrap)
        if tag == "a" and "photo_wrap" in classes:
            href = attrs_dict.get("href", "")
            if href:
                self._pending_images.append({"full": href})
            return

        if tag == "img" and "photo" in classes:
            src = attrs_dict.get("src", "")
            if self._pending_images and src:
                self._pending_images[-1]["thumb"] = src
            return

        # Videos (video_file_wrap)
        if tag == "a" and "video_file_wrap" in classes:
            href = attrs_dict.get("href", "")
            if href:
                self._pending_videos.append({"src": href, "thumb": "", "duration": "", "type": "video"})
            return

        # GIF animations (animated_wrap)
        if tag == "a" and "animated_wrap" in classes:
            href = attrs_dict.get("href", "")
            if href:
                self._pending_videos.append({"src": href, "thumb": "", "duration": "", "type": "gif"})
            return

        # Video/animated thumbnail image
        if tag == "img" and ("video_file" in classes or "animated" in classes):
            src = attrs_dict.get("src", "")
            if self._pending_videos and src:
                self._pending_videos[-1]["thumb"] = src
            return

        # Video duration
        if tag == "div" and "video_duration" in classes:
            self._in_video_duration = True
            self._video_duration_buffer = ""
            return

        # Reactions
        if tag == "span" and "reaction" in classes:
            self._in_reaction = True
            self._current_emoji = ""
            self._current_reaction_count = ""
            return

        if self._in_reaction and tag == "span" and "emoji" in classes:
            self._in_emoji = True
            return

        if self._in_reaction and tag == "span" and "count" in classes:
            self._in_count = True
            return

    def handle_endtag(self, tag):
        if self._in_service_body and tag == "div":
            self._in_service_body = False
            self.current_date_section = self._service_buffer.strip()
            return

        if self._in_service and tag == "div":
            self._in_service = False
            return

        if self._in_from_name and tag == "div":
            self._in_from_name = False
            if self.current_post and not self._is_joined:
                self.current_post["author"] = clean_author(self._from_buffer.strip())
            return

        if self._in_date and tag == "div":
            self._in_date = False
            if self.current_post and not self._is_joined and self._date_title:
                self.current_post["date"] = self._date_title
                try:
                    dt = datetime.strptime(self._date_title.split(" UTC")[0], "%d.%m.%Y %H:%M:%S")
                    self.current_post["dateISO"] = dt.isoformat()
                except:
                    self.current_post["dateISO"] = ""
            return

        if self._in_video_duration and tag == "div":
            self._in_video_duration = False
            if self._pending_videos:
                self._pending_videos[-1]["duration"] = self._video_duration_buffer.strip()
            return

        if self._in_text:
            if tag == "div":
                self._text_depth -= 1
                if self._text_depth <= 0:
                    self._in_text = False
                    if self.current_post:
                        cleaned = self._text_buffer.strip()
                        if cleaned:
                            if self.current_post["html"]:
                                self.current_post["html"] += "<br><br>" + cleaned
                            else:
                                self.current_post["html"] = cleaned
                    return
            elif tag in ("strong", "em", "b", "i"):
                self._text_buffer += f"</{tag}>"
            elif tag == "a":
                self._text_buffer += "</a>"
            elif tag == "blockquote":
                self._text_buffer += "</blockquote>"
            elif tag == "span":
                self._text_buffer += "</span>"
            return

        if self._in_count and tag == "span":
            self._in_count = False
            return

        if self._in_emoji and tag == "span":
            self._in_emoji = False
            return

        if self._in_reaction and tag == "span":
            self._in_reaction = False
            emoji = self._current_emoji.strip()
            count_str = self._current_reaction_count.strip()
            if emoji:
                try:
                    count = int(count_str) if count_str else 1
                except ValueError:
                    count = 1
                self._current_reactions.append({"emoji": emoji, "count": count})
            return

    def handle_data(self, data):
        if self._in_service_body:
            self._service_buffer += data
            return

        if self._in_from_name:
            self._from_buffer += data
            return

        if self._in_date:
            self._date_time += data
            return

        if self._in_text:
            self._text_buffer += data
            return

        if self._in_video_duration:
            self._video_duration_buffer += data
            return

        if self._in_emoji:
            self._current_emoji += data.strip()
            return

        if self._in_count:
            self._current_reaction_count += data.strip()
            return

    def _flush_post(self):
        """Finalize previous post — merge all accumulated images/videos/reactions."""
        if self.current_post:
            # Merge pending media into the post
            self.current_post["images"].extend(self._pending_images)
            self.current_post["videos"].extend(self._pending_videos)

            # Merge reactions (take the latest set — reactions are on the individual messages)
            if self._current_reactions:
                # Merge: add or update reaction counts
                existing = {r["emoji"]: r for r in self.current_post["reactions"]}
                for r in self._current_reactions:
                    if r["emoji"] in existing:
                        existing[r["emoji"]]["count"] += r["count"]
                    else:
                        existing[r["emoji"]] = r
                self.current_post["reactions"] = list(existing.values())

            # Reset pending for next message group
            self._pending_images = []
            self._pending_videos = []
            self._current_reactions = []

            # Plain text for search
            self.current_post["text"] = html_to_text(self.current_post["html"])

            # Skip posts with no content at all
            if self.current_post["text"] or self.current_post["images"] or self.current_post["videos"]:
                # Classify topics
                text_lower = self.current_post["text"].lower()
                self.current_post["topics"] = classify_post(text_lower, self.current_post["id"])

                # Add date section
                self.current_post["dateSection"] = self.current_date_section

                self.posts.append(self.current_post)

            self.current_post = None

    def finalize(self):
        """Call after feeding all HTML to flush the last post."""
        # Before flushing the last post, merge remaining pending media
        if self.current_post:
            self.current_post["images"].extend(self._pending_images)
            self.current_post["videos"].extend(self._pending_videos)
            if self._current_reactions:
                existing = {r["emoji"]: r for r in self.current_post["reactions"]}
                for r in self._current_reactions:
                    if r["emoji"] in existing:
                        existing[r["emoji"]]["count"] += r["count"]
                    else:
                        existing[r["emoji"]] = r
                self.current_post["reactions"] = list(existing.values())

            self._pending_images = []
            self._pending_videos = []
            self._current_reactions = []

            self.current_post["text"] = html_to_text(self.current_post["html"])
            if self.current_post["text"] or self.current_post["images"] or self.current_post["videos"]:
                text_lower = self.current_post["text"].lower()
                self.current_post["topics"] = classify_post(text_lower, self.current_post["id"])
                self.current_post["dateSection"] = self.current_date_section
                self.posts.append(self.current_post)
            self.current_post = None


def build_taxonomy_tree():
    """Build a clean taxonomy tree for the frontend."""
    tree = []
    for cat_id, cat in TAXONOMY.items():
        children = []
        for sub_id, sub in cat["children"].items():
            children.append({
                "id": sub_id,
                "label": sub["label"]
            })
        tree.append({
            "id": cat_id,
            "label": cat["label"],
            "children": children
        })
    return tree


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(script_dir, "old.html")
    output_path = os.path.join(script_dir, "posts.json")

    print(f"Reading {html_path}...")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    print("Parsing messages...")
    parser = TelegramParser()
    parser.feed(html_content)
    parser.finalize()

    posts = parser.posts
    print(f"Extracted {len(posts)} posts (joined messages merged)")

    # Stats
    total_images = sum(len(p["images"]) for p in posts)
    total_videos = sum(len(p["videos"]) for p in posts)
    with_topics = sum(1 for p in posts if p["topics"])
    with_videos = sum(1 for p in posts if p["videos"])
    print(f"  Images: {total_images}, Videos: {total_videos} (in {with_videos} posts)")
    print(f"  Posts with topics: {with_topics}/{len(posts)}")

    # Topic distribution
    topic_counts = {}
    for p in posts:
        for t in p["topics"]:
            key = f"{t['category']}/{t['subcategory']}"
            topic_counts[key] = topic_counts.get(key, 0) + 1

    print("\nTopic distribution:")
    for k, v in sorted(topic_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    # Show some multi-image posts
    multi = [p for p in posts if len(p["images"]) > 1]
    print(f"\nPosts with multiple images: {len(multi)}")
    for p in multi[:5]:
        print(f"  {p['id']}: {len(p['images'])} images, {len(p['videos'])} videos — {p['text'][:60]}...")

    output = {
        "taxonomy": build_taxonomy_tree(),
        "posts": posts
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nWritten to {output_path}")


if __name__ == "__main__":
    main()
