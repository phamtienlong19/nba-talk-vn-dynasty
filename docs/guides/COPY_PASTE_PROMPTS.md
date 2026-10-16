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

### Signs a prompt needs fixing
- The AI adds things you didn't ask for → add a **Don't** line.
- You can't tell whether it worked → add **Done when** checks.
- It keeps forgetting decisions → put them in `BRIEF.md` or `STATE.md` and start a fresh session.
- It asks you to choose between conflicting instructions → good. Decide, then update the brief.
