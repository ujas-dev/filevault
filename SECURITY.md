# 🔒 Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| v5.x | ✅ Active |
| v4.x | 🔧 Critical fixes only |
| < v4  | ❌ No longer supported |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: `security@your-email.com`  
Or use [GitHub Private Vulnerability Reporting](../../security/advisories/new).

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

We will respond within 72 hours and aim to release a patch within 14 days.

## Security Notes

- FileVault's secure shred uses DoD 5220.22-M (multi-pass overwrite + rename + delete).
- On SSDs, overwrite-based shredding cannot guarantee data erasure at the hardware level due to wear-leveling. Use full-disk encryption for maximum security on SSDs.
- The copy integrity gate (BLAKE3/SHA-256 hash comparison) is designed to prevent data loss — not as a cryptographic security primitive.
