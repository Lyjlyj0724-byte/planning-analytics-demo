# Planning Analytics Lab

A production and supply chain planning portfolio project focused on operational visibility, lean improvement thinking, and data automation. It turns synthetic planning snapshots into scoped work-in-progress indicators, traceable calculations, and transparent refresh records—helping demonstrate how a planner can make follow-up more structured without overstating what the data proves.

**Synthetic data only. No company account, private API, external model, or database service is required.** The demo interface is in Chinese; this README explains its design and limitations in English.

## Why this project

Operational dashboards need more than charts: users need to know what was queried, how a metric was calculated, whether a refresh actually succeeded, and what the data cannot prove. This project demonstrates that complete reasoning path in a small, reproducible application.

## Relevance to production planning and continuous improvement

- **Planning visibility:** compare unfinished counts across material-preparation stages and inspect the selected region/team's underlying records.
- **Structured follow-up:** make calculation scope and exceptions explicit before discussing actions with operations teams.
- **Lean improvement discipline:** establish consistent definitions, separate observed conditions from assumed root causes, and make abnormal refresh states visible. This is a foundation for an improvement discussion, not proof of a bottleneck or completed kaizen project.
- **Data automation:** replace an opaque refresh with reproducible generation, validation, snapshot publication, and evidence. The public demo simulates collection; it does not claim to replace a real production workflow.

This project does not measure inventory reduction, lead-time savings, on-time delivery, OEE, or financial impact. Such results require real baselines, approved definitions, and follow-up validation that synthetic data cannot provide.

## Quick start

Requires Python 3.11 or newer. No third-party runtime packages.

```sh
python app.py
```

Open [the local demo](http://127.0.0.1:8780). Choose **正常采集** (successful collection), then click **运行合成刷新** (run synthetic refresh). Windows users can also double-click `start-demo.cmd` if Python is on PATH.

```sh
python -m unittest discover -v
```

Run with `python app.py --port 8781` if the default port is occupied. Stop with Ctrl+C. Generated demo state is kept in `.demo-data/demo.sqlite`, which is excluded from Git.

## What to explore

1. **Scoped analytics:** inspect three separate unfinished-stage counts and a weighted completion rate; filter by region and department.
2. **Traceable evidence:** expand metric definitions to inspect formulas, denominators, record counts, snapshot identity, and the synthetic source timestamp.
3. **Failure transparency:** simulate expired authentication, invalid data, and a storage failure. A failed refresh never silently substitutes the previous successful snapshot.
4. **Empty-result handling:** an empty successful response creates a new empty batch; its completion rate is undefined, not zero or a stale value.
5. **Explicit historical access:** open the previous successful batch through a separate, clearly labeled history action.
6. **Scoped export:** export the selected records as CSV with synthetic provenance; a local audit entry records the batch and filters.

## Design

```text
Browser → loopback HTTP API → synthetic collection → validation
                                  ↓                    ↓
                             refresh ledger ← atomic snapshot commit
                                                       ↓
                                      scoped metrics → evidence → CSV
```

- **Python standard library:** deterministic generation, integer validation, Decimal-based percentages, HTTP API, and tests.
- **SQLite:** immutable batch identifiers, refresh stage events, persistent success/failure states, and export records.
- **Vanilla JavaScript/CSS:** responsive dashboard, safe text rendering, filters, and explicit provenance.
- **GitHub Actions:** automated tests on multiple Python versions for pull requests and main-branch pushes.

The completion rate is `100 × sum(completed) / sum(total)`, not an average of row-level percentages. Stage counts may overlap and must not be added together. Source rows are not unique contracts. Filters change the denominator. Multiple snapshots are never accumulated into one KPI.

## Privacy and honest boundaries

Every record, label, and number is generated from code. The fixed synthetic source timestamp is intentionally different from the actual refresh-request timestamp. No internal source exports, credentials, proprietary client libraries, or original development Git history belong in this repository.

This standalone demo **simulates orchestration locally**. It does not claim to connect to n8n, Metabase, or a live operational system. It showcases the failure semantics and analysis workflow without requiring those integrations. It also does not include a formal business knowledge base: metric definitions are explicitly pending business-owner review; follow-up suggestions are not policy requirements.

The server binds only to `127.0.0.1` and validates Host, Origin, and a per-process CSRF token for refresh requests. Only explicit static/API paths are served. These are local-demo safeguards, **not production multi-user authentication, row-level authorization, a tamper-proof audit system, or a complete security assessment**. Do not expose the server directly to a LAN or the internet. Storage-failure injection tests transaction rollback; it is not a full disk-outage test. A workflow refresh is synchronous and deliberately small; this is not a production scheduler.

## Portfolio evidence

The repository demonstrates translating operational questions into verifiable metric definitions, designing trustworthy failure states, separating data facts from unsupported business judgments, and shipping a testable local application. Features are described at the level implemented here; no business-impact claims are inferred from synthetic data.

**Short portfolio introduction:**

> Built a local-first planning analytics demo to showcase the intersection of production and supply chain planning, continuous improvement, and data automation. Implemented scoped unfinished-stage indicators, weighted completion metrics, traceable calculation evidence, and explicit refresh-failure handling using Python, SQLite, and a responsive web interface. Designed the public demo around fully synthetic data, with no company credentials or proprietary system dependencies.

See [the demo walkthrough](DEMO.md) and [the contribution workflow](CONTRIBUTING.md).
