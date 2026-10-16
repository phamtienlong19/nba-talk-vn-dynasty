# Building Software with AI: A Practical Guide

For people who have built a first small site (see [Start Here](START_HERE.md)) and want to build something real:
a league tool, a club system, an internal dashboard. It's based on a real project, **NBA Talk VN Dynasty**, a public
web board and tool set for a 16-team fantasy basketball league. It was built in about five weeks by a league member
working with AI coding agents. The case studies are from that project; the method applies to unrelated projects too.

> **What AI did and didn't do in that project.** AI agents wrote most of the code, tests and documentation. A person
> chose what to build, gathered the real rules and data, decided every league rule, found several of the most
> important bugs, judged every screen on a phone, and approved every change. Expect the same split on your projects.

**Contents**
1. [Is it worth building?](#1-is-it-worth-building)
2. [Requirements and scope](#2-requirements-and-scope)
3. [Plan the first usable version](#3-plan-the-first-usable-version)
4. [Tools and what each is for](#4-tools-and-what-each-is-for)
5. [Choosing models and effort](#5-choosing-models-and-effort)
6. [Writing good requests](#6-writing-good-requests)
7. [Context: keeping the AI informed without wasting it](#7-context-keeping-the-ai-informed-without-wasting-it)
8. [Building features](#8-building-features)
9. [Catching AI mistakes](#9-catching-ai-mistakes)
10. [Testing and checking](#10-testing-and-checking)
11. [Reviewing changes and pull requests](#11-reviewing-changes-and-pull-requests)
12. [Publishing and confirming it's live](#12-publishing-and-confirming-its-live)
13. [Feedback and iteration](#13-feedback-and-iteration)
14. [Security, credentials and privacy](#14-security-credentials-and-privacy)
15. [After launch: maintenance](#15-after-launch-maintenance)
16. [Small project vs serious project](#16-small-project-vs-serious-project)

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

## 5. Choosing models and effort

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

## 6. Writing good requests

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

## 7. Context: keeping the AI informed without wasting it

**Context** is everything the AI currently "knows" in a conversation. It's limited and it costs money. Long chats get
worse: the AI forgets early decisions or repeats fixed mistakes.

- **Keep durable facts in files, not in chat:** `BRIEF.md` (what and why), an instructions file (rules for agents),
  and `STATE.md` (where things stand: what's done, what's next, open questions).
- **Start each session** by having the agent read those files instead of the whole project.
- **Start a fresh session** when the task changes, when the chat has been summarised to save space, or when the
  agent repeats a mistake you already corrected.
- **End each session** by asking the agent to update `STATE.md`.

> **Case study:** several long working sessions on the project ran out of space and had to be summarised. Work
> continued smoothly only because the project's state was kept in files, not in the conversation.

## 8. Building features

One feature per request, one change per save (commit). After each: check it, then commit with a clear note.
Keep the official record separate from experiments. A "what if we traded…" screen must never alter the real data.
Use **stable IDs** for things like people and players, not names: names have accents, typos and duplicates.
Give anything that doesn't have an ID yet an explicit "provisional" status rather than a guess.

**Temporary features are fine.** On draft day the project had a live "draft room" screen showing who's on the clock,
recent picks and the best players available. After the draft it was archived. It did its job; retiring it was the
right call, not a failure.

## 9. Catching AI mistakes

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

## 10. Testing and checking

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

## 11. Reviewing changes and pull requests

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

## 12. Publishing and confirming it's live

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

## 13. Feedback and iteration

- Show the real thing to real users, on their devices, as early as possible.
- Ask them to **describe** what's wrong rather than prescribe a fix. A screenshot with one sentence is ideal.
- Keep a short list of requests, decide what's in and out, and say no to things outside the brief.
- **Simplifying is progress.** The project later removed a whole page and much of its wording because users found
  it busy. Fewer words and clearer symbols made it better on phones.

## 14. Security, credentials and privacy

- **Never put passwords, API keys or tokens in your project files or website.** Anything on a free GitHub Pages site,
  and in a public repository, is public. Use your hosting or CI's "secrets" settings for keys.
- **Personal data:** publish only what people have agreed to. Leave out phone numbers, addresses and emails unless
  that's the point of the site and people have consented.
- **Check each PR for accidental secrets or personal data** before merging.
- **Add libraries only when needed**, ask why each is needed, and prefer well-known ones.
- **Licences:** fonts, images and data have owners. Use open licences or things you have permission to use.
- **Don't paste confidential material into AI tools** unless your plan and organisation allow it.

## 15. After launch: maintenance

Launching creates ongoing work. Write down, for every data source: who updates it, how often, how you'll know it's
stale, and what happens if access changes.

> **Case study: when a data source closes.** After the draft, the project needed current team rosters weekly. Yahoo's
> roster API now requires an approved application, so a manual import was built: paste the rosters, review a list of
> differences, then confirm. It blocks the import if anything doesn't match a known player instead of silently dropping them.

Also note any recurring costs (hosting, subscriptions, your weekly time) and which features are temporary.

## 16. Small project vs serious project

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
