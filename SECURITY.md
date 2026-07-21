# Security Policy

## Supported Versions

This is a portfolio/reference project, not a maintained production service. The `main` branch is the only version that receives fixes.

## Reporting a Vulnerability

This project processes local CSV files only and does not expose any network service, API, or credentials by default. If you identify a security concern (e.g. in dependency versions, or in how configuration/secrets would be handled if this pipeline were adapted for production use), please open a GitHub issue describing the concern, or contact the maintainer directly if the issue involves sensitive details.

## Scope Notes

- This project does not process authentication credentials, API keys, or personally identifiable information (PII) in its current form. If adapting this pipeline for a real deployment with sensitive data, review `config/config.yaml` for any values that should move to environment variables or a secrets manager instead of plain YAML.
- Dependency versions are pinned in `requirements.txt` / `requirements-dev.txt`. Run `pip list --outdated` periodically and update pinned versions to pick up upstream security patches.
