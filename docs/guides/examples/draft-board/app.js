/* app.js — the screen. All rules live in draft-core.js.
   Where the data lives (read this):
   - The sample CSV files in data/ are the starting point. Opened from a web address (http/https) the page reads them itself.
   - Opened by double-clicking index.html (file://), browsers block reading other files, so you pick the CSV files by hand.
   - Every change YOU make is saved in THIS browser only (localStorage), and that saved copy wins over the CSV files on later visits
     (use "Clear saved data" to go back to the files). It survives a refresh. It is NOT shared with other
     devices or other browsers, and it can be lost if the browser data is cleared. Export the results regularly.
   - Text from CSV files is always inserted with textContent, never as HTML. */
(function () {
  "use strict";
  const Core = window.DraftCore;
  const params = new URLSearchParams(location.search);
  const lang = params.get("lang") === "en" ? "en" : "vi";
  const STORE_KEY = "draft-board-example-v1";
  const FILES = { teams: "teams.csv", players: "players.csv", order: "draft_order.csv", results: "draft_results.csv" };

  const T = {
    vi: {
      title: "Bảng draft — ví dụ", sub: "Dữ liệu giả, chỉ để thử",
      welcomeTitle: "Chọn các file CSV",
      welcomeText: "Bạn đang mở trang bằng cách bấm đúp vào file, nên trình duyệt không tự đọc được thư mục data/. Hãy chọn các file teams.csv, players.csv, draft_order.csv (và draft_results.csv nếu có) trong thư mục data/. Có thể chọn cùng lúc. Mẹo: chạy máy chủ local để trang tự tải dữ liệu (xem hướng dẫn).",
      pickFiles: "Chọn file CSV…", importLabel: "Nhập file CSV…", importOk: "Đã nhập dữ liệu mới.",
      onClock: "Đang đến lượt", pickNo: "Pick", draftComplete: "Draft đã xong",
      controls: "Điều khiển ban tổ chức", controlsNote: "Lưu ý: nút ẩn/hiện chỉ để trình bày. Đây KHÔNG phải bảo mật — ai mở trang này trên máy này đều bấm được. Trạng thái chỉ nằm trong trình duyệt này.",
      undo: "Hoàn tác pick cuối", exportCsv: "Tải kết quả (CSV)", exportJson: "Tải bản sao lưu (JSON)", audit: "Kiểm tra dữ liệu",
      reset: "Xoá dữ liệu đã lưu", resetConfirm: "Xoá toàn bộ pick và dữ liệu đã lưu trong trình duyệt này?",
      available: "Cầu thủ còn lại", search: "Tìm theo tên…", allPos: "Mọi vị trí", pick: "Chọn", none: "Không còn cầu thủ phù hợp.",
      board: "Bảng draft", cols: ["Pick", "Đội", "Cầu thủ", "Vị trí"], teams: "Đội hình",
      saveFail: "KHÔNG LƯU ĐƯỢC trong trình duyệt này (có thể đang ở chế độ riêng tư). Hãy tải kết quả CSV sau mỗi vài pick.", saved: "Đã lưu trong trình duyệt này lúc", notSaved: "Chưa lưu (dữ liệu mẫu). Không chia sẻ với thiết bị khác.", localOnly: "chỉ trong trình duyệt này",
      auditOk: "Kiểm tra xong: không có cầu thủ trùng, không có pick trùng, thứ tự đúng.", problems: "Có lỗi — chưa thay đổi gì:", warnings: "Lưu ý:",
      noUndo: "Chưa có pick nào để hoàn tác.", undone: "Đã hoàn tác pick", picked: "Đã ghi pick",
      demoWarn: "BẢN DEMO — dữ liệu giả. Pick chỉ lưu trong trình duyệt này, không chia sẻ với ai. Các nút tổ chức KHÔNG có xác thực (ai mở trang cũng bấm được). Không dùng cho giải thật; đừng nhập dữ liệu người thật.",
      footer: "Tất cả cầu thủ và đội là hư cấu. Luật draft thật do ban tổ chức quyết định.", loadFail: "Không tải được thư mục data/. Hãy dùng nút chọn file.",
      err: {
        E_CSV: "{file} dòng {line}: dấu ngoặc kép không được đóng.", E_EMPTY: "{file}: file trống.", E_HEADER: "{file}: thiếu cột — {message}",
        E_COLUMNS: "{file} dòng {line}: số cột không khớp. {message}", E_MISSING: "{file} dòng {line}: {message}", E_DUP_ID: "{file} dòng {line}: ID bị trùng ({value}).",
        E_VALUE: "{file} dòng {line}: giá trị không hợp lệ ({value}).", E_NUMBER: "{file} dòng {line}: số pick không hợp lệ ({value}).",
        E_DUP_PICK: "{file} dòng {line}: pick {value} bị trùng.", E_UNKNOWN_REF: "{file} dòng {line}: tham chiếu không tồn tại ({value}).", E_GAP: "{file}: thứ tự pick bị đứt quãng.",
        E_DUP_PLAYER: "{file} dòng {line}: cầu thủ {value} được chọn hai lần.", E_INELIGIBLE: "{file} dòng {line}: cầu thủ {value} không đủ điều kiện.",
        E_OUT_OF_ORDER: "{file}: pick phải được ghi theo thứ tự — {message}", E_NO_FILE: "{file}: chưa chọn file.", W_EXTRA: "{file}: {message}"
      },
      pickErr: { ALREADY_PICKED: "Cầu thủ này đã được chọn.", INELIGIBLE: "Cầu thủ này không đủ điều kiện.", DRAFT_COMPLETE: "Draft đã xong.", UNKNOWN_PLAYER: "Không tìm thấy cầu thủ." }
    },
    en: {
      title: "Draft board — example", sub: "Fictional data, for practice",
      welcomeTitle: "Choose the CSV files",
      welcomeText: "You opened this page by double-clicking the file, so the browser can't read the data/ folder by itself. Choose teams.csv, players.csv, draft_order.csv (and draft_results.csv if you have it) from the data/ folder. You can select them all at once. Tip: run a local server so the page loads the data itself (see the guide).",
      pickFiles: "Choose CSV files…", importLabel: "Import CSV files…", importOk: "New data imported.",
      onClock: "On the clock", pickNo: "Pick", draftComplete: "The draft is complete",
      controls: "Organizer controls", controlsNote: "Note: hiding the controls is only presentation. It is NOT security — anyone using this page on this computer can press the buttons. State lives in this browser only.",
      undo: "Undo last pick", exportCsv: "Download results (CSV)", exportJson: "Download backup (JSON)", audit: "Check data",
      reset: "Clear saved data", resetConfirm: "Delete all picks and saved data in this browser?",
      available: "Available players", search: "Search by name…", allPos: "All positions", pick: "Pick", none: "No matching players left.",
      board: "Draft board", cols: ["Pick", "Team", "Player", "Pos"], teams: "Teams",
      saveFail: "COULD NOT SAVE in this browser (private mode?). Download the results CSV every few picks.", saved: "Saved in this browser at", notSaved: "Not saved (sample data). Not shared with other devices.", localOnly: "this browser only",
      auditOk: "Check complete: no duplicate players, no duplicate picks, order is correct.", problems: "Problems found — nothing was changed:", warnings: "Notes:",
      noUndo: "No pick to undo.", undone: "Undid pick", picked: "Recorded pick",
      demoWarn: "DEMO — fictional data. Picks are stored only in this browser and shared with nobody. The organizer controls have NO authentication (anyone who opens the page can press them). Not for a real tournament; don't enter real people's data.",
      footer: "All players and teams are fictional. The real draft rules are the organizer's decision.", loadFail: "Could not load the data/ folder. Use the file picker.",
      err: {
        E_CSV: "{file} line {line}: a quoted value is never closed.", E_EMPTY: "{file}: the file is empty.", E_HEADER: "{file}: {message}",
        E_COLUMNS: "{file} line {line}: wrong number of values. {message}", E_MISSING: "{file} line {line}: {message}", E_DUP_ID: "{file} line {line}: duplicate ID ({value}).",
        E_VALUE: "{file} line {line}: invalid value ({value}).", E_NUMBER: "{file} line {line}: invalid pick number ({value}).",
        E_DUP_PICK: "{file} line {line}: pick {value} appears twice.", E_UNKNOWN_REF: "{file} line {line}: unknown reference ({value}).", E_GAP: "{file}: pick numbers have a gap.",
        E_DUP_PLAYER: "{file} line {line}: player {value} is picked twice.", E_INELIGIBLE: "{file} line {line}: player {value} is not eligible.",
        E_OUT_OF_ORDER: "{file}: picks must be recorded in order — {message}", E_NO_FILE: "{file}: no file chosen.", W_EXTRA: "{file}: {message}"
      },
      pickErr: { ALREADY_PICKED: "That player is already picked.", INELIGIBLE: "That player is not eligible.", DRAFT_COMPLETE: "The draft is complete.", UNKNOWN_PLAYER: "Player not found." }
    }
  }[lang];

  let state = null, savedAt = null, saveFailed = false, flash = "";
  const $ = (id) => document.getElementById(id);

  // ------------------------------------------------------------ storage
  function save() {
    try { const when = new Date(); localStorage.setItem(STORE_KEY, JSON.stringify({ version: 1, savedAt: when.toISOString(), state })); savedAt = when; saveFailed = false; return true; }
    catch (e) { saveFailed = true; return false; } // blocked storage (private mode, file:// in some browsers): tell the user, don't pretend
  }
  function loadSaved() {
    try {
      const raw = localStorage.getItem(STORE_KEY); if (!raw) return null;
      const obj = JSON.parse(raw); if (!obj || obj.version !== 1 || !obj.state) return null;
      if (Core.audit(obj.state).length) return null; // never trust saved data blindly: re-check it
      savedAt = new Date(obj.savedAt); return obj.state;
    } catch (e) { return null; }
  }

  // ------------------------------------------------------------- problems
  function describe(e) {
    const tpl = T.err[e.code] || "{file} line {line}: {message}";
    return tpl.replace("{file}", e.file).replace("{line}", e.line).replace("{value}", e.value).replace("{message}", e.message);
  }
  function showProblems(errors, warnings, heading) {
    const box = $("problems"); box.textContent = "";
    if (!errors.length && !(warnings && warnings.length)) { box.hidden = true; return; }
    if (errors.length) { const h = document.createElement("strong"); h.textContent = heading || T.problems; box.appendChild(h); }
    const ul = document.createElement("ul");
    for (const e of errors) { const li = document.createElement("li"); li.textContent = describe(e) + "  [" + e.code + "]"; ul.appendChild(li); }
    for (const w of warnings || []) { const li = document.createElement("li"); li.textContent = T.warnings + " " + describe(w); ul.appendChild(li); }
    box.appendChild(ul); box.hidden = false;
  }

  // -------------------------------------------------------------- loading
  async function fetchText(file, optional) {
    const res = await fetch("data/" + file, { cache: "no-store" });
    if (!res.ok) { if (optional) return null; throw new Error(file + " " + res.status); }
    return res.text();
  }
  async function loadFromDataFolder() {
    const texts = { teams: await fetchText(FILES.teams), players: await fetchText(FILES.players), order: await fetchText(FILES.order), results: await fetchText(FILES.results, true) };
    return Core.loadDataset(texts);
  }
  async function readPickedFiles(fileList) {
    const texts = {}; const byName = {}; for (const k in FILES) byName[FILES[k]] = k;
    for (const f of Array.from(fileList)) { const kind = byName[f.name.toLowerCase()]; if (kind) texts[kind] = await f.text(); }
    return Core.loadDataset({ teams: texts.teams, players: texts.players, order: texts.order, results: texts.results === undefined ? null : texts.results });
  }
  function applyLoaded(result, announce) {
    if (!result.ok) { showProblems(result.errors, result.warnings); return false; } // nothing changes on error
    state = result.state; if (announce) { save(); flash = T.importOk; } /* only YOUR actions are saved; the untouched sample is re-read from data/ each time */
    showProblems([], result.warnings); render(); return true;
  }
  async function importFiles(fileList) {
    const result = await readPickedFiles(fileList);
    if (result.ok && state && Core.officialResults(state).length && !window.confirm(T.resetConfirm)) return false;
    return applyLoaded(result, true);
  }

  // --------------------------------------------------------------- actions
  function doPick(id) {
    const r = Core.recordPick(state, id);
    if (!r.ok) { flash = T.pickErr[r.code] || r.code; render(); return; }
    state = r.state; save(); flash = T.picked + " " + r.pick; render();
  }
  function doUndo() {
    const r = Core.undoLastPick(state);
    if (!r.ok) { flash = T.noUndo; render(); return; }
    state = r.state; save(); flash = T.undone + " " + r.pick; render();
  }
  function download(name, text, type) {
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  function doReset() {
    if (!window.confirm(T.resetConfirm)) return;
    try { localStorage.removeItem(STORE_KEY); } catch (e) { /* ignore */ }
    state = null; savedAt = null; start(true);
  }

  // ---------------------------------------------------------------- render
  function el(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; }
  function render() {
    $("demoWarning").textContent = T.demoWarn; $("title").textContent = T.title; $("sub").textContent = T.sub; $("footer").textContent = T.footer;
    document.documentElement.lang = lang;
    document.body.classList.toggle("viewmode", params.get("mode") === "view");
    $("welcome").hidden = !!state; $("app").hidden = !state;
    $("welcomeTitle").textContent = T.welcomeTitle; $("welcomeText").textContent = T.welcomeText; $("pickFilesLabel").textContent = T.pickFiles;
    $("saveState").textContent = saveFailed ? T.saveFail : savedAt ? T.saved + " " + savedAt.toLocaleTimeString() + " (" + T.localOnly + ")" : T.notSaved;
    $("saveState").classList.toggle("bad", saveFailed);
    if (!state) return;

    const next = Core.nextPick(state), clock = $("clock"); clock.textContent = "";
    const wrap = el("div", undefined, "clock");
    if (next) {
      const team = Core.teamById(state, next.team_id);
      const left = el("div"); left.appendChild(el("div", T.onClock, "pickno")); left.appendChild(el("div", team ? team.team_name : next.team_id, "big"));
      wrap.appendChild(left); wrap.appendChild(el("div", T.pickNo + " " + next.overall_pick + " / " + state.order.length, "pickno"));
    } else wrap.appendChild(el("div", "✓ " + T.draftComplete, "done big"));
    clock.appendChild(wrap);
    if (flash) { clock.appendChild(el("p", flash, "note")); flash = ""; }

    $("controlsTitle").textContent = T.controls; $("controlsNote").textContent = T.controlsNote;
    $("undo").textContent = T.undo; $("exportCsv").textContent = T.exportCsv; $("exportJson").textContent = T.exportJson; $("audit").textContent = T.audit;
    $("importLabel").textContent = T.importLabel; $("reset").textContent = T.reset;
    $("undo").disabled = !Core.officialResults(state).length;

    $("availTitle").textContent = T.available; $("search").placeholder = T.search;
    const posSel = $("posFilter"), current = posSel.value, positions = [...new Set(state.players.map(p => p.position))].sort();
    posSel.textContent = ""; const all = el("option", T.allPos); all.value = ""; posSel.appendChild(all);
    for (const p of positions) { const o = el("option", p); o.value = p; posSel.appendChild(o); }
    posSel.value = positions.includes(current) ? current : "";
    renderAvailable(next);

    $("boardTitle").textContent = T.board;
    const table = $("board"); table.textContent = "";
    const head = el("tr"); T.cols.forEach(c => head.appendChild(el("th", c))); table.appendChild(head);
    const resultByPick = new Map(Core.officialResults(state).map(r => [r.overall_pick, r]));
    for (const o of state.order) {
      const r = resultByPick.get(o.overall_pick), tr = el("tr");
      if (next && next.overall_pick === o.overall_pick) tr.className = "current"; else if (!r) tr.className = "empty";
      const team = Core.teamById(state, o.team_id), pl = r ? Core.playerById(state, r.player_id) : null;
      tr.appendChild(el("td", String(o.overall_pick))); tr.appendChild(el("td", team ? team.team_name : o.team_id));
      tr.appendChild(el("td", pl ? pl.player_name : "—")); tr.appendChild(el("td", pl ? pl.position : ""));
      table.appendChild(tr);
    }
    $("teamsTitle").textContent = T.teams; const teamsBox = $("teams"); teamsBox.textContent = "";
    for (const t of state.teams) {
      const box = el("div", undefined, "team"); box.appendChild(el("h3", t.team_name)); const ol = el("ol");
      for (const e of Core.teamRoster(state, t.team_id)) ol.appendChild(el("li", e.player.player_name + " (" + e.player.position + ", #" + e.overall_pick + ")"));
      box.appendChild(ol); teamsBox.appendChild(box);
    }
  }
  function renderAvailable(next) {
    const q = $("search").value.trim().toLowerCase(), pos = $("posFilter").value, ul = $("available"); ul.textContent = "";
    const list = Core.availablePlayers(state).filter(p => (!pos || p.position === pos) && p.player_name.toLowerCase().includes(q));
    for (const p of list) {
      const li = el("li"), left = el("span"); left.appendChild(el("span", p.position, "pos")); left.appendChild(document.createTextNode(p.player_name));
      const b = el("button", T.pick); b.disabled = !next; b.addEventListener("click", () => doPick(p.player_id));
      li.appendChild(left); li.appendChild(b); ul.appendChild(li);
    }
    $("availEmpty").hidden = list.length > 0; $("availEmpty").textContent = T.none;
  }

  // ----------------------------------------------------------------- start
  async function start(afterReset) {
    if (!afterReset) { const saved = loadSaved(); if (saved) { state = saved; render(); return; } }
    if (location.protocol === "file:") { render(); return; } // browsers block fetch() on file:// — show the file picker
    try { const r = await loadFromDataFolder(); if (!applyLoaded(r, false)) render(); }
    catch (e) { showProblems([{ code: "E_LOAD", file: "data/", line: "", value: "", message: T.loadFail }], []); render(); }
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("undo").addEventListener("click", doUndo);
    $("exportCsv").addEventListener("click", () => download("draft_results.csv", Core.resultsToCSV(state), "text/csv"));
    $("exportJson").addEventListener("click", () => download("draft-backup.json", JSON.stringify({ version: 1, savedAt: new Date().toISOString(), state }, null, 2), "application/json"));
    $("audit").addEventListener("click", () => { const e = Core.audit(state); showProblems(e, []); if (!e.length) { flash = T.auditOk; render(); } });
    $("reset").addEventListener("click", doReset);
    $("importFiles").addEventListener("change", (ev) => { importFiles(ev.target.files); ev.target.value = ""; });
    $("welcomeFiles").addEventListener("change", (ev) => { importFiles(ev.target.files); ev.target.value = ""; });
    $("search").addEventListener("input", () => state && renderAvailable(Core.nextPick(state)));
    $("posFilter").addEventListener("change", () => state && renderAvailable(Core.nextPick(state)));
    start(false);
  });
  window.__draft = { importFiles, getState: () => state, doPick, doUndo }; // handy for testing
})();
