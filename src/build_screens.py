"""Generates the four Team Notices canvas screens as .pa.yaml files (paste whole screens into Power Apps Studio)."""
import re

import yaml

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.environ.get("TEAM_NOTICES_SETTINGS", os.path.join(_HERE, "..", "config", "settings.json"))
with open(_CFG_PATH, encoding="utf-8") as _f:
    CFG = json.load(_f)

OUT = os.path.join(_HERE, "..", "out", "screens")
NAVY = "RGBA(22, 36, 58, 1)"
NAVY_ON = "RGBA(42, 61, 92, 1)"
PAGE = "RGBA(243, 245, 248, 1)"
WHITE = "RGBA(255, 255, 255, 1)"
CLEAR = "RGBA(0, 0, 0, 0)"
BLUE = "RGBA(27, 79, 156, 1)"
TEXT = "RGBA(26, 34, 48, 1)"
MUTED = "RGBA(74, 85, 104, 1)"
GREEN = "RGBA(23, 96, 58, 1)"
AMBER = "RGBA(138, 75, 0, 1)"
AMBER_BG = "RGBA(255, 246, 229, 1)"
RED = "RGBA(168, 0, 0, 1)"
RED_BG = "RGBA(253, 236, 236, 1)"
LINE = "RGBA(214, 220, 229, 1)"

ACKS = "'Team Notice Acknowledgements'"
NOTICES = "'Team Notices'"
REQS = "'Team Notice Requests'"
MEMBERS = "'Team Notice Members'"
QUESTIONS = "'Team Notice Questions'"
APP_URL = CFG["appUrl"]
LINK = "<a href='" + APP_URL + "'>Open Team Notices</a>"

INIT = (
    "If(IsBlank(gMe),\n"
    "    Set(gMe, Lower(User().Email));\n"
    f"    Set(gMember, LookUp({MEMBERS}, Email = User().Email));\n"
    "    Set(gCanPost, Coalesce(gMember.CanPost, false) && Coalesce(gMember.Active, false))\n"
    ");\n"
    "If(CountRows(colJustAcked) = 0, Collect(colJustAcked, {Value: 0}))"
)


def ctl(name, kind, variant=None, children=None, meta=None, **props):
    return {"name": name, "kind": kind, "variant": variant, "meta": meta or {}, "props": props, "children": children or []}


def label(name, text, x, y, w, h, size=11, color=TEXT, bold=False, **extra):
    p = dict(Text=text, X=x, Y=y, Width=w, Height=h, Size=size, Color=color)
    if bold:
        p["FontWeight"] = "FontWeight.Semibold"
    p.update(extra)
    return ctl(name, "Label", **p)


def button(name, text, x, y, w, h, on_select, primary=True, **extra):
    p = dict(Text=text, X=x, Y=y, Width=w, Height=h, OnSelect=on_select, Size=11,
             Fill=BLUE if primary else WHITE, Color=WHITE if primary else TEXT,
             HoverFill=BLUE if primary else PAGE, HoverColor=WHITE if primary else TEXT,
             BorderColor=BLUE if primary else "RGBA(138, 149, 166, 1)", BorderThickness=1)
    p.update(extra)
    return ctl(name, "Classic/Button", **p)


def rect(name, x, y, w, h, fill, **extra):
    return ctl(name, "Rectangle", X=x, Y=y, Width=w, Height=h, Fill=fill, **extra)


def header(p, active):
    def nav(key, text, x, w, screen, visible=None, pre=""):
        extra = {"Visible": visible} if visible else {}
        return ctl(f"{p}Nav{key}", "Classic/Button", Text=f'"{text}"', X=x, Y=10, Width=w, Height=44, Size=11,
                   OnSelect=f"{pre}Navigate({screen})", Fill=NAVY_ON if active == key else CLEAR, Color=WHITE,
                   HoverFill=NAVY_ON, HoverColor=WHITE, BorderThickness=0, **extra)
    return [
        rect(f"{p}HdrBar", 0, 0, 1366, 64, NAVY),
        label(f"{p}HdrTitle", '"Team Notices"', 32, 12, 180, 40, size=14, color=WHITE, bold=True),
        nav("Mine", "My notices", 230, 130, "scrMyNotices"),
        nav("Search", "Search", 366, 100, "scrSearch"),
        nav("New", "New update", 472, 130, "scrNewNotice", visible="gCanPost", pre="Set(gCorrect, Blank()); "),
        label(f"{p}HdrUser", "User().FullName", 1006, 12, 328, 40, color="RGBA(213, 221, 234, 1)", Align="Align.Right"),
    ]


# ------------------------------------------------------------------ My notices
MINE_ITEMS = (
    "SortByColumns(\n"
    "    AddColumns(colMine, Ord, If(AckStatus.Value = \"Pending\" && !(NoticeId in colJustAcked.Value), 0, 1)),\n"
    "    \"Ord\", SortOrder.Ascending, \"ID\", SortOrder.Descending\n"
    ")"
)
LOAD_MINE = f"ClearCollect(colMine, Sort(Filter({ACKS}, PersonEmail = gMe), ID, SortOrder.Descending))"

my_notices = {
    "name": "scrMyNotices",
    "props": {"Fill": PAGE, "OnVisible": INIT + ";\n" + LOAD_MINE},
    "children": header("mn", "Mine") + [
        label("mnHeading", '"My notices"', 32, 84, 600, 44, size=18, bold=True),
        button("mnBtnRefresh", '"Refresh"', 1214, 86, 120, 40, LOAD_MINE, primary=False),
        label("mnEmpty", '"No notices yet. New updates will show here."', 32, 150, 900, 40, color=MUTED,
              Visible="CountRows(colMine) = 0"),
        ctl("mnGal", "Gallery", variant="Vertical", X=32, Y=140, Width=1302, Height=604, Items=MINE_ITEMS,
            TemplateSize=84, TemplatePadding=0, children=[
                rect("mnRowBg", 0, 4, "Parent.TemplateWidth", 76, WHITE, BorderColor=LINE, BorderThickness=1),
                label("mnRowTitle", "ThisItem.NoticeTitle", 20, 10, 900, 34, size=12, bold=True),
                label("mnRowStatus",
                      "If(ThisItem.Ord = 0, \"Not Reviewed\", \"Acknowledged\" & "
                      "If(IsBlank(ThisItem.AcknowledgedOn), \"\", \" \" & Text(ThisItem.AcknowledgedOn, \"mmm d, yyyy\")))",
                      20, 42, 900, 30, size=10, color=f"If(ThisItem.Ord = 0, {RED}, {GREEN})", bold=True),
                button("mnRowOpen", "If(ThisItem.Ord = 0, \"Read and acknowledge\", \"Open\")", 1062, 20, 220, 44,
                       f"Set(gNotice, LookUp({NOTICES}, ID = ThisItem.NoticeId));\nNavigate(scrNotice)",
                       Fill=f"If(ThisItem.Ord = 0, {BLUE}, {WHITE})", Color=f"If(ThisItem.Ord = 0, {WHITE}, {TEXT})"),
            ]),
    ],
}

# ------------------------------------------------------------------ Notice detail, questions, roster
LOAD_ROSTER = f"ClearCollect(colRoster, Filter({ACKS}, NoticeId = gNotice.ID))"
LOAD_Q = f"ClearCollect(colQ, Filter({QUESTIONS}, NoticeId = gNotice.ID))"
I_ACKED = "(gMyAck.AckStatus.Value = \"Acknowledged\" || gNotice.ID in colJustAcked.Value)"
PENDING_N = "CountRows(Filter(colRoster, AckStatus.Value = \"Pending\"))"
ROSTER_VIS = "gCanPost && locTab = \"R\""
Q_VIS = "locTab = \"Q\""
DLG_VIS = "!IsBlank(locAnswerTo)"
FILE_VIS = "!IsBlank(locFile)"
HAS_FILES = f"!IsEmpty(LookUp({NOTICES}, ID = gNotice.ID).Attachments)"
ANSWERS = "Sort(Filter(colQ, ParentId = ThisItem.ID), ID)"
REMIND = (
    LOAD_ROSTER + ";\n"
    "If(" + PENDING_N + " > 0 && !locReminded,\n"
    "UpdateContext({locReminded: true});\n"
    "Office365Outlook.SendEmailV2(\n"
    f"    Concat(Filter(colRoster, AckStatus.Value = \"Pending\" && PersonEmail in Filter({MEMBERS}, Active && ReceivesEmail).Email), PersonEmail, \";\"),\n"
    "    \"Reminder - please acknowledge: \" & gNotice.Title,\n"
    "    \"<p>This is a reminder to read and acknowledge the update <b>\" & gNotice.Title & \"</b>.</p>\" &\n"
    "    \"<p>It is due \" & Text(gNotice.AckDueDate, \"mmm d, yyyy\") & \".<br>" + LINK + "</p>\" &\n"
    "    \"<p>Open the app, read the update and select Acknowledge.</p>\",\n"
    "    {Importance: \"High\"}\n"
    ");\n"
    "Notify(\"Reminder emailed to \" & " + PENDING_N + " & \" people.\", NotificationType.Success),\n"
    "Notify(\"No reminder sent. Either everyone has acknowledged or you already sent one from this screen.\", NotificationType.Information)\n"
    ")"
)
ASK = (
    "If(!IsBlank(Trim(ntTxtAsk.Text)),\n"
    "    IfError(\n"
    f"        Patch({QUESTIONS}, Defaults({QUESTIONS}), {{Title: User().FullName, NoticeId: gNotice.ID, ParentId: 0, Message: Trim(ntTxtAsk.Text)}}),\n"
    "        Notify(\"Could not save your question. \" & FirstError.Message, NotificationType.Error),\n"
    f"        If(Coalesce(LookUp({MEMBERS}, Email = gNotice.PostedByEmail).ReceivesEmail, true), Office365Outlook.SendEmailV2(\n"
    "            gNotice.PostedByEmail,\n"
    "            \"Question on your update: \" & gNotice.Title,\n"
    "            \"<p>\" & User().FullName & \" asked:</p><p>&quot;\" & Trim(ntTxtAsk.Text) & \"&quot;</p>\" &\n"
    "            \"<p>" + LINK + " to answer. Everyone will see your answer in the app.</p>\"\n"
    "        )),\n"
    "        Reset(ntTxtAsk); Notify(\"Your question is posted, but the email to the poster failed. \" & FirstError.Message, NotificationType.Warning),\n"
    "        Reset(ntTxtAsk); Notify(\"Question posted.\", NotificationType.Success)\n"
    "    );\n"
    "    " + LOAD_Q + "\n"
    ")"
)
ANSWER = (
    "If(gCanPost && !IsBlank(Trim(ntTxtAnswer.Text)),\n"
    "    IfError(\n"
    f"        Patch({QUESTIONS}, Defaults({QUESTIONS}), {{Title: User().FullName, NoticeId: gNotice.ID, ParentId: locAnswerTo.ID, Message: Trim(ntTxtAnswer.Text)}}),\n"
    "        Notify(\"Could not save your answer. \" & FirstError.Message, NotificationType.Error),\n"
    f"        If(Coalesce(LookUp({MEMBERS}, Email = locAnswerTo.'Created By'.Email).ReceivesEmail, true), Office365Outlook.SendEmailV2(\n"
    "            locAnswerTo.'Created By'.Email,\n"
    "            \"Answer to your question: \" & gNotice.Title,\n"
    "            \"<p>You asked: &quot;\" & locAnswerTo.Message & \"&quot;</p>\" &\n"
    "            \"<p>\" & User().FullName & \" answered: &quot;\" & Trim(ntTxtAnswer.Text) & \"&quot;</p>\" &\n"
    "            \"<p>" + LINK + "</p>\"\n"
    "        )),\n"
    "        Reset(ntTxtAnswer); UpdateContext({locAnswerTo: Blank()}); Notify(\"Your answer is posted, but the email to the person who asked failed. \" & FirstError.Message, NotificationType.Warning),\n"
    "        Reset(ntTxtAnswer); UpdateContext({locAnswerTo: Blank()}); Notify(\"Answer posted.\", NotificationType.Success)\n"
    "    );\n"
    "    " + LOAD_Q + "\n"
    ")"
)


def tab(name, text, x, w, key, **extra):
    return button(name, text, x, 98, w, 40, "UpdateContext({locTab: \"" + key + "\"})",
                  Fill=f"If(locTab = \"{key}\", {BLUE}, {WHITE})", Color=f"If(locTab = \"{key}\", {WHITE}, {TEXT})", **extra)


notice = {
    "name": "scrNotice",
    "props": {"Fill": PAGE, "OnVisible": INIT + ";\nRefresh(" + NOTICES + ");\nUpdateContext({locReminded: false, locTab: \"Q\", locAnswerTo: Blank(), locFile: Blank()});\n" +
              f"Set(gMyAck, LookUp({ACKS}, AckKey = gNotice.ID & \"|\" & gMe));\n" + LOAD_ROSTER + ";\n" + LOAD_Q},
    "children": header("nt", "None") + [
        rect("ntCard", 32, 84, 580, 660, WHITE, BorderColor=LINE, BorderThickness=1),
        button("ntBtnBack", '"Back"', 52, 100, 100, 40, "Back()", primary=False),
        label("ntCategory",
              "Upper(gNotice.Category.Value) & \"   Version \" & gNotice.VersionNumber & "
              "If(gNotice.NoticeStatus.Value = \"Superseded\", \"   SUPERSEDED BY A NEWER VERSION\", \"\")",
              52, 150, 540, 28, size=9, color=BLUE, bold=True),
        label("ntTitle", "gNotice.Title", 52, 178, 540, 64, size=15, bold=True, VerticalAlign="VerticalAlign.Top"),
        label("ntBody", "gNotice.Body", 52, 246, 540, "If(" + HAS_FILES + ", 186, 280)", size=11, VerticalAlign="VerticalAlign.Top",
              Overflow="Overflow.Scroll"),
        ctl("ntGalFiles", "Gallery", variant="Vertical", X=52, Y=436, Width=540, Height=92, Visible=HAS_FILES,
            Items=f"LookUp({NOTICES}, ID = gNotice.ID).Attachments", TemplateSize=92, TemplatePadding=0, WrapCount=5, children=[
                ctl("ntFileImg", "Image", X=2, Y=2, Width=102, Height=62, Image="ThisItem.Value",
                    ImagePosition="ImagePosition.Fit", OnSelect="UpdateContext({locFile: ThisItem})"),
                label("ntFileName", "ThisItem.DisplayName", 2, 66, 102, 22, size=8, color=MUTED, Wrap="false",
                      OnSelect="UpdateContext({locFile: ThisItem})"),
            ]),
        label("ntMeta",
              "\"Posted \" & Text(gNotice.PostedOn, \"mmm d, yyyy h:mm AM/PM\") & \" by \" & gNotice.PostedByName & Char(10) & "
              "\"Effective \" & Text(gNotice.EffectiveDate, \"mmm d, yyyy\") & Char(10) & "
              "\"Acknowledge by \" & Text(gNotice.AckDueDate, \"mmm d, yyyy\")",
              52, 532, 540, 78, size=10, color=MUTED, VerticalAlign="VerticalAlign.Top"),
        button("ntBtnLink", '"Open related SOP or ticket"', 52, 614, 260, 40, "Launch(gNotice.RelatedLink)", primary=False,
               Visible="!IsBlank(gNotice.RelatedLink)"),
        button("ntBtnAck", '"I have read this: Acknowledge"', 52, 672, 320, 52,
               "IfError(\n"
               f"    Patch({REQS}, Defaults({REQS}), {{Title: \"Acknowledge\", RequestType: {{Value: \"Acknowledge\"}}, NoticeId: gNotice.ID}}),\n"
               "    Notify(\"Could not record your acknowledgement. \" & FirstError.Message, NotificationType.Error),\n"
               "    Collect(colJustAcked, {Value: gNotice.ID});\n"
               "    Notify(\"Acknowledged. Thank you.\", NotificationType.Success)\n"
               ")",
               Visible=f"!IsBlank(gMyAck) && !{I_ACKED}"),
        label("ntAcked",
              "\"You acknowledged this update\" & If(IsBlank(gMyAck.AcknowledgedOn), \"\", \" on \" & "
              "Text(gMyAck.AcknowledgedOn, \"mmm d, yyyy h:mm AM/PM\"))",
              52, 672, 540, 52, size=11, color=GREEN, bold=True, Visible=f"!IsBlank(gMyAck) && {I_ACKED}"),
        # side card with tabs
        rect("ntSideCard", 632, 84, 702, 660, WHITE, BorderColor=LINE, BorderThickness=1),
        tab("ntTabQ", "\"Questions (\" & CountRows(Filter(colQ, ParentId = 0)) & \")\"", 652, 190, "Q"),
        tab("ntTabR", '"Acknowledgements"', 850, 200, "R", Visible="gCanPost"),
        # questions tab
        label("ntAskLbl", '"Ask a question. Everyone can see the questions and answers."', 652, 148, 662, 28, size=10,
              color=MUTED, Visible=Q_VIS),
        ctl("ntTxtAsk", "Classic/TextInput", X=652, Y=178, Width=512, Height=64, Size=11, Mode="TextMode.MultiLine",
            Default='""', Visible=Q_VIS),
        button("ntBtnAsk", '"Ask"', 1174, 178, 140, 64, ASK, Visible=Q_VIS,
               DisplayMode="If(IsBlank(Trim(ntTxtAsk.Text)), DisplayMode.Disabled, DisplayMode.Edit)"),
        label("ntQEmpty", '"No questions yet."', 652, 256, 662, 36, size=10, color=MUTED,
              Visible=Q_VIS + " && CountRows(Filter(colQ, ParentId = 0)) = 0"),
        ctl("ntGalQ", "Gallery", variant="Vertical", X=652, Y=254, Width=662, Height=474, Visible=Q_VIS,
            Items="Sort(Filter(colQ, ParentId = 0), ID, SortOrder.Descending)", TemplateSize=150, TemplatePadding=0, children=[
                label("ntQMeta", "ThisItem.Title & \" asked on \" & Text(ThisItem.Created, \"mmm d, h:mm AM/PM\")",
                      12, 6, 500, 26, size=9, color=MUTED, bold=True),
                label("ntQText", "ThisItem.Message", 12, 32, 638, 46, size=11, bold=True, VerticalAlign="VerticalAlign.Top",
                      Overflow="Overflow.Scroll"),
                label("ntQAnswers",
                      "If(CountRows(" + ANSWERS + ") = 0, \"Not answered yet\", "
                      "Concat(" + ANSWERS + ", Title & \" answered \" & Char(34) & Message & Char(34), Char(10)))",
                      12, 80, 638, 60, size=10, color=f"If(CountRows({ANSWERS}) = 0, {MUTED}, {GREEN})",
                      VerticalAlign="VerticalAlign.Top", Overflow="Overflow.Scroll"),
                button("ntQAnswerBtn", '"Answer"', 532, 2, 118, 32, "UpdateContext({locAnswerTo: ThisItem})", primary=False,
                       Visible="gCanPost"),
                rect("ntQLine", 0, 146, "Parent.TemplateWidth", 1, LINE),
            ]),
        # acknowledgements tab, posters only
        label("ntRosterSummary",
              "CountRows(Filter(colRoster, AckStatus.Value = \"Acknowledged\")) & \" of \" & CountRows(colRoster) & \" acknowledged\"",
              652, 150, 400, 40, size=14, bold=True, Visible=ROSTER_VIS),
        button("ntBtnRefresh", '"Refresh"', 1204, 150, 110, 40, LOAD_ROSTER, primary=False, Visible=ROSTER_VIS),
        button("ntBtnRemind", "\"Email a reminder to the \" & " + PENDING_N + " & \" not reviewed\"", 652, 200, 340, 40, REMIND,
               Visible=ROSTER_VIS + " && " + PENDING_N + " > 0 && gNotice.NoticeStatus.Value = \"Posted\""),
        button("ntBtnCorrect", '"Post corrected version"', 1084, 200, 230, 40, "Set(gCorrect, gNotice);\nNavigate(scrNewNotice)",
               primary=False, Visible=ROSTER_VIS + " && gNotice.NoticeStatus.Value = \"Posted\""),
        label("ntColPerson", '"Teammate"', 664, 250, 240, 30, size=10, color=MUTED, bold=True, Visible=ROSTER_VIS),
        label("ntColStatus", '"Status"', 904, 250, 140, 30, size=10, color=MUTED, bold=True, Visible=ROSTER_VIS),
        label("ntColWhen", '"Acknowledged on"', 1044, 250, 270, 30, size=10, color=MUTED, bold=True, Visible=ROSTER_VIS),
        ctl("ntGalRoster", "Gallery", variant="Vertical", X=652, Y=282, Width=662, Height=446, Visible=ROSTER_VIS,
            Items=("SortByColumns(\n"
                   "    AddColumns(colRoster, Ord, If(AckStatus.Value = \"Pending\", 0, 1)),\n"
                   "    \"Ord\", SortOrder.Ascending, \"PersonName\", SortOrder.Ascending\n"
                   ")"),
            TemplateSize=40, TemplatePadding=0, TemplateFill=f"If(ThisItem.Ord = 0, {RED_BG}, {CLEAR})", children=[
                label("ntRowPerson", "ThisItem.PersonName", 12, 0, 240, 40, size=10, bold=True),
                label("ntRowStatus", "If(ThisItem.Ord = 0, \"Not Reviewed\", \"Acknowledged\")", 252, 0, 140, 40, size=10,
                      color=f"If(ThisItem.Ord = 0, {RED}, {GREEN})", bold=True),
                label("ntRowWhen",
                      "If(IsBlank(ThisItem.AcknowledgedOn), \"\", Text(ThisItem.AcknowledgedOn, \"mmm d, h:mm AM/PM\"))",
                      392, 0, 260, 40, size=10),
            ]),
        # answer dialog
        rect("ntDim", 0, 0, 1366, 768, "RGBA(0, 0, 0, 0.5)", Visible=DLG_VIS),
        rect("ntDlg", 383, 164, 600, 440, WHITE, Visible=DLG_VIS),
        label("ntDlgTitle", '"Answer this question"', 415, 184, 536, 44, size=16, bold=True, Visible=DLG_VIS),
        label("ntDlgQ", "locAnswerTo.Title & \" asked \" & Char(34) & locAnswerTo.Message & Char(34)", 415, 232, 536, 90,
              size=11, color=MUTED, Visible=DLG_VIS, VerticalAlign="VerticalAlign.Top", Overflow="Overflow.Scroll"),
        ctl("ntTxtAnswer", "Classic/TextInput", X=415, Y=330, Width=536, Height=170, Size=11, Mode="TextMode.MultiLine",
            Default='""', Visible=DLG_VIS),
        button("ntDlgSend", '"Post answer"', 415, 524, 180, 52, ANSWER, Visible=DLG_VIS,
               DisplayMode="If(IsBlank(Trim(ntTxtAnswer.Text)), DisplayMode.Disabled, DisplayMode.Edit)"),
        button("ntDlgCancel", '"Cancel"', 611, 524, 140, 52, "Reset(ntTxtAnswer);\nUpdateContext({locAnswerTo: Blank()})",
               primary=False, Visible=DLG_VIS),
        # attachment viewer
        rect("ntFileDim", 0, 0, 1366, 768, "RGBA(0, 0, 0, 0.7)", Visible=FILE_VIS),
        rect("ntFilePanel", 133, 44, 1100, 680, WHITE, Visible=FILE_VIS),
        label("ntFileTitle", "locFile.DisplayName", 157, 56, 700, 40, size=12, bold=True, Visible=FILE_VIS),
        button("ntFileOpen", '"Open or download"', 873, 56, 200, 40, "Launch(locFile.AbsoluteUri)", primary=False,
               Visible=FILE_VIS),
        button("ntFileClose", '"Close"', 1089, 56, 120, 40, "UpdateContext({locFile: Blank()})", Visible=FILE_VIS),
        ctl("ntFileBig", "Image", X=157, Y=108, Width=1052, Height=596, Image="locFile.Value",
            ImagePosition="ImagePosition.Fit", Visible=FILE_VIS),
    ],
}

# ------------------------------------------------------------------ New update
CATS = '["Process change", "Policy", "Outage", "Tool update", "Other"]'
SUBJECT = ("If(locTest, \"TEST - \", \"\") & If(IsBlank(gCorrect), \"Action needed - \", \"Corrected, action needed - \") & "
           "Trim(nnTxtTitle.Text)")
HTML = (
    "\"<p><b>\" & nnDrpCategory.Selected.Value & \"</b></p><h2>\" & Trim(nnTxtTitle.Text) & \"</h2>\" &\n"
    "        \"<p>\" & Substitute(nnTxtBody.Text, Char(10), \"<br>\") & \"</p>\" &\n"
    "        \"<p><b>Effective</b> \" & Text(nnDateEffective.SelectedDate, \"mmm d, yyyy\") & "
    "\"<br><b>Please acknowledge by</b> \" & Text(nnDateDue.SelectedDate, \"mmm d, yyyy\") & \"<br>" + LINK + "</p>\" &\n"
    "        \"<p><b>Action needed</b> Open the Team Notices app, read this update and select Acknowledge.</p>\" &\n"
    "        If(!IsBlank(Trim(nnTxtLink.Text)), \"<p><a href='\" & Trim(nnTxtLink.Text) & \"'>Related SOP or ticket</a></p>\", \"\") &\n"
    "        \"<p>Please let me know if you have any questions. You can reply to this email or ask in the app, "
    "where everyone can see the answer.</p>\""
)
PAYLOAD = (
    "JSON({\n"
    "    title: If(locTest, \"TEST - \", \"\") & Trim(nnTxtTitle.Text),\n"
    "    category: nnDrpCategory.Selected.Value,\n"
    "    body: nnTxtBody.Text,\n"
    "    effectiveDate: Text(nnDateEffective.SelectedDate, \"yyyy-mm-dd\"),\n"
    "    ackDueDate: Text(nnDateDue.SelectedDate, \"yyyy-mm-dd\"),\n"
    "    relatedLink: Trim(nnTxtLink.Text),\n"
    "    supersedesId: If(IsBlank(gCorrect) || locTest, \"\", Text(gCorrect.ID)),\n"
    "    recipients: Concat(colTo, Lower(Email), \";\"),\n"
    "    testOnly: locTest\n"
    "}, JSONFormat.Compact)"
)
SEND = (
    "If(gCanPost,\n"
    "    UpdateContext({locConfirm: false});\n"
    "    If(locTest,\n"
    f"        ClearCollect(colTo, ShowColumns(Filter({MEMBERS}, Email = User().Email), Title, Email)),\n"
    "        ClearCollect(colTo, ShowColumns(Filter(colPick, Sel), Title, Email))\n"
    "    );\n"
    "    ClearCollect(colAtt, ForAll(nnAttach.Attachments, {Name: Name, ContentBytes: Value}));\n"
    "    SubmitForm(nnForm)\n"
    ")"
)
ON_SUCCESS = (
    "IfError(\n"
    "    Office365Outlook.SendEmailV2(\n"
    "        Concat(colTo, Email, \";\"),\n"
    "        " + SUBJECT + ",\n"
    "        " + HTML + ",\n"
    "        {Importance: \"High\", Attachments: colAtt}\n"
    "    ),\n"
    "    Notify(\"Saved, but the email failed to send. \" & FirstError.Message, NotificationType.Error),\n"
    "    Notify(If(locTest, \"Test sent to you only.\", \"Update sent to \" & CountRows(colTo) & \" people.\"), NotificationType.Success);\n"
    "    Set(gCorrect, Blank());\n"
    "    Reset(nnTxtTitle); Reset(nnTxtBody); Reset(nnTxtLink); Reset(nnDrpCategory); Reset(nnDateEffective); Reset(nnDateDue);\n"
    "    NewForm(nnForm);\n"
    "    Navigate(scrMyNotices)\n"
    ")"
)
PICK_VIS = "locConfirm && !locTest"
TEST_VIS = "locConfirm && locTest"
READY = "If(!gCanPost || IsBlank(Trim(nnTxtTitle.Text)) || IsBlank(Trim(nnTxtBody.Text)), DisplayMode.Disabled, DisplayMode.Edit)"
DSI = "DataSourceInfo([@'Team Notice Requests'],DataSourceInfo.DisplayName,'%s')"
NAVY_CARD = "RGBA(0, 18, 107, 1)"


def field_label(name, text, x, y, w=300):
    return label(name, f'"{text}"', x, y, w, 28, size=10, bold=True)


def card(tag, variant, field, source_col, update, value_ctl, y, visible, key_text="Parent.DisplayName", required="false"):
    """One form card, shaped like the cards Power Apps Studio generates (same control types and versions)."""
    key, val, err, star = f"nnKey{tag}", f"nnVal{tag}", f"nnErr{tag}", f"nnStar{tag}"
    if tag == "Attach":
        val = "nnAttach"
    value_ctl = dict(value_ctl, name=val)
    return ctl(f"nnCard{tag}", "TypedDataCard@1.0.7", variant=variant, meta={"IsLocked": "false"},
               BorderColor=NAVY_CARD, DataField=f'"{field}"', Default=f"ThisItem.{source_col}",
               DisplayName=DSI % field, Required=required, Update=update, Visible=visible, Width=640, X=0, Y=y,
               children=[
                   ctl(key, "Label@2.5.1", meta={"MetadataKey": "FieldName"}, AutoHeight="true", Color=TEXT,
                       FontWeight="FontWeight.Semibold", Height=26, Size=10, Text=key_text, Width="Parent.Width", Wrap="false",
                       X=0, Y=0),
                   value_ctl,
                   ctl(err, "Label@2.5.1", meta={"MetadataKey": "ErrorMessage"}, AutoHeight="true", Color="RGBA(168, 0, 0, 1)",
                       Height=10, PaddingBottom=0, PaddingLeft=0, PaddingRight=0, PaddingTop=0, Size=10, Text="Parent.Error",
                       Visible="Parent.DisplayMode=DisplayMode.Edit", Width="Parent.Width", X=0, Y=f"{val}.Y + {val}.Height"),
                   ctl(star, "Label@2.5.1", meta={"MetadataKey": "FieldRequired"}, Height=f"{key}.Height", Text='"*"',
                       Visible="false", Width=30, Wrap="false", Y=f"{key}.Y"),
               ])


def text_value(tag):
    return ctl("x", "Classic/TextInput@2.3.2", meta={"MetadataKey": "FieldValue"}, Default="Parent.Default",
               DisplayMode="Parent.DisplayMode", Width="Parent.Width", X=0, Y=f"nnKey{tag}.Y + nnKey{tag}.Height + 2")


form = ctl("nnForm", "Form@2.4.4", variant="Classic", meta={"Layout": "Vertical"},
           BorderColor=CLEAR, DataSource="'Team Notice Requests'", DefaultMode="FormMode.New",
           X=56, Y=548, Width=640, Height=124,
           OnSuccess=ON_SUCCESS,
           OnFailure="Notify(\"Not saved, so nothing was sent. \" & nnForm.Error, NotificationType.Error)",
           children=[
               card("Attach", "ClassicAttachmentsEdit", "{Attachments}", "Attachments", "nnAttach.Attachments",
                    ctl("x", "Attachments@2.3.0", meta={"MetadataKey": "FieldValue"},
                        BorderColor="RGBA(138, 149, 166, 1)", DisplayMode="Parent.DisplayMode", Height=84, Items="Parent.Default",
                        Width="Parent.Width", X=0, Y="nnKeyAttach.Y + nnKeyAttach.Height + 2"),
                    0, "true", key_text='"Images or files (optional)"'),
               card("Title", "ClassicTextualEdit", "Title", "Title", '"Post"', text_value("Title"), 1, "false"),
               card("Type", "ClassicComboBoxEdit", "RequestType", "RequestType", '{Value: "Post"}',
                    ctl("x", "Classic/ComboBox@2.4.0", meta={"MetadataKey": "FieldValue"},
                        DefaultSelectedItems="Parent.Default", DisplayFields='["Value"]', DisplayMode="Parent.DisplayMode",
                        Items="Choices([@'Team Notice Requests'].'RequestType')", SearchFields='["Value"]',
                        SelectMultiple="false", Width="Parent.Width", X=0, Y="nnKeyType.Y + nnKeyType.Height + 2"),
                    2, "false"),
               card("Notice", "ClassicNumberEdit", "NoticeId", "NoticeId", "0", text_value("Notice"), 3, "false"),
               card("Payload", "ClassicTextualEdit", "Payload", "Payload", PAYLOAD, text_value("Payload"), 4, "false"),
           ])

new_notice = {
    "name": "scrNewNotice",
    "props": {"Fill": PAGE, "OnVisible": INIT + ";\nUpdateContext({locConfirm: false, locTest: false});\nNewForm(nnForm)"},
    "children": header("nn", "New") + [
        rect("nnCard", 32, 84, 1302, 660, WHITE, BorderColor=LINE, BorderThickness=1),
        label("nnHeading", "If(IsBlank(gCorrect), \"Post a new update\", \"Post a corrected version of \" & gCorrect.Title)",
              56, 96, 1250, 44, size=16, bold=True),
        field_label("nnLblTitle", "Title", 56, 146),
        ctl("nnTxtTitle", "Classic/TextInput", X=56, Y=174, Width=1254, Height=44, Size=11,
            Default="If(IsBlank(gCorrect), \"\", gCorrect.Title)"),
        field_label("nnLblCategory", "Category", 56, 228),
        ctl("nnDrpCategory", "Classic/DropDown", X=56, Y=256, Width=300, Height=44, Size=11, Items=CATS,
            Default="If(IsBlank(gCorrect), \"Process change\", gCorrect.Category.Value)"),
        field_label("nnLblEffective", "Effective date", 380, 228),
        ctl("nnDateEffective", "Classic/DatePicker", X=380, Y=256, Width=260, Height=44, Size=11,
            DefaultDate="If(IsBlank(gCorrect), Today(), gCorrect.EffectiveDate)"),
        field_label("nnLblDue", "Acknowledge by", 664, 228),
        ctl("nnDateDue", "Classic/DatePicker", X=664, Y=256, Width=260, Height=44, Size=11,
            DefaultDate="DateAdd(Today(), 2, TimeUnit.Days)"),
        field_label("nnLblBody", "What changed", 56, 310),
        ctl("nnTxtBody", "Classic/TextInput", X=56, Y=338, Width=1254, Height=128, Size=11, Mode="TextMode.MultiLine",
            Default="If(IsBlank(gCorrect), \"\", gCorrect.Body)"),
        field_label("nnLblLink", "Related SOP or ticket link (optional)", 56, 472, 500),
        ctl("nnTxtLink", "Classic/TextInput", X=56, Y=500, Width=1254, Height=44, Size=11,
            Default="If(IsBlank(gCorrect), \"\", gCorrect.RelatedLink)"),
        form,
        button("nnBtnSend", '"Send update to team"', 56, 676, 240, 52,
               f"ClearCollect(colPick, AddColumns(Filter({MEMBERS}, Active && ReceivesEmail), Sel, true));\n"
               "UpdateContext({locTest: false, locConfirm: true})",
               DisplayMode=READY),
        button("nnBtnTest", '"Send test to myself only"', 312, 676, 250, 52, "UpdateContext({locTest: true, locConfirm: true})",
               primary=False, DisplayMode=READY, Visible='gMe = "' + CFG["testSenderEmail"].lower() + '"'),
        button("nnBtnCancel", '"Cancel"', 578, 676, 120, 52,
               "Set(gCorrect, Blank());\nNewForm(nnForm);\nNavigate(scrMyNotices)", primary=False),
        label("nnNotPoster", '"Only posters can send updates."', 720, 676, 560, 52, size=11, color=AMBER, bold=True,
              Visible="!gCanPost"),
        # confirm dialog with recipient picker
        rect("nnDim", 0, 0, 1366, 768, "RGBA(0, 0, 0, 0.5)", Visible="locConfirm"),
        rect("nnDlg", 183, 84, 1000, 600, WHITE, Visible="locConfirm"),
        label("nnDlgTitle", "If(locTest, \"Send a test to yourself?\", \"Send this update to the team?\")",
              215, 98, 936, 40, size=16, bold=True, Visible="locConfirm"),
        label("nnDlgNotice", "Char(34) & Trim(nnTxtTitle.Text) & Char(34)", 215, 138, 936, 34, size=11, bold=True,
              Visible="locConfirm", Wrap="false"),
        label("nnDlgTest", '"Only you get the email and the acknowledgement request. Use this to check how it looks."',
              215, 190, 936, 60, size=11, color=MUTED, Visible=TEST_VIS, VerticalAlign="VerticalAlign.Top"),
        label("nnPickLbl", '"Select who this goes to"', 215, 178, 400, 28, size=10, bold=True, Visible=PICK_VIS),
        button("nnPickAll", '"Select all"', 215, 208, 130, 40, "UpdateIf(colPick, true, {Sel: true})", primary=False,
               Visible=PICK_VIS),
        button("nnPickClear", '"Clear"', 353, 208, 110, 40, "UpdateIf(colPick, true, {Sel: false})", primary=False,
               Visible=PICK_VIS),
        ctl("nnGalPick", "Gallery", variant="Vertical", X=215, Y=256, Width=560, Height=340, Visible=PICK_VIS,
            Items="SortByColumns(colPick, \"Title\", SortOrder.Ascending)", TemplateSize=46, TemplatePadding=0, WrapCount=3,
            children=[
                button("nnPickRow", "ThisItem.Title", 3, 3, 178, 40, "Patch(colPick, ThisItem, {Sel: !ThisItem.Sel})",
                       Size=10, Fill=f"If(ThisItem.Sel, {BLUE}, {WHITE})", Color=f"If(ThisItem.Sel, {WHITE}, {TEXT})",
                       HoverFill=f"If(ThisItem.Sel, {BLUE}, {PAGE})", HoverColor=f"If(ThisItem.Sel, {WHITE}, {TEXT})"),
            ]),
        label("nnToLbl", "\"Sending to (\" & CountRows(Filter(colPick, Sel)) & \")\"", 799, 178, 352, 28, size=10, bold=True,
              Visible=PICK_VIS),
        label("nnToNames", "Concat(SortByColumns(Filter(colPick, Sel), \"Title\", SortOrder.Ascending), Title, Char(10))",
              799, 208, 352, 388, size=10, Visible=PICK_VIS, VerticalAlign="VerticalAlign.Top", Overflow="Overflow.Scroll",
              Fill=PAGE, PaddingLeft=10, PaddingTop=8),
        button("nnDlgSend", "If(locTest, \"Send test\", \"Send update\")", 799, 614, 180, 52, SEND, Visible="locConfirm",
               DisplayMode="If(!locTest && CountRows(Filter(colPick, Sel)) = 0, DisplayMode.Disabled, DisplayMode.Edit)"),
        button("nnDlgBack", '"Go back"', 995, 614, 156, 52, "UpdateContext({locConfirm: false})", primary=False,
               Visible="locConfirm"),
    ],
}

# ------------------------------------------------------------------ Search
SEARCH_ITEMS = (
    "SortByColumns(\n"
    f"    Filter(Sort({NOTICES}, ID, SortOrder.Descending),\n"
    "        (srDrpCategory.Selected.Value = \"All categories\" || Category.Value = srDrpCategory.Selected.Value) &&\n"
    "        (IsBlank(srTxtSearch.Text) || srTxtSearch.Text in Title || srTxtSearch.Text in Body)\n"
    "    ),\n"
    "    \"PostedOn\", SortOrder.Descending\n"
    ")"
)
DONE = "ThisItem.AckCount >= ThisItem.AudienceCount"

search = {
    "name": "scrSearch",
    "props": {"Fill": PAGE, "OnVisible": INIT},
    "children": header("sr", "Search") + [
        label("srHeading", '"Find when something changed"', 32, 84, 700, 44, size=18, bold=True),
        ctl("srTxtSearch", "Classic/TextInput", X=32, Y=136, Width=900, Height=44, Size=11, Default='""'),
        ctl("srDrpCategory", "Classic/DropDown", X=948, Y=136, Width=386, Height=44, Size=11,
            Items='["All categories", "Process change", "Policy", "Outage", "Tool update", "Other"]',
            Default='"All categories"'),
        label("srCount", "CountRows(srGal.AllItems) & \" updates\"", 32, 186, 600, 30, size=10, color=MUTED),
        ctl("srGal", "Gallery", variant="Vertical", X=32, Y=220, Width=1302, Height=524, Items=SEARCH_ITEMS,
            TemplateSize=84, TemplatePadding=0, children=[
                rect("srRowBg", 0, 4, "Parent.TemplateWidth", 76, WHITE, BorderColor=LINE, BorderThickness=1),
                label("srRowTitle",
                      "ThisItem.Title & If(ThisItem.NoticeStatus.Value = \"Superseded\", \"  (superseded)\", \"\")",
                      20, 10, 860, 34, size=12, bold=True),
                label("srRowMeta",
                      "ThisItem.Category.Value & \"   Posted \" & Text(ThisItem.PostedOn, \"mmm d, yyyy\") & \" by \" & "
                      "ThisItem.PostedByName & \"   Effective \" & Text(ThisItem.EffectiveDate, \"mmm d, yyyy\")",
                      20, 42, 860, 30, size=10, color=MUTED),
                label("srRowCount", "If(ThisItem.AudienceCount = 0, \"No acknowledgement needed\", ThisItem.AckCount & \" of \" & ThisItem.AudienceCount & \" acknowledged\")",
                      880, 24, 220, 36, size=10, color=f"If({DONE}, {GREEN}, {RED})", bold=True, Align="Align.Right"),
                button("srRowOpen", '"Open"', 1140, 20, 140, 44, "Set(gNotice, ThisItem);\nNavigate(scrNotice)", primary=False),
            ]),
    ],
}


# ------------------------------------------------------------------ emit
def fmt(value):
    if isinstance(value, (int, float)):
        return str(value)
    return value


def emit_prop(lines, indent, key, value):
    f = "=" + fmt(value)
    pad = " " * indent
    if "\n" in f or ": " in f or " #" in f or f.endswith(":"):
        lines.append(f"{pad}{key}: |-")
        lines.extend(f"{pad}  {ln}" for ln in f.split("\n"))
    else:
        lines.append(f"{pad}{key}: {f}")


def emit_ctl(lines, indent, c):
    pad = " " * indent
    lines.append(f"{pad}- {c['name']}:")
    lines.append(f"{pad}    Control: {c['kind']}")
    if c["variant"]:
        lines.append(f"{pad}    Variant: {c['variant']}")
    for mk, mv in c["meta"].items():
        lines.append(f"{pad}    {mk}: {mv}")
    lines.append(f"{pad}    Properties:")
    for k, v in c["props"].items():
        emit_prop(lines, indent + 6, k, v)
    if c["children"]:
        lines.append(f"{pad}    Children:")
        for ch in c["children"]:
            emit_ctl(lines, indent + 6, ch)


def emit_screen(s):
    lines = ["Screens:", f"  {s['name']}:", "    Properties:"]
    for k, v in s["props"].items():
        emit_prop(lines, 6, k, v)
    lines.append("    Children:")
    for c in s["children"]:
        emit_ctl(lines, 6, c)
    return "\n".join(lines) + "\n"


def check(text, all_names):
    doc = yaml.safe_load(text)
    (sname, body), = doc["Screens"].items()
    names = []

    def walk(children):
        for c in children:
            (n, v), = c.items()
            names.append(n)
            for p, val in v.get("Properties", {}).items():
                s = str(val)
                assert s.startswith("="), (n, p)
                stripped = re.sub(r'"(?:[^"]|"")*"', "", s)
                for a, b in ("()", "{}", "[]"):
                    assert stripped.count(a) == stripped.count(b), (n, p, a)
            walk(v.get("Children", []))
    for p, val in body["Properties"].items():
        assert str(val).startswith("="), (sname, p)
    walk(body["Children"])
    assert len(names) == len(set(names)), "duplicate control name in " + sname
    return sname, names


os.makedirs(OUT, exist_ok=True)
everything, texts = [], {}
for scr in (my_notices, notice, new_notice, search):
    t = emit_screen(scr)
    texts[scr["name"]] = t
    sname, names = check(t, everything)
    everything += names + [sname]
assert len(everything) == len(set(everything)), "duplicate name across screens"
joined = "\n".join(texts.values())
for ref in set(re.findall(r"\b(?:mn|nt|nn|sr)[A-Z][A-Za-z0-9]+\b", joined)) | set(re.findall(r"\bscr[A-Z]\w+\b", joined)):
    assert ref in everything, "unknown reference " + ref
for name, t in texts.items():
    with open(os.path.join(OUT, name + ".pa.yaml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(t)
    print("wrote", name, len(t.splitlines()), "lines")
