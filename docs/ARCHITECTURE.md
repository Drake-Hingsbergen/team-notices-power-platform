# Architecture

How the Team Notices app is put together. Names and IDs here are examples. Real values live in `config/settings.json`.

## 1. What it is

- Power Apps canvas app. Tablet layout, 1366 x 768.
- Two Power Automate cloud flows.
- Five SharePoint lists on one site.
- Connectors: SharePoint and Office 365 Outlook only. No Teams. No premium connectors.
- Flows are generated as legacy import packages. Screens are generated as YAML and pasted into Power Apps Studio.
- Site URL, list IDs, mailbox and app link come from `config/settings.json` at build time.

## 2. SharePoint

Site: `siteUrl` in settings, for example https://contoso.sharepoint.com/sites/TeamNotices

All internal names equal the display names. No column is required at list level.

### Team Notices

One row per posted notice. Written only by flow TN-1. Created By is always the flow owner, never the poster.

| Column | Type | Notes |
|---|---|---|
| Title | Text | Notice title. Test notices start with "TEST - " |
| Category | Choice | Process change, Policy, Outage, Tool update, Other |
| Body | Multiple lines, plain | Notice text |
| EffectiveDate | Date only | |
| AckDueDate | Date only | |
| RelatedLink | Text | Optional URL |
| PostedByName | Text | The poster |
| PostedByEmail | Text | The poster, lower case |
| PostedOn | Date and time | UTC |
| NoticeStatus | Choice | Posted, Superseded |
| VersionNumber | Number | 1, then +1 per correction |
| SupersedesId | Number | ID of the notice this one replaced, or 0 |
| AudienceCount | Number | Roster size at post time. Can be 0 |
| AckCount | Number | Recounted from rows on each acknowledgement |
| EscalatedOn | Date and time | Set when the summary email is sent. Set at creation for tests |
| RequestId | Number | Unique, indexed. ID of the request row |
| Attachments | Built in | Copied from the request by TN-1 |

### Team Notice Acknowledgements

One row per person per notice. Created at post time as Pending. Written only by TN-1. Created By is always the flow owner. Created is the post time, not the acknowledgement time.

| Column | Type | Notes |
|---|---|---|
| Title | Text | The person's name, not the notice name |
| AckKey | Text | Unique, indexed. "<NoticeId>|<email lower case>" |
| NoticeId | Number | Indexed |
| NoticeTitle | Text | Notice name |
| PersonName | Text | |
| PersonEmail | Text | Indexed, lower case |
| AckStatus | Choice | Pending, Acknowledged |
| AcknowledgedOn | Date and time | UTC. Blank while Pending |
| AckMethod | Choice | Teams card, App. Always App now |
| LastRemindedOn | Date and time | Unused |

### Team Notice Requests

Inbox. The app adds a row. TN-1 does the work. Users can add rows and see only their own.

| Column | Type | Notes |
|---|---|---|
| Title | Text | "Post" or "Acknowledge" |
| RequestType | Choice | Post, Acknowledge, Remind (Remind is unused) |
| NoticeId | Number | 0 for Post |
| Payload | Multiple lines, plain | JSON for Post. Keys: title, category, body, effectiveDate, ackDueDate, relatedLink, supersedesId, recipients, testOnly |
| RequestStatus | Choice | New, Done, Rejected |
| Result | Text | Outcome message from TN-1 |
| Attachments | Built in | Files the poster attached |

### Team Notice Members

Roles live here. There are no directory groups for posters or audience.

| Column | Type | Notes |
|---|---|---|
| Title | Text | Display name |
| Email | Text | Unique, indexed. Must equal the person's sign-in address. No trailing space |
| Active | Yes/No | In the system at all |
| CanPost | Yes/No | Can post, answer questions, see the roster |
| ReceivesEmail | Yes/No | Gets emails and appears in the recipient picker |
| MustAcknowledge | Yes/No | Goes on rosters |

### Team Notice Questions

Written directly by the app. Here Created By is the real person.

| Column | Type | Notes |
|---|---|---|
| Title | Text | Name of the asker or answerer |
| NoticeId | Number | Indexed |
| ParentId | Number | 0 for a question. Question ID for an answer |
| Message | Multiple lines, plain | |

### Permissions

- Team has Read on the site through the Visitors group.
- Requests: team can add, and read only their own (ReadSecurity 2, WriteSecurity 2).
- Questions: team can read all, add and edit only their own.
- Notices, Acknowledgements, Members: read only for the team.
- The Microsoft 365 group behind the site must have owners only. Its members can edit every list.
- The app is shared separately in Power Apps.

## 3. Flows

Both run on the flow owner's connections.

### TN-1 Process Request

- Trigger: SharePoint, When an item is created, Team Notice Requests. Polls each minute.
- Checks the requester is an Active member. Match is on SharePoint Author Email, lower case.
- Post: requires CanPost and a title, body and both dates. If supersedesId is set, marks the old notice Superseded and sets the version. Creates the notice. Creates one Pending row per member who is Active, MustAcknowledge and in the recipients list. For testOnly, the roster is the requester only and EscalatedOn is stamped. Waits 40 seconds. Copies request attachments to the notice. Sets the request to Done.
- Acknowledge: finds the row by AckKey. If Pending, sets Acknowledged, AcknowledgedOn and AckMethod App. Recounts AckCount.
- Remind: present but unused.
- On any failure the request is set to Rejected with a message.

### TN-3 Due Date Summary

- Trigger: Recurrence, daily 17:00 in the configured time zone.
- Picks notices where NoticeStatus is Posted, EscalatedOn is empty, AudienceCount is above 0 and AckDueDate is between 7 days ago and today.
- Sends one email per notice from the summary shared mailbox to members with CanPost, Active and ReceivesEmail. Lists Not Reviewed names and Acknowledged names with times.
- Stamps EscalatedOn only after the send succeeds.

An earlier design sent Teams adaptive cards. It was dropped in favor of email from the poster's own mailbox.

## 4. App

Globals set on first screen open: gMe (sign-in email, lower case), gMember, gCanPost. Others: gNotice, gCorrect, gMyAck. Collections: colMine, colRoster, colQ, colPick, colTo, colAtt, colJustAcked.

| Screen | Purpose | Key controls |
|---|---|---|
| scrMyNotices | Start screen. The user's roster rows. Not Reviewed first | mnGal, mnRowOpen, mnBtnRefresh |
| scrNotice | Notice text, files, Acknowledge. Tabs: Questions (all), Acknowledgements (posters) | ntBtnAck, ntGalFiles, ntTabQ, ntTabR, ntGalQ, ntBtnAsk, ntDlgSend, ntGalRoster, ntBtnRemind, ntBtnCorrect |
| scrNewNotice | Post form, attachments form, recipient picker dialog | nnTxtTitle, nnDrpCategory, nnDateEffective, nnDateDue, nnTxtBody, nnTxtLink, nnForm, nnAttach, nnBtnSend, nnBtnTest, nnGalPick, nnDlgSend |
| scrSearch | Keyword and category search of all notices | srTxtSearch, srDrpCategory, srGal |

Behavior:

- Post: nnDlgSend submits nnForm to Requests. nnForm.OnSuccess sends the email from the poster's mailbox with attachments.
- Recipient picker lists members with Active and ReceivesEmail. All start selected.
- nnBtnTest is visible to one person only, `testSenderEmail` in settings.
- Acknowledge adds a request row. The roster updates after TN-1 runs, about 1 to 2 minutes.
- Reminder button emails Pending people from the poster's mailbox. Once per screen visit.
- Post corrected version opens scrNewNotice prefilled with gCorrect set.
- Roster wording: Teammate, Not Reviewed (red), Acknowledged (green), Acknowledged on.

Delegation:

- scrSearch srGal.Items uses "in", which is not delegable. It reads the newest rows up to the app data row limit (500 default, 2000 max). A problem past that many notices.
- Filters on Acknowledgements use equality on indexed columns and delegate.

## 5. Emails

| Email | Trigger | From | To |
|---|---|---|---|
| New update | Poster confirms Send update | Poster | Picked recipients |
| Corrected version | Same, from Post corrected version | Poster | Picked recipients |
| Test | Owner confirms Send test | Owner | Owner |
| Reminder | Poster selects the reminder button | Poster | Pending people with Active and ReceivesEmail |
| Summary | TN-3 at 17:00 on the due date | Summary shared mailbox | Posters with ReceivesEmail |
| Question asked | Ask | Asker | Notice poster, if ReceivesEmail |
| Question answered | Post answer | Answering poster | Asker, if ReceivesEmail |

## 6. Reading the data from another system

- Notices: read Title, Body, PostedOn, PostedByName. Created By is always the flow owner.
- Skip rows where NoticeStatus is Superseded or Title starts with "TEST - ".
- Acknowledgements: read PersonName, NoticeTitle and AcknowledgedOn. Filter AckStatus equals Acknowledged.
- Expected count per notice is AudienceCount. Outstanding names are rows with AckStatus Pending.

## 7. Known limits

- The flows run on one owner's connections. Add a co-owner.
- No alert when a flow run fails.
- A superseded notice's Pending rows stay in My notices.
- Not packaged as a solution. No environment variables or connection references.
- A trailing space in Members.Email drops that person from rosters.
- Search is not delegable and reads the newest rows up to the app's data row limit.
