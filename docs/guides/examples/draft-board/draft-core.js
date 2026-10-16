/* draft-core.js — the rules of the draft board, with no screen code.
   Plain JavaScript, no libraries. Works in a browser (window.DraftCore) and in Node (module.exports) so it can be tested.

   Everything here is fictional example logic. The real tournament's rules (order, trades, clock...) are decided by the
   organizer and change draft_order.csv and this file, not the guide. */
(function (root) {
  "use strict";

  // ------------------------------------------------------------------ CSV
  // A real CSV parser: quoted fields, commas and line breaks inside quotes, "" for a quote, CRLF/LF, UTF-8 BOM.
  // (Splitting each line on commas breaks as soon as a name contains a comma.)
  function parseCSV(text) {
    text = String(text).replace(/^﻿/, "");
    const rows = [];
    let row = [], field = "", inQuotes = false, line = 1, rowLine = 1, sawQuoteInField = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (inQuotes) {
        if (c === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; } else { inQuotes = false; }
        } else { if (c === "\n") line++; field += c; }
      } else if (c === '"' && field === "" && !sawQuoteInField) {
        inQuotes = true; sawQuoteInField = true;
      } else if (c === ",") {
        row.push(field); field = ""; sawQuoteInField = false;
      } else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(field); field = ""; sawQuoteInField = false;
        rows.push({ cells: row, line: rowLine }); row = []; line++; rowLine = line;
      } else { field += c; }
    }
    if (inQuotes) return { rows: [], unterminated: true };
    if (field !== "" || row.length) { row.push(field); rows.push({ cells: row, line: rowLine }); }
    return { rows: rows.filter(r => r.cells.some(c => c.trim() !== "")), unterminated: false };
  }

  const SCHEMAS = {
    teams:   { file: "teams.csv",        required: ["team_id", "team_name"] },
    players: { file: "players.csv",      required: ["player_id", "player_name", "position", "eligibility_status"] },
    order:   { file: "draft_order.csv",  required: ["overall_pick", "team_id"] },
    results: { file: "draft_results.csv", required: ["overall_pick", "player_id", "status"] }
  };
  const ELIGIBILITY = ["eligible", "ineligible"];
  const RESULT_STATUS = ["official", "void"];

  // Read one table. Returns { records:[{col:value, _line:n}], errors:[...], warnings:[...] }.
  function readTable(kind, text) {
    const schema = SCHEMAS[kind], file = schema.file, errors = [], warnings = [];
    const parsed = parseCSV(text);
    if (parsed.unterminated) { errors.push(err("E_CSV", file, 1, "A quoted value is never closed (missing closing quote).")); return { records: [], errors, warnings }; }
    if (!parsed.rows.length) { errors.push(err("E_EMPTY", file, 1, "The file is empty.")); return { records: [], errors, warnings }; }
    const header = parsed.rows[0].cells.map(h => h.trim().toLowerCase());
    const missing = schema.required.filter(h => !header.includes(h));
    if (missing.length) { errors.push(err("E_HEADER", file, 1, "Missing column(s): " + missing.join(", ") + ". Expected: " + schema.required.join(", "))); return { records: [], errors, warnings }; }
    const extra = header.filter(h => !schema.required.includes(h));
    if (extra.length) warnings.push(err("W_EXTRA", file, 1, "Extra column(s) ignored: " + extra.join(", ")));
    const records = [];
    for (const r of parsed.rows.slice(1)) {
      if (r.cells.length !== header.length) { errors.push(err("E_COLUMNS", file, r.line, "Expected " + header.length + " values but found " + r.cells.length + ".")); continue; }
      const rec = { _line: r.line };
      header.forEach((h, i) => { if (schema.required.includes(h)) rec[h] = r.cells[i].trim(); });
      for (const col of schema.required) {
        if (rec[col] === "") errors.push(err("E_MISSING", file, r.line, "Empty value in column '" + col + "'."));
      }
      records.push(rec);
    }
    return { records, errors, warnings };
  }

  function err(code, file, line, message, value) { return { code, file, line, message, value: value === undefined ? "" : value }; }

  // ----------------------------------------------------------- validation
  // Check a whole dataset BEFORE it replaces anything. Never "fixes" data; it only reports.
  // input: { teams, players, order, results } as arrays of records (results may be empty).
  function validateDataset(input) {
    const errors = [], warnings = [];
    const E = (code, file, rec, msg, value) => errors.push(err(code, file, rec._line, msg, value));

    const teamIds = new Set();
    for (const t of input.teams) {
      if (!t.team_id) continue;
      if (teamIds.has(t.team_id)) E("E_DUP_ID", "teams.csv", t, "Duplicate team_id '" + t.team_id + "'.", t.team_id);
      teamIds.add(t.team_id);
    }
    const players = new Map();
    for (const p of input.players) {
      if (!p.player_id) continue;
      if (players.has(p.player_id)) E("E_DUP_ID", "players.csv", p, "Duplicate player_id '" + p.player_id + "'.", p.player_id);
      players.set(p.player_id, p);
      if (p.eligibility_status && !ELIGIBILITY.includes(p.eligibility_status))
        E("E_VALUE", "players.csv", p, "eligibility_status must be one of: " + ELIGIBILITY.join(", ") + " (found '" + p.eligibility_status + "').", p.eligibility_status);
    }
    const orderPicks = new Map();
    for (const o of input.order) {
      const n = Number(o.overall_pick);
      if (o.overall_pick && (!Number.isInteger(n) || n < 1)) { E("E_NUMBER", "draft_order.csv", o, "overall_pick must be a whole number 1 or higher (found '" + o.overall_pick + "').", o.overall_pick); continue; }
      if (!o.overall_pick) continue;
      if (orderPicks.has(n)) E("E_DUP_PICK", "draft_order.csv", o, "Duplicate overall_pick " + n + ".", n);
      orderPicks.set(n, o);
      if (o.team_id && !teamIds.has(o.team_id)) E("E_UNKNOWN_REF", "draft_order.csv", o, "team_id '" + o.team_id + "' is not in teams.csv.", o.team_id);
    }
    const numbers = [...orderPicks.keys()].sort((a, b) => a - b);
    numbers.forEach((n, i) => { if (n !== i + 1 && !errors.some(e => e.code === "E_GAP")) errors.push(err("E_GAP", "draft_order.csv", 0, "overall_pick must run 1, 2, 3... without gaps (found " + n + " where " + (i + 1) + " was expected).", n)); });

    const seenPick = new Map(), seenPlayer = new Map();
    for (const r of input.results) {
      const n = Number(r.overall_pick);
      if (r.overall_pick && (!Number.isInteger(n) || n < 1)) { E("E_NUMBER", "draft_results.csv", r, "overall_pick must be a whole number (found '" + r.overall_pick + "').", r.overall_pick); continue; }
      if (r.status && !RESULT_STATUS.includes(r.status)) { E("E_VALUE", "draft_results.csv", r, "status must be one of: " + RESULT_STATUS.join(", ") + " (found '" + r.status + "').", r.status); continue; }
      if (r.overall_pick && !orderPicks.has(n)) E("E_UNKNOWN_REF", "draft_results.csv", r, "overall_pick " + n + " is not in draft_order.csv.", n);
      const p = players.get(r.player_id);
      if (r.player_id && !p) E("E_UNKNOWN_REF", "draft_results.csv", r, "player_id '" + r.player_id + "' is not in players.csv.", r.player_id);
      if (r.status !== "official") continue; // void rows are history only
      if (seenPick.has(n)) E("E_DUP_PICK", "draft_results.csv", r, "Pick " + n + " has two official results (first on line " + seenPick.get(n) + ").", n);
      seenPick.set(n, r._line);
      if (r.player_id) {
        if (seenPlayer.has(r.player_id)) E("E_DUP_PLAYER", "draft_results.csv", r, "Player '" + r.player_id + "' is picked twice (first on line " + seenPlayer.get(r.player_id) + ").", r.player_id);
        seenPlayer.set(r.player_id, r._line);
        if (p && p.eligibility_status !== "eligible") E("E_INELIGIBLE", "draft_results.csv", r, "Player '" + r.player_id + "' is not eligible.", r.player_id);
      }
    }
    const official = [...seenPick.keys()].sort((a, b) => a - b);
    official.forEach((n, i) => { if (n !== i + 1 && !errors.some(e => e.code === "E_OUT_OF_ORDER")) errors.push(err("E_OUT_OF_ORDER", "draft_results.csv", 0, "Picks must be recorded in order: pick " + n + " is recorded but pick " + (i + 1) + " is not.", n)); });
    return { errors, warnings };
  }

  // Read the four CSV texts, validate everything, and return a clean state or the list of problems.
  // texts: { teams, players, order, results? }  (results optional = nothing picked yet)
  function loadDataset(texts) {
    const errors = [], warnings = [], tables = {};
    for (const kind of ["teams", "players", "order", "results"]) {
      if (kind === "results" && (texts.results === undefined || texts.results === null)) { tables.results = { records: [] }; continue; }
      if (texts[kind] === undefined || texts[kind] === null) { errors.push(err("E_NO_FILE", SCHEMAS[kind].file, 0, "File not provided.")); tables[kind] = { records: [] }; continue; }
      const t = readTable(kind, texts[kind]);
      tables[kind] = t; errors.push(...t.errors); warnings.push(...t.warnings);
    }
    if (errors.length) return { ok: false, errors, warnings };
    const v = validateDataset({ teams: tables.teams.records, players: tables.players.records, order: tables.order.records, results: tables.results.records });
    errors.push(...v.errors); warnings.push(...v.warnings);
    if (errors.length) return { ok: false, errors, warnings };
    return { ok: true, errors: [], warnings, state: {
      teams: tables.teams.records.map(t => ({ team_id: t.team_id, team_name: t.team_name })),
      players: tables.players.records.map(p => ({ player_id: p.player_id, player_name: p.player_name, position: p.position, eligibility_status: p.eligibility_status })),
      order: tables.order.records.map(o => ({ overall_pick: Number(o.overall_pick), team_id: o.team_id })).sort((a, b) => a.overall_pick - b.overall_pick),
      results: tables.results.records.map(r => ({ overall_pick: Number(r.overall_pick), player_id: r.player_id, status: r.status }))
    } };
  }

  // ----------------------------------------------------------------- state
  function officialResults(state) { return state.results.filter(r => r.status === "official").sort((a, b) => a.overall_pick - b.overall_pick); }
  function pickedIds(state) { return new Set(officialResults(state).map(r => r.player_id)); }
  function nextPick(state) { const done = new Set(officialResults(state).map(r => r.overall_pick)); return state.order.find(o => !done.has(o.overall_pick)) || null; }
  function availablePlayers(state) { const picked = pickedIds(state); return state.players.filter(p => p.eligibility_status === "eligible" && !picked.has(p.player_id)); }
  function playerById(state, id) { return state.players.find(p => p.player_id === id) || null; }
  function teamById(state, id) { return state.teams.find(t => t.team_id === id) || null; }
  function teamRoster(state, teamId) {
    const pickTeam = new Map(state.order.map(o => [o.overall_pick, o.team_id]));
    return officialResults(state).filter(r => pickTeam.get(r.overall_pick) === teamId).map(r => ({ overall_pick: r.overall_pick, player: playerById(state, r.player_id) }));
  }
  function clone(state) { return JSON.parse(JSON.stringify(state)); }

  // Record the next pick. Returns { ok, state } or { ok:false, code }. Never changes the input state.
  function recordPick(state, playerId) {
    const next = nextPick(state);
    if (!next) return { ok: false, code: "DRAFT_COMPLETE" };
    const p = playerById(state, playerId);
    if (!p) return { ok: false, code: "UNKNOWN_PLAYER" };
    if (p.eligibility_status !== "eligible") return { ok: false, code: "INELIGIBLE" };
    if (pickedIds(state).has(playerId)) return { ok: false, code: "ALREADY_PICKED" };
    const s = clone(state);
    s.results.push({ overall_pick: next.overall_pick, player_id: playerId, status: "official" });
    return { ok: true, state: s, pick: next.overall_pick };
  }

  // Undo = mark the latest official pick "void". The row stays as history; the player becomes available again.
  function undoLastPick(state) {
    const off = officialResults(state);
    if (!off.length) return { ok: false, code: "NOTHING_TO_UNDO" };
    const last = off[off.length - 1], s = clone(state);
    const row = s.results.find(r => r.status === "official" && r.overall_pick === last.overall_pick && r.player_id === last.player_id);
    row.status = "void";
    return { ok: true, state: s, pick: last.overall_pick, player_id: last.player_id };
  }

  // Re-check a live state (used as an audit button and after every change).
  function audit(state) {
    const v = validateDataset({ teams: state.teams.map((x, i) => ({ ...x, _line: i + 2 })), players: state.players.map((x, i) => ({ ...x, _line: i + 2 })),
      order: state.order.map((x, i) => ({ ...x, overall_pick: String(x.overall_pick), _line: i + 2 })),
      results: state.results.map((x, i) => ({ ...x, overall_pick: String(x.overall_pick), _line: i + 2 })) });
    return v.errors;
  }

  // ---------------------------------------------------------------- export
  function csvCell(v) { v = String(v); return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
  function resultsToCSV(state) {
    const rows = [["overall_pick", "player_id", "status"]].concat(
      state.results.slice().sort((a, b) => a.overall_pick - b.overall_pick || (a.status === "void" ? -1 : 1) - (b.status === "void" ? -1 : 1))
        .map(r => [r.overall_pick, r.player_id, r.status]));
    return rows.map(r => r.map(csvCell).join(",")).join("\n") + "\n";
  }

  const api = { parseCSV, readTable, validateDataset, loadDataset, officialResults, nextPick, availablePlayers, playerById, teamById,
    teamRoster, recordPick, undoLastPick, audit, resultsToCSV, SCHEMAS };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.DraftCore = api;
})(typeof window !== "undefined" ? window : globalThis);
