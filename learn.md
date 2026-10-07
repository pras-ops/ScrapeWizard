# 🎓 How ScrapeWizard works

This is a tour of the code for someone who wants to understand it, change it or borrow from it.
For how to *use* the tool, see [README.md](README.md). For why it is built this way and what is
still open, see [SCRAPER_PLAN.md](SCRAPER_PLAN.md).

---

## 1. The idea in one paragraph

A scraper is not code here. It is a small **recipe**: where the page is, which element repeats,
which values to read from each repeat, how to reach the next page, and what a healthy run looks
like. One runtime can run any recipe. A recipe is built by looking at the page once, with plain
rules and no AI. Because the recipe is data, it can be checked, compared with the last run, and
repaired when the site changes.

```
scrapewizard <url>            scrapewizard run books.recipe.yaml
        │                                   │
   fetch the page                      load the recipe
        │                                   │
   find the list  ── builder.py        read every page ── extract.py
        │                                   │
   preview, one question               checks pass? ── no ──> repair ── heal.py
        │                                   │
   save data + recipe                  compare with last run ── state.py
                                            │
                                       save data
```

Everything below lives in `scrapewizard/recipe/` (about 2,700 lines) plus one command file,
`scrapewizard/cli/commands/recipe.py`.

---

## 2. The modules

| File | What it is responsible for |
|---|---|
| `model.py` | The recipe itself: loading, validating and saving the YAML |
| `types.py` | Recognising what a value is (money, number, date, email, link, image, text) and converting it |
| `fetch.py` | Getting a page: plain HTTP first, a browser when needed; "load more", scrolling, sign-in |
| `builder.py` | Finding the list on a page and writing a recipe for it. No AI. The largest file |
| `extract.py` | Running a recipe: reading rows, following pages and item pages, evaluating checks |
| `detail.py` | Working out what to collect from each item's own page (`--follow`) |
| `state.py` | What the last run saw, and the difference from this one |
| `heal.py` | Repairing a recipe that stopped matching, and proving the repair |
| `ai.py` | The optional AI help. Returns a recipe or new column names, never code |
| `output.py` | Writing CSV, JSON or Excel |

---

## 3. The recipe (`model.py`)

```yaml
name: books
url: https://books.toscrape.com
fetch: http                    # or: browser
collection:
  container: article.product_pod
  fields:
    title: {select: ["h3 > a@title"], type: text}
    price: {select: ["p.price_color"], type: money}
    url:   {select: ["div.image_container > a@href", "h3 > a@href"], type: url}
pagination: {type: next_link, select: "li.next > a", max_pages: 3}
checks: {min_records: 30, required: [title, price]}
```

Three things in it are worth knowing:

- **A field has a ladder of selectors**, tried in order. When a site changes one class, the next
  rung often still works. `p.instock.availability` is followed by `p.availability`, so an item
  that is out of stock (and has lost the `instock` class) is still read.
- **`@attr`** reads an attribute instead of the text: `a@href`, `img@src`, `time@datetime`.
- **A selector starting with `+`** reads from the element right *after* the item. That is how a
  record split over two neighbours is one row: a `dt` and the `dd` after it, or a title row and
  the details row under it.

Pagination types are `none`, `next_link`, `auto`, `load_more` and `scroll`.

---

## 4. Finding the list without AI (`builder.py`)

This is the heart of the tool. `build_recipe(html, url)` does five things.

### 4.1 Collect every repeating block

Two kinds of repetition are looked for:

1. **Elements that share a tag and classes** anywhere on the page: `article.product_pod`,
   `tr.team`. Classes that look machine-generated (`css-1x2y3z`, `sc-bdVaJa`) or that are layout
   utilities (`col-sm-4`, `mt-4`) are ignored.
2. **Same-tag children of one parent**: the `li`s of a `ul`, the `tr`s of a table. These are
   reached from the nearest ancestor that can be named uniquely by id or class
   (`#stats > tbody > tr`). If nothing can be named, the path starts at `body`.

Three or more repeats count as a candidate. The page is indexed once (`_PageIndex`: every
element by tag and by id) so that "what does `li.card` select?" is a lookup. Asking the selector
engine each time cost a scan of the whole page per question, which took 11 seconds on a long
Wikipedia table; the index brought that to 1.

### 4.2 Discover the fields of each candidate

For up to 12 sample items, every piece of text, link, image and date inside the item is
recorded together with a selector **relative to the item**: by class when that is unique inside
the item, otherwise by position (`:scope > td:nth-of-type(2)`).

Then the noise is removed:

- a value present in fewer than half the items is dropped;
- a value that is identical on every item is a label or a button ("Add to basket") and is
  dropped, unless its class says it is a status (`p.availability` → "In stock");
- text that is only a cut-off copy of another field ("A Light in the …") is dropped in favour
  of the full one;
- the members of a variable-length sub-list (tags, sizes) are not columns;
- two selectors that give the same values become one field with a two-rung ladder.

If the element after each item also holds data, it is examined the same way and its fields get
the `+` prefix. Two neighbouring cards with the same shape are two records, not a pair, and are
left alone.

### 4.3 Score the candidates

A candidate scores higher with more items, more readable fields, fuller fields and real text.
It scores lower when:

- its values can only be reached by counting ("the 7th div"), which usually means a mixed
  section and not a record (table cells are exempt);
- it holds nothing but link text (a menu);
- it has four items or fewer (usually page sections; a real list of four still wins when
  nothing larger competes);
- it sits in page furniture: `nav`, `header`, `footer`, `aside`, or a class such as `menu` or
  `sidebar`. Being inside `<main>` cancels the class rule, because sites do write
  `<ul class="menu">` for a list of posts.

### 4.4 Choose between nested blocks

Often several nested elements repeat equally often: the grid cell, the card inside it, the
stats line inside the card. Two rules settle it:

- **A wrapper is not a record.** If each outer block holds several inner records and has almost
  no text of its own, the inner one wins.
- **The fuller record wins, then the cleaner name.** Among blocks that describe the same
  records, the one holding more fields is chosen (the card, not its stats line); among blocks
  holding the same fields, the innermost is chosen because it is named for what it is
  (`article.product_pod`, not `li.col-xs-6`).

`--like "a value"` filters the candidates to those containing that value before any of this.

### 4.5 Name and type the fields

Types come from the values: if at least 60% of a field's values look like money, it is `money`.
Names come from, in order:

1. the table's heading row, for a table cell or anything inside one;
2. the type (`price`, `date`, `image`, `url`, `email`);
3. "title" for a heading, a `title` attribute, a class that says `title` or `headline`, or
   failing those the main link's text;
4. the element's own class (`span.author` → `author`), preferring a class that contains a
   telling word (title, name, author, price, date, …);
5. `text`, `text_2`, `number` when nothing says more.

Links are named after the text they belong to: the title's link is `url`, the author's is
`author_url`. Icon links with no text are dropped when the record has a real link.

Finally the recipe is run against the same page it was built from. Only a recipe that actually
returns rows is offered to the user.

---

## 5. Getting pages (`fetch.py`)

- **Plain HTTP first** with one shared connection. The character set is taken from the response
  header or the page's own `<meta charset>`.
- **A browser only when needed**: the plain page shows no list, the site refuses the request,
  the values given with `--like` are not in the plain page, or the user asks (`--browser`).
- **One browser session per run.** `BrowserSession` opens once and is reused for every page.
- **"Load more" and infinite scroll** are both waited on the same way: after the click or the
  scroll, wait until at least five new elements have appeared and the count has stopped
  growing. Page height and "network idle" turned out to be unreliable signals.
- **Sign-in** (`--login`) opens a visible window, the user signs in, and the browser's session
  is saved to `.scrapewizard/<name>.session.json`. That folder writes its own `.gitignore`,
  because the file holds login cookies.

---

## 6. Running a recipe (`extract.py`)

`run_recipe` reads page after page until there is no next page, the page limit is reached or a
page repeats. Rows are de-duplicated. Each value is converted by its type: numbers become
numbers, links and images become full addresses; money and dates are kept as cleaned text so
nothing is lost in conversion.

With `detail` in the recipe, each row's link is opened (four at a time over HTTP) and the
item-page fields are merged into the row. Item-page fields can be a selector, a labelled table
row (`th:-soup-contains("UPC") + td`), embedded structured data (`jsonld:offers.price`) or a
meta tag (`meta:description`).

After the run, the **checks** are evaluated: at least `min_records` rows, and each `required`
field filled in at least 90% of rows. `scrapewizard run` exits with an error code when a check
fails, so a scheduler can alert.

---

## 7. Memory, changes and repair (`state.py`, `heal.py`)

Every run saves a small state file, `.scrapewizard/<name>.state.json`: the rows, keyed by the
field that best tells them apart (a link if it is unique, otherwise a well-filled text field),
and how full each field was. The next run compares against it and reports "12 new, 3 changed,
0 removed".

The same file is what makes repair safe. When a recipe stops matching:

1. `what_broke` decides whether the run looks broken: no rows at all, a required field
   mostly empty, or a field that used to be nearly always filled and now mostly is not.
2. The page is analysed again from scratch, exactly as when the recipe was first built.
3. Each new field is matched to an old one **by its values**: if the new `span.cost` holds the
   prices the old `p.price_color` held last time, it is the price.
4. The repair is accepted only if known rows are found again (at least two, and at least a
   fifth of the smaller set). Otherwise it is refused, nothing is saved and the user is told.

A scraper has something a test tool lacks: yesterday's data says whether today's repair is
right. Repairs are recorded in the recipe's `history`. Item-page fields are not repaired yet.

---

## 8. Optional AI (`ai.py`)

AI is never needed and is used at most once, while building.

- `--ai` asks a model for better column names, and for a second attempt if no list was found.
- `--ask "job titles and salaries"` lets the user say what they want in words.

In both cases the page is first cut down (scripts, styling, comments, hidden elements and most
attributes removed, long text shortened, the whole thing capped in length), the prompt tells
the model the page content is untrusted, and the model must return a **recipe**. That recipe
is validated and run against the page like any other. One that returns fewer than three rows
is rejected, and a field that matches nothing is removed, so a made-up selector cannot get
through. For column names, the model only sees a few sample values per column.

The AI libraries are an optional install (`pip install ".[ai]"`).

---

## 9. The command (`cli/commands/recipe.py`)

`scrapewizard <url>` is `get`; `scrapewizard run <recipe>` is `run`. `cli/main.py` routes a
first argument that looks like an address to `get`, so there is no sub-command to remember.

The flow in `get` is: fetch, build, show a preview table, ask one question (this page, all
pages or quit), read the pages, save the data and the recipe in the current folder. Every
question has a flag (`--yes`, `--all-pages`, `--pages N`), so the same command works in a
script. Errors are written as what happened, the likely reason and what to try.

---

## 10. Tests

`tests/recipe/` holds the tests for everything above. Each builder test is a small page that
reproduces a shape that went wrong on a live site: cards inside grid wrappers, a quote with a
tag list, tables with and without classes, a `dt`/`dd` list, a title row with a details row,
a list marked `menu`, generated class names. No test touches the internet. Tests that need
JavaScript, "load more", scrolling or sign-in serve a page from the local machine and open it
in a real browser.

```bash
python -m pytest tests/ -v --ignore=tests/golden_sites
```

---

## 11. The older AI builder

`scrapewizard build --url ...` is the original tool and is still in the repository. It works
differently: a state machine (`core/orchestrator.py`) scans the page in a browser, asks an LLM
to describe it (`UnderstandingAgent`), asks an LLM to write a Python scraper (`CodeGenerator`),
runs it, and asks an LLM to fix it if the data looks wrong (`RepairAgent`). It needs an API key
or a local model, and produces a standalone script under `~/scrapewizard_projects/`.

`scrapewizard/engine/` (selector ladders, element fingerprints, healing, a point-and-click
picker) was written for that builder and is used only by its own tests. The ideas were carried
into the recipe path in a simpler form: ladders in the recipe, and repair checked against data
instead of against a fingerprint.

The plan is to retire this path once nothing depends on it; see SCRAPER_PLAN.md §8.
