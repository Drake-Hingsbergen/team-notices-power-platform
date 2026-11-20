/* Team Notices: adds "ReceivesEmail" and "MustAcknowledge" to the Members list and sets them.
   Run in the browser console (F12 > Console) while you are on
   https://contoso.sharepoint.com/sites/TeamNotices
   Safe to run more than once. */
(async () => {
  const SITE = "https://contoso.sharepoint.com/sites/TeamNotices";
  const LIST = "00000000-0000-0000-0000-000000000004" /* Team Notice Members list id from step 1 */;
  // email (lower case): [ReceivesEmail, MustAcknowledge]. Everyone not listed here gets true, true.
  const RULES = {
    "alex.rivera@contoso.com": [false, false],
    "jordan.lee@contoso.com": [true, false]
  };
  const _copy = typeof copy === "function" ? copy : null;
  const log = [];
  const say = (m) => { log.push(m); console.log("[TN roles] " + m); };

  if (!location.href.toLowerCase().startsWith(SITE.toLowerCase())) {
    console.error("[TN roles] Stopped. Open " + SITE + " in this tab first, then run this again.");
    return;
  }

  const result = { site: SITE, members: [], warnings: [], errors: [] };
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

    const base = "web/lists(guid'" + LIST + "')";
    for (const name of ["ReceivesEmail", "MustAcknowledge"]) {
      const f = await api(base + "/fields?$select=Id&$filter=InternalName eq '" + name + "'");
      if (f.results.length) continue;
      await api(base + "/fields/createfieldasxml", "POST", {
        parameters: {
          __metadata: { type: "SP.XmlSchemaFieldCreationInformation" },
          SchemaXml: '<Field Type="Boolean" Name="' + name + '" StaticName="' + name + '" DisplayName="' + name + '"><Default>1</Default></Field>',
          Options: 24
        }
      });
      say("added column " + name);
    }

    const type = (await api(base + "?$select=ListItemEntityTypeFullName")).ListItemEntityTypeFullName;
    const items = (await api(base + "/items?$select=Id,Title,Email,CanPost,Active&$top=500")).results;
    const seen = {};
    for (const it of items) {
      const email = (it.Email || "").toLowerCase();
      const rule = RULES[email] || [true, true];
      seen[email] = true;
      await api(base + "/items(" + it.Id + ")", "MERGE", {
        __metadata: { type: type }, ReceivesEmail: rule[0], MustAcknowledge: rule[1]
      });
      result.members.push({
        Name: it.Title, Email: it.Email, Active: it.Active, CanPost: it.CanPost,
        ReceivesEmail: rule[0], MustAcknowledge: rule[1]
      });
    }
    Object.keys(RULES).forEach((e) => { if (!seen[e]) result.warnings.push("Not found in the Members list: " + e); });
    say("Set " + items.length + " members");
  } catch (e) {
    result.errors.push(e.message);
    console.error("[TN roles] FAILED: " + e.message);
  }

  result.log = log;
  window.__TN_ROLES = JSON.stringify(result, null, 2);
  console.table(result.members);
  result.warnings.forEach((w) => console.warn("[TN roles] " + w));
  if (_copy) { _copy(window.__TN_ROLES); console.log("[TN roles] Result copied to clipboard. To copy again: copy(window.__TN_ROLES)"); }
  else console.log("[TN roles] To copy the result: copy(window.__TN_ROLES)");
  console.log(result.errors.length ? "[TN roles] Finished WITH ERRORS. Paste the result back to Claude." : "[TN roles] Finished. Check the table above.");
})();
