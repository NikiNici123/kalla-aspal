# ⚠️ NOT USED YET - scaffold only

Nothing in this folder is wired into the running app. `run_app.bat`,
`app.py`, and everything else you actually use day-to-day completely
ignore this folder. It exists purely as a **starting skeleton**, in case
you decide later that you want a standalone HTML/CSS/JS website version
of Kalla Aspal instead of (or alongside) the Streamlit app. Delete this
whole folder any time with zero effect on the real app.

## Read this first: you may not actually need this folder

You asked whether it makes sense to turn this into "a web type of file"
for when you want to deploy it online - worth untangling two different
questions there, because they have different answers:

**"Can the current app be deployed online?"** - Yes, already, as-is, with
no rewrite. Streamlit apps (exactly what `app.py` already is) deploy to
**Streamlit Community Cloud** (share.streamlit.io) by connecting your
GitHub repo - no code changes needed. We discussed this in an earlier
session: Vercel doesn't work for Streamlit (different hosting model),
but Streamlit Community Cloud does, and it can even restrict who's
allowed to view it by email address, since this app has no login system
of its own and holds real business data. **If "deployable online" is
the actual goal, that's the path - this folder isn't required for it.**

**"Should this become a plain HTML/CSS/JS website instead of Python?"** -
That's a different, much bigger project: a real rewrite, not a file
format change. Here's why. `app.py` today is a **Python program that
also draws the screen** - every button click re-runs Python code that
reads/writes the SQLite database directly and sends the result straight
back to your browser over a live connection Streamlit manages for you.
A "web type of file" (plain `.html`/`.css`/`.js`) has no such connection
and can't touch a database or run Python by itself - a static HTML page
is just a fixed page. To make one work like this app currently does,
you'd need to split it into two separate things talking to each other:

1. **A backend API** (still Python, e.g. Flask/FastAPI) - keeps all of
   today's `database/` and `services/` and `scraper/` logic almost
   unchanged, but exposes it as web endpoints (`GET /api/packages`,
   `POST /api/check-tender`, etc.) instead of Streamlit calling those
   functions directly.
2. **A frontend** (the HTML/CSS/JS in this folder) - runs in the
   browser, calls that API with JavaScript, and draws the tables/cards/
   calendar itself using the results.

That's a legitimate thing to want eventually (more control over the
exact look, no Streamlit quirks, could become a "real" website with its
own login for multiple admins) - but it roughly **doubles the amount of
code to maintain** (a backend AND a frontend, instead of one Streamlit
script) and isn't something to start without a clear reason, since the
Streamlit-Community-Cloud path already covers "put it online."

## What's actually in this folder right now

Just a static, disconnected skeleton - open `index.html` directly in a
browser and you'll see the Kalla Aspal look (header, road strip, a
couple of placeholder cards) with **fake, hardcoded sample data**. No
button does anything. No data is real. It's here so that if you DO
decide to go the backend+frontend route later, there's already a
starting page that matches the app's visual identity instead of
starting from a completely blank file.

- `index.html` - the skeleton page structure (header / metrics /
  tabs-look / sample activity card / sample package card), using the
  exact same CSS class names as the real app (`.kalla-header`,
  `.kalla-pkg-card`, etc.) so it's visually identical to the Streamlit
  version.
- `css/style.css` - **a snapshot copy** of `ui/style.css` as of the day
  this scaffold was made. It is NOT linked to the real one - if you
  change colors in `ui/style.css` later, this copy will NOT update on
  its own. If this folder is ever actually built out for real, re-copy
  the latest `ui/style.css` in at that point (or better, make it a
  genuinely shared file between the two - see "Next steps" below).
- `js/app.js` - empty placeholder. Nothing in it yet.

## If you do decide to build this out for real later

Rough order of operations, so future-you (or future-Claude) isn't
starting from zero:

1. Pick a small Python web framework for the API layer - FastAPI is a
   reasonable default (built-in request validation, auto-generated API
   docs, plays well with the existing `sqlite3`-based `database.py`).
2. Wrap the existing `services/*.py` functions with thin API endpoints -
   the actual business logic (scraping, comparison, filtering) barely
   changes, since those files already don't depend on Streamlit.
3. Replace the fake data in `index.html`/`app.js` with real `fetch()`
   calls to those endpoints.
4. Decide on hosting for the two pieces - the API needs somewhere that
   can run Python continuously (a small VPS, Railway, Render, etc. -
   NOT Vercel, same reason as Streamlit); the static frontend can live
   almost anywhere (GitHub Pages, Netlify, Vercel is actually fine for
   this half specifically since it's just static files).
5. Add real authentication if multiple people/devices will use it,
   since a public HTML page has no login by default the way this app
   currently avoids needing one (it just runs locally, one user).

None of this needs to happen unless you decide you actually want it -
raising it here so the option is understood, not to push you toward it.
