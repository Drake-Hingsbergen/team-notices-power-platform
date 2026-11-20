/* Team Notices: adds the Questions list.
   Run in the browser console (F12 > Console) while you are on
   https://contoso.sharepoint.com/sites/TeamNotices
   Safe to run more than once: it skips anything that already exists. */
(async () => {
  const SITE = "https://contoso.sharepoint.com/sites/TeamNotices";
  const TITLE = "Team Notice Questions";
  const _copy = typeof copy === "function" ? copy : null;
  const log = [];
  const say = (m) => { log.push(m); console.log("[TN questions] " + m); };

  if (!location.href.toLowerCase().startsWith(SITE.toLowerCase())) {
    console.error("[TN questions] Stopped. Open " + SITE + " in this tab first, then run this again.");
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
        throw new Error(method + " " + path + " -> " + r.status + " " + msg);
      }
      return j && j.d !== undefined ? j.d : j;
    };

    let listId;
    const found = await api("web/lists?$select=Id&$filter=Title eq '" + TITLE + "'");
    if (found.results.length) {
      listId = found.results[0].Id;
      say("List exists: " + TITLE);
    } else {
      const made = await api("web/lists", "POST", {
        __metadata: { type: "SP.List" }, BaseTemplate: 100, Title: TITLE,
        Description: "Questions and answers on updates. Everyone can read them and add their own.",
        EnableVersioning: true
      });
      listId = made.Id;
      say("Created list: " + TITLE);
    }
    result.lists.questions = listId;
    const base = "web/lists(guid'" + listId + "')";

    const ensureField = async (name, xml) => {
      const f = await api(base + "/fields?$select=Id&$filter=InternalName eq '" + name + "'");
      if (f.results.length) return;
      await api(base + "/fields/createfieldasxml", "POST", {
        parameters: { __metadata: { type: "SP.XmlSchemaFieldCreationInformation" }, SchemaXml: xml, Options: 24 }
      });
      say("  added column " + name);
    };
    const attrs = (n) => 'Name="' + n + '" StaticName="' + n + '" DisplayName="' + n + '"';
    await ensureField("NoticeId", '<Field Type="Number" Decimals="0" Indexed="TRUE" ' + attrs("NoticeId") + "/>");
    await ensureField("ParentId", '<Field Type="Number" Decimals="0" ' + attrs("ParentId") + "><Default>0</Default></Field>");
    await ensureField("Message", '<Field Type="Note" NumLines="6" RichText="FALSE" ' + attrs("Message") + "/>");

    let visitors = null;
    try { visitors = await api("web/associatedvisitorgroup?$select=Id,Title"); } catch (e) { visitors = null; }
    if (!visitors || !visitors.Id) {
      result.warnings.push("No Visitors group found. Give the team Contribute on the " + TITLE + " list by hand.");
    } else {
      const uniq = await api(base + "?$select=HasUniqueRoleAssignments");
      if (!uniq.HasUniqueRoleAssignments) {
        await api(base + "/breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true)", "POST");
      }
      await api(base + "/roleassignments/addroleassignment(principalid=" + visitors.Id + ",roledefid=1073741827)", "POST");
      await api(base, "MERGE", { __metadata: { type: "SP.List" }, ReadSecurity: 1, WriteSecurity: 2 });
      say("Permissions: the team can read every question and add or edit only their own");
    }
  } catch (e) {
    result.errors.push(e.message);
    console.error("[TN questions] FAILED: " + e.message);
  }

  result.log = log;
  window.__TN_QUESTIONS = JSON.stringify(result, null, 2);
  result.warnings.forEach((w) => console.warn("[TN questions] " + w));
  console.log(window.__TN_QUESTIONS);
  if (_copy) { _copy(window.__TN_QUESTIONS); console.log("[TN questions] Result copied to clipboard. To copy again: copy(window.__TN_QUESTIONS)"); }
  else console.log("[TN questions] To copy the result: copy(window.__TN_QUESTIONS)");
  console.log(result.errors.length ? "[TN questions] Finished WITH ERRORS. Paste the result back to Claude." : "[TN questions] Finished. Paste the result back to Claude.");
})();
