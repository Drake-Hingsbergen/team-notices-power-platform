# Team Notices

A read-and-acknowledge app for a support team, built on Power Apps, Power Automate and SharePoint with standard connectors only.

Leads post an update. The team gets it by email from the poster. Each teammate acknowledges in the app. Leads can search past updates and see who has and has not acknowledged, and get one summary email on the due date.

This is a generic template. It contains no organization data. All names, addresses and IDs are placeholders.

**Status:** complete. Every feature listed below is built and tested.

## What it does

- Post an update with category, effective date, acknowledge-by date, optional link and file attachments.
- Pick recipients in a dialog with select all and clear.
- Email goes out from the poster's own mailbox.
- One-click acknowledgement, stored with name and time.
- Questions and answers on each update, visible to everyone.
- Roster per update: Not Reviewed or Acknowledged, with a reminder button.
- Corrected versions supersede the original and need a fresh acknowledgement.
- Daily flow sends one summary per update on its due date from a shared mailbox.
- Roles are four yes/no columns on a members list: Active, CanPost, ReceivesEmail, MustAcknowledge.

## How it is built

| Part | What | Where |
|---|---|---|
| Data | Five SharePoint lists, created by browser console scripts over the SharePoint REST API | `setup/` |
| Flows | Two cloud flows, generated as legacy import packages by Python | `src/build_flows.py` |
| App | Four canvas screens, generated as `.pa.yaml` by Python and pasted into Studio | `src/build_screens.py` |
| Settings | Site URL, list IDs, mailbox, app link | `config/settings.example.json` |

Design choices worth noting:

- Users never write to the notice or acknowledgement lists. The app adds a row to a request list and a flow, running as the owner, validates the requester and does the write. That keeps the audit trail tamper resistant without premium licensing.
- A unique key per person per notice makes duplicate acknowledgements impossible. Counts are recalculated from rows, never incremented.
- Flow packages are generated from code, so every change is a diff and a rebuild, not designer clicks.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for lists, columns, flow logic, screens and limits.

## Deploy

1. Create a SharePoint team site.
2. Edit the site URL and the sample people at the top of each script in `setup/`. Open the site in a browser, press F12, and run the three scripts in order in the console. The first prints the list IDs.
3. Copy `config/settings.example.json` to `config/settings.json` and fill it in. `settings.json` is git-ignored.
4. Create a blank tablet canvas app. Add the five lists and the Office 365 Outlook connector. Copy the app's web link into settings.
5. Build:

```
pip install pyyaml
python src/build_flows.py
python src/build_screens.py
```

6. Import the two packages from `out/packages` in Power Automate with Import Package (Legacy), Create as new, and pick your connections.
7. Paste the four files from `out/screens` into the app as whole screens. Put `scrMyNotices` first.
8. Share the app with the team. Give them Read on the site, not membership of the site's Microsoft 365 group.

## How AI was used

Built with Claude as a pair engineer. I set the requirements, made the design decisions, ran every import and test in the tenant and fed errors back. Claude generated the scripts, flow definitions and screens. Each change was checked by a separate review agent before it was deployed, which caught several logic bugs before go-live.

## License and scope

Shared as a work sample and starting point. Test in a non-production environment first.
