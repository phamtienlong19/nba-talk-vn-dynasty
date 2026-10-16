# Intentionally broken example files

Use these to see the importer refuse bad data. Each file has a problem on purpose:

| File | Problem it demonstrates |
|---|---|
| `players_duplicate_id.csv` | Two players share `P05` (matching on names alone would hide this) |
| `players_missing_column.csv` | The `eligibility_status` column is missing |
| `results_duplicate_player.csv` | `P03` is picked twice |
| `results_unknown_player.csv` | `P99` is not in `players.csv` |
| `results_out_of_order.csv` | Pick 3 is recorded but pick 2 is not |
| `players_quoted_names.csv` | **Valid.** Names with commas and quotes. Splitting lines on commas would break it |

Import them together with the good files from `../data/` (replace only the one you want to test).
