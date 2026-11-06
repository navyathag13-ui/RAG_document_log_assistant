"""Build the labeled work-order PDFs used by bench/extraction_eval.py.

14 short maintenance documents (plus 6 held-out ones) in different styles (form, email, table, terse
shift notes), each with its expected fields in labels.json. Several are traps:
a field that is not stated (the right answer is null), parts that were only
ordered, a second machine that was only inspected, quantities written as words,
minutes instead of hours, and a date written as MM/DD/YYYY.

The PDFs are written by a tiny built-in writer (one page, Helvetica), so the
script needs no extra packages and the files are byte-for-byte reproducible.

Run:  python bench/extraction/make_docs.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "docs"

DOCS = [
    ("wo01_form", """WORK ORDER WO-2291
Equipment: PMP-104 (Coolant Pump 4)
Date: March 3, 2026
Technician: Maria Lopez
Work done: Replaced 2 bearings and 1 mechanical seal.
Downtime: 1.5 hours
Status: Closed - running normally""",
     dict(equipment_id="PMP-104", work_date="2026-03-03", technician="Maria Lopez",
          parts=[["bearing", 2], ["seal", 1]], downtime_hours=1.5, status="resolved")),

    ("wo02_email", """From: Dev Patel
Subject: Compressor CMP-210 fixed
Sent: April 9, 2026

Hi team, I swapped out the 3 inlet filters on CMP-210 this morning.
It was offline for 45 minutes. Pressure is back in range, so I'm closing this out.
Thanks, Dev""",
     dict(equipment_id="CMP-210", work_date="2026-04-09", technician="Dev Patel",
          parts=[["filter", 3]], downtime_hours=0.75, status="resolved")),

    ("wo03_table", """SERVICE REPORT  SR-0457
Asset ID | Date       | Tech
CNV-007  | 2026-02-17 | Aisha Khan
Part                 Qty
Drive belt           1
Roller bearing       4
Downtime (h): 3
Result: Belt tracking still off. Follow-up visit scheduled.""",
     dict(equipment_id="CNV-007", work_date="2026-02-17", technician="Aisha Khan",
          parts=[["belt", 1], ["bearing", 4]], downtime_hours=3, status="follow_up_required")),

    ("wo04_no_tech", """Maintenance log - Generator GEN-02
05/12/2026
Replaced 1 fuel filter and 1 air filter during the monthly service.
Unit down 2 hours. Completed, no issues found.""",
     dict(equipment_id="GEN-02", work_date="2026-05-12", technician=None,
          parts=[["fuel filter", 1], ["air filter", 1]], downtime_hours=2, status="resolved")),

    ("wo05_ordered_only", """WORK ORDER WO-3310
Equipment: HYD-55 hydraulic press
Date: January 28, 2026
Technician: Tom Becker
Replaced 1 pressure hose. Ordered 4 seal kits for next month, not installed yet.
Downtime: 1 hour. Status: complete.""",
     dict(equipment_id="HYD-55", work_date="2026-01-28", technician="Tom Becker",
          parts=[["hose", 1]], downtime_hours=1, status="resolved")),

    ("wo06_words", """Shift notes, June 2, 2026 - Grace Kim
Chiller CH-12: replaced three V-belts and two gaskets.
Chiller was down for one hour and thirty minutes.
Running fine at end of shift. Closed.""",
     dict(equipment_id="CH-12", work_date="2026-06-02", technician="Grace Kim",
          parts=[["belt", 3], ["gasket", 2]], downtime_hours=1.5, status="resolved")),

    ("wo07_two_machines", """WORK ORDER WO-4102
Equipment: PMP-221
Date: July 15, 2026
Technician: Omar Haddad
Replaced 1 impeller on PMP-221. Also inspected the neighbouring pump PMP-222,
no work needed there. Downtime 2.5 hours. Status: resolved.""",
     dict(equipment_id="PMP-221", work_date="2026-07-15", technician="Omar Haddad",
          parts=[["impeller", 1]], downtime_hours=2.5, status="resolved")),

    ("wo08_follow_up", """Field service report
Asset: BLR-01 (Boiler 1)   Date: 2026-08-04   Technician: Lena Fischer
Replaced 2 thermocouples. Burner still trips on high limit.
Needs a return visit with a combustion analyzer.
Downtime so far: 6 hours.""",
     dict(equipment_id="BLR-01", work_date="2026-08-04", technician="Lena Fischer",
          parts=[["thermocouple", 2]], downtime_hours=6, status="follow_up_required")),

    ("wo09_no_downtime", """WORK ORDER WO-5017
Equipment: FAN-33 exhaust fan
Date: September 22, 2026
Technician: Sam Rivera
Replaced 1 motor capacitor. Status: closed.""",
     dict(equipment_id="FAN-33", work_date="2026-09-22", technician="Sam Rivera",
          parts=[["capacitor", 1]], downtime_hours=None, status="resolved")),

    ("wo10_inspection", """Inspection record
Equipment: CRN-03 overhead crane
Date: October 6, 2026
Inspector: Priya Nair
Monthly inspection only. Hooks, chain and brakes checked, all within limits.
No parts used. No downtime. Closed.""",
     dict(equipment_id="CRN-03", work_date="2026-10-06", technician="Priya Nair",
          parts=[], downtime_hours=0, status="resolved")),

    ("wo11_no_date", """Work note - Mixer MIX-08
Technician: Carlos Mendes
Replaced 1 agitator shaft seal. Mixer down about 4 hours.
Job finished and tested.""",
     dict(equipment_id="MIX-08", work_date=None, technician="Carlos Mendes",
          parts=[["seal", 1]], downtime_hours=4, status="resolved")),

    ("wo12_terse", """WO#6120 TRB-4 11/03/2026 J. Okafor
repl 2x vibration sensor, 1x coupling insert
dt 120 min. OK, closed""",
     dict(equipment_id="TRB-4", work_date="2026-11-03", technician="J. Okafor",
          parts=[["sensor", 2], ["coupling", 1]], downtime_hours=2, status="resolved")),

    ("wo13_no_equipment", """Maintenance note
Date: April 20, 2026
Technician: Hannah Cole
Replaced 6 light fixtures in the warehouse aisle. About 1 hour of work.
Closed.""",
     dict(equipment_id=None, work_date="2026-04-20", technician="Hannah Cole",
          parts=[["fixture", 6]], downtime_hours=None, status="resolved")),

    ("wo14_unresolved_no_parts", """WORK ORDER WO-7003
Equipment: ELV-1 freight elevator
Date: May 30, 2026
Technician: Ben Ortiz
Door sensor fault reported. Cleaned and realigned sensor, fault came back.
Waiting on replacement sensor from vendor. Elevator out of service 8 hours.""",
     dict(equipment_id="ELV-1", work_date="2026-05-30", technician="Ben Ortiz",
          parts=[], downtime_hours=8, status="follow_up_required")),
]


# Written after the field descriptions were tuned on DOCS above, and run once,
# so their score is a fair check of the tuned prompt on documents it never saw.
HELDOUT = [
    ("h01_invoice", """ACME Industrial Services - Service Invoice 88213
Customer asset: ACU-17 rooftop unit
Service date: Oct. 21, 2026
Field tech: Rachel Singh
Item                         Qty
Compressor contactor         1
Pleated filter 20x25         4
Unit offline 50 minutes. Work complete.""",
     dict(equipment_id="ACU-17", work_date="2026-10-21", technician="Rachel Singh",
          parts=[["contactor", 1], ["filter", 4]], downtime_hours=0.8333, status="resolved")),

    ("h02_thread", """Re: FRK-3 forklift
Sent: September 30, 2026
From: Luis Romero

Update: today I replaced the 2 hydraulic lift chains on FRK-3. It's back in service
after 3 hours down. Closing the ticket.

> On August 2, 2026 Luis Romero wrote:
> Replaced 1 seat switch on FRK-3. Down 20 minutes.""",
     dict(equipment_id="FRK-3", work_date="2026-09-30", technician="Luis Romero",
          parts=[["chain", 2]], downtime_hours=3, status="resolved")),

    ("h03_short_name", """Job card - Asset #PRS-9 (stamping press)
Date: 2026-09-14
Tech: R. Novak
Changed a pair of brake pads on the clutch. Press down half an hour.
Done, tested OK.""",
     dict(equipment_id="PRS-9", work_date="2026-09-14", technician="R. Novak",
          parts=[["brake pad", 2]], downtime_hours=0.5, status="resolved")),

    ("h04_locked_out", """WORK ORDER WO-8840
Equipment: WLD-06 robotic welder
Date: August 19, 2026
Technician: Nina Petrova
Found a damaged power cable at the junction box. Unit locked out until an
electrician can replace it. No parts installed today.""",
     dict(equipment_id="WLD-06", work_date="2026-08-19", technician="Nina Petrova",
          parts=[], downtime_hours=None, status="follow_up_required")),

    ("h05_no_tech", """PM checklist - Air dryer DRY-2
July 7, 2026
Desiccant cartridge replaced (1). Drain valve cleaned.
Dryer bypassed for 2 hours during the swap. PM complete.""",
     dict(equipment_id="DRY-2", work_date="2026-07-07", technician=None,
          parts=[["cartridge", 1]], downtime_hours=2, status="resolved")),

    ("h06_many_parts", """WORK ORDER WO-9105
Equipment: PKG-14 packaging line
Date: June 25, 2026
Technician: Kofi Mensah
Replaced 5 suction cups, 2 proximity sensors and 1 timing belt.
Line stopped 4.5 hours. Ordered spare cups for stock. Status: closed.""",
     dict(equipment_id="PKG-14", work_date="2026-06-25", technician="Kofi Mensah",
          parts=[["cup", 5], ["sensor", 2], ["belt", 1]], downtime_hours=4.5, status="resolved")),
]


def write_pdf(path: Path, text: str) -> None:
    """Write `text` to a one-page PDF (Helvetica 11pt) that pypdf can read back."""
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines = text.split("\n")
    stream = "BT /F1 11 Tf 14 TL 60 740 Td\n" + "".join(f"({esc(l)}) Tj T*\n" for l in lines) + "ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    labels = {}
    for name, text, gold in DOCS:
        write_pdf(OUT / f"{name}.pdf", text)
        labels[f"{name}.pdf"] = gold
    (HERE / "labels.json").write_text(json.dumps(labels, indent=1) + "\n")
    held_dir = HERE / "docs_heldout"
    held_dir.mkdir(exist_ok=True)
    held_labels = {}
    for name, text, gold in HELDOUT:
        write_pdf(held_dir / f"{name}.pdf", text)
        held_labels[f"{name}.pdf"] = gold
    (HERE / "labels_heldout.json").write_text(json.dumps(held_labels, indent=1) + "\n")
    print(f"wrote {len(DOCS)} tuning PDFs and {len(HELDOUT)} held-out PDFs")


if __name__ == "__main__":
    main()
