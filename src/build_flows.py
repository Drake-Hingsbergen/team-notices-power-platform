"""Builds the three Team Notices legacy import packages (.zip)."""
import datetime
import json
import uuid
import zipfile

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.environ.get("TEAM_NOTICES_SETTINGS", os.path.join(_HERE, "..", "config", "settings.json"))
with open(_CFG_PATH, encoding="utf-8") as _f:
    CFG = json.load(_f)

SITE = CFG["siteUrl"]
NOTICES = CFG["lists"]["notices"]
ACKS = CFG["lists"]["acknowledgements"]
REQUESTS = CFG["lists"]["requests"]
MEMBERS = CFG["lists"]["members"]
OUT_DIR = os.path.join(_HERE, "..", "out", "packages")
TZ = CFG["timeZone"]

SP = "shared_sharepointonline"
TEAMS = "shared_teams"
API_INFO = {
    SP: ("SharePoint", "https://connectoricons-prod.azureedge.net/releases/v1.0.1676/1.0.1676.3222/sharepointonline/icon.png"),
    TEAMS: ("Microsoft Teams", "https://connectoricons-prod.azureedge.net/releases/v1.0.1676/1.0.1676.3222/teams/icon.png"),
}


def conn(api, op, params, run_after=None, kind="OpenApiConnection"):
    return {
        "runAfter": run_after or {},
        "type": kind,
        "inputs": {
            "host": {"connectionName": api, "operationId": op, "apiId": f"/providers/Microsoft.PowerApps/apis/{api}"},
            "parameters": params,
            "authentication": "@parameters('$authentication')",
        },
    }


def after(*names, status=("Succeeded",)):
    return {n: list(status) for n in names}


def get_items(lst, flt, run_after=None, top=5000):
    return conn(SP, "GetItems", {"dataset": SITE, "table": lst, "$filter": flt, "$top": top}, run_after)


def get_item(lst, id_expr, run_after=None):
    return conn(SP, "GetItem", {"dataset": SITE, "table": lst, "id": id_expr}, run_after)


def patch(lst, id_expr, fields, run_after=None):
    p = {"dataset": SITE, "table": lst, "id": id_expr}
    p.update({"item/" + k: v for k, v in fields.items()})
    return conn(SP, "PatchItem", p, run_after)


def create(lst, fields, run_after=None):
    p = {"dataset": SITE, "table": lst}
    p.update({"item/" + k: v for k, v in fields.items()})
    return conn(SP, "PostItem", p, run_after)


def message(recipient, html, run_after=None):
    return conn(TEAMS, "PostMessageToConversation", {
        "poster": "Flow bot", "location": "Chat with Flow bot",
        "body/recipient": recipient, "body/messageBody": html,
    }, run_after)


def compose(value, run_after=None):
    return {"runAfter": run_after or {}, "type": "Compose", "inputs": value}


def query(frm, where, run_after=None):
    return {"runAfter": run_after or {}, "type": "Query", "inputs": {"from": frm, "where": where}}


def select(frm, mapping, run_after=None):
    return {"runAfter": run_after or {}, "type": "Select", "inputs": {"from": frm, "select": mapping}}


def foreach(items, actions, run_after=None, sequential=True):
    a = {"runAfter": run_after or {}, "type": "Foreach", "foreach": items, "actions": actions}
    if sequential:
        a["operationOptions"] = "Sequential"
    return a


def cond(expr, yes, no=None, run_after=None):
    return {"runAfter": run_after or {}, "type": "If", "expression": {"equals": [expr, True]},
            "actions": yes, "else": {"actions": no or {}}}


def recount(prefix, nid, title, run_after):
    """Recalculate AckCount for a notice from the rows (idempotent, never increments)."""
    c, u = f"{prefix}_Count_acknowledged", f"{prefix}_Update_notice_count"
    return {
        c: get_items(ACKS, "NoticeId eq @{" + nid + "} and AckStatus eq 'Acknowledged'", run_after),
        u: patch(NOTICES, "@" + nid, {"Title": "@" + title, "AckCount": f"@length(body('{c}')?['value'])"}, after(c)),
    }


def sp_trigger(lst):
    return {"When_an_item_is_created": {
        "recurrence": {"frequency": "Minute", "interval": 1},
        "splitOn": "@triggerOutputs()?['body/value']",
        "type": "OpenApiConnection",
        "inputs": {
            "host": {"connectionName": SP, "operationId": "GetOnNewItems", "apiId": f"/providers/Microsoft.PowerApps/apis/{SP}"},
            "parameters": {"dataset": SITE, "table": lst},
            "authentication": "@parameters('$authentication')",
        },
    }}


# ---------------------------------------------------------------- TN-1 Process Request
EMAIL = "outputs('Requester_email')"
EMAIL_OD = "replace(outputs('Requester_email'),'''','''''')"
RNID = "outputs('Request_notice_id')"
MEMBER = "first(body('Get_member')?['value'])"
PAY = "outputs('Payload')"
SUP = "int(if(empty(" + PAY + "?['supersedesId']),0," + PAY + "?['supersedesId']))"
IS_TEST = "equals(toLower(string(coalesce(" + PAY + "?['testOnly'],false))),'true')"
RECIP = "toLower(string(coalesce(" + PAY + "?['recipients'],'')))"
PICKED = ("or(empty(" + RECIP + "),contains(concat(';'," + RECIP + ",';'),concat(';',toLower(coalesce(item()?['Email'],'')),';')))")
REQ_ID = "@triggerBody()?['ID']"
REQ_TITLE = "@coalesce(triggerBody()?['Title'],'Request')"


def finish(status, result, run_after=None):
    return patch(REQUESTS, REQ_ID, {"Title": REQ_TITLE, "RequestStatus/Value": status, "Result": result}, run_after)


FILES = "if(equals(actions('Get_request_attachments')?['status'],'Succeeded'),body('Get_request_attachments'),json('[]'))"
post_ok = {
    "Check_supersede": cond(
        "@greater(" + SUP + ",0)",
        {
            "Get_old_notice": get_item(NOTICES, "@" + SUP),
            "Set_Version": {"runAfter": after("Get_old_notice"), "type": "SetVariable", "inputs": {
                "name": "Version",
                "value": "@add(int(first(split(string(coalesce(body('Get_old_notice')?['VersionNumber'],1)),'.'))),1)"}},
            "Mark_old_superseded": patch(NOTICES, "@" + SUP, {
                "Title": "@body('Get_old_notice')?['Title']", "NoticeStatus/Value": "Superseded"}, after("Set_Version")),
        }),
    "Get_active_members": get_items(MEMBERS, "Active eq 1", after("Check_supersede"), top=500),
    "Audience": query(
        "@body('Get_active_members')?['value']",
        "@or(and(not(" + IS_TEST + "),equals(coalesce(item()?['MustAcknowledge'],true),true)," + PICKED + "),"
        "and(" + IS_TEST + ",equals(toLower(item()?['Email'])," + EMAIL + ")))",
        after("Get_active_members")),
    "Create_notice": create(NOTICES, {
        "Title": "@" + PAY + "?['title']",
        "Category/Value": "@coalesce(" + PAY + "?['category'],'Other')",
        "Body": "@" + PAY + "?['body']",
        "EffectiveDate": "@" + PAY + "?['effectiveDate']",
        "AckDueDate": "@" + PAY + "?['ackDueDate']",
        "RelatedLink": "@coalesce(" + PAY + "?['relatedLink'],'')",
        "PostedByName": "@coalesce(triggerBody()?['Author']?['DisplayName']," + EMAIL + ")",
        "PostedByEmail": "@" + EMAIL,
        "PostedOn": "@utcNow()",
        "NoticeStatus/Value": "Posted",
        "VersionNumber": "@variables('Version')",
        "SupersedesId": "@" + SUP,
        "AudienceCount": "@length(body('Audience'))",
        "AckCount": 0,
        "EscalatedOn": "@if(" + IS_TEST + ",utcNow(),null)",
        "RequestId": REQ_ID,
    }, after("Audience")),
    "For_each_member": foreach("@body('Audience')", {
        "Create_acknowledgement_row": create(ACKS, {
            "Title": "@items('For_each_member')?['Title']",
            "AckKey": "@concat(string(body('Create_notice')?['ID']),'|',toLower(items('For_each_member')?['Email']))",
            "NoticeId": "@body('Create_notice')?['ID']",
            "NoticeTitle": "@" + PAY + "?['title']",
            "PersonName": "@items('For_each_member')?['Title']",
            "PersonEmail": "@toLower(items('For_each_member')?['Email'])",
            "AckStatus/Value": "Pending",
        }),
    }, after("Create_notice")),
    "Wait_for_uploads": {"runAfter": after("For_each_member"), "type": "Wait",
                         "inputs": {"interval": {"count": 40, "unit": "Second"}}},
    "Get_request_attachments": conn(SP, "GetItemAttachments", {"dataset": SITE, "table": REQUESTS, "itemId": REQ_ID},
                                    after("Wait_for_uploads")),
    "For_each_attachment": foreach("@" + FILES, {
        "Get_attachment_content": conn(SP, "GetAttachmentContent", {
            "dataset": SITE, "table": REQUESTS, "itemId": REQ_ID, "attachmentId": "@items('For_each_attachment')?['Id']"}),
        "Add_to_notice": conn(SP, "CreateAttachment", {
            "dataset": SITE, "table": NOTICES, "itemId": "@body('Create_notice')?['ID']",
            "displayName": "@items('For_each_attachment')?['DisplayName']",
            "body": "@body('Get_attachment_content')"}, after("Get_attachment_content")),
    }, after("Get_request_attachments", status=("Succeeded", "Failed", "TimedOut"))),
    "Post_done": finish("Done", "@concat('Posted as notice ',string(body('Create_notice')?['ID']),' to ',string(length(body('Audience'))),"
                        "' people, ',string(length(" + FILES + ")),' file(s)')",
                        after("For_each_attachment", status=("Succeeded", "Failed"))),
}

case_post = {
    "Payload": compose("@json(triggerBody()?['Payload'])"),
    "Can_post_and_complete": cond(
        "@and(equals(" + MEMBER + "?['CanPost'],true),not(empty(" + PAY + "?['title'])),not(empty(" + PAY + "?['body'])),"
        "not(empty(" + PAY + "?['effectiveDate'])),not(empty(" + PAY + "?['ackDueDate'])))",
        post_ok,
        {"Post_rejected": finish("Rejected", "Not allowed to post, or the notice is missing a title, body or date")},
        after("Payload")),
}

MY_ACK = "first(body('Find_my_ack')?['value'])"
ack_yes = {
    "Mark_acknowledged": patch(ACKS, "@" + MY_ACK + "?['ID']", {
        "Title": "@" + MY_ACK + "?['Title']", "AckStatus/Value": "Acknowledged",
        "AcknowledgedOn": "@utcNow()", "AckMethod/Value": "App"}),
}
ack_yes.update(recount("App", RNID, MY_ACK + "?['NoticeTitle']", after("Mark_acknowledged")))
ack_yes["Ack_done"] = finish("Done", "Acknowledged", after("App_Update_notice_count"))

case_ack = {
    "Find_my_ack": get_items(ACKS, "AckKey eq '@{" + RNID + "}|@{" + EMAIL_OD + "}'", top=1),
    "Is_pending": cond(
        "@and(greater(length(body('Find_my_ack')?['value']),0),equals(" + MY_ACK + "?['AckStatus']?['Value'],'Pending'))",
        ack_yes,
        {"Ack_nothing_to_do": finish("Done", "Nothing to do: already acknowledged, or you are not on this notice")},
        after("Find_my_ack")),
}

case_remind = {
    "Can_remind": cond(
        "@and(equals(" + MEMBER + "?['CanPost'],true),equals(body('Get_remind_notice')?['NoticeStatus']?['Value'],'Posted'))",
        {
            "Get_pending_for_notice": get_items(ACKS, "NoticeId eq @{" + RNID + "} and AckStatus eq 'Pending'"),
            "For_each_pending": foreach("@body('Get_pending_for_notice')?['value']", {
                "Send_reminder": message(
                    "@items('For_each_pending')?['PersonEmail']",
                    "<p><strong>Reminder:</strong> please acknowledge the notice \"@{items('For_each_pending')?['NoticeTitle']}\". "
                    "Use the Acknowledge button on the card in this chat, or the Team Notices app.</p>"),
                "Stamp_reminded": patch(ACKS, "@items('For_each_pending')?['ID']", {
                    "Title": "@items('For_each_pending')?['Title']", "LastRemindedOn": "@utcNow()"}, after("Send_reminder")),
            }, after("Get_pending_for_notice")),
            "Remind_done": finish("Done", "@concat('Reminded ',string(length(body('Get_pending_for_notice')?['value'])),' people')",
                                  after("For_each_pending", status=("Succeeded", "Failed"))),
        },
        {"Remind_rejected": finish("Rejected", "Only posters can send reminders, and only on a current notice")},
        after("Get_remind_notice")),
}
case_remind = dict({"Get_remind_notice": get_item(NOTICES, "@int(" + RNID + ")")}, **case_remind)

tn1_actions = {
    "Init_Version": {"runAfter": {}, "type": "InitializeVariable",
                     "inputs": {"variables": [{"name": "Version", "type": "integer", "value": 1}]}},
    "Requester_email": compose("@toLower(coalesce(triggerBody()?['Author']?['Email'],''))", after("Init_Version")),
    "Request_notice_id": compose("@first(split(string(coalesce(triggerBody()?['NoticeId'],0)),'.'))", after("Requester_email")),
    "Get_member": get_items(MEMBERS, "Email eq '@{" + EMAIL_OD + "}' and Active eq 1", after("Request_notice_id"), top=1),
    "Handle_request": {"runAfter": after("Get_member"), "type": "Scope", "actions": {"Is_member": cond(
        "@greater(length(body('Get_member')?['value']),0)",
        {"Route_request": {
            "runAfter": {}, "type": "Switch", "expression": "@triggerBody()?['RequestType']?['Value']",
            "cases": {
                "Post": {"case": "Post", "actions": case_post},
                "Acknowledge": {"case": "Acknowledge", "actions": case_ack},
                "Remind": {"case": "Remind", "actions": case_remind},
            },
            "default": {"actions": {"Unknown_type": finish("Rejected", "Unknown request type")}},
        }},
        {"Not_a_member": finish("Rejected", "You are not on the Team Notice Members list")})}},
    "Request_failed": finish("Rejected", "The flow hit an error. Check the TN-1 run history.",
                             after("Handle_request", status=("Failed", "TimedOut"))),
}

# ---------------------------------------------------------------- TN-2 Send Card
NID2 = "outputs('Notice_id')"
NOTICE = "body('Get_notice')"
card = {
    "type": "AdaptiveCard",
    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
    "version": "1.4",
    "body": [
        {"type": "TextBlock", "size": "Small", "weight": "Bolder", "color": "Accent", "wrap": True,
         "text": "@{toUpper(coalesce(" + NOTICE + "?['Category']?['Value'],'Notice'))}  |  Posted by @{" + NOTICE + "?['PostedByName']}"},
        {"type": "TextBlock", "size": "Large", "weight": "Bolder", "wrap": True, "text": "@{" + NOTICE + "?['Title']}"},
        {"type": "TextBlock", "wrap": True, "text": "@{" + NOTICE + "?['Body']}"},
        {"type": "FactSet", "facts": [
            {"title": "Effective", "value": "@{formatDateTime(" + NOTICE + "?['EffectiveDate'],'MMM d, yyyy')}"},
            {"title": "Acknowledge by", "value": "@{formatDateTime(" + NOTICE + "?['AckDueDate'],'MMM d, yyyy')}"},
        ]},
        {"type": "TextBlock", "wrap": True, "isVisible": "@not(empty(" + NOTICE + "?['RelatedLink']))",
         "text": "@{concat('[Related SOP or ticket](',coalesce(" + NOTICE + "?['RelatedLink'],''),')')}"},
    ],
    "actions": [
        {"type": "Action.Submit", "title": "I have read this: Acknowledge", "style": "positive", "data": {"action": "acknowledge"}},
    ],
}

card_answered = {
    "Get_ack_now": get_item(ACKS, "@triggerBody()?['ID']"),
    "Still_pending": cond(
        "@equals(body('Get_ack_now')?['AckStatus']?['Value'],'Pending')",
        dict(
            {"Mark_acknowledged": patch(ACKS, "@triggerBody()?['ID']", {
                "Title": "@body('Get_ack_now')?['Title']", "AckStatus/Value": "Acknowledged",
                "AcknowledgedOn": "@utcNow()", "AckMethod/Value": "Teams card"})},
            **recount("Card", NID2, NOTICE + "?['Title']", after("Mark_acknowledged"))),
        {}, after("Get_ack_now")),
}

post_card = conn(TEAMS, "PostCardAndWaitForResponse", {
    "poster": "Flow bot", "location": "Chat with Flow bot",
    "body/body/recipient/to": "@{triggerBody()?['PersonEmail']};",
    "body/body/messageBody": "@{string(outputs('Card'))}",
    "body/body/updateMessage": "Acknowledged. Thank you, @{triggerBody()?['PersonName']}. Your acknowledgement is recorded.",
}, after("Card"), kind="OpenApiConnectionWebhook")
post_card["limit"] = {"timeout": "P29D"}

tn2_actions = {
    "Notice_id": compose("@first(split(string(triggerBody()?['NoticeId']),'.'))"),
    "Get_notice": get_item(NOTICES, "@int(" + NID2 + ")", after("Notice_id")),
    "Card": compose(card, after("Get_notice")),
    "Post_card_and_wait": post_card,
    "Card_answered": cond("@equals(actions('Post_card_and_wait')?['status'],'Succeeded')", card_answered, {},
                          after("Post_card_and_wait", status=("Succeeded", "TimedOut"))),
}

# ---------------------------------------------------------------- TN-3 Due Date Summary
OUTLOOK = "shared_office365"
API_INFO[OUTLOOK] = ("Office 365 Outlook", "https://connectoricons-prod.azureedge.net/releases/v1.0.1676/1.0.1676.3222/office365/icon.png")
SUMMARY_MAILBOX = CFG["summaryMailbox"]
APP_URL = CFG["appUrl"]
N = "items('For_each_due_notice')"
DUE = "formatDateTime(coalesce(" + N + "?['AckDueDate'],'9999-12-31'),'MMM d')"

summary_html = (
    "<p><b>@{" + N + "?['Title']}</b><br>"
    "Posted @{formatDateTime(convertFromUtc(coalesce(" + N + "?['PostedOn'],utcNow()),'" + TZ + "'),'MMM d')} "
    "by @{" + N + "?['PostedByName']}. Acknowledgement was due @{" + DUE + "}.</p>"
    "<p><b>Not Reviewed (@{length(body('Not_acknowledged'))})</b><br>"
    "@{if(equals(length(body('Not_acknowledged')),0),'Nobody. Everyone has acknowledged.',join(body('Select_pending_names'),', '))}</p>"
    "<p><b>Acknowledged (@{length(body('Acknowledged'))})</b><br>@{join(body('Select_acknowledged_lines'),'<br>')}</p>"
    "<p><a href=\"" + APP_URL + "\">Open Team Notices</a></p>"
)

per_due = {
    "Get_rows": get_items(ACKS, "NoticeId eq @{" + N + "?['ID']}"),
    "Not_acknowledged": query("@body('Get_rows')?['value']", "@equals(item()?['AckStatus']?['Value'],'Pending')", after("Get_rows")),
    "Acknowledged": query("@body('Get_rows')?['value']", "@equals(item()?['AckStatus']?['Value'],'Acknowledged')",
                          after("Not_acknowledged")),
    "Select_pending_names": select("@body('Not_acknowledged')", "@item()?['PersonName']", after("Acknowledged")),
    "Select_acknowledged_lines": select(
        "@body('Acknowledged')",
        "@concat(item()?['PersonName'],', ',formatDateTime(convertFromUtc(coalesce(item()?['AcknowledgedOn'],utcNow()),'" + TZ + "'),'MMM d h:mm tt'))",
        after("Select_pending_names")),
    "Send_summary": conn(OUTLOOK, "SharedMailboxSendEmailV2", {
        "emailMessage/MailboxAddress": SUMMARY_MAILBOX,
        "emailMessage/To": "@{join(body('Select_poster_emails'),';')}",
        "emailMessage/Subject": "Acknowledgement summary - @{" + N + "?['Title']} "
                                "(@{length(body('Acknowledged'))} of @{length(body('Get_rows')?['value'])})",
        "emailMessage/Body": summary_html,
        "emailMessage/Importance": "Normal",
    }, after("Select_acknowledged_lines")),
    "Mark_summary_sent": patch(NOTICES, "@" + N + "?['ID']", {"Title": "@" + N + "?['Title']", "EscalatedOn": "@utcNow()"},
                               after("Send_summary")),
}

tn3_actions = {
    "Today": compose("@formatDateTime(convertFromUtc(utcNow(),'" + TZ + "'),'yyyy-MM-dd')"),
    "Get_posters": get_items(MEMBERS, "CanPost eq 1 and Active eq 1 and ReceivesEmail eq 1", after("Today"), top=500),
    "Select_poster_emails": select("@body('Get_posters')?['value']", "@item()?['Email']", after("Get_posters")),
    "Get_posted_notices": get_items(NOTICES, "NoticeStatus eq 'Posted'", after("Select_poster_emails")),
    "Due_and_not_sent": query(
        "@body('Get_posted_notices')?['value']",
        "@and(empty(item()?['EscalatedOn']),"
        "lessOrEquals(formatDateTime(coalesce(item()?['AckDueDate'],'9999-12-31'),'yyyy-MM-dd'),outputs('Today')),"
        "greaterOrEquals(formatDateTime(coalesce(item()?['AckDueDate'],'9999-12-31'),'yyyy-MM-dd'),"
        "formatDateTime(addDays(convertFromUtc(utcNow(),'" + TZ + "'),-7),'yyyy-MM-dd')),"
        "greater(coalesce(item()?['AudienceCount'],0),0))",
        after("Get_posted_notices")),
    "For_each_due_notice": foreach("@body('Due_and_not_sent')", per_due, after("Due_and_not_sent")),
}
tn3_trigger = {"Recurrence": {"type": "Recurrence", "recurrence": {
    "frequency": "Day", "interval": 1, "timeZone": TZ, "schedule": {"hours": [17], "minutes": [0]}}}}


# ---------------------------------------------------------------- packaging
def build(file_name, display, description, triggers, actions, apis):
    flow_id = str(uuid.uuid4())   # source flow id, lives only in definition.json
    flow_res = str(uuid.uuid4())  # package resource key = asset path = folder name
    api_res = {k: str(uuid.uuid4()) for k in apis}
    conn_res = {k: str(uuid.uuid4()) for k in apis}
    conn_names = {k: k.replace("shared_", "shared-")[:22] + "-" + str(uuid.uuid4()) for k in apis}
    definition = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {"$connections": {"defaultValue": {}, "type": "Object"},
                       "$authentication": {"defaultValue": {}, "type": "SecureObject"}},
        "triggers": triggers, "actions": actions, "outputs": {},
    }
    flow_def = {
        "name": flow_id, "id": f"/providers/Microsoft.Flow/flows/{flow_id}", "type": "Microsoft.Flow/flows",
        "properties": {
            "apiId": "/providers/Microsoft.PowerApps/apis/shared_logicflows", "displayName": display,
            "definition": definition,
            "connectionReferences": {k: {"connectionName": conn_names[k], "source": "Embedded",
                                         "id": f"/providers/Microsoft.PowerApps/apis/{k}", "tier": "NotSpecified"} for k in apis},
            "flowFailureAlertSubscribed": False,
        },
    }
    resources = {flow_res: {
        "type": "Microsoft.Flow/flows",
        "suggestedCreationType": "New", "creationType": "Existing, New, Update",
        "details": {"displayName": display}, "configurableBy": "User", "hierarchy": "Root",
        "dependsOn": list(api_res.values()) + list(conn_res.values()),
    }}
    for k in apis:
        disp, icon = API_INFO[k]
        resources[api_res[k]] = {
            "id": f"/providers/Microsoft.PowerApps/apis/{k}", "name": k, "type": "Microsoft.PowerApps/apis",
            "suggestedCreationType": "Existing", "details": {"displayName": disp, "iconUri": icon},
            "configurableBy": "System", "hierarchy": "Child", "dependsOn": [],
        }
        resources[conn_res[k]] = {
            "type": "Microsoft.PowerApps/apis/connections", "suggestedCreationType": "Existing", "creationType": "Existing",
            "details": {"displayName": disp, "iconUri": icon}, "configurableBy": "User", "hierarchy": "Child",
            "dependsOn": [api_res[k]],
        }
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
    manifest = {"schema": "1.0", "details": {
        "displayName": display, "description": description, "createdTime": now,
        "packageTelemetryId": str(uuid.uuid4()), "creator": "N/A", "sourceEnvironment": ""}, "resources": resources}
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, file_name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("Microsoft.Flow/flows/manifest.json",
                   json.dumps({"packageSchemaVersion": "1.0", "flowAssets": {"assetPaths": [flow_res]}}, indent=2))
        z.writestr(f"Microsoft.Flow/flows/{flow_res}/definition.json", json.dumps(flow_def, indent=2))
        z.writestr(f"Microsoft.Flow/flows/{flow_res}/apisMap.json", json.dumps(api_res, indent=2))
        z.writestr(f"Microsoft.Flow/flows/{flow_res}/connectionsMap.json",
                   json.dumps({k: conn_res[k] for k in apis}, indent=2))
    print("wrote", path)


build("TN-1_Process_Request.zip", "TN-1 Process Request",
      "Handles post, acknowledge and remind requests from the Team Notices app.",
      sp_trigger(REQUESTS), tn1_actions, [SP, TEAMS])
build("TN-3_Due_Date_Summary.zip", "TN-3 Due Date Summary",
      "At 5 PM Eastern on each update's acknowledge-by date, emails the posters who has and has not acknowledged.",
      tn3_trigger, tn3_actions, [SP, OUTLOOK])
