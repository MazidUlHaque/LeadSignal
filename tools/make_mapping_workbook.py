"""Create the curriculum-mapping workbook (cs2013_cs2023_mapping.xlsx).

    python tools/make_mapping_workbook.py [output.xlsx]            checking workbook (Claude's draft)
    python tools/make_mapping_workbook.py [output.xlsx] --blank    empty workbook (second coder)

It never overwrites an existing file, so your filled workbook is safe.
Needs openpyxl (preinstalled on Colab and in most Python installs).
"""

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from leadsignal import groundtruth  # noqa: E402

FONT = "Cambria"
GREY = PatternFill("solid", fgColor="EDEDED")
HEAD = PatternFill("solid", fgColor="1F3864")
YOU = PatternFill("solid", fgColor="FFF8DC")
GREEN = PatternFill("solid", fgColor="D9EAD3")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")

CS2013_KAS = [
    ("AL", "Algorithms and Complexity"), ("AR", "Architecture and Organization"),
    ("CN", "Computational Science"), ("DS", "Discrete Structures"),
    ("GV", "Graphics and Visualization"), ("HCI", "Human-Computer Interaction"),
    ("IAS", "Information Assurance and Security"), ("IM", "Information Management"),
    ("IS", "Intelligent Systems"), ("NC", "Networking and Communication"),
    ("OS", "Operating Systems"), ("PBD", "Platform-based Development"),
    ("PD", "Parallel and Distributed Computing"), ("PL", "Programming Languages"),
    ("SDF", "Software Development Fundamentals"), ("SE", "Software Engineering"),
    ("SF", "Systems Fundamentals"), ("SP", "Social Issues and Professional Practice"),
]
CS2023_KAS = [
    ("AL", "Algorithmic Foundations"), ("AR", "Architecture and Organization"),
    ("AI", "Artificial Intelligence"), ("DM", "Data Management"),
    ("FPL", "Foundations of Programming Languages"), ("GIT", "Graphics and Interactive Techniques"),
    ("HCI", "Human-Computer Interaction"), ("MSF", "Mathematical and Statistical Foundations"),
    ("NC", "Networking and Communication"), ("OS", "Operating Systems"),
    ("PDC", "Parallel and Distributed Computing"), ("SEC", "Security"),
    ("SEP", "Society, Ethics, and the Profession"), ("SDF", "Software Development Fundamentals"),
    ("SE", "Software Engineering"), ("SPD", "Specialized Platform Development"),
    ("SF", "Systems Fundamentals"),
]

# (header shown, width, who fills it)
COLUMNS = [
    ("concept_id", 26, "fixed"), ("label", 26, "fixed"), ("concept_kind", 15, "fixed"),
    ("search_terms", 38, "fixed"),
    ("cs2013_knowledge_area", 22, "you"), ("cs2013_status", 14, "you"), ("cs2013_evidence", 30, "you"),
    ("cs2023_knowledge_area", 22, "you"), ("cs2023_status", 14, "you"), ("cs2023_evidence", 30, "you"),
    ("change", 12, "auto"), ("event_period", 12, "fixed"), ("notes", 34, "you"), ("row_done", 10, "auto"),
]


def _cell(ws, ref, value, bold=False, size=11, fill=None, color=None, wrap=True):
    c = ws[ref]
    c.value = value
    c.font = Font(name=FONT, bold=bold, size=size, color=color)
    if fill:
        c.fill = fill
    if wrap:
        c.alignment = WRAP
    return c


def start_sheet(wb):
    ws = wb.active
    ws.title = "Start here"
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 110
    _cell(ws, "B1", "LeadSignal-CS curriculum mapping (CS2013 to CS2023)", bold=True, size=16)
    _cell(ws, "B2", "Created by Mazid. Fill the yellow columns on the 'Mapping' tab. Grey columns are fixed.")
    _cell(ws, "B3", '=COUNTIF(Mapping!N2:N51,"yes")&" of 50 concepts done"', bold=True, size=13, color="1F3864")
    steps = [
        "Open the two curriculum documents (links are in the guide): CS2013 (one PDF) and the CS2023 Body of Knowledge (section 3.1 PDF).",
        "Go to the 'Mapping' tab. Work on one row (one concept) at a time. Do 10 concepts per sitting.",
        "In the CS2013 PDF, press Ctrl+F and search each word in the 'search_terms' column. Only the Body of Knowledge counts, not course exemplars or introductions.",
        "Decide the CS2013 status with the 'Rules' tab: core, minor or absent. Pick it from the dropdown in column F.",
        "Write where you found it in column E (knowledge area and unit, e.g. SE / Software Processes) and the evidence in column G (unit, tier and PDF page).",
        "Repeat for CS2023 in columns H, I and J.",
        "Column K (change) and column N (row_done) fill themselves. Do not type in them.",
        "If you searched and found nothing, choose 'absent' and write 'searched: <words>' in the evidence column.",
        "Save. Upload the file to Google Drive, folder MyDrive/leadsignal/ground_truth/, keeping the name cs2013_cs2023_mapping.xlsx.",
        "In Colab, run the 'events' cell. It reports progress and writes the events file for the analysis.",
    ]
    for i, s in enumerate(steps, start=5):
        _cell(ws, f"A{i}", i - 4, bold=True)
        _cell(ws, f"B{i}", s)
    _cell(ws, "B16", "Golden rules", bold=True, size=13)
    rules = [
        "Decide from the documents only, never from what you expect the detector to show.",
        "When a concept appears in several places, use the HIGHEST status you found.",
        "Do not rename, reorder or delete columns. Do not change the concept_id column.",
        "If unsure, choose the lower status and explain in 'notes'. Consistency matters more than perfection.",
    ]
    for i, s in enumerate(rules, start=17):
        _cell(ws, f"B{i}", "- " + s)


def mapping_sheet(wb):
    ws = wb.create_sheet("Mapping")
    for j, (name, width, who) in enumerate(COLUMNS, start=1):
        col = ws.cell(row=1, column=j).column_letter
        ws.column_dimensions[col].width = width
        c = ws.cell(row=1, column=j, value=name)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BOX
    ws.row_dimensions[1].height = 32
    blank = groundtruth.blank_mapping()
    for i, r in enumerate(blank.itertuples(index=False), start=2):
        row = r._asdict()
        for j, (name, _, who) in enumerate(COLUMNS, start=1):
            c = ws.cell(row=i, column=j)
            if name == "change":
                c.value = (f'=IF(OR(F{i}="",I{i}=""),"",IF(F{i}=I{i},"none",IF(I{i}="core","adoption",'
                           f'IF(I{i}="minor",IF(F{i}="absent","expansion","reduction"),"removal"))))')
            elif name == "row_done":
                c.value = (f'=IF(AND(F{i}<>"",I{i}<>"",OR(F{i}="absent",G{i}<>""),'
                           f'OR(I{i}="absent",J{i}<>"")),"yes","")')
            else:
                c.value = row.get(name, "") or None
            c.font = Font(name=FONT)
            c.alignment = WRAP
            c.border = BOX
            c.fill = YOU if who == "you" else GREY
    ws.freeze_panes = "C2"
    last = len(blank) + 1
    dv = DataValidation(type="list", formula1='"core,minor,absent"', allow_blank=True,
                        showErrorMessage=True, errorTitle="Choose from the list",
                        error="Status must be core, minor or absent.",
                        promptTitle="Status", prompt="core, minor or absent (see the Rules tab)",
                        showInputMessage=True)
    ws.add_data_validation(dv)
    dv.add(f"F2:F{last}")
    dv.add(f"I2:I{last}")
    ws.conditional_formatting.add(f"A2:N{last}", FormulaRule(formula=[f'$N2="yes"'], fill=GREEN))
    ws.auto_filter.ref = f"A1:N{last}"


def rules_sheet(wb):
    ws = wb.create_sheet("Rules")
    for col, w in zip("ABCD", (16, 48, 48, 30)):
        ws.column_dimensions[col].width = w
    row = 1
    _cell(ws, f"A{row}", "How to decide the status", bold=True, size=14)
    row = 3
    for j, h in enumerate(["Status", "CS2013 meaning", "CS2023 meaning", "Typical wording in the PDF"]):
        c = ws.cell(row=row, column=j + 1, value=h)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEAD
    table = [
        ("core", "Named in a Core-Tier1 or Core-Tier2 topic of any knowledge unit.",
         "Named in a CS Core or KA Core topic of any knowledge unit.",
         "[Core-Tier1], [Core-Tier2] / CS Core:, KA Core:"),
        ("minor", "Named only in Elective topics, or only in a unit's learning outcomes or description.",
         "Named only in Non-core topics, or only in a unit's learning outcomes or description.",
         "[Elective] / Non-core:"),
        ("absent", "Not named anywhere in the Body of Knowledge after searching every term.",
         "Not named anywhere in the Body of Knowledge after searching every term.",
         "Write 'searched: <words>' as evidence"),
    ]
    for r in table:
        row += 1
        for j, v in enumerate(r):
            _cell(ws, ws.cell(row=row, column=j + 1).coordinate, v, bold=(j == 0))
    row += 2
    _cell(ws, f"A{row}", "What counts as 'named'", bold=True, size=14)
    named = [
        "Counts: the concept's name, one of its lexicon aliases (the same words the system searches for on arXiv), or an unmistakable synonym, written as a topic or as an example, e.g. '(e.g., large language models)'.",
        "Counts: a knowledge area or unit whose title is the concept (e.g. PL/Functional Programming) when it contains core topics.",
        "Does not count: a related but different idea. 'Tree' does not make 'graph neural networks'. 'Security' in general does not make 'federated learning'.",
        "Does not count: text outside the Body of Knowledge (course exemplars or course packaging, introductions and preambles, the CS2023 'Generative AI and the Curriculum' essay). Write such mentions in 'notes'.",
        "Several places: use the highest status found, and cite that place.",
        "Unsure between two statuses: choose the lower one and explain in 'notes'.",
    ]
    for t in named:
        row += 1
        _cell(ws, f"A{row}", "-")
        ws.merge_cells(f"B{row}:D{row}")
        _cell(ws, f"B{row}", t)
        ws.row_dimensions[row].height = 34
    row += 2
    _cell(ws, f"A{row}", "The change column (filled automatically)", bold=True, size=14)
    changes = [("CS2013", "CS2023", "change", "used in the analysis as"),
               ("absent or minor", "core", "adoption", "adoption event"),
               ("absent", "minor", "expansion", "adoption event"),
               ("core", "minor", "reduction", "decline event"),
               ("minor or core", "absent", "removal", "decline event"),
               ("absent", "absent", "none", "negative control (topics only; tools are excluded)"),
               ("same level", "same level", "none", "no event")]
    for k, r in enumerate(changes):
        row += 1
        for j, v in enumerate(r):
            c = _cell(ws, ws.cell(row=row, column=j + 1).coordinate, v, bold=(k == 0))
            if k == 0:
                c.fill = HEAD
                c.font = Font(name=FONT, bold=True, color="FFFFFF")
    row += 2
    _cell(ws, f"A{row}", "Evidence format examples", bold=True, size=14)
    for t in ["CS2013: SE/Software Processes [Core-Tier1], PDF p. <page> (printed p. <page>)",
              "CS2023: AI-ML topic 8.b [CS Core], PDF p. <page>",
              "Absent: searched: Kubernetes, orchestration (no match)"]:
        row += 1
        ws.merge_cells(f"A{row}:D{row}")
        _cell(ws, f"A{row}", t)
    row += 1
    ws.merge_cells(f"A{row}:D{row}")
    _cell(ws, f"A{row}", "In CS2013 the PDF page is 3 higher than the number printed on the page. In CS2023 they are the same.",
          color="C00000")


def ka_sheet(wb):
    ws = wb.create_sheet("Knowledge areas")
    for col, w in zip("ABDE", (10, 42, 10, 42)):
        ws.column_dimensions[col].width = w
    _cell(ws, "A1", "CS2013 (18 knowledge areas)", bold=True, size=13)
    _cell(ws, "D1", "CS2023 (17 knowledge areas)", bold=True, size=13)
    for i, (ab, name) in enumerate(CS2013_KAS, start=2):
        _cell(ws, f"A{i}", ab, bold=True)
        _cell(ws, f"B{i}", name)
    for i, (ab, name) in enumerate(CS2023_KAS, start=2):
        _cell(ws, f"D{i}", ab, bold=True)
        _cell(ws, f"E{i}", name)


CHECK_COLS = [
    ("concept_id", 24, "fixed"), ("label", 22, "fixed"), ("concept_kind", 11, "fixed"), ("check_first", 12, "fixed"),
    ("cs2013_status", 12, "you"), ("cs2013_knowledge_area", 22, "you"), ("cs2013_evidence", 34, "you"),
    ("cs2013_quote", 40, "fixed"), ("check_2013", 11, "you"),
    ("cs2023_status", 12, "you"), ("cs2023_knowledge_area", 18, "you"), ("cs2023_evidence", 32, "you"),
    ("cs2023_quote", 40, "fixed"), ("check_2023", 11, "you"),
    ("change", 12, "auto"), ("event_period", 10, "fixed"), ("notes", 50, "you"),
    ("claude_draft_2013", 12, "fixed"), ("claude_draft_2023", 12, "fixed"), ("row_done", 10, "auto"),
]
RED = Font(name=FONT, bold=True, color="C00000")


def check_start_sheet(wb):
    ws = wb.active
    ws.title = "Start here"
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 110
    _cell(ws, "B1", "LeadSignal-CS curriculum mapping: checking Claude's draft", bold=True, size=16)
    _cell(ws, "B2", "Created by Mazid. Claude has pre-filled every row from the two PDFs, with the exact sentence and page. "
                    "Your job is to check each decision and mark it OK or changed.")
    _cell(ws, "B3", '=COUNTIF(Mapping!T2:T51,"yes")&" of 50 concepts checked"', bold=True, size=13, color="1F3864")
    steps = [
        "Open the two PDFs you uploaded: cs2013_web_final.pdf and 3.1-Body-of-Knowledge-1.pdf.",
        "Go to the 'Mapping' tab. Start with the 10 rows marked CHECK FIRST in column D. They are the judgement calls.",
        "Read the CS2013 decision: status (E), unit (F), evidence with page (G) and the exact sentence (H).",
        "In the CS2013 PDF, go to that PDF page and find the sentence with Ctrl+F. Look at the nearest tier label above it: [Core-Tier1], [Core-Tier2] or [Elective].",
        "Read Claude's note in column Q, then decide. If you agree, choose OK in column I.",
        "If you disagree, change the status in E (and F and G if needed), choose 'changed' in column I, and add your reason at the end of the note in Q.",
        "For an 'absent' row there is no sentence to find. Search one or two of the listed words yourself; if you find the concept in the Body of Knowledge, change it.",
        "Do the same for CS2023 in columns J to N. There the labels are CS Core:, KA Core: and Non-core:.",
        "The row turns green when both checks (I and N) are filled. Columns O and T fill themselves. Never type in R or S (Claude's draft).",
        "Save. Upload to Google Drive, folder MyDrive/leadsignal/ground_truth/, with the name cs2013_cs2023_mapping.xlsx. In Colab, run Cell 14b.",
    ]
    for i, t in enumerate(steps, start=5):
        _cell(ws, f"A{i}", i - 4, bold=True)
        _cell(ws, f"B{i}", t)
    _cell(ws, "B16", "Golden rules", bold=True, size=13)
    rules = [
        "Decide from the documents only, never from what you expect the detector to show.",
        "Do not accept a row you have not looked at. Marking OK means you checked it.",
        "Do not rename, reorder or delete columns.",
        "When unsure, choose the lower status and explain in the note.",
    ]
    for i, t in enumerate(rules, start=17):
        _cell(ws, f"B{i}", "- " + t)


def check_mapping_sheet(wb, frame):
    ws = wb.create_sheet("Mapping")
    col_of = {}
    for j, (name, width, who) in enumerate(CHECK_COLS, start=1):
        letter = ws.cell(row=1, column=j).column_letter
        col_of[name] = letter
        ws.column_dimensions[letter].width = width
        c = ws.cell(row=1, column=j, value=name)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BOX
    ws.row_dimensions[1].height = 32
    E, J, I, N = col_of["cs2013_status"], col_of["cs2023_status"], col_of["check_2013"], col_of["check_2023"]
    for i, r in enumerate(frame.to_dict("records"), start=2):
        for j, (name, _, who) in enumerate(CHECK_COLS, start=1):
            c = ws.cell(row=i, column=j)
            if name == "change":
                c.value = (f'=IF(OR({E}{i}="",{J}{i}=""),"",IF({E}{i}={J}{i},"none",IF({J}{i}="core","adoption",'
                           f'IF({J}{i}="minor",IF({E}{i}="absent","expansion","reduction"),"removal"))))')
            elif name == "row_done":
                c.value = f'=IF(AND({E}{i}<>"",{J}{i}<>"",{I}{i}<>"",{N}{i}<>""),"yes","")'
            else:
                c.value = r.get(name, "") or None
            c.font = RED if name == "check_first" else Font(name=FONT)
            c.alignment = WRAP
            c.border = BOX
            c.fill = YOU if who == "you" else GREY
    last = len(frame) + 1
    ws.freeze_panes = "C2"
    status = DataValidation(type="list", formula1='"core,minor,absent"', allow_blank=True,
                            showErrorMessage=True, errorTitle="Choose from the list",
                            error="Status must be core, minor or absent.")
    check = DataValidation(type="list", formula1='"OK,changed"', allow_blank=True,
                           showErrorMessage=True, errorTitle="Choose from the list",
                           error="Choose OK (you agree) or changed (you changed the status).",
                           promptTitle="Your check", prompt="OK = you agree with the draft; changed = you changed it",
                           showInputMessage=True)
    ws.add_data_validation(status)
    ws.add_data_validation(check)
    status.add(f"{E}2:{E}{last}")
    status.add(f"{J}2:{J}{last}")
    check.add(f"{I}2:{I}{last}")
    check.add(f"{N}2:{N}{last}")
    T = col_of["row_done"]
    ws.conditional_formatting.add(f"A2:{T}{last}", FormulaRule(formula=[f'${T}2="yes"'], fill=GREEN))
    ws.auto_filter.ref = f"A1:{T}{last}"


def build_checking(out: Path, draft_csv: Path) -> Path:
    """Workbook pre-filled from Claude's draft, for row-by-row checking."""
    import pandas as pd
    if out.exists():
        print(f"[workbook] {out} already exists; not overwritten (your work is kept)")
        return out
    frame = groundtruth.prefilled_mapping(pd.read_csv(draft_csv, dtype=str))
    wb = Workbook()
    check_start_sheet(wb)
    check_mapping_sheet(wb, frame)
    rules_sheet(wb)
    ka_sheet(wb)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"[workbook] wrote {out} (pre-filled from {draft_csv.name}; check every row)")
    return out


def build(out: Path) -> Path:
    if out.exists():
        print(f"[workbook] {out} already exists; not overwritten (your work is kept)")
        return out
    wb = Workbook()
    start_sheet(wb)
    mapping_sheet(wb)
    rules_sheet(wb)
    ka_sheet(wb)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"[workbook] wrote {out}")
    return out


if __name__ == "__main__":
    # python tools/make_mapping_workbook.py <out.xlsx> [--blank]
    #   default: the checking workbook pre-filled from Claude's draft
    #   --blank: an empty workbook (for a second coder, who must not see the draft)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = Path(args[0]) if args else ROOT / "data" / "ground_truth" / "cs2013_cs2023_mapping.xlsx"
    draft = ROOT / "data" / "ground_truth" / groundtruth.DRAFT_FILE
    if "--blank" in sys.argv or not draft.exists():
        build(target)
    else:
        build_checking(target, draft)
