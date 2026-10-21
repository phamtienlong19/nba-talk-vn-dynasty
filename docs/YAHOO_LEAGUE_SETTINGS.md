# Yahoo league settings (relevant to the tool)

Source: the league's Yahoo "Scoring & Settings" page, pasted by the owner on 2026-10-21 (league 85092, publicly viewable).
Only settings the tool depends on are kept; `config/trade_rules.json` (`yahoo`) carries the numbers.

| Setting | Value | Used for |
|---|---|---|
| Roster positions | PG, SG, G, SF, PF, F, C, FC, Util, BN x3, IL x3 | 15 spots; 12 outside IL (9 + 3), 3 IL slots (trade checker slot rules) |
| Trade End Date | February 18, 2027 | deadline rule; Trade Tank cutoff = 2 weeks earlier (Feb 4) |
| Allow Draft Pick Trades | Yes | pick moves in the Trade Machine |
| Trade Review / Reject Time | Commissioner / 2 days | pending-period note |
| Max Trades / Max Acquisitions | none / 7 per week (adds) | not enforced here |
| Playoffs | 8 teams, weeks 18-20 (ends Mar 21, 2027) | future Trade Tank eligibility (weeks to playoffs) |
| IL from waivers / FA | injured players may be added straight to IL | free-agent adds, not trades |
| Can't Cut List | Yahoo Sports | mirrors the drop rule (20+ never, 10-19 review) |

Peculiarity the Trade Machine models: players received in a trade never land on IL (they arrive in the lineup / bench), and only
injured players (Yahoo status Out / INJ / OFS / Doubtful ...) can be moved to IL, so a team at 12 players outside IL cannot take a
player without a drop or an IL move first, even if it has an open IL slot.
