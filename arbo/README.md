# Arbo

A website for UC Davis students: every dining commons dish with its macros, a food log, cut and bulk phases, and a TDEE / macro calculator.

- **Today**: calories-left ring and macro bars, meals for the day, add DC dishes (by servings or grams), your own foods, and verified community foods.
- **Menu**: Segundo, Tercero and Cuarto by day and meal, grouped by the DC's colour zones. Filter vegan / vegetarian / halal. Marks the top picks for your goal and builds a suggested plate that fits your remaining calories. A DC with no data yet shows "Coming soon" and switches on by itself once the scraper finds its menu.
- **Calendar**: every day scored Hit / Close / Off against your targets (Hit = calories within 10% and at least 90% of your protein), your streak and hit rate, and each week's average weight with the change from the week before. Tap a day to see its numbers.
- **Progress**: start a cut, bulk or maintenance phase, log weigh-ins, see a 7-day trend chart, and get told when to change your calories. After 10+ logged days it estimates your *real* maintenance from your own data.
- **Plan**: Mifflin-St Jeor TDEE calculator with cut / maintain / bulk, two paces and three macro splits, or set your own numbers.
- **Feel**: frosted-glass design with a sidebar on wide screens and a floating dock on phones, a light that follows your cursor over cards, ripples, count-up numbers, and soft sound effects made in the browser (no audio files). The speaker button mutes them. Dark mode follows the device setting.
- **Suggestions**: students suggest missing foods through a pre-filled GitHub form. You check them and add the good ones to `docs/data/community.json`.

Everything a student logs is saved in their own browser. There are no accounts yet, so there are no passwords or personal data on a server.

---

## How the pieces fit together

```
UC Davis menu pages ──(Python scraper, every morning on GitHub)──► docs/data/menu.json
                                                                        │
students' phones ◄──────────(GitHub Pages hosts the docs/ folder)───────┘
```

| Path | What it is |
|---|---|
| `scraper/scrape.py` | Downloads the three DC menu pages and pulls out each dish's nutrition. |
| `tests/test_scrape.py` | Checks the scraper against a saved copy of a menu page. |
| `docs/index.html` | The whole website: layout, styles and JavaScript in one file. Search for `CALENDAR SCORING`, `PHASE COACHING`, `GOAL-AWARE MENU` and `Sound effects` to find the logic behind those features. |
| `docs/data/menu.json` | The menu data the site reads. Rewritten by the scraper. |
| `docs/data/community.json` | Foods you've approved. You edit this by hand. |
| `.github/workflows/update-menu.yml` | Tells GitHub to run the scraper every morning. |
| `.github/workflows/tests.yml` | Runs the tests every time you push code. |
| `.github/ISSUE_TEMPLATE/food-suggestion.yml` | The form students fill in to suggest a food. |

The `menu.json` in this folder right now is **sample data** (a real slice of Tercero's Monday menu). The first time the GitHub job runs, it's replaced with every DC's real week.

---

## Put it online (about 20 minutes, free)

You need a GitHub account and Git installed. On a Mac, Git comes with the Xcode command line tools (`xcode-select --install`). On Windows, install it from git-scm.com.

**1. Make an empty repository on GitHub.** Click **New repository**, name it `arbo`, make it **Public**, and don't add a README.

**2. Upload this folder.** In a terminal, from inside the `arbo` folder:

```bash
git init
git add .
git commit -m "First version of Arbo"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/arbo.git
git push -u origin main
```

(Dragging files into GitHub's web page can skip the hidden `.github` folder, which holds the daily job. Use the commands above.)

**3. Turn on the website.** In the repo: **Settings → Pages**. Under *Build and deployment*, choose **Deploy from a branch**, branch **main**, folder **/docs**, then **Save**. After a minute your site is live at `https://YOUR-USERNAME.github.io/arbo/`.

**4. Load the real menus.** Go to the **Actions** tab. If GitHub asks, click to enable workflows. Pick **Update menu** → **Run workflow**. When it finishes with a green check, open `docs/data/menu.json` in the repo and you should see all three DCs. From now on it runs by itself every morning.

If the job fails at "Download today's menus", the dining site may have changed its layout. See *When the scraper breaks* below.

**5. Switch on food suggestions.** In `docs/index.html`, near the top of the `<script>`, set:

```js
githubRepo: "YOUR-USERNAME/arbo"
```

Commit and push. The **Suggest it for everyone** button now opens a pre-filled form in your repo's **Issues** tab. Suggesting needs a free GitHub account; if your users don't have one, you can later swap this for a Google Form.

---

## Approving a suggested food

1. Open the suggestion in the **Issues** tab.
2. Check the numbers against the source they gave (official nutrition page or label). Reject anything without a source you can confirm.
3. Add it to `docs/data/community.json`, copying the shape of the existing entries. Give each one a unique `id` that starts with `c-`.
4. Commit, push, and close the issue.

The three starter foods (banana, egg, rice) use USDA values. Double-check them before launch.

---

## Working on it on your own computer

```bash
pip install -r requirements.txt     # one-time: install the Python packages
python -m pytest                    # run the tests
python scraper/scrape.py            # fetch real menus into docs/data/menu.json
cd docs && python -m http.server    # then open http://localhost:8000
```

Opening `index.html` by double-clicking won't load the menu, because browsers block pages opened that way from reading other files. Use the `http.server` line.

---

## When the scraper breaks

The scraper reads the menu page's headings in order: day (`h1`), meal (`h2`), zone (`h3`), dish (`h4`), then the nutrition text under each dish. If the dining site redesigns its page, that pattern stops matching and the scraper finds 0 dishes. When that happens it **keeps the old menu.json** and the GitHub job fails, so GitHub emails you instead of the site going blank.

To fix it: save the new page (right-click → *Save Page As*), replace `tests/fixtures/tercero_sample.html` with it, update `parse_menu_page` in `scraper/scrape.py` until `python -m pytest` passes, and push.

---

## Known limits of this version

- Logs live in one browser. A new phone or cleared browser data starts fresh.
- Build-your-own stations (salad bar, deli bar, omelette bar) are listed by the DC per 100 g, so students have to weigh or estimate.
- Some official numbers are wrong (e.g. dishes listing 0 g protein). The site marks entries whose calories don't match their macros with **Check numbers**.
- Retail spots (CoHo, Latitude, The Gunrock, markets) aren't scraped yet.

## Ideas for the next version

- Accounts so logs sync across devices (use a hosted login service rather than handling passwords yourself).
- Scrape retail menus.
- Remember a student's usual portion for build-your-own stations.
- An in-site approval page instead of GitHub Issues.

---

Not affiliated with UC Davis. Menu data comes from UC Davis Student Housing and Dining Services' public online menus.
