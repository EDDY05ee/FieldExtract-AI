FieldExtract AI

Human-Verified Invoice Extraction and Validation

FieldExtract AI is a prototype application that extracts structured information from invoice PDFs and images, presents the results for human review, validates financial totals, and supports export to CSV, JSON, and Excel.

The Problem

Transferring invoice information into spreadsheets can involve repetitive manual entry and checking. Automated extraction can also produce incomplete or incorrect values.

FieldExtract AI explores a workflow that combines automated extraction with human verification.

How It Works

Upload → Extract → Review Evidence → Validate → Approve → Export

1. Upload an invoice PDF or supported image.
2. Extract text using PDF text extraction or OCR.
3. Identify structured invoice fields.
4. Inspect field evidence and prototype confidence estimates.
5. Edit extracted values when necessary.
6. Validate subtotal, tax, and total.
7. Complete human verification and approval.
8. Export approved data.

Key Features

- PDF and image invoice upload
- PDF text extraction and Tesseract OCR
- Extraction of eight invoice fields
- Field-level source evidence
- Rule-based confidence estimates
- Editable human review
- Financial total validation
- Human verification and approval gates
- CSV, JSON, and Excel export
- File type and file size checks
- Application reset and document-state isolation

Extracted Fields

- Vendor
- Invoice number
- Invoice date
- Due date
- Currency
- Subtotal
- Tax
- Total

Technology Stack

- Python
- Streamlit
- PyMuPDF
- Tesseract OCR and pytesseract
- Pandas
- Pillow
- openpyxl

Run Locally

Requirements

- Python
- Git
- Tesseract OCR installed

Installation

Clone the repository:

git clone https://github.com/EDDY05ee/FieldExtract-AI.git
cd FieldExtract-AI

Create a virtual environment:

python -m venv .venv
.\.venv\Scripts\Activate.ps1

Install dependencies:

python -m pip install streamlit pandas pillow pytesseract pypdf openpyxl pymupdf

Run the application:

python -m streamlit run app.py

If Tesseract is installed in a different location, configure its executable path in the application.

Prototype Evaluation

In a controlled test using a synthetic invoice, the prototype successfully processed the eight expected fields and completed the review, validation, approval, and export workflow.

This is an initial functional test, not evidence of general invoice accuracy or measured productivity improvement.

The displayed confidence values are rule-based estimates and are not calibrated probabilities.

Privacy and Responsible Use

- Use synthetic or non-confidential invoices during development and demonstrations.
- Review extracted values before relying on them.
- Do not treat automated extraction as a substitute for appropriate financial checks.
- Verify actual processing and storage behavior before using confidential documents.

Limitations

- Complex invoice layouts may require manual correction.
- The prototype has not been evaluated on a large or representative invoice dataset.
- No real-user interviews or productivity study are claimed.
- Confidence estimates are not calibrated.
- This is a prototype, not a production accounting system.

Future Improvements

- Test more varied invoice layouts.
- Compare extraction against a defined baseline.
- Measure field-level precision, recall, and correction requirements.
- Improve handling of ambiguous values.
- Explore secure deployment and optional database integration.

Hackathon Project

Project: FieldExtract AI
Track: Future of Work & Automation

Repository: https://github.com/EDDY05ee/FieldExtract-AI

Demo video and live-demo links will be added when available.