# Club directory example (from START_HERE.md)

Fictional members. Three plain files per version: `index.html`, `style.css`, `app.js`. Open `index.html` by double-clicking.

| Folder | What it is |
|---|---|
| `v1-first-version/` | The first working version (Step 5). Search box, member list, count |
| `v2-role-filter/` | After Step 11: adds a Role drop-down that works together with the search |

**Expected result (v1):** "5 of 5 members"; searching "captain" shows only Maya Chen; searching "zzz" shows
"No members match your search." and "0 of 5 members".
**Expected result (v2):** the drop-down lists All roles, Captain, Coach, Member, Treasurer. Choosing **Member** shows
Lena Novak and Sam Rivera; then typing "sam" shows only Sam Rivera.

## What changed from v1 to v2

- `index.html`: a `Role` label and `<select id="role">` below the search input.
- `style.css`: `input, select` share one rule; `label` gets a little top margin.
- `app.js`: the role menu is filled from the data; the filter also checks `role.value`; a `change` listener calls `render()`.

Compare the two folders with any "diff" tool, or ask your AI agent: "Explain the difference between these two folders."
