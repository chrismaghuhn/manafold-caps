# Manafold CAP miner

This small exploratory repository measures whether public Scryfall, Forge, and XMage datasets can supply auditable evidence for a future capability/requirement census.

It is not part of the Manafold engine, does not define the CAP ontology, and does not decide Magic rules. Forge and XMage are implementation witnesses and may contain errors; Oracle text is card-specific source input. This experiment does not yet load the Comprehensive Rules or official rulings.

## Install and run

Requires Python 3.12 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe src\cap_miner.py all
```

The CLI also supports `download`, `inspect`, `mine`, and `report`. `all` downloads or reuses the Hugging Face cache, inventories schemas, mines evidence, and writes the report.

## Data sources

- `nishtahir/scryfall-oracle-cards`
- `404NotF0und/MtG-json-to-ForgeScript`
- `Frogski/xMageData`

The datasets are third-party snapshots and can have stale text, malformed records, or implementation mistakes. The miner pins the Phase 0.1.0 dataset revisions; any current Hub-head difference is recorded without silently changing the inputs. Revisions and observed schemas are in `REPORT.md` and `data/output/inventory.json`.

## Outputs

Generated files go under ignored `data/output/`: inventory, vocabulary CSVs, matching samples, requirement candidates/statistics, mapping coverage, unmapped token lists, the Oracle mismatch audit, and the suspicious-join audit. Hugging Face cache files go under ignored `data/raw/`. Generated data is not committed.

The 0.1.2 suspicious-join review decisions are recorded in `reviewed_join_decisions.yaml`; the concise human audit is `JOIN_AUDIT.md`. Review flags concern identity/source quality only and do not validate requirement semantics.

Requirement candidates separate extraction, implementation evidence, rules evidence, and review state. Agreement between Forge and XMage means corroboration only; it does not establish semantic correctness.
