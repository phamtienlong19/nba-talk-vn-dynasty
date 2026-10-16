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
const role = document.getElementById("role");

// Fill the role menu from the data, so new roles appear automatically.
for (const r of [...new Set(members.map(m => m.role))].sort()) {
  const opt = document.createElement("option");
  opt.value = r;
  opt.textContent = r;
  role.appendChild(opt);
}

function render() {
  const q = search.value.trim().toLowerCase();
  const shown = members.filter(m =>
    (m.name + " " + m.role).toLowerCase().includes(q) && (role.value === "" || m.role === role.value));
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
role.addEventListener("change", render);
render();
