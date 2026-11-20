/* Team Notices: one-time SharePoint setup.
   Run in the browser console (F12 > Console) while you are on
   https://contoso.sharepoint.com/sites/TeamNotices
   Safe to run more than once: it skips anything that already exists. */
(async () => {
  const SITE = "https://contoso.sharepoint.com/sites/TeamNotices";
  const _copy = typeof copy === "function" ? copy : null;
  const log = [];
  const say = (m) => { log.push(m); console.log("[TN setup] " + m); };

  const MEMBERS = [
    ["Alex Rivera", "alex.rivera@contoso.com", true],
    ["Jordan Lee", "jordan.lee@contoso.com", true],
    ["Sam Patel", "sam.patel@contoso.com", false],
    ["Taylor Kim", "taylor.kim@contoso.com", false]
  ];

  if (!location.href.toLowerCase().startsWith(SITE.toLowerCase())) {
    console.error("[TN setup] Stopped. Open " + SITE + " in this tab first, then run this again.");
    return;
  }

  const result = { site: SITE, lists: {}, warnings: [], errors: [] };
  try {
    const ctx = await fetch(SITE + "/_api/contextinfo", {
      method: "POST", credentials: "same-origin",
      headers: { Accept: "application/json;odata=nometadata" }
    });
    const digest = (await ctx.json()).FormDigestValue;

    const api = async (path, method = "GET", body) => {
      const r = await fetch(SITE + "/_api/" + path, {
        method: method === "MERGE" ? "POST" : method,
        credentials: "same-origin",
        headers: Object.assign({
          Accept: "application/json;odata=verbose",
          "Content-Type": "application/json;odata=verbose",
          "X-RequestDigest": digest
        }, method === "MERGE" ? { "X-HTTP-Method": "MERGE", "IF-MATCH": "*" } : {}),
        body: body ? JSON.stringify(body) : undefined
      });
      const t = await r.text();
      let j = null;
      try { j = t ? JSON.parse(t) : null; } catch (e) { j = null; }
      if (!r.ok) {
        const msg = j && j.error && j.error.message ? j.error.message.value : t.slice(0, 200);
        const err = new Error(method + " " + path + " -> " + r.status + " " + msg);
        err.status = r.status;
        throw err;
      }
      return j && j.d !== undefined ? j.d : j;
    };

    const ensureList = async (title, description) => {
      const found = await api("web/lists?$select=Id,Title&$filter=Title eq '" + title + "'");
      if (found.results.length) { say("List exists: " + title); return found.results[0].Id; }
      const made = await api("web/lists", "POST", {
        __metadata: { type: "SP.List" }, BaseTemplate: 100, Title: title,
        Description: description, EnableVersioning: true
      });
      say("Created list: " + title);
      return made.Id;
    };

    const ensureField = async (listId, name, xml) => {
      const base = "web/lists(guid'" + listId + "')/fields";
      const found = await api(base + "?$select=Id&$filter=InternalName eq '" + name + "'");
      if (found.results.length) return;
      await api(base + "/createfieldasxml", "POST", {
        parameters: { __metadata: { type: "SP.XmlSchemaFieldCreationInformation" }, SchemaXml: xml, Options: 24 }
      });
      say("  added column " + name);
    };

    const attrs = (n, extra) => 'Name="' + n + '" StaticName="' + n + '" DisplayName="' + n + '" ' + (extra || "");
    const fText = (n, extra) => '<Field Type="Text" MaxLength="255" ' + attrs(n, extra) + "/>";
    const fNote = (n) => '<Field Type="Note" NumLines="8" RichText="FALSE" ' + attrs(n) + "/>";
    const fNum = (n, extra) => '<Field Type="Number" Decimals="0" ' + attrs(n, extra) + "/>";
    const fDate = (n, dateOnly) => '<Field Type="DateTime" Format="' + (dateOnly ? "DateOnly" : "DateTime") + '" ' + attrs(n) + "/>";
    const fBool = (n, def) => '<Field Type="Boolean" ' + attrs(n) + "><Default>" + def + "</Default></Field>";
    const fChoice = (n, choices, def) => '<Field Type="Choice" Format="Dropdown" ' + attrs(n) + "><Default>" + def +
      "</Default><CHOICES>" + choices.map((c) => "<CHOICE>" + c + "</CHOICE>").join("") + "</CHOICES></Field>";
    const UNIQUE = 'Indexed="TRUE" EnforceUniqueValues="TRUE"';
    const INDEXED = 'Indexed="TRUE"';

    // 1. Notices
    const notices = await ensureList("Team Notices", "Posted notices. Written only by the Team Notices flows.");
    result.lists.notices = notices;
    for (const [n, x] of [
      ["Category", fChoice("Category", ["Process change", "Policy", "Outage", "Tool update", "Other"], "Process change")],
      ["Body", fNote("Body")],
      ["EffectiveDate", fDate("EffectiveDate", true)],
      ["AckDueDate", fDate("AckDueDate", true)],
      ["RelatedLink", fText("RelatedLink")],
      ["PostedByName", fText("PostedByName")],
      ["PostedByEmail", fText("PostedByEmail")],
      ["PostedOn", fDate("PostedOn", false)],
      ["NoticeStatus", fChoice("NoticeStatus", ["Posted", "Superseded"], "Posted")],
      ["VersionNumber", fNum("VersionNumber")],
      ["SupersedesId", fNum("SupersedesId")],
      ["AudienceCount", fNum("AudienceCount")],
      ["AckCount", fNum("AckCount")],
      ["EscalatedOn", fDate("EscalatedOn", false)],
      ["RequestId", fNum("RequestId", UNIQUE)]
    ]) await ensureField(notices, n, x);

    // 2. Acknowledgements
    const acks = await ensureList("Team Notice Acknowledgements", "One row per person per notice. Written only by the Team Notices flows.");
    result.lists.acknowledgements = acks;
    for (const [n, x] of [
      ["AckKey", fText("AckKey", UNIQUE)],
      ["NoticeId", fNum("NoticeId", INDEXED)],
      ["NoticeTitle", fText("NoticeTitle")],
      ["PersonName", fText("PersonName")],
      ["PersonEmail", fText("PersonEmail", INDEXED)],
      ["AckStatus", fChoice("AckStatus", ["Pending", "Acknowledged"], "Pending")],
      ["AcknowledgedOn", fDate("AcknowledgedOn", false)],
      ["AckMethod", fChoice("AckMethod", ["Teams card", "App"], "Teams card")],
      ["LastRemindedOn", fDate("LastRemindedOn", false)]
    ]) await ensureField(acks, n, x);

    // 3. Requests (the only list people can write to)
    const requests = await ensureList("Team Notice Requests", "Inbox for the app. People add a request, the flows do the work.");
    result.lists.requests = requests;
    for (const [n, x] of [
      ["RequestType", fChoice("RequestType", ["Post", "Acknowledge", "Remind"], "Acknowledge")],
      ["NoticeId", fNum("NoticeId")],
      ["Payload", fNote("Payload")],
      ["RequestStatus", fChoice("RequestStatus", ["New", "Done", "Rejected"], "New")],
      ["Result", fText("Result")]
    ]) await ensureField(requests, n, x);

    // 4. Members (audience and posters)
    const members = await ensureList("Team Notice Members", "Who receives notices and who can post them.");
    result.lists.members = members;
    for (const [n, x] of [
      ["Email", fText("Email", UNIQUE)],
      ["CanPost", fBool("CanPost", 0)],
      ["Active", fBool("Active", 1)]
    ]) await ensureField(members, n, x);

    const memberType = (await api("web/lists(guid'" + members + "')?$select=ListItemEntityTypeFullName")).ListItemEntityTypeFullName;
    const existing = (await api("web/lists(guid'" + members + "')/items?$select=Email&$top=500")).results
      .map((i) => (i.Email || "").toLowerCase());
    let seeded = 0;
    for (const [name, email, canPost] of MEMBERS) {
      if (existing.includes(email.toLowerCase())) continue;
      await api("web/lists(guid'" + members + "')/items", "POST", {
        __metadata: { type: memberType }, Title: name, Email: email, CanPost: canPost, Active: true
      });
      seeded++;
    }
    say("Members list: added " + seeded + ", already there " + (MEMBERS.length - seeded));

    // 5. Permissions: everyone reads, nobody edits, requests are add-your-own only
    let visitors = null;
    try { visitors = await api("web/associatedvisitorgroup?$select=Id,Title"); } catch (e) { visitors = null; }
    if (!visitors || !visitors.Id) {
      result.warnings.push("No Visitors group found on the site. Give the team Read on the site by hand.");
    } else {
      let added = 0;
      for (const [, email] of MEMBERS) {
        try {
          const u = await api("web/ensureuser", "POST", { logonName: email });
          await api("web/sitegroups(" + visitors.Id + ")/users", "POST", {
            __metadata: { type: "SP.User" }, LoginName: u.LoginName
          });
          added++;
        } catch (e) { result.warnings.push("Could not add " + email + " to " + visitors.Title + ": " + e.message); }
      }
      say("Read access: " + added + " of " + MEMBERS.length + " people are in " + visitors.Title);

      const reqBase = "web/lists(guid'" + requests + "')";
      const uniq = await api(reqBase + "?$select=HasUniqueRoleAssignments");
      if (!uniq.HasUniqueRoleAssignments) {
        await api(reqBase + "/breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true)", "POST");
      }
      await api(reqBase + "/roleassignments/addroleassignment(principalid=" + visitors.Id + ",roledefid=1073741827)", "POST");
      await api(reqBase, "MERGE", { __metadata: { type: "SP.List" }, ReadSecurity: 2, WriteSecurity: 2 });
      say("Requests list: team can add items and see only their own");
    }

    try {
      const mg = await api("web/associatedmembergroup?$select=Id,Title");
      const mu = await api("web/sitegroups(" + mg.Id + ")/users?$select=Title");
      if (mu.results.length) {
        result.warnings.push(mg.Title + " has " + mu.results.length + " entr" + (mu.results.length === 1 ? "y" : "ies") +
          " (" + mu.results.map((x) => x.Title).join(", ") + "). Anyone in it can edit the lists directly. Keep it empty.");
      }
    } catch (e) { /* no members group, nothing to warn about */ }
  } catch (e) {
    result.errors.push(e.message);
    console.error("[TN setup] FAILED: " + e.message);
  }

  result.log = log;
  window.__TN_SETUP = JSON.stringify(result, null, 2);
  console.table(result.lists);
  result.warnings.forEach((w) => console.warn("[TN setup] " + w));
  console.log(window.__TN_SETUP);
  if (_copy) { _copy(window.__TN_SETUP); console.log("[TN setup] Result copied to clipboard. To copy again: copy(window.__TN_SETUP)"); }
  else console.log("[TN setup] To copy the result: copy(window.__TN_SETUP)");
  console.log(result.errors.length ? "[TN setup] Finished WITH ERRORS. Paste the result back to Claude." : "[TN setup] Finished. Paste the result back to Claude.");
})();
