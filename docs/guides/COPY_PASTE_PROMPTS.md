# Copy-Paste Prompts

Short prompts for each stage of a small AI-assisted project. Replace everything in `<angle brackets>`.
Use the smallest prompt that does the job: a typo fix doesn't need a project plan.

**Where to paste:** prompts marked **Chat** go into any conversational AI (ChatGPT, Claude, Gemini…). Prompts marked
**Agent** go into your coding agent, which can read and change the files in your project (for example Copilot in
Agent mode, Claude Code or Codex).

---

## 1. Turn an idea into a project brief · Chat
```
I want to build a small <website/tool> for <who>. Today they <how it's done now>, which is a problem because <why>.
Constraints: <e.g. single page, plain HTML/CSS/JavaScript, no server or login, free hosting on GitHub Pages, public>.
Ask me up to 5 short questions first. Then write a one-page brief with: Goal, Who uses it, Must have (max 5),
Not doing (at least 3), Done when (checkable bullets), Open questions, Sample data (made-up).
```
**Replace:** who, the current process, the problem, your constraints.
**A good answer:** asks real questions first; stays within one page; "Done when" items can each be checked in under
two minutes; "Not doing" includes things you were tempted by; no invented rules (unknowns go under Open questions).

## 2. Clarify requirements · Chat
```
Here is my brief: <paste>. Find what's ambiguous or missing. For each gap, ask me one question and suggest a sensible
default. Then list the 3 riskiest assumptions and how I could check each before building.
```
**Replace:** your brief.
**A good answer:** specific questions ("What happens when two members share a name?"), not generic ones; defaults you can accept or change.

## 3. Choose a tech stack · Chat
```
For this brief: <paste>. I am a <beginner / some experience>. Recommend the simplest technology that meets it, and
one alternative. Say what each costs, where it would be hosted, and what I'd have to maintain. Avoid servers, databases
and frameworks unless the brief truly needs them, and say why if it does.
```
**Replace:** your brief and experience level.
**A good answer:** for small public sites, plain HTML/CSS/JavaScript on a free static host; a clear reason for anything heavier.

## 4. Create the first version · Agent
```
Read BRIEF.md. Build the first working version in this folder using <stack, e.g. index.html, style.css, app.js>.
Keep it as simple as possible: no libraries or build tools unless I approve. It must <work by opening index.html /
run with one command> and look right on a phone. Then tell me in 3 bullets what you made and how to test it.
```
**Replace:** your stack and how it should run.
**A good answer:** the files actually appear in your folder; a short summary; test steps you can follow; no unexpected extra files.

## 5. Add a feature · Agent
```
Goal: <what a user can do>. Done when: <1–3 checkable results>. Don't: <what must not change>.
Change only what's needed, then tell me which files you changed and how you checked it.
```
**Replace:** the goal, done-when checks, limits. For a tiny change, one sentence is enough: `Change <X> to <Y> in <file>.`
**A good answer:** a small change limited to the files it names; a description of how it was checked.

## 6. Debug an error · Agent
```
Problem: <what you see, exact error text or screenshot>. Expected: <what should happen>.
Steps to reproduce: <what you clicked/typed>. Find the root cause before changing anything; tell me the cause in one
sentence. Then fix it with the smallest change and tell me how to confirm it's fixed.
```
**Replace:** the exact error (copy it from the browser Console or terminal), expected behaviour, steps.
**A good answer:** names a specific cause; a small fix; doesn't rewrite unrelated parts.

## 7. Independent review · Chat or a new Agent session
Use a **fresh** conversation, not the one that wrote the code.
```
Review this project/change as a sceptical tester. Brief: <paste or point to BRIEF.md>. Change: <files or PR link>.
1) How could it appear to work but be wrong? 2) Does it meet the brief's goal, not just the literal request?
3) Anything changed that wasn't asked for? 4) Privacy or security problems (personal data, keys)? 5) Phone usability.
List findings by severity with evidence. Don't fix anything yet.
```
**Replace:** the brief and the change.
**A good answer:** concrete findings with where and why; separates real problems from preferences; may find nothing serious, which is fine.

## 8. Improve the visual design · Agent
```
Make the page look cleaner and easier to read on a phone, without changing what it does.
Keep: <colours/layout to keep>. Fix: <what bothers you, e.g. "cramped list", "small text">.
No new libraries or web fonts. Check at phone width (about 390 px) and computer width, and fix anything cut off.
```
**Replace:** what to keep and what bothers you. Attach a screenshot if your tool supports it.
**A good answer:** fewer, clearer elements; nothing cut off on phones; functionality unchanged.

## 9. Prepare a release · Agent
```
Before I publish: confirm all my changes are saved and committed, the site works when opened fresh, there are no
errors in the browser console, nothing private (keys, personal data) is in the files, and the "last updated" date
is current. Report each item as OK or a problem.
```
**Replace:** nothing; add project-specific checks if you have any.
**A good answer:** a short checklist with OK/problem and evidence for each.

## 10. Check that changes are live · Agent or Chat
```
I pushed a change to <repository> and my site is <URL>. Help me confirm the live site shows it: what to check in
GitHub (latest commit, Actions/deployment status), how to bypass my browser cache, and which visible detail on the
page proves it's the new version.
```
**Replace:** repository and URL.
**A good answer:** checks in order: commit pushed → deployment finished → hard refresh or private window → a visible marker.

## 11. Preserve context between sessions · Agent
**At the end of a session:**
```
Update STATE.md (keep it under 15 lines): what the project does now, what changed today, what's next,
open questions, and anything that went wrong that I should remember.
```
**At the start of a new session:**
```
Read BRIEF.md and STATE.md only. Summarise in 3 lines where we are. Then: <today's task>.
```
**Replace:** today's task.
**A good answer:** a short, accurate summary; the agent doesn't re-read the whole project unless the task needs it.

## 12. Plan the next iteration · Chat
```
My site: <URL or description>. Feedback so far: <paste what users said>. My brief: <paste>.
Group the feedback into: bugs, missing must-haves, nice-to-haves, and out of scope.
Suggest the next 3 small changes, each with a "done when" check, and one thing to remove or simplify.
```
**Replace:** your site, feedback, brief.
**A good answer:** small, specific next steps; suggests removing something as well as adding.

---

## For a real event: a tournament draft (prompts 13–22)

Use these when you have a real project, such as a basketball tournament with a player draft, and (optionally) data in
Excel or Google Sheets. Vietnamese versions of the two most important ones are in
[BASKETBALL_DRAFT_FAST_START_VI.md](BASKETBALL_DRAFT_FAST_START_VI.md). A tested example with fictional data is in
[`examples/draft-board/`](examples/draft-board/README.md). **Use fictional or consented data in AI tools and public pages.**

### 13. Turn the idea into a requirements specification · Chat
```
I'm organizing <event>. Today we handle the draft by <current process>. Write a business-analyst style specification:
actors, user stories, functional requirements, business rules, data definitions (with stable IDs), exceptions and edge
cases, acceptance criteria, non-goals. Do NOT invent rules: anything I haven't told you goes under "Open questions".
First ask me up to 10 questions about the things that would change the design.
```
**Replace:** event, current process. **Good answer:** questions first; every rule traceable to something you said; a clear
Open questions list; non-goals that keep version 1 small.

### 14. Find the rules nobody has decided yet · Chat
```
Here is my draft description: <paste>. List every rule a draft needs that I haven't defined (who may pick, order type,
pick trades, corrections, clock, eligibility changes, what's public, what happens if someone is absent, ...). For each one:
the question to ask the organizers, the realistic options, and what it changes in the software. Don't choose for me.
```
**Replace:** your description. **Good answer:** a checklist of decisions with consequences, not a finished design.

### 15. No-code, browser builder or coding agent? · Chat
```
Compare four ways to build this: (A) a browser-based AI app builder, (B) a coding agent working on files I own,
(C) Google Sheets/no-code, (D) one chat-generated HTML file on static hosting. My situation: <experience, budget,
devices, where the data lives, how many people record picks, one venue or remote viewers, how long it must last>.
Recommend one path with reasons, say when another would be better, and flag every price or limit you are not sure
about so I can verify it on the provider's official page.
```
**Replace:** the situation line. **Good answer:** a recommendation tied to *your* constraints, honest uncertainty about
prices, and the conditions that would change it.

### 16. Turn an Excel sheet into a clean data model · Chat
Paste the **column headers and 5 made-up rows**, not real personal data.
```
This is how my spreadsheet looks: <headers + 5 fictional rows>. Propose clean CSV files for a draft board with stable IDs:
teams, players, draft_order, draft_results. Show each file's columns, how the files refer to each other, which values are
allowed (eligibility, status), and the problems this sheet would cause (duplicates, merged cells, names used as keys).
Give 3 rows of example output per file.
```
**Replace:** headers and rows. **Good answer:** IDs instead of names, explicit relationships, a list of cleanup steps.

### 17. Read-only draft-board MVP · Agent
Inputs: `BRIEF.md` and the four CSV files in `data/`.
```
Read BRIEF.md and the CSV files in data/. Build a read-only draft board in plain HTML/CSS/JavaScript: draft order with the
team and player for each pick, the team on the clock, the available players, and each team's roster. Load data with fetch()
when served over http, and let me choose the CSV files when opened from file:// (fetch is blocked there). Use textContent,
not innerHTML, for imported text. Phone-friendly. Tell me how to run it and what it cannot do.
```
**Good answer:** files on disk; a run command; a list of limits; the sample data displayed correctly.

### 18. A local, organizer-operated draft tracker · Agent
Input: the read-only board from prompt 17.
```
Extend the board so one organizer can record the next pick from the available players. Rules: only the team on the clock
picks; a player can't be picked twice; ineligible players are refused; "Undo last pick" marks it void and keeps the history;
export draft_results.csv. Save state in localStorage and say on the page that it is saved only in this browser. Do not
call hidden buttons "security". Add rule tests (for example with node --test) for picking, duplicates and undo.
```
**Good answer:** the rules enforced in code you can test; a visible warning about local-only state; exported CSV that can be re-imported.

### 19. Import and validate CSV · Agent
```
Add CSV import using a real CSV parser (quoted fields, commas inside names, doubled quotes, CRLF, BOM). Before applying
anything, validate: required headers, empty values, duplicate IDs, references to unknown teams/players/picks, duplicate
players, duplicate or out-of-order picks. If any check fails, show every problem with file and line number and change
nothing. Add example bad files and tests for each failure.
```
**Good answer:** a list of error types, bad-file examples, tests that fail if validation is removed.

### 20. Audit duplicate picks and ownership · Agent or fresh Chat
```
Audit the current draft state and code. Without changing anything, report: can one player appear twice? can two results
share a pick? can a pick be recorded out of order or by a team not on the clock? what happens after undo and re-pick?
what happens if the same CSV is imported twice, or with a changed ID? Show the code or test that proves each answer.
```
**Good answer:** each question answered with evidence, and any gap listed as a finding rather than quietly fixed.

### 21. Do I really need real-time sync? · Chat
```
My draft: <venue, number of teams/devices, who must see results and when>. Do I need a shared backend, or are
"one organizer's laptop + republished results" enough? Explain what actually requires shared state, authentication,
duplicate prevention under simultaneous clicks and recovery. If a backend is needed, describe the smallest version and what
it would cost me in setup, money and maintenance. Don't assume I need it.
```
**Good answer:** a proportionate recommendation; a clear threshold for when a backend becomes necessary.

### 22. Rehearsal plan for the real tournament · Chat
```
Write a rehearsal for my draft using these facts: <devices, people, network, number of teams, tools>. Include: a full
mock draft, a deliberate wrong pick and undo, closing the browser mid-draft and reopening, exporting and opening the CSV,
a bad import, bad Wi-Fi, a backup (paper + latest CSV), and who does what. End with a go/no-go checklist.
```
**Good answer:** concrete steps with pass/fail checks and a fallback for each failure.

---

### Signs a prompt needs fixing
- The AI adds things you didn't ask for → add a **Don't** line.
- You can't tell whether it worked → add **Done when** checks.
- It keeps forgetting decisions → put them in `BRIEF.md` or `STATE.md` and start a fresh session.
- It asks you to choose between conflicting instructions → good. Decide, then update the brief.
