"""
Tests for the scraper. Run them with:   python -m pytest
They use a saved copy of a menu page (tests/fixtures/tercero_sample.html),
so they work without internet and don't bother the dining website.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scraper"))
import scrape  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "tercero_sample.html"


def load_menu():
    return scrape.parse_menu_page(FIXTURE.read_text(encoding="utf-8"))


def find(menu, day, meal, name):
    return next(d for d in menu[day][meal] if d["name"] == name)


def test_finds_the_right_days_and_meals():
    menu = load_menu()
    # Sunday has only empty zones, so it should not appear at all.
    assert list(menu) == ["monday"]
    assert list(menu["monday"]) == ["breakfast", "lunch", "dinner"]


def test_reads_every_dish_and_skips_placeholders():
    menu = load_menu()
    names = [d["name"] for d in menu["monday"]["breakfast"]]
    assert len(names) == 18
    assert "Currently there are no dishes at this zone" not in names
    assert "Breakfast" not in names  # the zone-hours heading


def test_reads_nutrition_numbers():
    dish = find(load_menu(), "monday", "breakfast", "Scrambled Egg Whites")
    assert dish["calories"] == 121.32
    assert dish["protein"] == 12.34
    assert dish["carbs"] == 0.0
    assert dish["fat"] == 7.0
    assert dish["serving"] == "4.25 oz"
    assert dish["serving_g"] == 120.5
    assert dish["zone"] == "Yellow"


def test_reads_tags_and_allergens():
    menu = load_menu()
    tofu = find(menu, "monday", "breakfast", "Scrambled Tofu")
    assert tofu["tags"] == ["halal", "vegan"]
    assert tofu["allergens"] == ["Soy", "Wheat/Gluten"]

    oatmeal = find(menu, "monday", "breakfast", "Oatmeal")
    assert oatmeal["allergens"] == []

    fries = find(menu, "monday", "breakfast", "Seasoned Wedge Fries")
    assert fries["shared_fryer"] is True
    assert fries["allergens"] == ["Soybean Oil", "Wheat/Gluten"]


def test_description_does_not_swallow_the_numbers():
    dish = find(load_menu(), "monday", "lunch", "Carne Asada Taco")
    assert dish["description"].startswith("A taco filled with")
    assert "Calories" not in dish["description"]


def test_serving_units():
    assert scrape.parse_serving("100 g") == ("100 g", 100.0)
    assert scrape.parse_serving("2 oz") == ("2 oz", 56.7)
    assert scrape.parse_serving("0.21 lb") == ("0.21 lb", 95.3)
    assert scrape.parse_serving("1 each") == ("1 each", None)


def test_same_dish_gets_same_id_at_lunch_and_dinner():
    menu = load_menu()
    lunch = find(menu, "monday", "lunch", "Grass-Fed Cheeseburger")
    dinner = find(menu, "monday", "dinner", "Grass-Fed Cheeseburger")
    assert lunch["id"] == dinner["id"]


def test_week_dates_start_on_sunday():
    week = scrape.dates_for_this_week(date(2026, 10, 26))  # a Monday
    assert week["sunday"] == "2026-10-25"
    assert week["monday"] == "2026-10-26"
    assert week["saturday"] == "2026-10-31"


def test_empty_page_finds_nothing():
    assert scrape.parse_menu_page("<html><body><h1>Online menus are unavailable</h1></body></html>") == {}


def test_keeps_yesterdays_menu_when_a_dc_comes_back_empty():
    dish = {"name": "Oatmeal", "calories": 15}
    yesterday = {"dcs": {"cuarto": {"name": "Cuarto", "days": {"monday": {"meals": {"breakfast": [dish]}}}}}}
    today = {"dcs": {"tercero": {"name": "Tercero", "days": {"monday": {"meals": {"breakfast": [dish]}}}},
                     "cuarto": {"name": "Cuarto", "days": {}}}}
    kept = scrape.keep_previous(today, yesterday)
    assert kept == ["Cuarto"]
    assert scrape.count_dc(today["dcs"]["cuarto"]) == 1
    assert scrape.count_dc(today["dcs"]["tercero"]) == 1


def test_latitude_is_scraped_and_labelled():
    assert "latitude" in scrape.DINING_COMMONS
    out = scrape.build_output({"latitude": {"monday": {"lunch": []}}}, date(2026, 10, 26))
    assert out["dcs"]["latitude"]["label"] == "Latitude"
