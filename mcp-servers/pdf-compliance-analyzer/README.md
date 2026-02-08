# PDF Compliance Analyzer MCP Server

Financial compliance PDF analysis server for Dedalus agents. Provides specialized tools for analyzing 10-Ks, SOX 404 reports, 8-K filings, and invoices.

## Features

- **find_regulatory_sections**: Locate required SEC/FINRA sections by document type
- **extract_financial_statements**: Identify and extract Balance Sheets, Income Statements, etc.
- **validate_financial_math**: Check balance sheet equations, invoice totals, table sums
- **check_required_signatures**: Verify CFO/CEO certifications and approval signatures
- **detect_compliance_red_flags**: Search for "going concern", "material weakness", etc.
- **extract_comparative_periods**: Multi-period data extraction with change calculations

## Installation

```bash
cd mcp-servers/pdf-compliance-analyzer
pip install -r requirements.txt
```

## Running the Server

```bash
python server.py
```

The server runs on stdio and can be registered with Dedalus.

## Usage with Dedalus

```python
from dedalus_labs import AsyncDedalus, DedalusRunner

client = AsyncDedalus(api_key=os.getenv("DEDALUS_API_KEY"))
runner = DedalusRunner(client)

response = await runner.run(
    input="Analyze this 10-K for compliance gaps",
    model="anthropic/claude-opus-4-6",
    mcp_servers=["local://pdf-compliance-analyzer"],
    tools=[
        "find_regulatory_sections",
        "extract_financial_statements",
        "validate_financial_math"
    ]
)
```

## Tools

### find_regulatory_sections
Finds required compliance sections based on document type. Supports 10-K (SEC Items 1, 1A, 7, 8, 9A), SOX 404 (ITGC, Access Controls, Management Assessment), 8-K (Items 1.01, 2.01, 5.02, 9.01), and Invoice (Invoice Number, Date, Line Items, Total).

### extract_financial_statements
Extracts tables from PDFs and classifies them as Balance Sheet, Income Statement, Cash Flow Statement, or Invoice. Identifies time periods and key line items.

### validate_financial_math
Validates mathematical accuracy: balance sheet equation (A = L + E), income statement (Revenue - Expenses = Net Income), and column/row sums. Flags discrepancies > $0.01.

### check_required_signatures
Checks for digital signature fields and text-based signature mentions. Applies document-type-specific requirements (SOX 404 needs CFO+CEO, 10-K needs CEO+CFO+CAO, Invoice >$10K needs approver).

### detect_compliance_red_flags
Searches for known compliance warning phrases with severity levels: critical (going concern, material weakness, restatement), high (significant deficiency, qualified/adverse opinion), medium (related party, subsequent event, contingent liability).

### extract_comparative_periods
Extracts multi-period financial data, calculates period-over-period changes (absolute and percent), and flags material changes (>10% or >$100K).
