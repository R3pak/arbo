"""
Arbo menu scraper.

What this file does, in plain words:
  1. Downloads the menu page for each UC Davis dining commons (DC).
  2. Reads the page and pulls out every dish with its nutrition numbers.
  3. Saves everything into one file, docs/data/menu.json, which the website reads.

Run it yourself with:   python scraper/scrape.py
Run it on a saved page: python scraper/scrape.py --from-file tercero=path/to/page.html

GitHub runs this automatically every morning (see .github/workflows/update-menu.yml).
"""

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# The three dining commons and the page that lists each one's weekly menu.
DINING_COMMONS = {
    "segundo": {"name": "Segundo", "url": "https://housing.ucdavis.edu/dining/dining-commons/segundo/"},
    "tercero": {"name": "Tercero", "url": "https://housing.ucdavis.edu/dining/dining-commons/tercero/"},
    "cuarto": {"name": "Cuarto", "url": "https://housing.ucdavis.edu/dining/dining-commons/cuarto/"},
}

DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
MEALS = ["breakfast", "brunch", "lunch", "dinner", "late night"]

# Where the website expects the data file to be.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "docs" / "data" / "menu.json"

# Be polite to the university's server: say who we are and don't rush.
HEADERS = {"User-Agent": "Arbo/1.0 (student project; daily menu refresh)"}
SECONDS_BETWEEN_REQUESTS = 2

DAVIS_TIME = ZoneInfo("America/Los_Angeles")

# How many grams are in one of each unit. Used to turn "2.47 oz" into grams.
GRAMS_PER_UNIT = {"g": 1.0, "gram": 1.0, "grams": 1.0, "oz": 28.3495, "lb": 453.592, "lbs": 453.592}


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------

def parse_serving(text):
    """
    Turn a serving size like "4.25 oz" into ("4.25 oz", 120.5).
    The second value is grams, or None if we don't recognise the unit.
    """
    if not text:
        return None, None
    text = text.strip()
    match = re.match(r"([\d.]+)\s*([a-zA-Z]+)", text)
    if not match:
        return text, None
    amount = float(match.group(1))
    unit = match.group(2).lower()
    grams_per = GRAMS_PER_UNIT.get(unit)
    grams = round(amount * grams_per, 1) if grams_per else None
    return f"{match.group(1)} {match.group(2)}", grams


def find_number(label, text):
    """Find the number after a label, e.g. 'Calories: 67.95' -> 67.95. Returns None if missing."""
    match = re.search(re.escape(label) + r"\s*:\s*([\d.]+)", text)
    return round(float(match.group(1)), 2) if match else None


def make_id(*parts):
    """A short, stable id for a dish, so the same dish gets the same id every day."""
    joined = "|".join(p.lower().strip() for p in parts)
    return hashlib.sha1(joined.encode()).hexdigest()[:10]


def clean(text):
    """Collapse runs of spaces and newlines into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def is_heading(element):
    return isinstance(element, Tag) and element.name in ("h1", "h2", "h3", "h4")


# ---------------------------------------------------------------------------
# Reading one dish
# ---------------------------------------------------------------------------

def read_dish_block(heading):
    """
    Everything that belongs to a dish sits after its <h4> title and before the
    next heading. Walk forward through the page collecting that text, plus the
    little diet icons (vegan / vegetarian / halal), which are images.
    """
    pieces = []
    tags = set()
    for element in heading.next_elements:
        if element is heading or (isinstance(element, NavigableString) and element.parent is heading):
            continue
        if isinstance(element, NavigableString) and heading in element.parents:
            continue  # text inside the title link itself
        if is_heading(element):
            break
        if isinstance(element, Tag) and element.name == "img":
            alt = (element.get("alt") or "").strip().lower()
            source = (element.get("src") or "").lower()
            for diet in ("vegan", "vegetarian", "halal"):
                if diet == alt or f"/{diet}." in source:
                    tags.add(diet)
        elif isinstance(element, NavigableString):
            pieces.append(str(element))
    return clean(" ".join(pieces)), sorted(tags)


def parse_dish(name, block_text, tags):
    """Turn the text under one dish into a dictionary of numbers and labels."""
    # The description is whatever comes before the allergen line.
    description = block_text.split("Contains", 1)[0].strip() if "Contains" in block_text else ""

    contains_match = re.search(r"Contains\s*:\s*(.+?)\.(?:\s|$)", block_text)
    contains_text = contains_match.group(1) if contains_match else ""
    if contains_text.lower().startswith("no major allergens"):
        allergens = []
    else:
        allergens = [a.strip() for a in contains_text.split(",") if a.strip()]

    serving_match = re.search(r"Serving Size\s*:\s*([\d.]+\s*[a-zA-Z]+)", block_text)
    serving, serving_g = parse_serving(serving_match.group(1) if serving_match else None)

    dish = {
        "name": name,
        "description": description,
        "serving": serving,
        "serving_g": serving_g,
        "calories": find_number("Calories", block_text),
        "fat": find_number("Fat (g)", block_text),
        "carbs": find_number("Carbohydrates (g)", block_text),
        "sugar": find_number("Sugar", block_text),
        "protein": find_number("Protein (g)", block_text),
        "allergens": allergens,
        "shared_fryer": "shared fryer" in block_text.lower(),
        "tags": tags,
    }
    # A dish with no calories listed isn't useful for tracking.
    return dish if dish["calories"] is not None else None


# ---------------------------------------------------------------------------
# Reading a whole menu page
# ---------------------------------------------------------------------------

def parse_menu_page(html):
    """
    The menu page is laid out with headings:
        <h1> day      (Monday)
        <h2> meal     (Breakfast)
        <h3> zone     (Yellow Zone)   - the DC's colour-coded stations
        <h4> dish     (Scrambled Egg Whites) followed by its nutrition text
    We walk the headings in order and remember which day/meal/zone we're in.

    Returns {"monday": {"breakfast": [dish, dish, ...], ...}, ...}
    """
    soup = BeautifulSoup(html, "html.parser")
    menu = {}
    day = meal = zone = None

    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = clean(heading.get_text()).lower()

        if heading.name == "h1":
            day = text if text in DAYS else None
            meal = zone = None
        elif heading.name == "h2":
            meal = text if text in MEALS else None
            zone = None
        elif heading.name == "h3":
            zone = clean(heading.get_text()) if text.endswith("zone") else None
        elif heading.name == "h4" and day and meal and zone:
            link = heading.find("a", href=re.compile(r"^#collapse"))
            if not link:
                continue  # e.g. "Currently there are no dishes at this zone"
            name = clean(link.get_text())
            block_text, tags = read_dish_block(heading)
            dish = parse_dish(name, block_text, tags)
            if dish:
                dish["zone"] = zone.replace(" Zone", "")
                dish["id"] = make_id(name, dish["serving"] or "")
                menu.setdefault(day, {}).setdefault(meal, []).append(dish)
    return menu


def dates_for_this_week(today):
    """Map 'sunday'..'saturday' to the dates of the week (Sunday to Saturday) containing today."""
    days_since_sunday = (today.weekday() + 1) % 7  # Python's Monday is 0
    sunday = today - timedelta(days=days_since_sunday)
    return {name: (sunday + timedelta(days=i)).isoformat() for i, name in enumerate(DAYS)}


def build_output(pages, today):
    """Combine the parsed pages into the structure the website reads."""
    week = dates_for_this_week(today)
    output = {
        "generated_at": datetime.now(DAVIS_TIME).isoformat(timespec="minutes"),
        "week_of": week["sunday"],
        "source": "UC Davis Student Housing and Dining Services online menus",
        "dcs": {},
    }
    for key, menu in pages.items():
        info = DINING_COMMONS[key]
        output["dcs"][key] = {
            "name": info["name"],
            "url": info["url"],
            "days": {
                day: {"date": week[day], "meals": menu[day]}
                for day in DAYS
                if day in menu
            },
        }
    return output


def count_dishes(output):
    return sum(
        len(dishes)
        for dc in output["dcs"].values()
        for day in dc["days"].values()
        for dishes in day["meals"].values()
    )


# ---------------------------------------------------------------------------
# Running the scraper
# ---------------------------------------------------------------------------

def download(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()  # stop with an error if the page didn't load
    return response.text


def main():
    parser = argparse.ArgumentParser(description="Refresh docs/data/menu.json from the UC Davis DC menus.")
    parser.add_argument("--from-file", action="append", default=[],
                        help="Use a saved page instead of downloading, e.g. tercero=page.html")
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    parser.add_argument("--sample", action="store_true", help="Mark the output as sample data")
    args = parser.parse_args()

    pages = {}
    if args.from_file:
        for pair in args.from_file:
            key, path = pair.split("=", 1)
            pages[key] = parse_menu_page(Path(path).read_text(encoding="utf-8"))
    else:
        for i, (key, info) in enumerate(DINING_COMMONS.items()):
            if i:
                time.sleep(SECONDS_BETWEEN_REQUESTS)
            try:
                pages[key] = parse_menu_page(download(info["url"]))
                print(f"{info['name']}: read the menu page")
            except requests.RequestException as error:
                print(f"{info['name']}: could not download ({error})", file=sys.stderr)

    output = build_output(pages, datetime.now(DAVIS_TIME).date())
    if args.sample:
        output["sample"] = True
    total = count_dishes(output)

    for dc in output["dcs"].values():
        n = sum(len(d) for day in dc["days"].values() for d in day["meals"].values())
        print(f"  {dc['name']}: {n} dishes across {len(dc['days'])} days")

    # Safety check: if we found nothing, the website changed or is down.
    # Keep yesterday's file instead of replacing it with an empty one, and fail
    # loudly so GitHub emails you.
    if total == 0:
        print("Found 0 dishes. Keeping the existing menu.json. The menu page may have changed.",
              file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {total} dishes to {out_path}")


if __name__ == "__main__":
    main()
