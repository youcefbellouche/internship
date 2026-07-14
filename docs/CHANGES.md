# Standalone 5G Testbed Modifications

This directory contains records of all custom modifications and extensions made to the Standalone 5G SA network simulator components.

## Modification Index

Each custom change has its own markdown file detailing the goal, code changes, and verification instructions under the `changes/` subdirectory.

| ID | Date | Document | Summary |
| :--- | :--- | :--- | :--- |
| **00** | 2026-06-16 | [00-multi-connectivity-ntn.md](changes/00-multi-connectivity-ntn.md) | Documented analysis of why multi-connectivity (MR-DC) and Non-Terrestrial Networks (NTN) are not implemented. |
| **01** | 2026-06-19 | [01-layer-logging.md](changes/01-layer-logging.md) | Separated gNB and UE protocol layer logs (PDCP, RLC, MAC, PHY) into their own individual files. |
| **02** | 2026-06-22 | [02-pdcp-reordering-tests.md](changes/02-pdcp-reordering-tests.md) | Implemented and verified custom tests for duplicate discarding, reordering timers, and middle server. |
| **03** | 2026-06-23 | [README.md](phase-2-test/README.md) | Generated execution logs for PDCP RX tests and analyzed results, duplicate logging, and async logger buffering artifacts. |
| **04** | 2026-07-13 | [04-monolithic-dual-path-ue-stack.md](changes/04-monolithic-dual-path-ue-stack.md) | Implemented dual DUs attached to a single CU and a monolithic single-process dual-path UE stack (1 shared PDCP, 2 RLC/MAC/PHY paths linked via C++ pointers). |
| **05** | 2026-07-14 | [05-dynamic-split-policy.md](changes/05-dynamic-split-policy.md) | Implemented congestion-aware dynamic split bearer policy at UE PDCP and verified E2E user-plane ping with Open5GS and dual DUs. |




---

## How to Add New Changes
If you introduce additional custom changes or features to this repository:
1. Create a new markdown file inside the `docs/changes/` directory using the naming convention `XX-description.md` (e.g., `02-my-new-feature.md`).
2. Document the goal, the specific files modified, and the validation tests.
3. Add a new row to the table above in this file (`CHANGES.md`).
