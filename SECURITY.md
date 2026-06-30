# Security Policy

## Supported Versions

The latest released version receives security updates.

| Version | Supported |
| ------- | --------- |
| 1.0.x   | ✅        |

## Reporting a Vulnerability

This tool handles AWS credentials and 1Password data, so security reports
are taken seriously.

**Do not open a public issue for security vulnerabilities.**

Instead, report privately via GitHub's
[private vulnerability reporting](https://github.com/nguyenquangkhai/aws-credential-manage/security/advisories/new),
or email the maintainer at khai.nguyenquang27@gmail.com.

Please include:

- A description of the vulnerability and its impact.
- Steps to reproduce.
- Any suggested remediation.

You can expect an initial response within 7 days. Once the issue is
confirmed, a fix and disclosure timeline will be coordinated with you.

## Handling of Credentials

- Access keys are stored only in `~/.aws/credentials`, never in 1Password.
- Passwords are generated with the `secrets` module (a CSPRNG).
- Secrets are never logged or printed in error messages.
- Credential files are backed up before destructive operations, with
  rollback on failure.
