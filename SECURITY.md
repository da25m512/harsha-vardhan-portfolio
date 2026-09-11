# Security review

Reviewed against the OWASP Top 10 (2021). Automated checks live in
`tools/test_owasp.py` (146 assertions) and `tools/test_security.py`
(DOM-level checks on the rendered page). Both must pass before deploying.

## What was found and fixed

| # | Issue found during review | Fix |
| --- | --- | --- |
| 1 | Guestbook text and all stored content was rendered into raw HTML | Everything passes through `esc()` / `attr()` before reaching the page |
| 2 | Any URL could be placed in a video embed | Embeds restricted to YouTube and Vimeo, parsed and rebuilt from the video ID |
| 3 | Uploads trusted the file extension | Extension **and** file-signature (magic byte) checks, plus a markup sniff |
| 4 | Admin password compared with `==` | `hmac.compare_digest`, plus a 5-attempt lockout and 8-hour session cap |
| 5 | `new_media_path` kept dots from the original filename | Dots stripped from the stem; extension must match `^\.[a-z0-9]{1,5}$` |
| 6 | Streamlit re-sends an uploaded file on every rerun | Uploads are fingerprinted, so one pick commits exactly once |
| 7 | Two visitors posting at once could lose a message | GitHub writes retry on 409/422 after re-reading the file SHA |

## A01 — Broken access control

- The admin console is reachable only at `?view=admin` and renders nothing
  but the password form until authentication succeeds.
- Unpublished projects and unapproved messages are filtered out of the
  public render, not merely hidden with CSS.
- Admin state lives in server-side session state; there is no client-side
  flag a visitor can set.
- Being logged in does not change what the public page shows.

## A02 — Cryptographic failures

- The password is never stored by the app; it is read from Streamlit
  secrets and compared in constant time.
- The GitHub token stays server-side. It is never rendered, logged, or
  placed in a URL. Nothing writes it to the repo — `.streamlit/secrets.toml`
  is git-ignored and absent from the deployable file set.

## A03 — Injection / XSS

This is the main risk, because the page is composed as HTML strings and the
guestbook accepts anonymous input.

- Every interpolated value goes through `esc()` (element text) or `attr()`
  (attribute values). Tested against 14 XSS payload families.
- `safe_url()` rejects `javascript:`, `vbscript:`, `data:text/html`,
  `file:`, protocol-relative URLs, plain HTTP, and null-byte tricks.
- Streamlit does not execute `<script>` inside `st.markdown`; the escaping
  above is the actual control, not that behaviour.

## A04 — Insecure design

- Messages are held for approval by default.
- Limits: 60-character names, 600-character messages, a 45-second cooldown
  per visitor, at most one link, a hidden honeypot field, and a hard cap of
  500 stored messages.

## A05 — Security misconfiguration

- `showErrorDetails = false` keeps stack traces off the public page.
- Only YouTube/Vimeo iframes are emitted, each with `sandbox` and
  `referrerpolicy="strict-origin-when-cross-origin"`.
- Every `target="_blank"` link carries `rel="noopener noreferrer"`.

## A08 — Software and data integrity

- Uploads are validated by extension, size, and file signature. A PHP
  shell, an SVG, or an HTML file renamed `.png` is rejected.
- Images are capped at 10 MB, videos at 20 MB.
- Generated storage paths cannot escape `media/<folder>/`.
- Content is written to a Git branch, so every change is attributable and
  revertible.

## A10 — SSRF

- The app makes outbound requests to exactly one host, `api.github.com`,
  with a fixed owner/repo from configuration — never to a user-supplied URL.
- Video links are parsed, the ID extracted, and a known-good embed URL is
  rebuilt. Tested against 12 SSRF payloads including cloud metadata
  endpoints, loopback addresses, and `youtube.com.evil.com` style
  look-alikes.

## Residual risks — worth knowing

1. **The token can write to the whole repo.** GitHub fine-grained tokens
   scope to a repository, not a branch. Use a token limited to this one
   repo, with only *Contents: read and write*.
2. **The guestbook writes on behalf of anonymous visitors.** Rate limits are
   per browser session, so a determined attacker with fresh sessions could
   still create commits. Moderation means nothing reaches the public page,
   and the guestbook can be switched off in **Appearance**. If it is ever
   abused, turn it off and delete the spam commits.
3. **No CSP or security headers.** Streamlit Community Cloud does not let
   you set response headers. Output escaping is therefore the primary XSS
   control rather than a backstop.
4. **Content is public.** The `content` branch lives in a public repo, so
   uploaded media is publicly readable by design. Do not upload anything
   private.
5. **Token expiry.** When the fine-grained token expires, saving stops
   working. The admin Overview tab shows the connection status, and the
   fix is to generate a new token and update the Streamlit secret.
