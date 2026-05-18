# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please follow these steps:

1. **Do not** open a public GitHub issue
2. Email security@vidrev.local with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

3. Expected response time: **48 hours**

4. We will:
   - Acknowledge receipt within 48 hours
   - Provide an estimated timeline for a fix
   - Credit you in the release notes (if desired)

## Security Best Practices

When using VideoReverse:

- **Never commit `.env` files** — use `.env.example` as template
- Rotate `GEMINI_API_KEY` regularly
- Store API keys in a secrets manager (AWS Secrets, HashiCorp Vault)
- Enable GitHub secret scanning in your organization settings