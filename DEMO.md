# Three-minute walkthrough

1. Start `python app.py` and open the local URL. Point out the **synthetic-only** banner and absence of sign-in or external service dependencies.
2. Run the normal scenario. Explain the collection → validation → ingestion → success events. The timestamp describes a synthetic fixture, not real-time company data.
3. Filter one region. Compare the displayed count with its detail rows, then expand the weighted completion evidence to inspect its numerator and denominator.
4. Run the authentication-failure scenario. The current analysis disappears; the failure is recorded. Only the explicit history button can reopen the previous successful batch, labeled as historical.
5. Repeat with validation and storage failures. Explain that invalid data is rejected and the simulated storage exception rolls back snapshot publication.
6. Run the empty scenario. The result is successful with zero rows and no completion percentage. It does not reuse the previous dataset.
7. Run normal again, select a department, and export the scoped synthetic CSV. Close with the distinction between implemented metric definitions and an approved business policy.

## Talking points

- Scope before aggregation: no cross-snapshot accumulation, overlapping-stage sum, or average of percentages.
- Traceability before recommendations: formulas and source identity are visible; causal and overdue claims are out of scope.
- Failure transparency before convenience: a historical success does not mean the current refresh succeeded.
- Privacy by separation: the public demo has its own source-only repository and no original private Git history.

## Optional browser regression

With the app running and Playwright installed in your development environment:

```sh
node smoke-browser.mjs
```

The script exercises only synthetic scenarios. `PLAYWRIGHT_MODULE` can point to an existing Playwright installation; `DEMO_BROWSER_CHANNEL` can select an installed browser such as `msedge`. These are optional development dependencies, not needed to run the demo or its Python CI tests.
