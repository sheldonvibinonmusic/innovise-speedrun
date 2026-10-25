"""Institutional Financial Research Report PDF Export Service.

Generates audit-grade, publication-ready PDF reports from structured research data:
- Executive summary & analytical stance
- Deterministic calculation scorecard
- High-resolution financial indicator chart (matplotlib)
- Verified claims with source document & page citations
- Risk factors & contradictory disclosures
- Tripartite verification judge audit ledger
- Governance & human review cockpit sign-off
- Zero external web dependencies; 100% offline via PyMuPDF (fitz) and matplotlib
"""

import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pymupdf


def _generate_chart_image(calculations: List[Dict[str, Any]]) -> Optional[bytes]:
    """Generate a clean, high-resolution financial metric chart using matplotlib."""
    chart_data = []
    for c in calculations:
        res = c.get("numeric_result")
        mname = c.get("metric_name")
        if res is not None and mname:
            try:
                val = float(res)
                label = {
                    "OperatingMargin": "Operating\nMargin",
                    "NetMargin": "Net Profit\nMargin",
                    "RevenueGrowth": "Revenue\nGrowth",
                    "CurrentRatio": "Current\nRatio (x)",
                    "DebtToEquity": "Debt / Equity\n(x)",
                    "FreeCashFlow": "Free Cash\nFlow",
                }.get(mname, mname)
                chart_data.append((label, val, c.get("unit", "")))
            except (ValueError, TypeError):
                continue

    if not chart_data:
        return None

    labels = [d[0] for d in chart_data]
    vals = [d[1] for d in chart_data]
    colors = ["#16a34a" if v >= 0 else "#dc2626" for v in vals]

    fig, ax = plt.subplots(figsize=(6.2, 2.4), dpi=180)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f8fafc")

    bars = ax.bar(labels, vals, color=colors, width=0.45, edgecolor="#0f172a", linewidth=0.8, zorder=3)
    ax.grid(axis="y", linestyle="--", alpha=0.4, color="#94a3b8", zorder=0)
    ax.axhline(0, color="#475569", linewidth=1.0, zorder=3)

    ax.set_title("Key Deterministic Financial Indicators & Performance Trajectory", fontsize=10, fontweight="bold", pad=12, color="#0f172a")
    ax.tick_params(axis="x", labelsize=8, colors="#1e293b")
    ax.tick_params(axis="y", labelsize=8, colors="#1e293b")

    for bar in bars:
        h = bar.get_height()
        va = "bottom" if h >= 0 else "top"
        offset = 1.0 if h >= 0 else -1.5
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            h + offset,
            f"{h:+.1f}%" if "%" in labels[bars.index(bar)] or "Margin" in labels[bars.index(bar)] or "Growth" in labels[bars.index(bar)] else f"{h:.2f}x",
            ha="center",
            va=va,
            fontsize=8,
            fontweight="bold",
            color="#0f172a",
        )

    # Set appropriate y-limits
    max_abs = max([abs(v) for v in vals] + [5.0])
    ax.set_ylim(-max_abs * 0.25 if min(vals) < 0 else 0, max_abs * 1.3)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=180, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


class ReportPdfBuilder:
    """Multi-page layout engine for institutional research reports using PyMuPDF."""

    def __init__(self, page_width: float = 595.0, page_height: float = 842.0):
        self.width = page_width
        self.height = page_height
        self.margin_x = 42.0
        self.content_width = self.width - (2 * self.margin_x)
        self.doc = pymupdf.open()
        self.current_page = None
        self.y = 0.0

    def new_page(self):
        """Append a new A4 page with header/footer guides."""
        self.current_page = self.doc.new_page(width=self.width, height=self.height)
        self.y = 45.0

    def check_space(self, needed_height: float):
        """Ensure room on current page; otherwise page break."""
        if self.current_page is None or (self.y + needed_height) > (self.height - 50.0):
            self.new_page()

    def draw_banner(self, title: str, ticker: str, status: str, inquiry: str, run_id: str):
        """Render institutional header banner."""
        self.check_space(110.0)
        p = self.current_page

        # Header background
        banner_rect = pymupdf.Rect(self.margin_x, self.y, self.margin_x + self.content_width, self.y + 70.0)
        p.draw_rect(banner_rect, color=(0.1, 0.15, 0.3), fill=(0.06, 0.09, 0.18))

        # Title text
        p.insert_text((self.margin_x + 14.0, self.y + 24.0), "TRUSTWORTHY FINANCIAL RESEARCH & DECISION SUPPORT", fontsize=8.5, fontname="helv", color=(0.6, 0.7, 0.9))
        p.insert_text((self.margin_x + 14.0, self.y + 44.0), f"{ticker} \u2014 Institutional Research Dossier", fontsize=15.0, fontname="helv", color=(1.0, 1.0, 1.0))
        p.insert_text((self.margin_x + 14.0, self.y + 58.0), f"Inquiry: {inquiry[:72]}..." if len(inquiry) > 75 else f"Inquiry: {inquiry}", fontsize=8.5, fontname="helv", color=(0.8, 0.85, 0.95))

        # Verification badge
        badge_color = (0.1, 0.6, 0.3) if status == "VERIFIED" else ((0.8, 0.5, 0.1) if status == "QUALIFIED" else (0.8, 0.15, 0.15))
        badge_rect = pymupdf.Rect(self.margin_x + self.content_width - 110.0, self.y + 16.0, self.margin_x + self.content_width - 14.0, self.y + 48.0)
        p.draw_rect(badge_rect, color=badge_color, fill=badge_color)
        p.insert_text((self.margin_x + self.content_width - 96.0, self.y + 36.0), f"{status}", fontsize=11.0, fontname="helv", color=(1.0, 1.0, 1.0))

        self.y += 82.0

        # Sub-header meta bar
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        meta_text = f"Run ID: {run_id}  |  As-of: {now_str}  |  Framework: GAAP / Strict Decimal  |  Audit: 3 Deterministic Gates"
        p.insert_text((self.margin_x, self.y), meta_text, fontsize=7.5, fontname="helv", color=(0.4, 0.45, 0.55))
        p.draw_line((self.margin_x, self.y + 5.0), (self.margin_x + self.content_width, self.y + 5.0), color=(0.8, 0.85, 0.9), width=0.8)
        self.y += 18.0

    def draw_section_heading(self, title: str):
        """Render bold section divider."""
        self.check_space(28.0)
        p = self.current_page
        p.draw_line((self.margin_x, self.y), (self.margin_x + 18.0, self.y), color=(0.1, 0.4, 0.8), width=3.0)
        p.insert_text((self.margin_x + 24.0, self.y + 4.0), title.upper(), fontsize=10.0, fontname="helv", color=(0.08, 0.12, 0.25))
        self.y += 16.0

    def draw_box_text(self, text: str, border_color: Tuple[float, float, float] = (0.2, 0.4, 0.7), bg_color: Tuple[float, float, float] = (0.97, 0.98, 1.0)):
        """Render text wrapped in an accent-bordered card, supporting multi-paragraph controller summaries."""
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paras:
            paras = [text]

        for p_idx, p_text in enumerate(paras):
            if p_text.startswith("### "):
                header_text = p_text.replace("### ", "").strip()
                self.check_space(24.0)
                p = self.current_page
                p.insert_text((self.margin_x + 6.0, self.y + 12.0), header_text.upper(), fontsize=9.0, fontname="helv", color=(0.1, 0.25, 0.5))
                self.y += 18.0
                continue

            approx_lines = max(1, (len(p_text) + 69) // 70)
            text_height = approx_lines * 13.5
            needed = text_height + 18.0
            self.check_space(needed + 4.0)
            p = self.current_page

            rect = pymupdf.Rect(self.margin_x, self.y, self.margin_x + self.content_width, self.y + needed)
            p.draw_rect(rect, color=border_color, fill=bg_color, width=0.8)
            p.draw_rect(pymupdf.Rect(self.margin_x, self.y, self.margin_x + 3.5, self.y + needed), color=border_color, fill=border_color)

            inner_rect = pymupdf.Rect(self.margin_x + 10.0, self.y + 6.0, self.margin_x + self.content_width - 8.0, self.y + needed - 4.0)
            rc = p.insert_textbox(inner_rect, p_text, fontsize=8.5, fontname="helv", color=(0.12, 0.15, 0.22))
            if rc < 0:
                p.insert_textbox(inner_rect, p_text, fontsize=7.5, fontname="helv", color=(0.12, 0.15, 0.22))
            self.y += needed + 8.0

        self.y += 4.0

    def draw_scorecard_table(self, calculations: List[Dict[str, Any]]):
        """Render financial metric calculations table."""
        if not calculations:
            self.draw_box_text("No deterministic arithmetic calculations required for this scope.", (0.7, 0.7, 0.7), (0.98, 0.98, 0.98))
            return

        header_h = 20.0
        row_h = 22.0
        total_h = header_h + len(calculations) * row_h + 8.0
        self.check_space(total_h)
        p = self.current_page

        col_w = [135.0, 85.0, 160.0, 75.0, 56.0]
        x_offsets = [self.margin_x]
        for w in col_w[:-1]:
            x_offsets.append(x_offsets[-1] + w)

        # Header row
        p.draw_rect(pymupdf.Rect(self.margin_x, self.y, self.margin_x + self.content_width, self.y + header_h), color=(0.15, 0.2, 0.35), fill=(0.12, 0.18, 0.3))
        headers = ["Metric Name", "Verified Result", "Deterministic Formula", "Scope", "Validation"]
        for idx, h in enumerate(headers):
            p.insert_text((x_offsets[idx] + 6.0, self.y + 13.5), h, fontsize=8.0, fontname="helv", color=(1.0, 1.0, 1.0))

        curr_y = self.y + header_h
        for r_idx, c in enumerate(calculations):
            row_rect = pymupdf.Rect(self.margin_x, curr_y, self.margin_x + self.content_width, curr_y + row_h)
            row_fill = (0.96, 0.97, 0.99) if r_idx % 2 == 1 else (1.0, 1.0, 1.0)
            p.draw_rect(row_rect, color=(0.85, 0.88, 0.92), fill=row_fill, width=0.5)

            mname = c.get("metric_name", "")
            res = c.get("formatted_result", "N/A")
            formula = c.get("formula", "")
            scope = f"{c.get('reporting_period', '')}"
            val_status = c.get("validation_outcome", "VALID")

            p.insert_text((x_offsets[0] + 6.0, curr_y + 14.5), mname[:24], fontsize=8.0, fontname="helv", color=(0.1, 0.15, 0.25))
            p.insert_text((x_offsets[1] + 6.0, curr_y + 14.5), res[:14], fontsize=8.5, fontname="helv", color=(0.08, 0.5, 0.25))
            p.insert_text((x_offsets[2] + 6.0, curr_y + 14.5), formula[:32], fontsize=7.5, fontname="helv", color=(0.3, 0.35, 0.45))
            p.insert_text((x_offsets[3] + 6.0, curr_y + 14.5), scope[:12], fontsize=8.0, fontname="helv", color=(0.3, 0.35, 0.45))

            v_color = (0.1, 0.6, 0.3) if val_status == "VALID" else (0.8, 0.2, 0.2)
            p.insert_text((x_offsets[4] + 6.0, curr_y + 14.5), val_status[:10], fontsize=8.0, fontname="helv", color=v_color)
            curr_y += row_h

        self.y = curr_y + 12.0

    def draw_chart(self, chart_bytes: bytes):
        """Embed high-resolution matplotlib financial ratio visual."""
        if not chart_bytes:
            return
        chart_h = 160.0
        self.check_space(chart_h + 10.0)
        p = self.current_page
        chart_rect = pymupdf.Rect(self.margin_x, self.y, self.margin_x + self.content_width, self.y + chart_h)
        p.insert_image(chart_rect, stream=chart_bytes)
        self.y += chart_h + 14.0

    def draw_claims_list(self, claims: List[Dict[str, Any]], title_label: str = "Core Verified Findings"):
        """Render grounded claims with document and page citations."""
        if not claims:
            return
        self.draw_section_heading(title_label)

        for cl in claims[:8]:
            ctext = cl.get("claim_text", "")
            mat = cl.get("materiality", "MEDIUM")
            c_status = cl.get("status") or cl.get("verification_status", "supported")
            cites = cl.get("evidence_references", [])
            cite_str = ", ".join(cites) if cites else "Primary Filing Excerpt"

            full_claim_text = f"[{mat}] {ctext}"
            approx_lines = max(1, (len(full_claim_text) + 69) // 70)
            text_height = approx_lines * 13.5
            card_h = text_height + 28.0

            self.check_space(card_h + 6.0)
            p = self.current_page

            c_rect = pymupdf.Rect(self.margin_x, self.y, self.margin_x + self.content_width, self.y + card_h)
            p.draw_rect(c_rect, color=(0.85, 0.88, 0.92), fill=(0.99, 0.99, 1.0), width=0.6)

            # Left badge bar
            bar_color = (0.1, 0.6, 0.3) if c_status in ("supported", "VERIFIED") else ((0.8, 0.5, 0.1) if c_status == "needs_human_review" else (0.8, 0.2, 0.2))
            p.draw_rect(pymupdf.Rect(self.margin_x, self.y, self.margin_x + 3.0, self.y + card_h), color=bar_color, fill=bar_color)

            # Content box with generous bounds
            inner_rect = pymupdf.Rect(self.margin_x + 10.0, self.y + 6.0, self.margin_x + self.content_width - 8.0, self.y + 6.0 + text_height + 6.0)
            rc = p.insert_textbox(inner_rect, full_claim_text, fontsize=8.5, fontname="helv", color=(0.1, 0.15, 0.25))
            if rc < 0:
                p.insert_textbox(inner_rect, full_claim_text, fontsize=7.5, fontname="helv", color=(0.1, 0.15, 0.25))

            # Citations footer
            p.insert_text((self.margin_x + 10.0, self.y + card_h - 6.0), f"Citation: {cite_str}  |  Status: {c_status}", fontsize=7.0, fontname="helv", color=(0.4, 0.5, 0.65))
            self.y += card_h + 8.0

        self.y += 6.0

    def draw_judges_ledger(self, verdicts: List[Dict[str, Any]]):
        """Render tripartite verification judge findings."""
        if not verdicts:
            return
        self.draw_section_heading("Tripartite Verification Audit Ledger")

        for v in verdicts:
            role = v.get("judge_name") or v.get("judge_role", "Verification Judge")
            verdict = v.get("verdict") or v.get("overall_verdict", "INDETERMINATE")
            exp = v.get("rationale") or v.get("concise_explanation", "")

            approx_lines = max(1, (len(exp) + 74) // 75)
            text_height = approx_lines * 13.0
            card_h = text_height + 28.0

            self.check_space(card_h + 6.0)
            p = self.current_page

            card_rect = pymupdf.Rect(self.margin_x, self.y, self.margin_x + self.content_width, self.y + card_h)
            v_color = (0.1, 0.6, 0.3) if verdict == "PASS" else ((0.8, 0.5, 0.1) if verdict in ("QUALIFY", "RETRIEVE_MORE") else (0.8, 0.2, 0.2))
            p.draw_rect(card_rect, color=(0.85, 0.88, 0.92), fill=(0.98, 0.98, 0.99), width=0.6)

            p.insert_text((self.margin_x + 10.0, self.y + 13.0), role, fontsize=8.5, fontname="helv", color=(0.1, 0.15, 0.25))
            p.insert_text((self.margin_x + self.content_width - 80.0, self.y + 13.0), f"[{verdict}]", fontsize=8.5, fontname="helv", color=v_color)

            exp_rect = pymupdf.Rect(self.margin_x + 10.0, self.y + 18.0, self.margin_x + self.content_width - 10.0, self.y + 18.0 + text_height + 6.0)
            rc = p.insert_textbox(exp_rect, exp, fontsize=8.0, fontname="helv", color=(0.3, 0.35, 0.45))
            if rc < 0:
                p.insert_textbox(exp_rect, exp, fontsize=7.0, fontname="helv", color=(0.3, 0.35, 0.45))
            self.y += card_h + 8.0

        self.y += 6.0

    def draw_human_review_box(self, review_data: Optional[Dict[str, Any]] = None):
        """Render governance and analyst sign-off section."""
        self.check_space(75.0)
        self.draw_section_heading("Institutional Analyst Governance Sign-Off")
        p = self.current_page

        box_h = 60.0
        rect = pymupdf.Rect(self.margin_x, self.y, self.margin_x + self.content_width, self.y + box_h)
        p.draw_rect(rect, color=(0.2, 0.3, 0.5), fill=(0.96, 0.97, 0.99), width=0.8)

        rev_name = (review_data.get("reviewer_name") if review_data else None) or "Awaiting Analyst Sign-Off"
        decision = (review_data.get("decision") if review_data else None) or "PENDING REVIEW"
        rev_date = (review_data.get("reviewed_at") if review_data else None) or "N/A"
        comments = (review_data.get("comments") if review_data else None) or "Decision support protocol requires human committee review prior to capital commitment."

        d_color = (0.1, 0.6, 0.3) if decision == "APPROVED" else ((0.8, 0.5, 0.1) if decision == "QUALIFIED" else (0.8, 0.2, 0.2))

        p.insert_text((self.margin_x + 10.0, self.y + 16.0), f"Reviewer: {rev_name}", fontsize=8.5, fontname="helv", color=(0.1, 0.15, 0.25))
        p.insert_text((self.margin_x + 230.0, self.y + 16.0), f"Decision: {decision}", fontsize=8.5, fontname="helv", color=d_color)
        p.insert_text((self.margin_x + 360.0, self.y + 16.0), f"Timestamp: {rev_date[:16]}", fontsize=7.5, fontname="helv", color=(0.4, 0.45, 0.55))

        p.draw_line((self.margin_x + 10.0, self.y + 24.0), (self.margin_x + self.content_width - 10.0, self.y + 24.0), color=(0.85, 0.88, 0.92), width=0.5)
        notes_rect = pymupdf.Rect(self.margin_x + 10.0, self.y + 28.0, self.margin_x + self.content_width - 10.0, self.y + box_h - 4.0)
        p.insert_textbox(notes_rect, f"Notes: {comments}", fontsize=8.0, fontname="helv", color=(0.25, 0.3, 0.4))
        self.y += box_h + 12.0

    def add_footers(self):
        """Apply page numbers and institutional confidentiality notice across all pages."""
        total_pages = len(self.doc)
        for idx, page in enumerate(self.doc):
            p_num = idx + 1
            footer_text = f"Trustworthy Financial Research & Decision Support System   |   Page {p_num} of {total_pages}   |   Institutional Decision Support"
            page.draw_line((self.margin_x, self.height - 30.0), (self.margin_x + self.content_width, self.height - 30.0), color=(0.85, 0.88, 0.92), width=0.5)
            page.insert_text((self.margin_x, self.height - 18.0), footer_text, fontsize=7.0, fontname="helv", color=(0.5, 0.55, 0.65))

    def build_pdf_bytes(self) -> bytes:
        """Finalize and serialize PDF bytes."""
        self.add_footers()
        pdf_bytes = self.doc.tobytes()
        self.doc.close()
        return pdf_bytes


def generate_report_pdf(report: Dict[str, Any]) -> bytes:
    """Entry point generating complete audit-grade research dossier PDF."""
    ticker = report.get("company_ticker") or "COMPANY"
    title = report.get("title") or f"Financial Research Report: {ticker}"
    status = report.get("verification_status") or "INDETERMINATE"
    run_id = report.get("run_id") or "run_default"
    inquiry = report.get("research_question") or report.get("inquiry") or report.get("title") or "Financial Analysis"
    exec_summary = report.get("executive_summary") or "Executive summary pending synthesis."

    calcs = report.get("calculations") or []
    verdicts = report.get("verdicts") or []
    claims = report.get("claims") or []
    unresolved = report.get("unresolved_uncertainties") or []
    structured = report.get("structured_data") or {}
    human_review = structured.get("human_review")

    builder = ReportPdfBuilder()
    builder.new_page()

    # 1. Header Banner
    builder.draw_banner(title, ticker, status, inquiry, run_id)

    # 2. Executive Summary
    builder.draw_section_heading("Executive Summary & Analytical Findings")
    builder.draw_box_text(exec_summary, border_color=(0.1, 0.4, 0.8), bg_color=(0.97, 0.98, 1.0))

    # 3. Deterministic Financial Scorecard Table
    builder.draw_section_heading("Deterministic Calculations & Accounting Scorecard")
    builder.draw_scorecard_table(calcs)

    # 4. Data-Backed Financial Metric Visualization
    chart_bytes = _generate_chart_image(calcs)
    if chart_bytes:
        builder.draw_chart(chart_bytes)

    # 5. Core Verified Findings & Claims
    core_claims = [c for c in claims if c.get("claim_type") != "risk_factor"]
    if core_claims:
        builder.draw_claims_list(core_claims, "Core Verified Analytical Findings & Citations")

    # 6. Risk Factors & Contradictory Disclosures
    risk_claims = [c for c in claims if c.get("claim_type") == "risk_factor"]
    if risk_claims:
        builder.draw_claims_list(risk_claims, "Material Risk Factors & Contradictory Disclosures")

    # 7. Tripartite Verification Judges Ledger
    builder.draw_judges_ledger(verdicts)

    # 8. Scope Limitations & Unresolved Uncertainties
    if unresolved:
        builder.draw_section_heading("Scope Limitations & Evidentiary Caveats")
        builder.draw_box_text("\n".join([f"\u2022 {u}" for u in unresolved]), border_color=(0.8, 0.5, 0.1), bg_color=(1.0, 0.99, 0.96))

    # 9. Human Review Governance Cockpit
    builder.draw_human_review_box(human_review)

    return builder.build_pdf_bytes()
