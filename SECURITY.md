# 🔒 Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| v4.x | ✅ Active — current stable |
| v3.x | 🔧 Critical fixes only |
| < v3  | ❌ No longer supported |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Use [GitHub Private Vulnerability Reporting](../../security/advisories/new) to report privately and securely.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

We will respond within 72 hours and aim to release a patch within 14 days.
Once the fix is released, the vulnerability will be publicly disclosed in the relevant GitHub Security Advisory.

## Security Notes

- FileVault's secure shred implements DoD 5220.22-M (multi-pass overwrite + ghost rename + delete).
- **SSD Warning:** Overwrite-based shredding cannot guarantee data erasure on SSDs due to hardware-level wear-leveling and over-provisioning. For maximum security on SSDs, use full-disk encryption (e.g. BitLocker, LUKS, FileVault on macOS).
- The copy integrity gate (BLAKE3/SHA-256 hash comparison) is designed to prevent accidental data loss — it is not a cryptographic security primitive.
- FileVault never transmits any file data, metadata, or paths over a network. It operates entirely offline and locally.
