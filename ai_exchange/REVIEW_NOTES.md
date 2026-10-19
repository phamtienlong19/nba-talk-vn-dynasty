## Issues

- `rosters/team_map.json` maps all 16 Yahoo team ids to franchises (name prefix + every Yahoo-listed player on that team belongs to that franchise). Please confirm.
- First Yahoo import committed (RS-2026-10-19-878cd6e3): 18 players added, 3 dropped (Risacher, Will Riley, Santi Aldama); payroll unchanged everywhere. Jayden Quaintance recorded at $0 under the owner's 2026-10-19 rule.
- The 6 provisional rookies are still provisional (Yahoo ids appear as link candidates); not linked.
- Yahoo's keeper-salary label for RJ Barrett is 5; the frozen salary is 0. Not changed.

- Team names now follow Yahoo (2026-10-19, `rosters/team_map.json` `name`): e.g. Bsy → Bulls Dynasty, sup fam → Crashed for Caleb, CrazyCat → Damageeeee, Maxfixe → Maxfixe, LC → Long con dynasty. The locked keeper freeze and franchises.json keep the old names as history.

## Decisions Required

- Whether to link the 6 provisional rookies to their Yahoo ids (`import_rosters.py link-provisional`).
