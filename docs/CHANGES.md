# Standalone 5G Testbed Modifications

This directory contains records of all custom modifications and extensions made to the Standalone 5G SA network simulator components.

## Modification Index

Each custom change has its own markdown file detailing the goal, code changes, and verification instructions under the `changes/` subdirectory.

| ID | Date | Document | Summary |
| :--- | :--- | :--- | :--- |
| **01** | 2026-06-19 | [01-layer-logging.md](changes/01-layer-logging.md) | Separated gNB protocol layer logs (PDCP, RLC, MAC, PHY) into their own individual files. |

---

## How to Add New Changes
If you introduce additional custom changes or features to this repository:
1. Create a new markdown file inside the `docs/changes/` directory using the naming convention `XX-description.md` (e.g., `02-my-new-feature.md`).
2. Document the goal, the specific files modified, and the validation tests.
3. Add a new row to the table above in this file (`CHANGES.md`).
