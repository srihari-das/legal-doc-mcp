"""
PDF Compliance Analyzer MCP Server

A standalone DMCP (Dedalus Model Context Protocol) server providing
financial compliance PDF analysis tools. Supports 10-K, SOX 404,
8-K, and Invoice documents.

Owner: Person 1
"""

from dedalus_mcp import MCPServer, tool, ToolError
import pymupdf
import json
from typing import List, Dict
import re

server = MCPServer(
    name="pdf-compliance-analyzer",
    version="1.0.0",
    instructions="Financial compliance PDF analysis with regulatory intelligence",
    streamable_http_stateless=True,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_required_sections(doc_type: str) -> List[Dict]:
    """
    Returns required sections for each document type.
    Each section has: name, critical (bool), search_terms (list of alternatives)
    """
    sections = {
        "10-K": [
            {"name": "Item 1: Business", "critical": False, "search_terms": ["item 1", "business"]},
            {"name": "Item 1A: Risk Factors", "critical": True, "search_terms": ["item 1a", "risk factors"]},
            {"name": "Item 7: MD&A", "critical": True, "search_terms": ["item 7", "management's discussion", "md&a"]},
            {"name": "Item 8: Financial Statements", "critical": True, "search_terms": ["item 8", "financial statements"]},
            {"name": "Item 9A: Controls and Procedures", "critical": True, "search_terms": ["item 9a", "controls and procedures"]},
        ],
        "SOX 404": [
            {"name": "IT General Controls", "critical": True, "search_terms": ["it general controls", "itgc", "it controls"]},
            {"name": "Access Controls", "critical": True, "search_terms": ["access controls", "access management"]},
            {"name": "Change Management", "critical": False, "search_terms": ["change management", "change controls"]},
            {"name": "Management Assessment", "critical": True, "search_terms": ["management assessment", "management certification"]},
        ],
        "8-K": [
            {"name": "Item 1.01: Material Agreements", "critical": True, "search_terms": ["item 1.01", "material definitive agreement", "material agreement"]},
            {"name": "Item 2.01: Acquisition/Disposition", "critical": True, "search_terms": ["item 2.01", "acquisition", "disposition of assets"]},
            {"name": "Item 5.02: Officer Changes", "critical": False, "search_terms": ["item 5.02", "departure of directors", "officer changes"]},
            {"name": "Item 9.01: Financial Statements/Exhibits", "critical": True, "search_terms": ["item 9.01", "financial statements and exhibits"]},
            {"name": "Filing Timeliness", "critical": True, "search_terms": ["date of report", "date of earliest event"]},
        ],
        "Invoice": [
            {"name": "Invoice Number", "critical": True, "search_terms": ["invoice number", "invoice #", "inv #", "invoice no"]},
            {"name": "Date", "critical": True, "search_terms": ["date", "invoice date"]},
            {"name": "Line Items", "critical": True, "search_terms": ["description", "line items", "item"]},
            {"name": "Total", "critical": True, "search_terms": ["total", "amount due", "balance due"]},
            {"name": "Payment Terms", "critical": False, "search_terms": ["payment terms", "due date", "net 30", "net 60"]},
        ],
    }
    return sections.get(doc_type, [])


def parse_currency(text: str) -> float:
    """
    Extract numeric value from currency string.
    Handles: $1,000.00, (500), 1000, $1M, dashes as zero
    """
    if not text:
        return None

    try:
        text = str(text).strip()

        # Handle empty or dash
        if text in ["", "-", "\u2014", "\u2013", "N/A", "n/a"]:
            return 0.0

        # Check if negative (parentheses)
        is_negative = "(" in text and ")" in text

        # Remove non-numeric except decimal point
        cleaned = re.sub(r"[^\d.]", "", text)

        if not cleaned:
            return None

        value = float(cleaned)

        # Handle millions/thousands abbreviations
        if "M" in text.upper() and "MANAGEMENT" not in text.upper():
            value *= 1_000_000
        elif "K" in text.upper():
            value *= 1_000

        return -value if is_negative else value

    except Exception:
        return None


def search_text_in_pdf(doc, search_terms: List[str]) -> Dict:
    """
    Search for terms (case-insensitive) and return first match with context.
    Returns: {"found": bool, "page": int, "excerpt": str}
    """
    for page_num, page in enumerate(doc):
        text = page.get_text()
        text_lower = text.lower()

        for term in search_terms:
            if term.lower() in text_lower:
                pos = text_lower.find(term.lower())
                excerpt_start = max(0, pos - 100)
                excerpt_end = min(len(text), pos + 200)

                return {
                    "found": True,
                    "page": page_num + 1,
                    "excerpt": text[excerpt_start:excerpt_end].strip(),
                }

    return {"found": False, "page": None, "excerpt": None}


# ============================================================================
# TOOL 1: FIND REGULATORY SECTIONS
# ============================================================================


@tool(
    name="find_regulatory_sections",
    description="Find required compliance sections in PDF based on document type (10-K, SOX 404, 8-K, Invoice)",
)
async def find_regulatory_sections(pdf_path: str, doc_type: str) -> str:
    """Find required sections based on document type."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        raise ToolError(f"Failed to open PDF: {e}")

    try:
        required_sections = get_required_sections(doc_type)

        sections_found = {}
        missing_critical = []

        for section in required_sections:
            result = search_text_in_pdf(doc, section["search_terms"])

            sections_found[section["name"]] = {
                "required": True,
                "critical": section["critical"],
                "found": result["found"],
                "page": result["page"],
                "excerpt": result["excerpt"],
            }

            if section["critical"] and not result["found"]:
                missing_critical.append(section["name"])

        doc.close()

        total_required = len(required_sections)
        total_found = sum(1 for s in sections_found.values() if s["found"])

        return json.dumps(
            {
                "success": True,
                "doc_type": doc_type,
                "sections_found": sections_found,
                "summary": {
                    "total_required": total_required,
                    "total_found": total_found,
                    "missing_critical": missing_critical,
                },
            },
            indent=2,
        )

    except ToolError:
        raise
    except Exception as e:
        doc.close()
        raise ToolError(f"Failed to find regulatory sections: {e}")


# ============================================================================
# TOOL 2: EXTRACT FINANCIAL STATEMENTS
# ============================================================================


@tool(
    name="extract_financial_statements",
    description="Extract financial statements from PDF and identify their type (Balance Sheet, Income Statement, etc.)",
)
async def extract_financial_statements(pdf_path: str) -> str:
    """Extract and classify financial statements."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        raise ToolError(f"Failed to open PDF: {e}")

    try:
        statements = []

        for page_num, page in enumerate(doc):
            page_text = page.get_text().lower()

            # Detect statement type
            statement_type = None
            if "balance sheet" in page_text or "statement of financial position" in page_text:
                statement_type = "Balance Sheet"
            elif "income statement" in page_text or "statement of operations" in page_text or "p&l" in page_text:
                statement_type = "Income Statement"
            elif "cash flow" in page_text:
                statement_type = "Cash Flow Statement"
            elif "invoice" in page_text or "bill to" in page_text:
                statement_type = "Invoice"

            if not statement_type:
                continue

            # Extract tables
            tables = page.find_tables()
            if not tables or not tables.tables:
                continue

            for table in tables.tables:
                table_data = table.extract()

                # Look for period columns (years)
                periods = []
                if table_data:
                    header_row = table_data[0]
                    for cell in header_row:
                        if re.search(r"20\d{2}", str(cell)):
                            periods.append(str(cell).strip())

                # Extract key items
                key_items = {}
                for row in table_data[1:]:
                    if row and len(row) > 0:
                        item_name = str(row[0]).strip()
                        if any(
                            keyword in item_name.lower()
                            for keyword in [
                                "total assets",
                                "total liabilities",
                                "total equity",
                                "stockholders",
                                "revenue",
                                "net income",
                                "net loss",
                                "total",
                                "subtotal",
                                "operating",
                                "investing",
                                "financing",
                            ]
                        ):
                            values = {}
                            for i, period in enumerate(periods):
                                if i + 1 < len(row):
                                    values[period] = parse_currency(row[i + 1])
                            key_items[item_name] = values

                statements.append(
                    {
                        "type": statement_type,
                        "page": page_num + 1,
                        "periods": periods,
                        "key_items": key_items,
                        "table_data": table_data[:10],
                    }
                )

        doc.close()

        return json.dumps({"success": True, "statements": statements}, indent=2)

    except ToolError:
        raise
    except Exception as e:
        doc.close()
        raise ToolError(f"Failed to extract financial statements: {e}")


# ============================================================================
# TOOL 3: VALIDATE FINANCIAL MATH
# ============================================================================


@tool(
    name="validate_financial_math",
    description="Validate mathematical accuracy in financial documents (balance sheet equation, invoice totals, table sums)",
)
async def validate_financial_math(pdf_path: str) -> str:
    """Validate financial calculations."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        raise ToolError(f"Failed to open PDF: {e}")

    try:
        errors = []
        warnings = []
        tables_checked = 0

        for page_num, page in enumerate(doc):
            page_text = page.get_text().lower()
            tables = page.find_tables()

            if not tables or not tables.tables:
                continue

            for table_num, table in enumerate(tables.tables):
                table_data = table.extract()
                tables_checked += 1

                if not table_data or len(table_data) < 2:
                    continue

                # Check balance sheet equation
                if "balance sheet" in page_text or "statement of financial position" in page_text:
                    assets = None
                    liabilities = None
                    equity = None

                    for row in table_data:
                        if row and len(row) >= 2:
                            label = str(row[0]).lower()
                            if "total assets" in label:
                                assets = parse_currency(row[1])
                            elif "total liabilities" in label:
                                liabilities = parse_currency(row[1])
                            elif "total equity" in label or "total stockholders" in label:
                                equity = parse_currency(row[1])

                    if assets and liabilities and equity:
                        diff = abs(assets - (liabilities + equity))
                        if diff > 0.01:
                            errors.append(
                                {
                                    "type": "Balance Sheet Imbalance",
                                    "page": page_num + 1,
                                    "severity": "critical",
                                    "assets": assets,
                                    "liabilities_equity": liabilities + equity,
                                    "difference": round(diff, 2),
                                    "description": (
                                        f"Assets (${assets:,.2f}) != "
                                        f"Liabilities + Equity (${liabilities + equity:,.2f})"
                                    ),
                                }
                            )

                # Check income statement equation
                if "income statement" in page_text or "statement of operations" in page_text:
                    revenue = None
                    expenses = None
                    net_income = None

                    for row in table_data:
                        if row and len(row) >= 2:
                            label = str(row[0]).lower()
                            if "total revenue" in label or "net revenue" in label:
                                revenue = parse_currency(row[1])
                            elif "total expenses" in label or "total operating expenses" in label:
                                expenses = parse_currency(row[1])
                            elif "net income" in label or "net loss" in label:
                                net_income = parse_currency(row[1])

                    if revenue is not None and expenses is not None and net_income is not None:
                        expected = revenue - expenses
                        diff = abs(expected - net_income)
                        if diff > 0.01:
                            errors.append(
                                {
                                    "type": "Income Statement Mismatch",
                                    "page": page_num + 1,
                                    "severity": "critical",
                                    "revenue": revenue,
                                    "expenses": expenses,
                                    "expected_net": round(expected, 2),
                                    "reported_net": net_income,
                                    "difference": round(diff, 2),
                                    "description": (
                                        f"Revenue - Expenses (${expected:,.2f}) != "
                                        f"Net Income (${net_income:,.2f})"
                                    ),
                                }
                            )

                # Check column sums for all tables
                if len(table_data) >= 3:
                    num_cols = len(table_data[0])

                    for col_idx in range(1, num_cols):
                        numbers = []
                        for row_idx in range(len(table_data) - 1):
                            if row_idx < len(table_data) and col_idx < len(table_data[row_idx]):
                                value = parse_currency(table_data[row_idx][col_idx])
                                if value is not None:
                                    numbers.append(value)

                        if numbers:
                            calculated_sum = sum(numbers)
                            if col_idx < len(table_data[-1]):
                                reported_sum = parse_currency(table_data[-1][col_idx])

                                if reported_sum is not None and abs(calculated_sum - reported_sum) > 0.01:
                                    errors.append(
                                        {
                                            "type": "Column Sum Mismatch",
                                            "page": page_num + 1,
                                            "table_number": table_num + 1,
                                            "column": col_idx + 1,
                                            "calculated_sum": round(calculated_sum, 2),
                                            "reported_sum": round(reported_sum, 2),
                                            "difference": round(calculated_sum - reported_sum, 2),
                                            "description": (
                                                f"Column total mismatch: calculated "
                                                f"${calculated_sum:,.2f}, reported ${reported_sum:,.2f}"
                                            ),
                                        }
                                    )

        doc.close()

        return json.dumps(
            {
                "success": True,
                "validation": {
                    "tables_checked": tables_checked,
                    "errors": errors,
                    "warnings": warnings,
                },
            },
            indent=2,
        )

    except ToolError:
        raise
    except Exception as e:
        doc.close()
        raise ToolError(f"Failed to validate financial math: {e}")


# ============================================================================
# TOOL 4: CHECK REQUIRED SIGNATURES
# ============================================================================


@tool(
    name="check_required_signatures",
    description="Check for required signatures in PDF based on document type and amount thresholds",
)
async def check_required_signatures(
    pdf_path: str, doc_type: str, invoice_amount: float = None
) -> str:
    """Check for required signatures."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        raise ToolError(f"Failed to open PDF: {e}")

    try:
        found_signatures = []

        for page_num, page in enumerate(doc):
            # Check for digital signature fields
            widgets = page.widgets()
            if widgets:
                for widget in widgets:
                    if widget.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE:
                        found_signatures.append(
                            {
                                "type": "digital_signature",
                                "signer": widget.field_name or "Unknown",
                                "page": page_num + 1,
                                "excerpt": f"Digital signature field: {widget.field_name}",
                            }
                        )

            # Check for text-based signature mentions
            text = page.get_text()
            signature_keywords = [
                ("CFO", "CFO"),
                ("CEO", "CEO"),
                ("Chief Financial Officer", "CFO"),
                ("Chief Executive Officer", "CEO"),
                ("Chief Accounting Officer", "CAO"),
                ("signed by", "Authorized Signer"),
                ("approved by", "Approver"),
                ("certified by", "Certifier"),
            ]

            for keyword, role in signature_keywords:
                if keyword.lower() in text.lower():
                    pos = text.lower().find(keyword.lower())
                    excerpt = text[max(0, pos - 50) : min(len(text), pos + 100)]

                    already_found = any(
                        s["signer"] == role and s["page"] == page_num + 1
                        for s in found_signatures
                    )
                    if not already_found:
                        found_signatures.append(
                            {
                                "type": "text_mention",
                                "signer": role,
                                "page": page_num + 1,
                                "excerpt": excerpt.strip(),
                            }
                        )

        # Determine required signatures based on doc type
        required_signatures = []
        if doc_type == "SOX 404":
            required_signatures = ["CFO Certification", "CEO Certification"]
        elif doc_type == "10-K":
            required_signatures = ["CEO Signature", "CFO Signature", "CAO Signature"]
        elif doc_type == "8-K":
            required_signatures = ["Authorized Signer"]
        elif doc_type == "Invoice":
            if invoice_amount and invoice_amount > 10000:
                required_signatures = ["Authorized Approver"]
            else:
                required_signatures = []

        # Check which required signatures are missing
        found_roles = [sig["signer"] for sig in found_signatures]
        missing_signatures = []

        for required in required_signatures:
            found = False
            for role in found_roles:
                if any(keyword in role.upper() for keyword in required.upper().split()):
                    found = True
                    break
            if not found:
                missing_signatures.append(required)

        compliance_status = "COMPLETE" if not missing_signatures else "INCOMPLETE"

        doc.close()

        return json.dumps(
            {
                "success": True,
                "signature_requirements": {
                    "doc_type": doc_type,
                    "invoice_amount": invoice_amount,
                    "required_signatures": required_signatures,
                    "found_signatures": found_signatures,
                    "missing_signatures": missing_signatures,
                    "compliance_status": compliance_status,
                },
            },
            indent=2,
        )

    except ToolError:
        raise
    except Exception as e:
        doc.close()
        raise ToolError(f"Failed to check signatures: {e}")


# ============================================================================
# TOOL 5: DETECT COMPLIANCE RED FLAGS
# ============================================================================


@tool(
    name="detect_compliance_red_flags",
    description="Search for compliance warning phrases in PDF (going concern, material weakness, etc.)",
)
async def detect_compliance_red_flags(pdf_path: str) -> str:
    """Detect compliance red flags."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        raise ToolError(f"Failed to open PDF: {e}")

    try:
        red_flags = []

        red_flag_phrases = {
            "going concern": {"type": "going_concern", "severity": "critical"},
            "material weakness": {"type": "material_weakness", "severity": "critical"},
            "restatement": {"type": "restatement", "severity": "critical"},
            "significant deficiency": {"type": "significant_deficiency", "severity": "high"},
            "qualified opinion": {"type": "qualified_opinion", "severity": "high"},
            "adverse opinion": {"type": "adverse_opinion", "severity": "high"},
            "related party transaction": {"type": "related_party", "severity": "medium"},
            "related party": {"type": "related_party", "severity": "medium"},
            "subsequent event": {"type": "subsequent_event", "severity": "medium"},
            "contingent liability": {"type": "contingent_liability", "severity": "medium"},
        }

        for page_num, page in enumerate(doc):
            text = page.get_text()
            text_lower = text.lower()

            for phrase, metadata in red_flag_phrases.items():
                if phrase in text_lower:
                    pos = text_lower.find(phrase)
                    excerpt = text[max(0, pos - 100) : min(len(text), pos + 300)]

                    # Try to determine context (which note or section)
                    context = "Unknown section"
                    context_keywords = ["note ", "item ", "section "]
                    for keyword in context_keywords:
                        context_pos = text_lower.rfind(keyword, 0, pos)
                        if context_pos != -1:
                            context_end = text.find("\n", context_pos)
                            if context_end != -1:
                                context = text[context_pos:context_end].strip()
                                break

                    already_flagged = any(
                        f["phrase"] == phrase and f["page"] == page_num + 1
                        for f in red_flags
                    )
                    if not already_flagged:
                        red_flags.append(
                            {
                                "phrase": phrase,
                                "type": metadata["type"],
                                "severity": metadata["severity"],
                                "page": page_num + 1,
                                "excerpt": excerpt.strip(),
                                "context": context,
                            }
                        )

        doc.close()

        summary = {
            "total_flags": len(red_flags),
            "critical": sum(1 for f in red_flags if f["severity"] == "critical"),
            "high": sum(1 for f in red_flags if f["severity"] == "high"),
            "medium": sum(1 for f in red_flags if f["severity"] == "medium"),
        }

        return json.dumps(
            {"success": True, "red_flags": red_flags, "summary": summary},
            indent=2,
        )

    except ToolError:
        raise
    except Exception as e:
        doc.close()
        raise ToolError(f"Failed to detect red flags: {e}")


# ============================================================================
# TOOL 6: EXTRACT COMPARATIVE PERIODS (OPTIONAL)
# ============================================================================


@tool(
    name="extract_comparative_periods",
    description="Extract multi-period financial data and calculate period-over-period changes",
)
async def extract_comparative_periods(pdf_path: str) -> str:
    """Extract multi-period financial data and calculate changes."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        raise ToolError(f"Failed to open PDF: {e}")

    try:
        comparative_data = []

        for page_num, page in enumerate(doc):
            tables = page.find_tables()
            if not tables or not tables.tables:
                continue

            for table in tables.tables:
                table_data = table.extract()
                if not table_data or len(table_data) < 2:
                    continue

                # Find period columns from header
                header = table_data[0]
                period_indices = {}
                for col_idx, cell in enumerate(header):
                    match = re.search(r"(20\d{2})", str(cell))
                    if match:
                        period_indices[match.group(1)] = col_idx

                if len(period_indices) < 2:
                    continue

                sorted_periods = sorted(period_indices.keys(), reverse=True)

                for row in table_data[1:]:
                    if not row or len(row) < 2:
                        continue

                    metric = str(row[0]).strip()
                    if not metric or len(metric) < 3:
                        continue

                    periods_data = {}
                    has_values = False
                    for period, col_idx in period_indices.items():
                        if col_idx < len(row):
                            val = parse_currency(row[col_idx])
                            if val is not None:
                                periods_data[period] = val
                                has_values = True

                    if not has_values or len(periods_data) < 2:
                        continue

                    changes = {}
                    for i in range(len(sorted_periods) - 1):
                        current = sorted_periods[i]
                        previous = sorted_periods[i + 1]

                        if current in periods_data and previous in periods_data:
                            curr_val = periods_data[current]
                            prev_val = periods_data[previous]
                            abs_change = curr_val - prev_val
                            pct_change = (
                                ((curr_val - prev_val) / abs(prev_val)) * 100
                                if prev_val != 0
                                else None
                            )
                            material = (
                                abs(pct_change) > 10 if pct_change is not None else False
                            ) or abs(abs_change) > 100_000

                            changes[f"{current}_vs_{previous}"] = {
                                "absolute": round(abs_change, 2),
                                "percent": round(pct_change, 2) if pct_change is not None else None,
                                "material": material,
                                "direction": "increase" if abs_change > 0 else "decrease",
                            }

                    if changes:
                        comparative_data.append(
                            {
                                "metric": metric,
                                "page": page_num + 1,
                                "periods": periods_data,
                                "changes": changes,
                            }
                        )

        doc.close()

        return json.dumps(
            {"success": True, "comparative_data": comparative_data},
            indent=2,
        )

    except ToolError:
        raise
    except Exception as e:
        doc.close()
        raise ToolError(f"Failed to extract comparative periods: {e}")


# ============================================================================
# REGISTER TOOLS & RUN SERVER
# ============================================================================

server.collect(
    find_regulatory_sections,
    extract_financial_statements,
    validate_financial_math,
    check_required_signatures,
    detect_compliance_red_flags,
    extract_comparative_periods,
)


async def main():
    await server.serve(port=8080)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
