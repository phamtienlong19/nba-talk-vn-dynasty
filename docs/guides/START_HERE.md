# Start Here: Your First Website Built with AI

This guide takes you from an idea to a small working website at a public web address. You don't need any programming
experience. You'll use free tools, and you won't need to type commands into a terminal.

**What you'll build:** a club member directory, a page that lists members and lets visitors search and filter them.
It runs entirely in the browser, with no server, database, login or paid service.

**Time:** about 2–3 hours the first time, mostly installing and signing in. Later projects go much faster.

**Cost:** $0. Every tool in the main path has a free option. The free AI coding allowance is limited per month, but
this project needs only a handful of requests.

> **How to read this guide:** Each step has **Do** (what to click or type), **You should see** (how to know it worked)
> and sometimes **If not** (the most common fix). The full troubleshooting section is at the end. Grey boxes marked
> **Copy** are text to copy exactly. Boxes marked **Example** show what something might look like and are not meant to be copied.

---

## The tools and why each is needed

| Tool | What it is | Why you need it | Cost |
|---|---|---|---|
| **GitHub account** | A website that stores projects and can publish them as web pages | Saving your work online and publishing the site | Free |
| **GitHub Desktop** | An app that saves versions of your project and uploads them to GitHub | Saving and publishing without a terminal | Free |
| **Visual Studio Code (VS Code)** | A free editor for code files | Where you open the project and talk to the AI | Free |
| **GitHub Copilot (Free plan)** | An AI assistant inside VS Code that can create and edit files | Writing the code for you | Free (monthly limit) |
| **A chat AI** (ChatGPT, Claude, Gemini, Copilot chat…) | A conversational AI | Thinking the idea through before building | Free tiers are enough |
| **A web browser** | Chrome, Edge, Firefox or Safari | Viewing and testing your site | Free |

You don't need several paid AI subscriptions. Other coding agents (Claude Code, OpenAI Codex, Cursor and others) are
good alternatives and are covered in [Other ways to do this](#other-ways-to-do-this). They can cost money and some
need the terminal, so they aren't the default path here.

### Six words you'll see

- **Repository (repo):** your project folder, with its full history. It lives on your computer and on GitHub.
- **Commit:** a saved snapshot of your project, with a short note describing what changed.
- **Push:** sending your new commits from your computer to GitHub.
- **Publish / deploy:** making the site available at a public web address.
- **Agent:** an AI that can create and change files itself, not just chat.
- **Local preview:** opening the site from your own computer before publishing it.

---

## Step 1 — Choose a small first project

A good first project:

- solves something real for you or a group you belong to
- fits on **one page**
- uses data you can type into a list (10–50 items)
- has one or two useful interactions, such as search, filter, sort or a total
- doesn't need logins, payments or saving data entered by visitors

**Good first projects:** a club or team directory, a reading list, a recipe index, a training-session schedule, an equipment checklist.
**Save for later:** anything with user accounts, payments, private information, or data that many people edit.

> ⚠️ **Your site will be public.** Anyone with the address can see it, and on the free plan they can also see its files.
> Use made-up names or only information people have agreed to share. Never put passwords, phone numbers or home addresses in it.

This guide uses a **chess club member directory** as the example. You can follow along exactly, or swap in your own idea.

---

## Step 2 — Explain your idea to a chat AI

Before building anything, spend 10 minutes getting the idea clear. This saves a lot of wasted AI requests later.

**Do:** Open any chat AI in your browser (for example chatgpt.com, claude.ai or gemini.google.com) and paste:

**Copy:**
```
I want to build a very small website as my first project. I have no programming experience.
Idea: a member directory for my chess club. Visitors should see each member's name and role,
search by name or role, and see how many members match.
It must be a single page using only HTML, CSS and JavaScript, with no server, database, login or paid service.
It will be published free on GitHub Pages, so it is public: I'll use made-up names.

Please ask me up to 5 short questions to clarify the idea. Then write a project brief with these headings:
Goal (2 sentences), Who uses it, Must have (max 5 bullets), Not doing (at least 3 bullets),
Done when (checkable bullets), Sample data (5–8 made-up members with name and role).
Keep it under one page.
```

Answer its questions. Then:

**You should see:** a short brief with those six headings. Keep it open; you'll paste it into your project in Step 4.

**If the brief is long or adds features you didn't ask for** (logins, databases, frameworks), reply:

**Copy:**
```
Simplify: one page, plain HTML/CSS/JavaScript, no frameworks, no backend. Remove anything not in my original idea.
```

---

## Step 3 — Install the tools and sign in

### 3a. Create a GitHub account
**Do:** Go to **github.com**, click **Sign up**, and follow the steps. Choose a username you're happy to have in your
site's address, which will look like `https://USERNAME.github.io/club-directory/`.

### 3b. Install GitHub Desktop
**Do:** Go to **desktop.github.com**, download it for Windows or Mac, install it and open it.
Choose **Sign in to GitHub.com** and approve it in the browser window that opens.
When asked to **configure Git**, enter your name and the email address you used for GitHub (or the private
`…@users.noreply.github.com` address GitHub offers), then click **Finish**.

**You should see:** a "Let's get started!" screen.

> GitHub Desktop handles Git for you, so you don't need to install Git separately.

### 3c. Install Visual Studio Code
**Do:** Go to **code.visualstudio.com**, download it for your system and install it.
- **Windows:** in the installer, tick **"Add 'Open with Code' action"**. It's optional but handy.
- **Mac:** after downloading, drag **Visual Studio Code** into your **Applications** folder, then open it from there.

### 3d. Turn on the AI assistant (GitHub Copilot Free)
**Do:** In VS Code, find the **Copilot icon** (a small face or sparkle) in the bottom status bar or the top title bar.
Click it and choose the option to **use AI features / sign in**, then sign in with your GitHub account.
If you don't have a Copilot subscription, this signs you up for the **Copilot Free** plan.

**You should see:** a **Chat** panel you can open (usually on the right). The keyboard shortcut is
**Ctrl+Alt+I** on Windows or **Ctrl+Cmd+I** on Mac.

> VS Code updates its AI features often, so button names and positions may differ slightly from this guide.
> Look for "Chat" and "Agent". You need the mode that **edits files** (usually called **Agent**), not just "Ask".

---

## Step 4 — Create your project (repository)

**Do (in GitHub Desktop):**
1. Click **Create a New Repository on your Hard Drive…** (or **File → New repository**).
2. **Name:** `club-directory`
3. **Local path:** leave the default (for example `Documents/GitHub`). Remember where it is.
4. Tick **Initialize this repository with a README**.
5. Click **Create repository**.
6. Click **Repository → Open in Visual Studio Code** (it may say **Open in External Editor**).

**You should see:** VS Code open with a folder called `club-directory` in the left-hand **Explorer**, containing `README.md`.

**If not:** set the editor in GitHub Desktop under **File → Options → Integrations** (Windows) or
**GitHub Desktop → Settings → Integrations** (Mac): **External editor → Visual Studio Code**, then try again.
Or open VS Code yourself and use **File → Open Folder…** to choose the `club-directory` folder.

**Add your brief:**
1. In VS Code's Explorer, hover over the folder name and click the **New File** icon. Name the file `BRIEF.md`.
2. Paste the brief from Step 2 into it.
3. Save with **Ctrl+S** (Windows) or **Cmd+S** (Mac).

> If VS Code asks **"Do you trust the authors of the files in this folder?"**, choose **Yes**. It's your own folder.

---

## Step 5 — Ask the AI to build the first version

**Do:** Open the Chat panel, switch it to **Agent** mode, and paste:

**Copy:**
```
Read BRIEF.md. Build the first working version of this website in this folder.
Use exactly three files: index.html, style.css and app.js. Plain HTML, CSS and JavaScript only:
no frameworks, no build tools, no external libraries, no internet resources.
Put the member data as a list inside app.js (no separate data file).
It must work when I double-click index.html to open it from my computer.
It must look good on a phone screen (about 390 pixels wide).
When you're done, tell me in 3 short bullet points what you created and how I can test it.
```

The AI will work for a minute or so. It may ask permission to create files; allow it.

**You should see:**
- three new files in the Explorer: `index.html`, `style.css`, `app.js`
- a summary from the AI in the chat
- **Keep** / **Undo** buttons next to the changes. The edits are already saved to your files; click **Keep** to accept them.

**If the files aren't there:** see [The AI said it finished but there are no files](#the-ai-said-it-finished-but-there-are-no-files).

> **Your files should look roughly like the reference version** in [Appendix: reference code](#appendix-reference-code).
> It's tested and works. If the AI struggles, you can copy it instead and carry on with the guide.

---

## Step 6 — Run it and look at it

This site doesn't need to be "started". You just open the file.

**Do:**
1. In VS Code's Explorer, right-click `index.html` and choose **Reveal in File Explorer** (Windows) or **Reveal in Finder** (Mac).
2. Double-click `index.html`. It opens in your browser.

**You should see:** your club name, a search box, and a list of members with their roles and a count such as "5 of 5 members".
The browser's address bar will start with `file://` — that's normal for a local preview.

**If the page is blank:** see [The browser shows a blank page](#the-browser-shows-a-blank-page).

---

## Step 7 — Check it properly, then ask for fixes

The AI saying "done" isn't the same as the site working. Check it yourself; this takes 3 minutes.

**Check:**
1. **Search:** type part of a name. The list should shrink. Type nonsense, and a "no matches" message should appear. Clear the box, and everyone should come back.
2. **The count** should change as you search.
3. **Phone view:** press **F12** (Windows) or **Cmd+Option+I** (Mac) to open the browser's developer tools. Click the
   **phone/tablet icon** (device toolbar) and pick a phone. Nothing should be cut off or need sideways scrolling.
4. **Errors:** in the developer tools, open the **Console** tab. Red messages mean something is broken.

> **Mac with Safari:** Safari hides developer tools by default. Turn them on in **Safari → Settings → Advanced →
> "Show features for web developers"**, or open the file in Chrome or Edge instead: right-click `index.html` →
> **Open With** → the browser.
5. **Content:** names and roles match your brief, and there's no leftover placeholder text.

**To fix something,** describe what you saw rather than what you think the code should be. Paste into the Agent chat:

**Example (adapt to what you saw):**
```
Problem: on a phone-sized screen, long roles wrap under the name and look messy.
Expected: name on the left, role on the right, on one line.
Please fix only this, keep everything else the same, and tell me which file you changed.
```

Reload the browser tab after each fix to see the change (**F5** or **Ctrl+R** on Windows, **Cmd+R** on Mac), and re-check.

> **Good habit:** ask for one fix at a time. Big multi-part requests are harder to check and more likely to break something else.

---

## Step 8 — Save your work (commit)

A commit is a saved snapshot you can always go back to.

**Do (in GitHub Desktop):**
1. On the left you'll see the changed files (`BRIEF.md`, `index.html`, `style.css`, `app.js`).
2. In the **Summary** box at the bottom left, type: `First working version of the club directory`
3. Click **Commit to main**.

**You should see:** the list of changes empty out. Under **History** you'll see your commit.

---

## Step 9 — Publish it on the web (GitHub Pages)

### 9a. Upload the project to GitHub
**Do (in GitHub Desktop):** click **Publish repository**.
- **Untick "Keep this code private"**. GitHub Pages is free only for **public** repositories.
- Click **Publish repository**.

**You should see:** the button change to **Fetch origin**. Your project is now at `https://github.com/USERNAME/club-directory`.

### 9b. Turn on GitHub Pages
**Do:**
1. In GitHub Desktop, click **Repository → View on GitHub**. Your project opens in the browser.
2. Click **Settings** (top of the page; if you can't see it, open the **⋯** menu).
3. In the left sidebar, click **Pages**.
4. Under **Build and deployment → Source**, choose **Deploy from a branch**.
5. Under **Branch**, choose **main** and folder **/ (root)**, then click **Save**.

**You should see:** after a minute or two (refresh the Settings page), a message like **"Your site is live at
https://USERNAME.github.io/club-directory/"** with a **Visit site** button.

> The address always follows the pattern `https://USERNAME.github.io/REPOSITORY-NAME/`, with your username and repository name.

---

## Step 10 — Check that the public site really works

**Do:**
1. Click **Visit site**, or type the address.
2. Repeat the Step 7 checks on the live address.
3. Open the address **on your phone** (outside Wi-Fi if you can), or in a **private/incognito window** on your computer.
4. On GitHub, click the **Actions** tab. A green tick on **"pages build and deployment"** means the latest publish succeeded.
   A yellow dot means it's still running; a red ✗ means it failed (click it to see why).

**You should see:** the same page you saw locally, now at your public address.

**Share the link.** You've built and published a website. 🎉

---

## Step 11 — Make your first improvement

Every future change follows the same loop: **ask → check → commit → push → verify live**.

**The improvement:** add a **role filter**, a drop-down menu that shows only Captains, only Members, and so on, and
works together with the search box.

**1. Ask (Agent chat):**

**Copy:**
```
Add a "Role" drop-down below the search box. Its options are "All roles" plus each role that exists in the member data
(filled in automatically from the data, sorted A–Z). Selecting a role shows only members with that role, and it must
work together with the search box. Update the member count accordingly. Keep the design consistent and phone-friendly.
Change only what's needed and tell me which files you changed.
```

**2. Check** (open or reload `index.html` locally):
- "All roles" shows everyone.
- Choosing **Member** shows only members; then typing a name narrows it further.
- The phone view still looks right, and the Console has no red errors.

**3. Commit (GitHub Desktop):** Summary `Add role filter` → **Commit to main**.

**4. Push:** click **Push origin**. This uploads the new commit to GitHub.

**5. Verify live:** wait 1–2 minutes (watch the **Actions** tab turn green), then open your site and do a
**hard refresh** to make sure you're not seeing an old saved copy: **Ctrl+Shift+R** (Windows) or **Cmd+Shift+R** (Mac).
The role drop-down should be there.

> **Tip:** Update the "Last updated" date in the footer with each change. It's an easy way to tell whether you're
> looking at the new version or an old copy.

---

## What you've learned

- An AI coding agent can write the code; **you** decide what to build, check that it works, and approve every change.
- The loop is **brief → small request → check yourself → commit → push → verify the live site**.
- "The AI says it's done", "it works on my computer" and "it's live on the internet" are three different things.
  Check each one.

**Next steps:** read [Building with AI](BUILDING_WITH_AI.md) for the full method (bigger projects, testing, reviewing
AI mistakes, privacy). Keep [Copy-paste prompts](COPY_PASTE_PROMPTS.md) open while you work.

---

## Troubleshooting

### "Command not found" in a terminal
You don't need a terminal for this guide. If you followed another tutorial and see `git: command not found` or
`claude: command not found`, the tool isn't installed or the terminal was opened before installing it.
**Check first:** close and reopen the terminal; check the tool's install instructions for your system
(on Mac, `git` is installed by running `xcode-select --install`; on Windows, install "Git for Windows").
**Prompt:**
```
I'm on <Windows/Mac>. I ran <exact command> and got: <exact error>. I'm a beginner.
Explain what it means and give me the exact steps to fix it, one at a time.
```

### GitHub sign-in or publishing fails
**Check first:** in GitHub Desktop, open **File → Options → Accounts** (Windows) or **GitHub Desktop → Settings → Accounts** (Mac).
Sign out and sign back in. Make sure you can sign in at github.com in the browser. If you have two-factor
authentication, complete it in the browser window GitHub Desktop opens.
**Prompt:**
```
GitHub Desktop shows this error when I click <Publish/Push>: <exact message>. What should I check, step by step?
```

### The AI can't see or change my files
**Check first:** VS Code must have the **project folder** open (Explorer shows `club-directory`), not just a single
file. Use **File → Open Folder…**. The chat must be in **Agent** mode, you must be signed in to Copilot, and if you
were asked whether to trust the folder, you must have chosen **Yes**. If you've used up the free monthly allowance,
the chat will tell you.
**Prompt:**
```
List the files in this workspace and tell me whether you can create and edit files here. If not, tell me why.
```

### The site doesn't open, or nothing happens
**Check first:** make sure you're opening **`index.html`** itself (from Finder/File Explorer), not `app.js` or the
folder. The address bar should end in `index.html`.
**Prompt:**
```
When I double-click index.html, <what happens>. Check that index.html links to style.css and app.js correctly
and that the site works when opened directly from disk (file://), with no server.
```

### The browser shows a blank page
**Check first:** open the developer tools (**F12** / **Cmd+Option+I**) → **Console**. Copy any red error message.
**Prompt:**
```
My page is blank. The browser console shows: <paste the red error>. Find the cause and fix it.
Tell me what was wrong in one sentence.
```

### The AI said it finished but there are no files
**Check first:** look in VS Code's Explorer and expand the folder. Check whether the chat was in **Ask** mode (which only
answers questions) instead of **Agent** mode. Check whether the AI only showed code in the chat; if so, it didn't
create files. Check whether you clicked **Undo** by mistake.
**Prompt:**
```
I don't see index.html, style.css or app.js in my project folder. Create the files in this workspace now
(don't just show the code in chat), then list the files that exist.
```

### Everything "passes" but the page looks wrong
Automated checks and AI summaries can't see what you see. Trust your eyes.
**Check first:** take a screenshot of the problem, at the phone size if it's a layout issue.
**Prompt (attach the screenshot if your tool allows it):**
```
The page works but looks wrong: <describe exactly what's wrong and where, e.g. "the role text overlaps the name on
phone width">. Expected: <what it should look like>. Fix only this and keep the rest unchanged.
```

### GitHub Pages shows an old version
**Check first, in order:**
1. Did you **commit** *and* **push**? GitHub Desktop should show no "Push origin" count.
2. On GitHub, open the **Actions** tab: is the latest "pages build and deployment" finished and green?
3. Hard refresh (**Ctrl+Shift+R** / **Cmd+Shift+R**), or open the site in a private window. Browsers keep old copies.
4. Check the "Last updated" footer date to confirm which version you're seeing.

**Prompt:**
```
I pushed a change but my GitHub Pages site still shows the old version. Give me a checklist to find out whether the
problem is my commit, the push, the GitHub Pages deployment, or my browser cache.
```

### The AI gets confused, repeats mistakes or forgets earlier decisions
Long conversations degrade. The fix is a fresh start with the right context.
**Check first:** is your brief still accurate? Update `BRIEF.md` with decisions you've made since.
**Do:** start a **new chat** and paste:
```
Read BRIEF.md, index.html, style.css and app.js. Summarise in 3 lines what the site currently does.
Then: <your one request>.
```

### How do I safely undo a change?
- **Not committed yet:** in GitHub Desktop, right-click the changed file → **Discard changes…**. In VS Code you can
  also click **Undo** on the AI's edits.
- **Already committed but not pushed:** GitHub Desktop → **History**, right-click the commit → **Undo commit**.
- **Already pushed:** GitHub Desktop → **History**, right-click the commit → **Revert changes in commit**, then
  **Push origin**. This creates a new commit that reverses the old one, and your history stays intact.

**Prompt:**
```
I want to undo <describe the change>. It is <not committed / committed / pushed>. Which is the safest way using
GitHub Desktop, step by step?
```

---

## Other ways to do this

The path above uses free tools and no terminal. Common alternatives:

| Option | What changes | Cost |
|---|---|---|
| **Claude Code** (Anthropic) | A coding agent that runs in a terminal or inside VS Code. Very capable on larger projects | Needs a paid Claude plan |
| **OpenAI Codex** | A coding agent (app, terminal or editor extension) | Limited on ChatGPT's free plan; fuller access on paid plans |
| **Cursor, Windsurf and similar** | Editors with built-in AI agents | Free tiers with limits; paid plans |
| **Terminal Git** instead of GitHub Desktop | The same steps, typed as commands (`git add`, `git commit`, `git push`) | Free |
| **Netlify / Cloudflare Pages** instead of GitHub Pages | Other free static hosts, with drag-and-drop or Git-connected publishing | Free tiers |

Plans, limits and button names change often. Check each provider's current pricing and setup page before choosing.
Pick **one** AI coding tool and learn it well; you don't need several.

---

## Appendix: reference code

A tested version of the first project. Use it to compare with what your AI produced, or copy it if you get stuck.
Create the three files in your project folder and paste each one in.

**Copy — `index.html`:**
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Riverside Chess Club — Members</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>Riverside Chess Club</h1>
    <p class="sub">Member directory · <span id="count"></span></p>
  </header>
  <main>
    <label for="search">Search by name or role</label>
    <input id="search" type="search" placeholder="e.g. Maya or Captain" autocomplete="off">
    <ul id="list"></ul>
    <p id="empty" hidden>No members match your search.</p>
  </main>
  <footer>Last updated: 2026-10-16</footer>
  <script src="app.js"></script>
</body>
</html>
```

**Copy — `style.css`:**
```css
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; background: #f5f6f8; color: #1d2433; }
header, main, footer { max-width: 640px; margin: 0 auto; padding: 16px; }
h1 { margin: 8px 0 0; font-size: 1.6rem; }
.sub { margin: 4px 0 0; color: #5b6475; }
label { display: block; font-weight: 600; margin-bottom: 6px; }
input { width: 100%; padding: 10px 12px; font-size: 1rem; border: 1px solid #c5cbd6; border-radius: 8px; }
ul { list-style: none; padding: 0; margin: 16px 0; }
li { background: #fff; border: 1px solid #e2e6ee; border-radius: 10px; padding: 12px 14px; margin-bottom: 8px;
     display: flex; justify-content: space-between; gap: 12px; }
.name { font-weight: 600; }
.role { color: #5b6475; white-space: nowrap; }
footer { color: #5b6475; font-size: .85rem; }
```

**Copy — `app.js`:**
```js
// Member list. Use made-up names or people who agreed to be listed — this page is public.
const members = [
  { name: "Maya Chen", role: "Captain" },
  { name: "Tom Okafor", role: "Treasurer" },
  { name: "Lena Novak", role: "Member" },
  { name: "Sam Rivera", role: "Member" },
  { name: "Priya Shah", role: "Coach" }
];

const list = document.getElementById("list");
const search = document.getElementById("search");
const empty = document.getElementById("empty");
const count = document.getElementById("count");

function render() {
  const q = search.value.trim().toLowerCase();
  const shown = members.filter(m => (m.name + " " + m.role).toLowerCase().includes(q));
  list.innerHTML = "";
  for (const m of shown) {
    const li = document.createElement("li");
    li.innerHTML = '<span class="name"></span><span class="role"></span>';
    li.querySelector(".name").textContent = m.name;
    li.querySelector(".role").textContent = m.role;
    list.appendChild(li);
  }
  empty.hidden = shown.length > 0;
  count.textContent = shown.length + " of " + members.length + " members";
}

search.addEventListener("input", render);
render();
```

**Expected result:** "5 of 5 members"; searching "captain" shows only Maya Chen; searching "zzz" shows
"No members match your search." and "0 of 5 members".

### Reference: the role filter (Step 11)

**In `index.html`**, directly below the `<input id="search" …>` line, add:
```html
    <label for="role">Role</label>
    <select id="role"><option value="">All roles</option></select>
```

**In `style.css`**, replace the `label` and `input` lines with:
```css
label { display: block; font-weight: 600; margin: 12px 0 6px; }
input, select { width: 100%; padding: 10px 12px; font-size: 1rem; border: 1px solid #c5cbd6; border-radius: 8px; }
```

**In `app.js`**, add after the line `const count = …`:
```js
const role = document.getElementById("role");

// Fill the role menu from the data, so new roles appear automatically.
for (const r of [...new Set(members.map(m => m.role))].sort()) {
  const opt = document.createElement("option");
  opt.value = r;
  opt.textContent = r;
  role.appendChild(opt);
}
```
then replace the `const shown = …` line with:
```js
  const shown = members.filter(m =>
    (m.name + " " + m.role).toLowerCase().includes(q) && (role.value === "" || m.role === role.value));
```
and add at the end, just above `render();`:
```js
role.addEventListener("change", render);
```

**Expected result:** the drop-down lists All roles, Captain, Coach, Member, Treasurer. Choosing **Member** shows Lena
Novak and Sam Rivera; then typing "sam" shows only Sam Rivera.
