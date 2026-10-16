# Building Software with AI: A Practical Guide

For people who have built a first small site (see [Start Here](START_HERE.md)) and want to build something real:
a league tool, a club system, an internal dashboard. It's based on a real project, **NBA Talk VN Dynasty**, a public
web board and tool set for a 16-team fantasy basketball league. It was built in about five weeks by a league member
working with AI coding agents. The case studies are from that project; the method applies to unrelated projects too.

> **In a hurry, with a real event to run?** Start with the Vietnamese fast start for a basketball draft,
> [BASKETBALL_DRAFT_FAST_START_VI.md](BASKETBALL_DRAFT_FAST_START_VI.md), and the tested example in [`examples/draft-board/`](examples/draft-board/README.md).

> **What AI did and didn't do in that project.** AI agents wrote most of the code, tests and documentation. A person
> chose what to build, gathered the real rules and data, decided every league rule, found several of the most
> important bugs, judged every screen on a phone, and approved every change. Expect the same split on your projects.

**Contents**
1. [Is it worth building?](#1-is-it-worth-building)
2. [Requirements and scope](#2-requirements-and-scope)
3. [Plan the first usable version](#3-plan-the-first-usable-version)
4. [Tools and what each is for](#4-tools-and-what-each-is-for)
5. [Choosing a toolchain](#5-choosing-a-toolchain)
6. [Choosing models and effort](#6-choosing-models-and-effort)
7. [Writing good requests](#7-writing-good-requests)
8. [Context, tokens and cost](#8-context-tokens-and-cost)
9. [Data: where it lives and how it gets in](#9-data-where-it-lives-and-how-it-gets-in)
10. [From a static page to shared state](#10-from-a-static-page-to-shared-state)
11. [Building features](#11-building-features)
12. [Catching AI mistakes](#12-catching-ai-mistakes)
13. [Testing and checking](#13-testing-and-checking)
14. [Reviewing changes and pull requests](#14-reviewing-changes-and-pull-requests)
15. [Publishing and confirming it's live](#15-publishing-and-confirming-its-live)
16. [Feedback and iteration](#16-feedback-and-iteration)
17. [Security, credentials and privacy](#17-security-credentials-and-privacy)
18. [After launch: maintenance](#18-after-launch-maintenance)
19. [Small project vs serious project](#19-small-project-vs-serious-project)

---

## 1. Is it worth building?

Build software when a **real, repeated task** is slow, error-prone or hard to check, and you can get the **real
inputs** (rules, data, examples). If a better spreadsheet or checklist would do, use that.

**Watch the current process before replacing it.** Write down each manual step, where it goes wrong, and what people
*enjoy* about it. Automate the chores, not the part people value.

> **Case study: the lottery wheel.** The league runs its draft lottery live on a group call: a host spins an online
> wheel to draw three numbers, and everyone watches. The chores were the problem: building and freezing a table of 120
> number combinations, looking up the winner in a spreadsheet, keeping a record. The first tool kept the external wheel
> and automated only the chores. One later version made the app itself the drawing tool. It worked, but the
> commissioner objected that people wouldn't trust a result produced entirely by one tool. The next version restored
> the external wheel as the default. **Lesson:** trust and familiarity are requirements, and code that works can still
> miss them. Test with the person who has to defend the result.

**Do this:** Write three sentences: who is affected, what they do today, and what "better" means to them. If you can't
name the person and the current workaround, wait.

## 2. Requirements and scope

A **requirement** is something the software must do. You need four short lists:

- **Must have**: the few things that make it useful (3–5 items).
- **Done when**: checks anyone can run in two minutes ("searching 'captain' shows only captains").
- **Not doing**: features you're deliberately skipping for now. This list protects you more than any other.
- **Open questions**: rules nobody has decided yet. The software must **not** guess these; list them and ask.

**Sources of truth.** When the rule document, the old spreadsheet and someone's memory disagree, which wins? Decide
this up front and write it down.

> **Case study: a rule written before code.** Before the lottery app had any code, it had a short packet: the problem,
> the exact rules, an analysis of the old spreadsheet, a list of open questions, and real past results to test against.
> Any AI agent, or a person, could pick it up without the chat history that produced it.

**Do this:** Use the BRIEF prompt in [Copy-paste prompts](COPY_PASTE_PROMPTS.md) and keep the result as `BRIEF.md`
in your project.

**If you have a business-analyst background, you already own the hardest part.** Your artefacts map directly:

| BA artefact | In an AI-built project it becomes |
|---|---|
| Actors, roles | Who may change what (this decides whether you need logins at all) |
| User stories | The request you give the agent, and your "done when" list |
| Business rules | Tests and written rules the software must follow. The AI must not invent them |
| Data dictionary | The CSV/column definitions and stable IDs |
| Exceptions, edge cases | Edge-case checks (duplicates, undo, bad imports) |
| Acceptance criteria | Your checklist before you call it done |
| Non-goals | The "Not doing" list that keeps the first version small |

The skill that matters most is refusing to let the AI guess a rule nobody has decided.


## 3. Plan the first usable version

Build in **vertical slices**: each step produces something a person can actually use, end to end. Don't build all the
data handling first and the screens last.

A good order for data-driven tools:
1. A read-only page showing real data (even typed in by hand), published.
2. Data loaded from the real source by a script, checked against what people see today.
3. The rules as separate, testable pieces of code, checked against real past results.
4. Changes (trades, edits, entries) **recorded as a list of events**, with the current state calculated from them,
   instead of editing results by hand.
5. "What if" views, kept strictly separate from the official record.
6. Operations: refreshing data, importing, undoing.

**How much planning is enough?** For a small site, one page. For a serious tool, enough that someone new could
build the first slice without asking you questions. If you're writing a fourth planning document before anything
runs, stop and build the slice. Real output answers questions faster.

**Do this:** Ask an agent to propose the first slice and 3–5 later slices without writing code (PLAN prompt), then approve one.

## 4. Tools and what each is for

| Tool | Use it for | Don't use it for |
|---|---|---|
| **Chat AI** (ChatGPT, Claude, Gemini…) | Thinking through the idea, writing the brief and task descriptions, second opinions | Changing your files |
| **Coding agent** (GitHub Copilot agent, Claude Code, OpenAI Codex, Cursor…) | Creating and editing files, running checks, preparing changes | Deciding rules or which data is true |
| **VS Code** (code editor) | Seeing files and changes, running the agent | — |
| **Git + GitHub** | Saving versions, reviewing changes, undoing, publishing | — |
| **GitHub Actions (CI)** | Re-running checks automatically on every change; scheduled jobs | Making decisions |
| **Hosting** (GitHub Pages, Netlify, Cloudflare Pages) | Serving your site | Storing secrets or private data |
| **Browser + developer tools** | The real test: does it look and work right, on a phone too? | — |

**Pick one coding agent and learn it.** Expect AI products, plans and interfaces to change, and check current pricing
before paying.

**Four things decide what an agent can do. Check all four before blaming the AI:**
1. **Capability:** can the model reason about this task?
2. **Permissions:** is it allowed to run commands and edit these files?
3. **Tools:** does it have a browser, a test runner, access to GitHub?
4. **Connectivity:** can it reach the internet or your data?

> **Case study: the agent that couldn't.** The project set up an AI agent that works directly on GitHub tasks.
> It was asked to run the project's checks, but wasn't permitted to run them, so a narrow permission list was added.
> It was asked to refresh player data from Yahoo, but its environment had no internet access, so that job moved to a
> scheduled GitHub workflow that proposes the update for review. It was asked to apply a commercial font, which was
> blocked on licensing, and open fonts were used instead. None of these were the AI being "bad". They were permission,
> connectivity and legal limits.

**Write a script instead of asking the AI repeatedly** when the same transformation will run more than twice, the input
is structured (a spreadsheet, a data feed), or the result must be identical every time. Have the AI write the script
and its tests once, then just run the script.

> **Case study: draft day.** 48 draft picks were recorded over one day. Instead of having the AI hand-edit data 48
> times, a small import script took each pick, matched the player name to a stable player ID, checked the pick order
> and owner, and refused duplicates or out-of-order entries.

## 5. Choosing a toolchain

There is no single best path. Compare approaches on what *you* need, not on which AI seems smartest.

**A. Browser-based AI app builders** (Lovable, Bolt, Replit and similar). You describe the app in a web page and it builds
and hosts it. Fastest way to *see* something tonight, with nothing to install. Trade-offs: free allowances are small and
usage-based (credits or tokens), you see less of what's happening in the code, hosting and any database are tied to
the platform, and you must check whether you can export the code and keep it in your own GitHub account. Good for a
sketch you will redo, riskier for something you must rely on at an event.

**B. Repository-based coding agents** (GitHub Copilot agent in VS Code, Claude Code, OpenAI Codex, Cursor and similar).
The agent works on real files in a folder you own. You get full control of structure, tests, Git history and where it
is hosted, and you can move to another tool later. Trade-offs: some setup (editor, Git, sign-in), you must check what
the AI changed, and usage is limited by your plan.

**C. Spreadsheet or no-code first** (Google Sheets, AppSheet and similar). Often the right answer when the data already
lives in a spreadsheet and you mainly need to view, filter and share it. Multi-user editing and simple rules (for
example, flagging a duplicate pick with a data-validation rule) are built in. Trade-offs: draft-specific logic,
presentation and permissions are limited, and you depend on the platform. Ask first whether you need custom code at all.

**D. Chat-generated HTML on simple static hosting.** Ask a chat AI for a single HTML file, save it, host it. Lowest cost
and complexity, fine for a read-only board. Trade-offs: no version history unless you add Git, becomes hard to change
as it grows, and static hosting cannot hold shared, changing data.

| You want… | Best fit | Why |
|---|---|---|
| A prototype to look at **tonight**, no install | A (or D) | Nothing to set up. Treat the result as a sketch |
| The **lowest cost** for a small prototype | C or D, then B with a free plan | Spreadsheets and static files cost nothing; free agent plans exist but are limited |
| To work comfortably **with files** | B | You own the folder, can read diffs, and can switch tools |
| **Spreadsheet-based administration** by non-technical organizers | C, or B importing CSV | Keep their spreadsheet; add code only for what it can't do |
| **Long-term control and portability** | B (or D with Git) | The code is yours; no platform lock-in |
| **Shared, changing data** edited by several people | Anything + a hosted backend | That needs a server that checks permissions and prevents conflicts. See section 10 |

**What was checked on 16 Oct 2026 against official pages** (re-check before relying on any of it; plans change often):
Claude Code is included in paid Claude plans (Pro is listed at $20/month, or $17/month billed annually), not in the Free plan.
OpenAI says Codex is included in ChatGPT Free and Go, but the page I checked states usage limits only for Plus and
Business. Lovable Free: 5 build credits a day, up to 30 a month. Bolt Free: 300K tokens a day and 1M a month, with Bolt
branding on published sites. GitHub Pages in GitHub Free is for **public** repositories, and the published site is
public. Netlify's Free plan is credit-limited (production deploys and bandwidth use credits). Google Sheets "Publish to
the web" republishes changes automatically, which "might take a few minutes", and charts expose their underlying data.
**Not verified:** GitHub Copilot Free's exact monthly allowance, Replit's free tier, whether Lovable's or Bolt's free plans
can export to GitHub, and AppSheet pricing.

**A reasonable default** for an organizer with spreadsheet data, a real event and a small budget: a free chat AI to
write the requirements, then B with whichever agent you already have access to, data kept as CSV files with stable
IDs, and hosting on a free static host (GitHub Pages, or Netlify/Cloudflare Pages if the repository must stay private;
check their current terms). Choose differently when: you hate installing software (start with A as a sketch); the
organizers only want to edit a spreadsheet and view it (C may be enough); or several remote people must record picks live
(you need a backend, so plan for it and consider help from someone with backend experience).

Don't pick a tool because someone you admire uses it. The NBA Talk project used a chat assistant for planning and Claude
Code for implementation, but other combinations work too.


## 6. Choosing models and effort

Most tools let you choose a model and, sometimes, how much "thinking" it does. Decide by **how uncertain the task
is × how costly a mistake would be**:

| Task | Choice |
|---|---|
| Rename, restyle, add one row of data, fix a typo | Fast/cheap model, low effort |
| A feature that follows an existing pattern | Standard model |
| New business rules, calculations, money, history, data matching, puzzling bugs | Strongest model, more effort, plus your own checks |
| Hard-to-undo changes (data migrations, structure changes) | Strongest model **and** an independent review |

Don't pay for heavy reasoning on mechanical edits, and don't save money on the logic people will rely on.
Model names change. Think in tiers (fast / standard / strongest) rather than in specific products.

## 7. Writing good requests

A good request has: **goal**, **where**, **done when**, **don't**, and **report back**.

**Weak:**
```
Make the page better and add filtering.
```
**Strong:**
```
Goal: visitors can filter members by role.
Where: the member list page.
Done when: a "Role" menu lists each role from the data; choosing one filters the list; it works with search;
the count updates; it fits on a phone.
Don't: change the design elsewhere or add libraries.
Report back: which files changed and how you checked it.
```

**Size the request:**
- **Tiny** (one value, one typo): one sentence.
- **Small** (one behaviour): goal + done when + don't.
- **Feature:** the full structure above.
- **Big:** split it. Ask for a plan first, then build one slice at a time.

**Put standing rules in a file once** (most agents read a project instructions file, such as `AGENTS.md`,
`CLAUDE.md` or `.github/copilot-instructions.md`), so you don't repeat them in every request:
- read the brief first
- never invent rules or data
- don't add libraries without saying why
- **if instructions conflict with the data, stop and ask**

> **Case study: the trade written backwards.** A trade was described as "Team A receives players X and Y", but Team A
> already owned them. The agent quietly reversed the direction to make it work and then showed its correction note on
> the public page. The direction was right, but deciding it was not the agent's call, and the note shouldn't have been
> public. **Lesson:** tell agents to stop and ask when instructions contradict the data, and keep internal notes off
> user-facing screens.

## 8. Context, tokens and cost

**Context** is everything the AI currently "knows" in a conversation. It's limited and it costs money. Long chats get
worse: the AI forgets early decisions or repeats fixed mistakes.

- **Keep durable facts in files, not in chat:** `BRIEF.md` (what and why), an instructions file (rules for agents),
  and `STATE.md` (where things stand: what's done, what's next, open questions).
- **Start each session** by having the agent read those files instead of the whole project, and tell it to *search* for
  the relevant place before opening large files.
- **Don't paste your whole project into a chat** to ask a small question. Point a coding agent at the folder, or paste
  only the part that matters.
- **Start a fresh session** when the task changes, when the chat has been summarised to save space, or when the
  agent repeats a mistake you already corrected.
- **End each session** by asking the agent to update `STATE.md`.

**Four different costs.** Keep them apart: the **subscription** (money per month), **token or credit use** (how fast
you run through your allowance), **your time**, and **maintenance later**. Usually your time is the biggest one.

**What actually reduces waste:**
1. A clear brief with "done when" and "not doing". It prevents the most rework.
2. Planning in a chat AI (cheap, conversational) and file operations in a coding agent.
3. One small, checkable change per request.
4. A **script instead of repetition**: if you would otherwise ask an AI to enter 48 draft picks, ask it once to write an
   import that checks and loads them.
5. Batch mechanical edits (rename a column, add rows) into one request instead of many.
6. A stronger model for high-risk logic (rules, duplicate prevention, import checks) and a cheaper one for wording and colour.
7. An independent review only for risky changes, not every edit.

**Signs the agent is wasting your allowance:** it "fixes" the same thing repeatedly, changes files you didn't mention,
reports success without evidence, or keeps asking questions you already answered in the brief. Stop. Restate the problem
with one concrete example, or start a fresh session with the brief.

**A cheap first evening:**
1. Free chat AI: interview + brief (one conversation).
2. Start from a working example folder, or ask an agent for the smallest version.
3. Run it; check it yourself with real-looking data.
4. Ask for one or two fixes, each as a single request.
5. Commit; stop for the night. Don't switch tools mid-way.

> **Case study:** several long working sessions on the NBA Talk project ran out of space and had to be summarised. Work
> continued smoothly only because the project's state was kept in files, not in the conversation.


## 9. Data: where it lives and how it gets in

For anything with a list of people, teams or results, decide the **source of truth**: the one place a fact is kept.
Then decide how data gets into your app.

| Way in | Fits when | Watch out for |
|---|---|---|
| **Typed into a source file** | A small, fixed prototype | Painful when data changes often; typos go unnoticed |
| **CSV (or Excel exported as CSV) import** | Organizers already keep spreadsheets | Fixed column names; you must check rows before applying them |
| **Google Sheets as the source** | Non-technical people edit the data | Changes reach a published copy only after you republish, with a delay; a shared sheet is not a permissioned live system |
| **Database or API** | Several authorized people write the same data, or data syncs automatically | More complexity, maintenance and possibly cost |

**Use stable IDs, not names.** Names repeat, change spelling and accents, and get abbreviated. Give each team and player an ID
(`T1`, `P07`) and have every other file refer to that ID. Then "this player was already picked" is an exact question.

A tiny, realistic data model for a draft (details and sample files in
[`examples/draft-board/`](examples/draft-board/README.md)):
`teams.csv` (`team_id`, `team_name`), `players.csv` (`player_id`, `player_name`, `position`, `eligibility_status`),
`draft_order.csv` (`overall_pick`, `team_id`), `draft_results.csv` (`overall_pick`, `player_id`, `status`).

**Validate before you apply.** An import should check headers, empty values, duplicate IDs, references to things that
don't exist, duplicate or out-of-order picks, and malformed quoting, and it should change **nothing** if any check fails.
Read CSV with a proper parser: a name like `"Tran, Minh"` breaks code that just splits each line on commas.

**Browser rule that surprises beginners:** a page opened by double-clicking (`file://`) usually can't `fetch()` other
local files. Either choose the files with a file picker, or run a small local server, or publish it (any web address works).

**Write the import once.** The NBA Talk project recorded 48 draft picks in one day through an importer that matched each
pick to a stable player ID, checked order and ownership, and refused duplicates. Players that the external data source
hadn't listed yet got explicit "provisional" entries instead of guesses.

**Personal data:** publish only what people agreed to show. Be especially careful with minors. Prefer IDs or nicknames.
A public page, and the repository behind a free GitHub Pages site, are public.

## 10. From a static page to shared state

Be exact about what each layer can do:

- A **static page** shows information that was published. It's cheap and very reliable.
- **`localStorage`** remembers things in *one browser on one device*. It survives a refresh. It is **not** shared with
  another phone or browser, and it can disappear if browser data is cleared.
- **GitHub Pages and other static hosts** have no place for many people to write data and no login.
- A **spreadsheet or JSON snapshot** the organizer updates and republishes is a legitimate middle step, but you must
  know who controls the official result and how long viewers wait for updates.
- A **hidden "admin" button is not security.** Anything in the page can be found. Permissions must be checked on a server.

A genuinely **live, multi-user** draft needs: one authoritative shared state; authorized organizer actions checked on
a server; prevention of duplicate picks when two people act at once; saved history and corrections; viewers who refresh or
subscribe; and recovery after a closed tab or lost connection.

| Stage | What it gives | Where state lives | Server needed? |
|---|---|---|---|
| A. Read-only board | Teams, order, sample picks, a shareable link | CSV files in the repository | No |
| B. One organizer's tracker | Record, undo, prevent duplicates, export | That organizer's browser | No |
| C. Published results | Latest official results for everyone | Files you update and republish | No (manual, delayed) |
| D. Authenticated live draft | Several people see and/or record picks in real time | A shared database | **Yes** |

For one venue, A + B + C is usually enough: one organizer's laptop on a screen, results republished after each round.
Do D only if you truly need remote, simultaneous participants. It is not a beginner prerequisite.

> **Case study: official vs "what if".** NBA Talk kept an official record separate from experimental trade views, so a
> "what if" could never change real results. In a tournament, keep rehearsal data and real data in different files.

A full worked example (fictional four-team draft, with requirements, data files and a tested prototype) is in
[`examples/draft-board/`](examples/draft-board/README.md), with a Vietnamese walkthrough in
[BASKETBALL_DRAFT_FAST_START_VI.md](BASKETBALL_DRAFT_FAST_START_VI.md).

## 11. Building features

One feature per request, one change per save (commit). After each: check it, then commit with a clear note.
Keep the official record separate from experiments. A "what if we traded…" screen must never alter the real data.
Use **stable IDs** for things like people and players, not names: names have accents, typos and duplicates.
Give anything that doesn't have an ID yet an explicit "provisional" status rather than a guess.

**Temporary features are fine.** On draft day the project had a live "draft room" screen showing who's on the clock,
recent picks and the best players available. After the draft it was archived. It did its job; retiring it was the
right call, not a failure.

## 12. Catching AI mistakes

AI mistakes come in kinds, and each needs a different response:

| Kind | Sign | What to do |
|---|---|---|
| **Wrong implementation** | Clear request, wrong result | Ask for a fix **and** a test that would have caught it |
| **Incomplete request** | It did what you asked, but you forgot something obvious | Add the missing rule to your brief, then fix |
| **Changed requirement** | The rules or your goals changed | Record the change; don't rewrite history |
| **Environment limit** | Permissions, internet access, licences | Change where or how the job runs |
| **Overconfidence** | "Done!" without evidence | Ask for proof: test output, a screenshot, the exact command |

> **Case study: right on paper, wrong in practice.** A ranking of available players followed its written formula
> exactly, but left out two rookies any league manager would expect near the top. The owner caught it from a
> screenshot within minutes. The ranking went through several adjustments; some were legitimate taste and some came
> from never having written down its purpose. **Lesson:** before tuning a ranking or formula, write its purpose and
> 3–5 examples that must come out right.

**You don't need to read the code to challenge it.** Ask:
- "Which input would make this give the wrong answer?"
- "What did you assume?"
- "Show me the test that would fail if this were wrong."
- "Show the actual output." Then compare three values against the source yourself.

## 13. Testing and checking

A **test** is a small program that checks your code gives the right answer. Ask the agent to write tests for anything
involving rules, numbers or data.

**Test rules that must always hold, not just one known answer.**

> **Case study: the cap model that passed while wrong.** The league's salary cap is calculated from player
> salaries. The first version reproduced the league's published cap figures exactly, so its test passed. But it
> grouped players by Yahoo's ranking instead of by salary, and the match was a coincidence of that week's data. When
> the data changed, a person spotted that the cap was $1 off and traced the cause. The test that would have caught it
> checks the *method* ("players are grouped by salary, highest first"), not just one result.

**Match the checks to the software:**

| Kind of software | Minimum check |
|---|---|
| A web page | Open it on a phone and a computer; look for cut-off text, overflow, wrong numbers |
| A data script | Run it on a real file; compare to a known-good result; run it twice and get the same result |
| Rules and calculations | Check 3–10 real past cases; add tests for rules that must always hold |
| Anything connecting to another service | One real call, then saved sample responses for repeatable tests |

Visual checks matter for screens. They aren't needed for programs without a screen.

## 14. Reviewing changes and pull requests

- A **branch** is a separate copy of your project for one change.
- A **pull request (PR)** asks to merge that branch into the main version. GitHub shows exactly what changed.
- **CI** re-runs the checks automatically on every PR.

**What to look at in every PR, even if you can't read code:**
- the list of changed files: did anything change that you didn't ask for, especially data?
- the description of how it was checked, with evidence
- the CI result (green tick)

**For important changes, get an independent review:** a fresh AI session, or a different tool, that sees only the
change and the brief, not the conversation that produced it. Ask it how the change could pass the tests and still be
wrong (REVIEW prompt).

## 15. Publishing and confirming it's live

The real sequence has seven distinct steps. Each can succeed while the next fails:

1. **Implement** on a branch made from the latest main version
2. **Tests pass**
3. **You've checked it yourself**
4. **PR into main**, reviewed, CI green
5. **Merged**
6. **Deployed:** the host has published the new version
7. **Live and visible:** the public address shows the change

> **Case study: "why isn't it live?"** Twice, a change was merged into a branch that had already been merged
> elsewhere, so it never reached the main version (a "stacked PR" mistake). Another time, the change *was* live but
> the browser showed an old saved copy. **Lessons:** always merge PRs into main; after merging, confirm the change is
> in main; check the live site with a hard refresh or a private window; put a visible "last updated" date on the page.

Know how to undo a release before you need to: in GitHub you can **revert** a merged change, which creates a new
change that reverses it.

## 16. Feedback and iteration

- Show the real thing to real users, on their devices, as early as possible.
- Ask them to **describe** what's wrong rather than prescribe a fix. A screenshot with one sentence is ideal.
- Keep a short list of requests, decide what's in and out, and say no to things outside the brief.
- **Simplifying is progress.** The project later removed a whole page and much of its wording because users found
  it busy. Fewer words and clearer symbols made it better on phones.

## 17. Security, credentials and privacy

- **Never put passwords, API keys or tokens in your project files or website.** Anything on a free GitHub Pages site,
  and in a public repository, is public. Use your hosting or CI's "secrets" settings for keys.
- **Personal data:** publish only what people have agreed to. Leave out phone numbers, addresses and emails unless
  that's the point of the site and people have consented.
- **Check each PR for accidental secrets or personal data** before merging.
- **Spreadsheet formula injection:** when you export text that users typed into a CSV for Excel or Sheets, a value that starts
  with `=`, `+`, `-` or `@` can be run as a formula. Export IDs and numbers where you can, or neutralise such values.
- **Add libraries only when needed**, ask why each is needed, and prefer well-known ones.
- **Licences:** fonts, images and data have owners. Use open licences or things you have permission to use.
- **Don't paste confidential material into AI tools** unless your plan and organisation allow it.

## 18. After launch: maintenance

Launching creates ongoing work. Write down, for every data source: who updates it, how often, how you'll know it's
stale, and what happens if access changes.

> **Case study: when a data source closes.** After the draft, the project needed current team rosters weekly. Yahoo's
> roster API now requires an approved application, so a manual import was built: paste the rosters, review a list of
> differences, then confirm. It blocks the import if anything doesn't match a known player instead of silently dropping them.

Also note any recurring costs (hosting, subscriptions, your weekly time) and which features are temporary.

## 19. Small project vs serious project

| Always (any project) | Only when it matters (others rely on it, rules or money, long life, several agents) |
|---|---|
| A one-page brief with "done when" and "not doing" | A written record of sources of truth and decisions |
| Small requests, one change at a time | Every change through a PR into main with CI checks |
| Check it yourself on the real device | Tests for rules that must always hold + checks against real history |
| Commit after each working change | An independent review for risky changes |
| Confirm it's live | A release checklist, a rollback plan, a maintenance plan |
| No secrets or private data in files | Event logs, separate "what if" views, scheduled data jobs |

Start small. Add rigour when someone depends on the result, not because the project feels bigger.

---

*Based on the NBA Talk VN Dynasty project (September–October 2026). Tool names, plans and interfaces change; check
current documentation before relying on specific steps or prices.*
