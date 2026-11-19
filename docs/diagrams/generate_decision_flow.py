"""Render static illustrations of the decision-engine run graph.

The geometry and state vocabulary here mirror
``frontend/src/features/decisions/lib/runModel.ts`` (same canvas size, node
box, column centres and pitch) so the images in this folder show the same
diagram the UI draws. The app renders HTML nodes over an SVG edge layer with
Tailwind/oklch tokens; these PNGs are a flat rendering for the report and for
reviewing the layout without a browser.

Regenerate:

    python docs/diagrams/generate_decision_flow.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

S = 2  # supersampling factor

W, H = 900, 958
HEADER = 46
LEGEND = 36
CANVAS_W = W
CANVAS_H = H + HEADER + LEGEND
DY = HEADER

NODE_W, NODE_H, TERM_H = 200, 76, 54
SPINE_CX, TOP, PITCH = 450, 18, 100
BUS_Y, BRANCH_Y, CONT_Y, CONT2_Y = 628, 654, 764, 864
COL = {"block": 120, "shadow": 340, "human": 560, "auto": 780}

FONT_DIR = "C:/Windows/Fonts"


def font(name: str, size: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, name), int(round(size * S)))


F_TITLE = font("segoeuib.ttf", 11)
F_SUB = font("segoeui.ttf", 9.5)
F_PILL = font("segoeuib.ttf", 8)
F_MONO = font("consola.ttf", 8.5)
F_H1 = font("segoeuib.ttf", 13)
F_H2 = font("segoeui.ttf", 9.5)
F_LEG = font("segoeui.ttf", 9.5)

INK = "#0f172a"
MUTED = "#64748b"
FAINT = "#94a3b8"
CANVAS_BG = "#ffffff"

# state -> (stroke, fill, label, pill_bg)
STATE = {
    "success": ("#16a34a", "#f2fbf4", "#15803d", "#dcf3e2"),
    "active": ("#2563eb", "#eff5ff", "#1d4ed8", "#dbe8fe"),
    "shadow": ("#d97706", "#fff9ec", "#b45309", "#fdeccb"),
    "escalated": ("#ea580c", "#fff5ef", "#c2410c", "#fde3d2"),
    "blocked": ("#dc2626", "#fef3f2", "#b91c1c", "#fbdcda"),
    "failed": ("#b91c1c", "#fdf1f1", "#991b1b", "#f6d6d6"),
    "skipped": ("#cbd5e1", "#fbfcfd", "#94a3b8", "#eef2f6"),
    "pending": ("#cbd5e1", "#fbfcfd", "#94a3b8", "#eef2f6"),
}

EDGE = {
    "done": "#16a34a",
    "active": "#2563eb",
    "skipped": "#d5dde6",
    "failed": "#dc2626",
}


def sp(v: float) -> int:
    return int(round(v * S))


def box(x: float, y: float, w: float, h: float) -> list[int]:
    return [sp(x), sp(y + DY), sp(x + w), sp(y + h + DY)]


def dashed(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, fill, width=1, dash=5, gap=4):
    """Axis-aligned dashed segment, in node space (HEADER offset applied)."""
    y1 = y1 + DY
    y2 = y2 + DY
    if y1 == y2:
        x = min(x1, x2)
        end = max(x1, x2)
        while x < end:
            draw.line([sp(x), sp(y1), sp(min(x + dash, end)), sp(y1)], fill=fill, width=sp(width))
            x += dash + gap
    else:
        y = min(y1, y2)
        end = max(y1, y2)
        while y < end:
            draw.line([sp(x1), sp(y), sp(x1), sp(min(y + dash, end))], fill=fill, width=sp(width))
            y += dash + gap


def arrow(draw: ImageDraw.ImageDraw, x: float, y: float, colour: str):
    """Downward arrowhead whose tip sits at (x, y) in node space."""
    draw.polygon(
        [
            (sp(x - 4), sp(y - 8 + DY)),
            (sp(x + 4), sp(y - 8 + DY)),
            (sp(x), sp(y - 1 + DY)),
        ],
        fill=colour,
    )


def fit(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: float) -> str:
    if draw.textlength(text, font=fnt) / S <= max_w:
        return text
    trimmed = text
    while trimmed and draw.textlength(trimmed + "…", font=fnt) / S > max_w:
        trimmed = trimmed[:-1]
    return trimmed + "…"


class Node:
    def __init__(self, nid, kind, title, subtitle, state, duration="—", badge=None, x=0, y=0, h=NODE_H):
        self.id = nid
        self.kind = kind
        self.title = title
        self.subtitle = subtitle
        self.state = state
        self.duration = duration
        self.badge = badge
        self.x = x
        self.y = y
        self.w = NODE_W
        self.h = h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def bottom(self) -> float:
        return self.y + self.h


def draw_node(draw: ImageDraw.ImageDraw, n: Node):
    stroke, fill, label_colour, pill_bg = STATE[n.state]
    b = box(n.x, n.y, n.w, n.h)
    if n.state in ("skipped", "pending"):
        draw.rectangle(b, fill=fill)
        dashed(draw, n.x, n.y, n.x + n.w, n.y, stroke, 1)
        dashed(draw, n.x, n.y + n.h, n.x + n.w, n.y + n.h, stroke, 1)
        dashed(draw, n.x, n.y, n.x, n.y + n.h, stroke, 1)
        dashed(draw, n.x + n.w, n.y, n.x + n.w, n.y + n.h, stroke, 1)
    else:
        draw.rounded_rectangle(b, radius=sp(8), fill=fill, outline=stroke, width=sp(1.4))

    # state dot
    draw.ellipse(
        [sp(n.x + 9), sp(n.y + 11 + DY), sp(n.x + 15), sp(n.y + 17 + DY)], fill=stroke
    )

    title_room = n.w - 30 - (44 if n.badge else 0)
    draw.text(
        (sp(n.x + 21), sp(n.y + 7 + DY)),
        fit(draw, n.title, F_TITLE, title_room),
        font=F_TITLE,
        fill=INK,
    )

    if n.badge:
        bw = draw.textlength(n.badge, font=F_PILL) / S
        draw.rounded_rectangle(
            [sp(n.x + n.w - 8 - bw - 6), sp(n.y + 7 + DY), sp(n.x + n.w - 8), sp(n.y + 19 + DY)],
            radius=sp(4),
            fill=pill_bg,
        )
        draw.text(
            (sp(n.x + n.w - 8 - bw - 3), sp(n.y + 8.6 + DY)),
            n.badge,
            font=F_PILL,
            fill=label_colour,
        )

    draw.text(
        (sp(n.x + 9), sp(n.y + 24 + DY)),
        fit(draw, n.subtitle, F_SUB, n.w - 18),
        font=F_SUB,
        fill=MUTED,
    )

    if n.kind == "terminal":
        return

    # bottom row: state label pill (left) + duration (right)
    pill = n.state.upper() if n.kind == "step" else n.state.upper()
    pw = draw.textlength(pill, font=F_PILL) / S
    draw.rounded_rectangle(
        [sp(n.x + 8), sp(n.y + n.h - 19 + DY), sp(n.x + 8 + pw + 8), sp(n.y + n.h - 7 + DY)],
        radius=sp(3),
        fill=pill_bg,
    )
    draw.text(
        (sp(n.x + 12), sp(n.y + n.h - 17.6 + DY)), pill, font=F_PILL, fill=label_colour
    )
    dur = n.duration
    dw = draw.textlength(dur, font=F_MONO) / S
    draw.text(
        (sp(n.x + n.w - 8 - dw), sp(n.y + n.h - 18 + DY)),
        dur,
        font=F_MONO,
        fill=FAINT if dur == "—" else MUTED,
    )


def edge(draw: ImageDraw.ImageDraw, x: float, y1: float, y2: float, state: str, arrow_head=True):
    colour = EDGE[state]
    if state == "skipped":
        dashed(draw, x, y1, x, y2 - 6, colour, 1)
    else:
        draw.line([sp(x), sp(y1 + DY), sp(x), sp(y2 - 7 + DY)], fill=colour, width=sp(1.3))
    if arrow_head:
        arrow(draw, x, y2, colour)


def render(scenario: dict, filename: str):
    img = Image.new("RGB", (sp(CANVAS_W), sp(CANVAS_H)), CANVAS_BG)
    draw = ImageDraw.Draw(img)

    draw.text((sp(14), sp(12)), scenario["title"], font=F_H1, fill=INK)
    draw.text((sp(14), sp(29)), scenario["caption"], font=F_H2, fill=MUTED)

    nodes: dict[str, Node] = {}

    spine_defs = [
        ("input", "Anomaly received", scenario["input_sub"], "success", "—", None),
        ("context", "Graph context", "0 up · 0 down · blast 0", "success", "1.2ms", None),
        ("rules", "Rule evaluation", "restart_isolated_leaf_service", "success", "0.6ms", "1 rejected"),
        ("severity_action", "Severity & action", "LOW · RESTART_POD", "success", "0.3ms", None),
        ("validation", "Safety validation", scenario["validation_sub"], "success", "4.1ms", scenario["validation_badge"]),
        ("guardrails", "Safety guardrails", scenario["guardrails_sub"], scenario["guardrails_state"], scenario["guardrails_dur"], scenario["guardrails_badge"]),
    ]
    for i, (nid, title, sub, state, dur, badge) in enumerate(spine_defs):
        nodes[nid] = Node(nid, "step", title, sub, state, dur, badge, x=SPINE_CX - NODE_W / 2, y=TOP + i * PITCH)

    branch_defs = [
        ("block", "block", "BLOCK", scenario["block_sub"], scenario["block_state"], "—", scenario["block_badge"]),
        ("shadow", "shadow", "SHADOW", "observe only", "skipped", "—", None),
        ("human", "human", "HUMAN LOOP", scenario["human_sub"], scenario["human_state"], "—", scenario["human_badge"]),
        ("auto", "auto", "AUTO EXECUTE", "confidence high · risk low", scenario["auto_state"], "—", scenario["auto_badge"]),
    ]
    for nid, col, title, sub, state, dur, badge in branch_defs:
        nodes[nid] = Node(nid, "branch", title, sub, state, dur, badge, x=COL[col] - NODE_W / 2, y=BRANCH_Y)

    nodes["block_terminal"] = Node(
        "block_terminal", "terminal", "No action taken", "logged only", scenario["block_term"],
        x=COL["block"] - NODE_W / 2, y=CONT_Y, h=TERM_H,
    )
    nodes["shadow_terminal"] = Node(
        "shadow_terminal", "terminal", "Counterfactual logged", "shadow_records", "skipped",
        x=COL["shadow"] - NODE_W / 2, y=CONT_Y, h=TERM_H,
    )
    nodes["escalation"] = Node(
        "escalation", "step", "Escalation · 3 attempts", scenario["escalation_sub"], scenario["escalation_state"],
        scenario["escalation_dur"], scenario["escalation_badge"], x=COL["human"] - NODE_W / 2, y=CONT_Y,
    )
    nodes["human_decision"] = Node(
        "human_decision", "terminal", scenario["human_term_title"], scenario["human_term_sub"], scenario["human_term_state"],
        x=COL["human"] - NODE_W / 2, y=CONT2_Y,
    )
    nodes["execution"] = Node(
        "execution", "step", "Executor", scenario["execution_sub"], scenario["execution_state"],
        scenario["execution_dur"], scenario["execution_badge"], x=COL["auto"] - NODE_W / 2, y=CONT_Y,
    )
    nodes["outcome"] = Node(
        "outcome", "terminal", scenario["outcome_title"], scenario["outcome_sub"], scenario["outcome_state"],
        x=COL["auto"] - NODE_W / 2, y=CONT2_Y,
    )

    # ── edges ──────────────────────────────────────────────────
    spine_ids = ["input", "context", "rules", "severity_action", "validation", "guardrails"]
    for a, b in zip(spine_ids, spine_ids[1:]):
        src, dst = nodes[a], nodes[b]
        st = "skipped" if dst.state in ("skipped", "pending") else "done"
        edge(draw, src.cx, src.bottom, dst.y, st)

    # queue label on the first edge
    draw.text(
        (sp(nodes["input"].cx + 6), sp(nodes["input"].bottom + 7 + DY)),
        scenario["queue_label"],
        font=F_MONO,
        fill=FAINT,
    )

    edge(draw, nodes["guardrails"].cx, nodes["guardrails"].bottom, BUS_Y, scenario["trunk_state"], arrow_head=False)
    draw.line(
        [sp(COL["block"]), sp(BUS_Y + DY), sp(COL["auto"]), sp(BUS_Y + DY)],
        fill=EDGE[scenario["bus_state"]],
        width=sp(1.3),
    )
    for nid in ("block", "shadow", "human", "auto"):
        n = nodes[nid]
        st = "done" if n.state not in ("skipped", "pending") else "skipped"
        edge(draw, n.cx, BUS_Y, n.y, st)

    for a, b in [
        ("block", "block_terminal"),
        ("shadow", "shadow_terminal"),
        ("human", "escalation"),
        ("escalation", "human_decision"),
        ("auto", "execution"),
        ("execution", "outcome"),
    ]:
        src, dst = nodes[a], nodes[b]
        st = "skipped" if dst.state in ("skipped", "pending") else "done"
        edge(draw, dst.cx, src.bottom, dst.y, st)

    for n in nodes.values():
        draw_node(draw, n)

    # ── legend ─────────────────────────────────────────────────
    legend = [
        ("active", "running"),
        ("success", "done"),
        ("shadow", "shadow"),
        ("escalated", "escalated"),
        ("blocked", "blocked"),
        ("failed", "failed"),
        ("skipped", "not taken"),
    ]
    lx = 14.0
    ly = H + HEADER + 16
    for state, label in legend:
        stroke = STATE[state][0]
        draw.ellipse([sp(lx), sp(ly - 8), sp(lx + 6), sp(ly - 2)], fill=stroke)
        draw.text((sp(lx + 10), sp(ly - 10)), label, font=F_LEG, fill=MUTED)
        lx += 10 + draw.textlength(label, font=F_LEG) / S + 16

    draw.text(
        (sp(lx + 4), sp(ly - 10)),
        "—  = not instrumented",
        font=F_LEG,
        fill=FAINT,
    )

    img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename))
    print("wrote", filename, img.size)


BASE = dict(
    input_sub="17:45:53 · ANM-metrics-collector",
    validation_sub="conf 88% · risk LOW",
    validation_badge="Auto-execute",
    queue_label="+8.4s queued",
)

AUTO = dict(
    BASE,
    title="Decision engine run — AUTO_EXECUTE",
    caption="16 nodes · 7 stages · the guardrails passed and the executor ran",
    guardrails_sub="cooldown · counter · idempotency",
    guardrails_state="success",
    guardrails_dur="0.9ms",
    guardrails_badge="passed",
    block_sub="safety veto",
    block_state="skipped",
    block_badge=None,
    block_term="skipped",
    human_sub="asks a human",
    human_state="skipped",
    human_badge=None,
    auto_state="success",
    auto_badge="gate passed",
    execution_sub="SUCCESS",
    execution_state="success",
    execution_dur="1.4s",
    execution_badge="SUCCESS",
    outcome_title="Recovered",
    outcome_sub="pod restarted",
    outcome_state="success",
    escalation_sub="not created",
    escalation_state="skipped",
    escalation_dur="—",
    escalation_badge=None,
    human_term_title="Awaiting operator",
    human_term_sub="schedule: T+0 · T+5m · T+15m",
    human_term_state="skipped",
    trunk_state="done",
    bus_state="done",
)

HUMAN = dict(
    BASE,
    title="Decision engine run — HUMAN_LOOP",
    caption="risk HIGH · 2 of 3 escalation attempts sent · waiting on an operator",
    validation_sub="conf 62% · risk HIGH",
    validation_badge="Human in the loop",
    guardrails_sub="not required for this outcome",
    guardrails_state="skipped",
    guardrails_dur="—",
    guardrails_badge=None,
    block_sub="safety veto",
    block_state="skipped",
    block_badge=None,
    block_term="skipped",
    human_sub="2/3 attempts",
    human_state="escalated",
    human_badge="approval",
    auto_state="skipped",
    auto_badge=None,
    execution_sub="not reached",
    execution_state="skipped",
    execution_dur="—",
    execution_badge=None,
    outcome_title="Action dispatched",
    outcome_sub="awaiting executor",
    outcome_state="skipped",
    escalation_sub="attempt 2/3 · AWAITING_HUMAN",
    escalation_state="escalated",
    escalation_dur="4.2s",
    escalation_badge="2/3",
    human_term_title="Awaiting operator",
    human_term_sub="T+0 sent · T+5m sent · T+15m pending",
    human_term_state="escalated",
    trunk_state="done",
    bus_state="done",
)

BLOCK = dict(
    BASE,
    title="Decision engine run — BLOCK (guardrail veto)",
    caption="the same action was already attempted inside the cooldown window",
    validation_sub="conf 88% · risk LOW",
    validation_badge="Auto-execute",
    guardrails_sub="vetoed the action",
    guardrails_state="blocked",
    guardrails_dur="1.1ms",
    guardrails_badge="blocked",
    block_sub="guardrail veto",
    block_state="blocked",
    block_badge="guardrail",
    block_term="blocked",
    human_sub="asks a human",
    human_state="skipped",
    human_badge=None,
    auto_state="skipped",
    auto_badge=None,
    execution_sub="not reached",
    execution_state="skipped",
    execution_dur="—",
    execution_badge=None,
    outcome_title="Action dispatched",
    outcome_sub="awaiting executor",
    outcome_state="skipped",
    escalation_sub="not created",
    escalation_state="skipped",
    escalation_dur="—",
    escalation_badge=None,
    human_term_title="Awaiting operator",
    human_term_sub="schedule: T+0 · T+5m · T+15m",
    human_term_state="skipped",
    trunk_state="done",
    bus_state="done",
)


if __name__ == "__main__":
    render(AUTO, "decision-engine-flow-auto.png")
    render(HUMAN, "decision-engine-flow-human.png")
    render(BLOCK, "decision-engine-flow-block.png")
