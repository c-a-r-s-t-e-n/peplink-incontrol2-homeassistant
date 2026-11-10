# Security policy

Do not include OAuth client secrets, access tokens, full router API responses,
serial numbers, public IP addresses or GPS history in public issues.

If you discover a security vulnerability, please use **GitHub → Security →
Advisories → Report a vulnerability** (when enabled by the maintainer), rather
than opening a public issue. Never post production credentials.

If a secret was committed, revoke/rotate it in Peplink InControl 2 immediately.
Deleting the file in a later commit does not remove it from Git history.
