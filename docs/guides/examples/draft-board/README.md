# Draft board example (fictional data)

A small, tested prototype of a basketball draft board: 4 teams, 12 players, a fixed (snake) order, 8 picks already
made. Everything is fictional. It exists so you can **see a working draft board in minutes**, then change the CSV files
to your own tournament.

## What it can do (Stage A + B)

- Shows who is on the clock, the full draft board, available players (search + position filter) and each team's picks.
- One organizer records picks, **undoes the last pick** (kept as a `void` row, not erased), and **exports** the results CSV
  and a JSON backup.
- Refuses a player who is already picked or not eligible. A "Check data" button re-audits the whole state.
- **Imports CSV files** and validates them *before* anything changes (headers, empty values, duplicate IDs, unknown
  references, duplicate or out-of-order picks, malformed quotes). A bad import changes nothing.
- Vietnamese by default; add `?lang=en` for English.

## What it cannot do

- **Share live state.** Picks are saved in *this browser on this device* (`localStorage`). Another phone, another
  browser, or a cleared browser does not see them. Export results and publish them yourself (see the guide).
- **Protect the organizer controls.** `?mode=view` only hides the buttons. It is presentation, not security. Anyone with
  the page can recover them. Real protection needs a server that checks who is allowed to write.
- Handle trades, a draft clock, multi-round rules or accounts. Those are decisions for your tournament (see
  `REQUIREMENTS_EXAMPLE_VI.md`).

## Files

| File | Purpose |
|---|---|
| `index.html`, `style.css`, `app.js` | The screen |
| `draft-core.js` | The rules and CSV validation (no screen code) |
| `data/*.csv` | The sample tournament: `teams`, `players`, `draft_order`, `draft_results` |
| `data-invalid/` | Deliberately broken files to see the validation work |
| `test/draft-core.test.js` | Rule tests |

## Run it

**Easiest (double-click):** open `index.html`. Browsers block a page from reading other files when opened this way, so
the page asks you to choose the CSV files. Select the four files in `data/` at once.

**Better (a local server — the page loads `data/` by itself):** in a terminal inside this folder run

- Mac: `python3 -m http.server 8000`
- Windows: `py -m http.server 8000` (needs Python from python.org)

then open <http://localhost:8000>. Stop it with Ctrl+C. (VS Code's "Live Server" extension does the same job; check its
current documentation.)

**Published (GitHub Pages):** the same files work from `https://USERNAME.github.io/REPO/` because it is a web address.

## Gotchas

**Each address has its own saved state.** `file://…/index.html`, `http://localhost:8000` and
`https://USERNAME.github.io/REPO/` are three different places for the browser. Picks recorded at one do not appear at
another. Pick one way of opening the board for the whole event and keep using it (same browser too).

**At the event, run it from the organizer's laptop** (double-click, or the local server). It has no outside files, so it
works without internet; a public link would not if the Wi-Fi drops. Publish the results separately.

**If storage is blocked** (some private/incognito modes), the page says so in red. Download the results CSV every few picks.

**Saved state wins over the files.**

After you pick, undo or import, the page saves your state in the browser and uses it on later visits. If you then edit
`data/*.csv` and nothing changes, press **Clear saved data** (or **Xoá dữ liệu đã lưu**).

## Run the tests (optional, needs Node.js 18+)

```
node --test
```
