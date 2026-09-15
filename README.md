# Marothu Harsha Vardhan

Portfolio and showreel — films, music videos, animation and visual work.

| Who | How you get in | What you can do |
| --- | --- | --- |
| **Visitor** | Just open the site. No login, ever. | Read everything, browse the work, watch the reel, leave a message |
| **Owner (admin)** | Add `?view=admin` to the URL, enter the password | Edit every word, image, video and setting on the site |

Nothing is hard-coded. Every piece of text, every photo, every video and
every section heading is editable from the admin console, and everything is
saved permanently.

## Where the content lives

Content is stored **in this same GitHub repository, on a separate branch
called `content`**:

```
content branch
├── data/site.json        profile, hero, contact, appearance
├── data/projects.json    the work
├── data/timeline.json    milestones
├── data/gallery.json     stills
├── data/press.json       quotes and recognition
├── data/messages.json    visitor messages
└── media/…               every uploaded image and video
```

Using a separate branch matters: Streamlit Community Cloud watches the
branch it deployed from (`main`), so saving content never reboots the live
site. You also get a full version history of every edit for free, and you
can always recover an older version from the repo.

## Setup

### 1. Create a GitHub token

GitHub → **Settings → Developer settings → Personal access tokens →
Fine-grained tokens → Generate new token**

- **Repository access:** Only select repositories → this repo
- **Permissions:** Repository permissions → **Contents: Read and write**
- **Expiration:** whatever you're comfortable with (you'll need to replace
  it when it expires)

Copy the token — GitHub shows it only once.

### 2. Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. **Create app** → pick this repo, branch `main`, main file `streamlit_app.py`
3. Open **Advanced settings → Secrets** and paste:

```toml
admin_password = "pick-something-long-and-private"

[github]
token  = "github_pat_…"
owner  = "your-github-username"
repo   = "this-repo-name"
branch = "content"
```

4. Deploy.

The `content` branch is created automatically the first time you save
something in the admin console.

### 3. Log in and fill it in

Open `https://your-app.streamlit.app/?view=admin`, enter the password, and
work through the tabs: **Profile** first, then **Work**.

## Running it locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Without secrets it runs against a local `local_content/` folder so you can
try it offline. That folder is temporary — only the GitHub backend keeps
content permanently.

## Limits worth knowing

- **Images:** 10 MB each
- **Videos:** 20 MB each for direct upload. Anything longer belongs on
  YouTube or Vimeo — paste the link and it embeds properly. Only YouTube
  and Vimeo links are accepted, deliberately.
- Uploaded media is served through the jsDelivr CDN, which is why the 20 MB
  ceiling exists.

## Security

- The admin password is compared in constant time and locks out for 5
  minutes after 5 wrong attempts; the session expires after 8 hours.
- Every piece of stored content is HTML-escaped before it reaches the page,
  so a visitor cannot inject scripts through the guestbook.
- Uploads are checked by extension *and* by file signature, so a script
  renamed `photo.png` is rejected.
- Video embeds are restricted to YouTube and Vimeo, sandboxed, and given a
  strict referrer policy.
- Visitor messages are held for approval by default and rate-limited.

Full detail is in `SECURITY.md`.
