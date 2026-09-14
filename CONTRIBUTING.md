# Contribution workflow

1. Create a feature branch from `main`.
2. Keep changes synthetic and independent of corporate services.
3. Run `python -m unittest discover -v`; include browser checks when changing UI behavior.
4. Open a pull request describing the change, test evidence, and data/security boundaries.
5. Review the diff and wait for GitHub Actions to pass before merging.

Do not commit `.demo-data`, local logs, credentials, personal account details, copied business records, proprietary adapters, or internal screenshots. Examples must be invented, not anonymized source exports. Never imply formal business approval when only a code-defined metric exists.

Repository permissions, required reviews, and branch protection are separate GitHub settings; the presence of this document does not mean they are enforced.
