# PDF Compliance Analyzer MCP Server

Financial compliance PDF analysis server built with [Dedalus MCP](https://github.com/dedalus-labs/dedalus-mcp-python). Provides specialized tools for analyzing 10-Ks, SOX 404 reports, 8-K filings, and invoices.

## Features

- **find_regulatory_sections**: Locate required SEC/FINRA sections by document type
- **extract_financial_statements**: Identify and extract Balance Sheets, Income Statements, etc.
- **validate_financial_math**: Check balance sheet equations, invoice totals, table sums
- **check_required_signatures**: Verify CFO/CEO certifications and approval signatures
- **detect_compliance_red_flags**: Search for "going concern", "material weakness", etc.
- **extract_comparative_periods**: Multi-period data extraction with change calculations

## Installation

```bash
pip install -r requirements.txt
```

## Running Locally

```bash
cd src
python main.py
```

The server starts on `http://127.0.0.1:8080/mcp` by default.

## Deploying to Dedalus Labs

1. Push this repo to GitHub
2. Go to the [Dedalus Dashboard](https://www.dedaluslabs.ai/dashboard)
3. Click **Add Server** and connect your GitHub repo
4. No environment variables needed (PyMuPDF runs locally)
5. Click **Deploy**

## Usage with Dedalus SDK

```python
import os
from dedalus_labs import AsyncDedalus, DedalusRunner

client = AsyncDedalus(api_key=os.getenv("DEDALUS_API_KEY"))
runner = DedalusRunner(client)

response = await runner.run(
    input="Analyze this 10-K for compliance gaps",
    model="anthropic/claude-sonnet-4-5-20250929",
    mcp_servers=["your-org/pdf-compliance-analyzer"],
    tools=[
        "find_regulatory_sections",
        "extract_financial_statements",
        "validate_financial_math",
        "check_required_signatures",
        "detect_compliance_red_flags",
    ]
)
```

## Tools

### find_regulatory_sections
Finds required compliance sections based on document type. Supports 10-K (SEC Items 1, 1A, 7, 8, 9A), SOX 404 (ITGC, Access Controls, Management Assessment), 8-K (Items 1.01, 2.01, 5.02, 9.01), and Invoice (Invoice Number, Date, Line Items, Total).

**Input:** `pdf_path` (string), `doc_type` (enum: "10-K", "SOX 404", "8-K", "Invoice")

### extract_financial_statements
Extracts tables from PDFs and classifies them as Balance Sheet, Income Statement, Cash Flow Statement, or Invoice. Identifies time periods and key line items.

**Input:** `pdf_path` (string)

### validate_financial_math
Validates mathematical accuracy: balance sheet equation (A = L + E), income statement (Revenue - Expenses = Net Income), and column/row sums. Flags discrepancies > $0.01.

**Input:** `pdf_path` (string)

### check_required_signatures
Checks for digital signature fields and text-based signature mentions. Applies document-type-specific requirements (SOX 404 needs CFO+CEO, 10-K needs CEO+CFO+CAO, Invoice >$10K needs approver).

**Input:** `pdf_path` (string), `doc_type` (enum: "10-K", "SOX 404", "8-K", "Invoice"), `invoice_amount` (number, optional)

### detect_compliance_red_flags
Searches for known compliance warning phrases with severity levels: critical (going concern, material weakness, restatement), high (significant deficiency, qualified/adverse opinion), medium (related party, subsequent event, contingent liability).

**Input:** `pdf_path` (string)

### extract_comparative_periods
Extracts multi-period financial data, calculates period-over-period changes (absolute and percent), and flags material changes (>10% or >$100K).

**Input:** `pdf_path` (string)

## Integration Notes for Person 2

This MCP server is standalone and optional. To integrate into Agent 2:

1. Add to Dedalus `mcp_servers` list
2. Include relevant tools in the agent's prompt
3. Agent 2 can use tool outputs for compliance reasoning

No changes required to existing Agent 2 code to test this server independently.
