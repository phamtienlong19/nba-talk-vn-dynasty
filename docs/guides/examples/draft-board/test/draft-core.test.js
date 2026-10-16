// Run with:  node --test test/        (Node 18 or newer). Not needed to use the board — this checks the rules.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const C = require("../draft-core.js");

const read = (f) => fs.readFileSync(path.join(__dirname, "..", f), "utf8");
const good = () => ({ teams: read("data/teams.csv"), players: read("data/players.csv"), order: read("data/draft_order.csv"), results: read("data/draft_results.csv") });
const load = (over = {}) => C.loadDataset({ ...good(), ...over });
const codes = (r) => r.errors.map((e) => e.code);

test("sample data loads: 4 teams, 12 players, 12 picks, 8 selections", () => {
  const r = load();
  assert.equal(r.ok, true, JSON.stringify(r.errors));
  assert.deepEqual([r.state.teams.length, r.state.players.length, r.state.order.length, C.officialResults(r.state).length], [4, 12, 12, 8]);
  assert.equal(C.nextPick(r.state).overall_pick, 9);
  assert.deepEqual(C.availablePlayers(r.state).map((p) => p.player_id), ["P08", "P10", "P11", "P12"]);
});

test("CSV parser: quotes, commas, doubled quotes, line breaks, CRLF and BOM", () => {
  const r = C.loadDataset({ ...good(), players: "﻿" + read("data-invalid/players_quoted_names.csv").replace(/\n/g, "\r\n") , results: "" });
  // results: "" is an empty file -> error; use null to mean "no results yet"
  assert.ok(codes(r).includes("E_EMPTY"));
  const ok = C.loadDataset({ ...good(), players: "﻿" + read("data-invalid/players_quoted_names.csv"), results: null });
  assert.equal(ok.ok, true, JSON.stringify(ok.errors));
  assert.deepEqual(ok.state.players.map((p) => p.player_name), ["Trần, Minh Khoa", 'Gia Bảo "Voi" Nguyễn', "Tên\nhai dòng"]);
  const crlf = C.parseCSV("a,b\r\n1,\"x,y\"\r\n");
  assert.deepEqual(crlf.rows.map((x) => x.cells), [["a", "b"], ["1", "x,y"]]);
});

test("unterminated quote is reported, not guessed", () => {
  const r = load({ players: 'player_id,player_name,position,eligibility_status\nP01,"Bad,G,eligible\n' });
  assert.deepEqual(codes(r), ["E_CSV"]);
});

test("validation: header, columns, empty values", () => {
  assert.ok(codes(load({ players: read("data-invalid/players_missing_column.csv") })).includes("E_HEADER"));
  assert.ok(codes(load({ players: "player_id,player_name,position,eligibility_status\nP01,Minh Khoa,G\n" })).includes("E_COLUMNS"));
  assert.ok(codes(load({ players: "player_id,player_name,position,eligibility_status\nP01,,G,eligible\n" })).includes("E_MISSING"));
});

test("validation: duplicate ids, unknown references, ineligible, bad status", () => {
  assert.ok(codes(load({ players: read("data-invalid/players_duplicate_id.csv"), results: null })).includes("E_DUP_ID"));
  const dup = load({ results: read("data-invalid/results_duplicate_player.csv") });
  assert.ok(codes(dup).includes("E_DUP_PLAYER"));
  assert.equal(dup.errors.find((e) => e.code === "E_DUP_PLAYER").line, 3); // file line number, header = line 1
  assert.ok(codes(load({ results: read("data-invalid/results_unknown_player.csv") })).includes("E_UNKNOWN_REF"));
  assert.ok(codes(load({ results: read("data-invalid/results_out_of_order.csv") })).includes("E_OUT_OF_ORDER"));
  assert.ok(codes(load({ results: "overall_pick,player_id,status\n1,P03,maybe\n" })).includes("E_VALUE"));
  const inel = read("data/players.csv").replace("P03,Tuấn Kiệt,C,eligible", "P03,Tuấn Kiệt,C,ineligible");
  assert.ok(codes(load({ players: inel })).includes("E_INELIGIBLE"));
  assert.ok(codes(load({ order: "overall_pick,team_id\n1,T1\n2,T9\n" })).includes("E_UNKNOWN_REF"));
  assert.ok(codes(load({ order: "overall_pick,team_id\n1,T1\n1,T2\n" })).includes("E_DUP_PICK"));
  assert.ok(codes(load({ order: "overall_pick,team_id\n1,T1\n3,T2\n" })).includes("E_GAP"));
  assert.ok(codes(load({ order: "overall_pick,team_id\nfirst,T1\n" })).includes("E_NUMBER"));
});

test("a bad import changes nothing: loadDataset returns no state", () => {
  const r = load({ results: read("data-invalid/results_duplicate_player.csv") });
  assert.equal(r.ok, false);
  assert.equal(r.state, undefined);
});

test("recordPick: next team picks, duplicates and ineligible players are refused, input never mutated", () => {
  const s = load().state, before = JSON.stringify(s);
  const a = C.recordPick(s, "P08");
  assert.equal(a.ok, true);
  assert.equal(a.pick, 9);
  assert.equal(JSON.stringify(s), before);
  assert.equal(C.recordPick(a.state, "P08").code, "ALREADY_PICKED");
  assert.equal(C.recordPick(s, "P03").code, "ALREADY_PICKED");
  assert.equal(C.recordPick(s, "P99").code, "UNKNOWN_PLAYER");
  let cur = s;
  for (const id of ["P08", "P10", "P11", "P12"]) cur = C.recordPick(cur, id).state;
  assert.equal(C.nextPick(cur), null);
  assert.equal(C.recordPick(cur, "P01").code, "DRAFT_COMPLETE");
  assert.deepEqual(C.audit(cur), []);
});

test("undo voids the last pick, keeps history, frees the player, and pick can be redone", () => {
  let s = load().state;
  s = C.recordPick(s, "P08").state;
  const u = C.undoLastPick(s);
  assert.equal(u.ok, true);
  assert.equal(u.player_id, "P08");
  assert.equal(C.nextPick(u.state).overall_pick, 9);
  assert.ok(C.availablePlayers(u.state).some((p) => p.player_id === "P08"));
  assert.equal(u.state.results.filter((r) => r.overall_pick === 9).length, 1); // the voided row is kept
  const again = C.recordPick(u.state, "P10");
  assert.equal(again.ok, true);
  assert.deepEqual(C.audit(again.state), []);
  assert.equal(C.undoLastPick({ ...s, results: [] }).code, "NOTHING_TO_UNDO");
});

test("export round-trips: exported results re-import to the same state, void rows included", () => {
  let s = load().state;
  s = C.recordPick(s, "P08").state;
  s = C.undoLastPick(s).state;
  s = C.recordPick(s, "P10").state;
  const csv = C.resultsToCSV(s);
  assert.match(csv, /^overall_pick,player_id,status\n/);
  assert.match(csv, /9,P08,void\n9,P10,official\n/);
  const back = load({ results: csv });
  assert.equal(back.ok, true, JSON.stringify(back.errors));
  assert.deepEqual(C.officialResults(back.state), C.officialResults(s));
});

test("team rosters follow the draft order (snake order in the sample)", () => {
  const s = load().state;
  const r = (t) => C.teamRoster(s, t).map((x) => x.player.player_id + "@" + x.overall_pick);
  assert.deepEqual(r("T1"), ["P03@1", "P07@8"]);
  assert.deepEqual(r("T4"), ["P06@4", "P04@5"]);
});
