# Security Policy

## Supported Versions

Only the latest release of the `l3a0` plugin is supported. Update with
`claude plugin update l3a0@l3a0` before reporting an issue.

| Version | Supported |
| ------- | --------- |
| 0.2.x (latest) | ✅ |
| < 0.2 | ❌ |

## Reporting a Vulnerability

Please report vulnerabilities privately via
[GitHub's private vulnerability reporting](https://github.com/l3a0/claude-plugins/security/advisories/new)
for this repository. If that page is unavailable, open a
[GitHub issue](https://github.com/l3a0/claude-plugins/issues/new) asking for a
private contact channel — do not include exploit details in the public issue.

You can expect an acknowledgement within a week. Please allow a fix to land
before public disclosure.

## Scope

The skills in this repo run locally and drive the user's own logged-in
browser session and local app data (see each skill's README/SKILL.md for its
exact access). Reports of particular interest:

- Anything that could exfiltrate highlight data or credentials off-machine
  (the pipeline is designed to be local-only; the capture receiver binds
  `127.0.0.1` and validates paths).
- Path injection or command injection via scraped page content or filenames.
- Prompt-injection vectors in skill instructions that could cause unintended
  actions.
