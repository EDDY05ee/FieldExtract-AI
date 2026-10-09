import hashlib
import io
import json
import re
from pathlib import Path

import fitz
import pandas as pd
import pytesseract
import streamlit as st
from PIL import Image, UnidentifiedImageError


# ============================================================
# CONFIGURATION
# ============================================================

APP_NAME = "FieldExtract AI"
APP_VERSION = "HackNowa 2026 Prototype"

TESSERACT_PATH = Path(
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

SUPPORTED_EXTENSIONS = (
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
)

if TESSERACT_PATH.exists():
    pytesseract.pytesseract.tesseract_cmd = str(
        TESSERACT_PATH
    )


st.set_page_config(
    page_title=APP_NAME,
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# PROFESSIONAL UI
# ============================================================

st.markdown(
    """
<style>

    .main-title {
        font-size: 2.6rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }

    .main-subtitle {
        font-size: 1.15rem;
        color: #64748b;
        margin-bottom: 1.5rem;
    }

    .section-card {
        padding: 1.2rem;
        border-radius: 14px;
        border: 1px solid #e2e8f0;
        background: #ffffff;
        margin-bottom: 1rem;
    }

    .workflow-card {
        padding: 0.9rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        text-align: center;
        background: #f8fafc;
    }

    .workflow-number {
        font-size: 1.6rem;
        font-weight: 700;
    }

    .workflow-label {
        font-size: 0.9rem;
        font-weight: 600;
    }

    .metric-label {
        color: #64748b;
        font-size: 0.85rem;
    }

    .small-note {
        color: #64748b;
        font-size: 0.85rem;
    }

    .approved-box {
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #86efac;
        background: #f0fdf4;
    }

    .locked-box {
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #fecaca;
        background: #fef2f2;
    }

    div[data-testid="stMetric"] {
        border-radius: 12px;
        padding: 0.8rem;
    }

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# FIELD DEFINITIONS
# ============================================================

FIELD_LABELS = {
    "vendor": "Vendor",
    "invoice_number": "Invoice Number",
    "invoice_date": "Invoice Date",
    "due_date": "Due Date",
    "currency": "Currency",
    "subtotal": "Subtotal",
    "tax": "Tax",
    "total": "Total",
}


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "extraction_result": None,
    "invoice_fields": None,
    "original_fields": None,
    "verified": False,
    "approved": False,
    "review_saved": False,
    "file_signature": None,
}

for key, value in DEFAULT_STATE.items():

    if key not in st.session_state:
        st.session_state[key] = value


def reset_application():
    """
    Completely reset the current invoice workflow.
    """

    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value

    # Remove dynamic review widgets.
    for key in list(st.session_state.keys()):

        if key.startswith("edit_"):
            del st.session_state[key]


def get_file_signature(uploaded_file):
    """
    Generate a SHA-256 fingerprint for the uploaded document.

    This prevents stale invoice state from being reused
    when a different document is selected.
    """

    if uploaded_file is None:
        return None

    file_bytes = uploaded_file.getvalue()

    return hashlib.sha256(
        file_bytes
    ).hexdigest()


# ============================================================
# DOCUMENT VALIDATION
# ============================================================

def validate_uploaded_file(uploaded_file):
    """
    Validate file size and extension before processing.
    """

    if uploaded_file is None:
        return False, "No file selected."

    filename = uploaded_file.name.lower()

    if not filename.endswith(
        SUPPORTED_EXTENSIONS
    ):
        return (
            False,
            "Unsupported file type. "
            "Please upload PDF, PNG, JPG or JPEG.",
        )

    file_size = uploaded_file.size

    if file_size <= 0:
        return False, "The uploaded file is empty."

    if file_size > MAX_FILE_SIZE_BYTES:
        return (
            False,
            f"File is too large. Maximum allowed size "
            f"is {MAX_FILE_SIZE_MB} MB.",
        )

    return True, ""


# ============================================================
# DOCUMENT PROCESSING
# ============================================================

def extract_text_from_pdf(pdf_bytes):
    """
    Extract embedded text from a PDF.
    """

    text_parts = []

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    try:

        if len(document) == 0:
            return ""

        for page_number, page in enumerate(
            document,
            start=1,
        ):

            page_text = page.get_text("text")

            if page_text.strip():

                text_parts.append(
                    f"--- Page {page_number} ---\n"
                    f"{page_text.strip()}"
                )

    finally:

        document.close()

    return "\n\n".join(text_parts)


def ocr_image(image):
    """
    Perform Tesseract OCR on an image.
    """

    try:

        return pytesseract.image_to_string(
            image,
            config="--psm 6",
        )

    except Exception as error:

        raise RuntimeError(
            "Tesseract OCR failed. "
            "Please verify that Tesseract is installed "
            "correctly."
        ) from error


def ocr_pdf(pdf_bytes):
    """
    Render PDF pages and run OCR.
    """

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    page_results = []

    try:

        if len(document) == 0:
            return ""

        for page_number, page in enumerate(
            document,
            start=1,
        ):

            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(2, 2),
                alpha=False,
            )

            image = Image.open(
                io.BytesIO(
                    pixmap.tobytes("png")
                )
            )

            text = ocr_image(image)

            page_results.append(
                f"--- Page {page_number} ---\n"
                f"{text.strip()}"
            )

    finally:

        document.close()

    return "\n\n".join(page_results)


def process_document(uploaded_file):
    """
    Main document processing pipeline.

    PDF:
        1. Try embedded PDF text.
        2. If insufficient, fall back to OCR.

    Image:
        Directly use Tesseract OCR.
    """

    valid, error_message = validate_uploaded_file(
        uploaded_file
    )

    if not valid:
        raise ValueError(error_message)

    file_bytes = uploaded_file.getvalue()

    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):

        direct_text = extract_text_from_pdf(
            file_bytes
        )

        if len(direct_text.strip()) >= 30:

            return {
                "method": "PDF text extraction",
                "text": direct_text,
                "ocr_used": False,
            }

        ocr_text = ocr_pdf(file_bytes)

        if not ocr_text.strip():

            raise ValueError(
                "The PDF could not produce readable text "
                "through direct extraction or OCR."
            )

        return {
            "method": "OCR on scanned PDF",
            "text": ocr_text,
            "ocr_used": True,
        }

    try:

        image = Image.open(
            io.BytesIO(file_bytes)
        )

        image.load()

    except (
        UnidentifiedImageError,
        OSError,
    ) as error:

        raise ValueError(
            "The uploaded image could not be read."
        ) from error

    text = ocr_image(image)

    if not text.strip():

        raise ValueError(
            "OCR did not produce readable text "
            "from the image."
        )

    return {
        "method": "Tesseract OCR",
        "text": text,
        "ocr_used": True,
    }


# ============================================================
# STRUCTURED EXTRACTION
# ============================================================

def extract_invoice_fields(text):
    """
    Extract the defined invoice fields using
    transparent rule-based extraction.
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    fields = {
        "vendor": "",
        "invoice_number": "",
        "invoice_date": "",
        "due_date": "",
        "currency": "",
        "subtotal": "",
        "tax": "",
        "total": "",
    }

    # --------------------------------------------------------
    # Vendor
    # --------------------------------------------------------

    for index, line in enumerate(lines):

        if line.upper() == "INVOICE":

            if index > 0:

                candidate = lines[index - 1]

                if (
                    candidate
                    and "TEST VENDOR"
                    not in candidate.upper()
                ):

                    fields["vendor"] = candidate

            break

    if not fields["vendor"]:

        ignored_terms = (
            "PAGE",
            "INVOICE",
            "INVOICE NUMBER",
            "INVOICE NO",
            "INVOICE DATE",
            "DUE DATE",
            "CURRENCY",
            "SUBTOTAL",
            "TAX",
            "TOTAL",
        )

        for line in lines:

            upper = line.upper()

            if (
                not any(
                    term in upper
                    for term in ignored_terms
                )
                and "TEST VENDOR"
                not in upper
            ):

                fields["vendor"] = line
                break

    # --------------------------------------------------------
    # Invoice Number
    # --------------------------------------------------------

    invoice_number_pattern = re.compile(
        r"^\s*invoice\s*"
        r"(?:number|no\.?|#)"
        r"\s*[:\-]\s*"
        r"([A-Z0-9][A-Z0-9\-\/]*)"
        r"\s*$",
        re.IGNORECASE,
    )

    for line in lines:

        match = invoice_number_pattern.match(line)

        if match:

            fields["invoice_number"] = (
                match.group(1).strip()
            )

            break

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    date_pattern = (
        r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})"
    )

    invoice_date_pattern = re.compile(
        r"^\s*invoice\s*date\s*[:\-]\s*"
        + date_pattern
        + r"\s*$",
        re.IGNORECASE,
    )

    for line in lines:

        match = invoice_date_pattern.match(line)

        if match:

            fields["invoice_date"] = (
                match.group(1)
            )

            break

    due_date_pattern = re.compile(
        r"^\s*due\s*date\s*[:\-]\s*"
        + date_pattern
        + r"\s*$",
        re.IGNORECASE,
    )

    for line in lines:

        match = due_date_pattern.match(line)

        if match:

            fields["due_date"] = (
                match.group(1)
            )

            break

    # --------------------------------------------------------
    # Currency
    # --------------------------------------------------------

    currency_pattern = re.compile(
        r"\b(INR|USD|EUR|GBP)\b|[₹$€£]",
        re.IGNORECASE,
    )

    currency_map = {
        "₹": "INR",
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
    }

    for line in lines:

        match = currency_pattern.search(line)

        if match:

            token = match.group(0).upper()

            fields["currency"] = currency_map.get(
                token,
                token,
            )

            break

    # --------------------------------------------------------
    # Amounts
    # --------------------------------------------------------

    number_pattern = (
        r"[0-9][0-9,]*(?:\.[0-9]{1,2})?"
    )

    def find_labeled_amount(label):

        pattern = re.compile(
            r"^\s*"
            + re.escape(label)
            + r"\s*[:\-]\s*"
            r"(?:₹|INR|USD|\$|EUR|€|GBP|£)?"
            r"\s*("
            + number_pattern
            + r")\s*$",
            re.IGNORECASE,
        )

        for line in lines:

            match = pattern.match(line)

            if match:

                return match.group(1)

        return ""

    fields["subtotal"] = find_labeled_amount(
        "subtotal"
    )

    fields["tax"] = find_labeled_amount(
        "tax"
    )

    fields["total"] = find_labeled_amount(
        "total"
    )

    return fields


# ============================================================
# VALIDATION
# ============================================================

def number_value(value):

    if not value:
        return None

    try:

        cleaned = str(value).replace(
            ",",
            "",
        )

        return float(cleaned)

    except (
        ValueError,
        TypeError,
    ):

        return None


def validate_invoice(fields):
    """
    Validate required fields and amount relationship.
    """

    messages = []
    valid = True

    subtotal = number_value(
        fields.get("subtotal", "")
    )

    tax = number_value(
        fields.get("tax", "")
    )

    total = number_value(
        fields.get("total", "")
    )

    if (
        subtotal is not None
        and tax is not None
        and total is not None
    ):

        calculated_total = round(
            subtotal + tax,
            2,
        )

        if abs(
            calculated_total - total
        ) < 0.01:

            messages.append(
                "✓ Subtotal + Tax matches Total."
            )

        else:

            messages.append(
                f"⚠ Subtotal + Tax = "
                f"{calculated_total:.2f}, "
                f"but Total = {total:.2f}."
            )

            valid = False

    else:

        messages.append(
            "⚠ Unable to validate the amount relationship."
        )

        valid = False

    missing_fields = [
        field
        for field, value in fields.items()
        if not value
    ]

    if missing_fields:

        messages.append(
            "⚠ Missing fields: "
            + ", ".join(
                field.replace("_", " ")
                for field in missing_fields
            )
        )

        valid = False

    return valid, messages


# ============================================================
# EVIDENCE
# ============================================================

def normalize_for_match(value):

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip().lower(),
    )


def find_evidence(
    field_key,
    value,
    text,
):

    if not value or not text:
        return ""

    normalized_value = normalize_for_match(
        value
    )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    label = FIELD_LABELS[
        field_key
    ].lower()

    # Prefer evidence on a correctly labeled line.
    for line in lines:

        normalized_line = normalize_for_match(
            line
        )

        if (
            label in normalized_line
            and normalized_value
            in normalized_line
        ):

            return line

    # Fallback: search for the value.
    for line in lines:

        normalized_line = normalize_for_match(
            line
        )

        if normalized_value in normalized_line:

            return line

    return ""


def calculate_confidence(
    value,
    evidence,
    processing_method,
):

    if not value:

        return {
            "level": "Low",
            "score": 0,
            "reason": "No value extracted.",
        }

    if (
        evidence
        and processing_method
        == "PDF text extraction"
    ):

        return {
            "level": "High",
            "score": 95,
            "reason":
                "Exact source evidence found "
                "in PDF text.",
        }

    if (
        evidence
        and processing_method
        == "Tesseract OCR"
    ):

        return {
            "level": "Medium",
            "score": 80,
            "reason":
                "Value found in OCR source text.",
        }

    if evidence:

        return {
            "level": "Medium",
            "score": 75,
            "reason":
                "Matching source evidence found.",
        }

    return {
        "level": "Low",
        "score": 40,
        "reason":
            "No direct source evidence found.",
    }


def build_evidence_table(
    fields,
    text,
    processing_method,
):

    rows = []

    for field_key, label in FIELD_LABELS.items():

        value = fields.get(
            field_key,
            "",
        )

        evidence = find_evidence(
            field_key,
            value,
            text,
        )

        confidence = calculate_confidence(
            value,
            evidence,
            processing_method,
        )

        if confidence["level"] == "High":
            status = "🟢 High"

        elif confidence["level"] == "Medium":
            status = "🟡 Medium"

        else:
            status = "🔴 Low"

        rows.append(
            {
                "Field": label,
                "Value": value,
                "Confidence": status,
                "Score":
                    f"{confidence['score']}%",
                "Source Evidence":
                    evidence
                    if evidence
                    else "No direct evidence found",
                "Reason":
                    confidence["reason"],
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# EVALUATION
# ============================================================

def calculate_evaluation(
    original_fields,
    current_fields,
    text,
    validation_valid,
):

    total_fields = len(FIELD_LABELS)

    extracted_fields = sum(
        1
        for key in FIELD_LABELS
        if original_fields.get(
            key,
            "",
        )
    )

    missing_fields = [
        FIELD_LABELS[key]
        for key in FIELD_LABELS
        if not original_fields.get(
            key,
            "",
        )
    ]

    corrections = sum(
        1
        for key in FIELD_LABELS
        if original_fields.get(
            key,
            "",
        )
        != current_fields.get(
            key,
            "",
        )
    )

    evidence_available = sum(
        1
        for key in FIELD_LABELS
        if find_evidence(
            key,
            current_fields.get(
                key,
                "",
            ),
            text,
        )
    )

    evidence_coverage = (
        evidence_available / total_fields
        if total_fields
        else 0
    )

    return {
        "total_fields": total_fields,
        "extracted_fields": extracted_fields,
        "missing_fields": missing_fields,
        "corrections": corrections,
        "evidence_available": evidence_available,
        "evidence_coverage": evidence_coverage,
        "validation_passed": validation_valid,
    }


# ============================================================
# EXPORT
# ============================================================

def create_csv_bytes(fields):

    dataframe = pd.DataFrame(
        [fields]
    )

    return dataframe.to_csv(
        index=False
    ).encode("utf-8")


def create_json_bytes(fields):

    return json.dumps(
        fields,
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")


def create_excel_bytes(fields):

    dataframe = pd.DataFrame(
        [fields]
    )

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        dataframe.to_excel(
            writer,
            index=False,
            sheet_name="Invoice",
        )

    return output.getvalue()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("📄 FieldExtract AI")

    st.caption(
        "Invoice intelligence with "
        "human-controlled verification."
    )

    st.divider()

    st.subheader("Workflow")

    if st.session_state.extraction_result:
        st.write("✅ Extracted")
    else:
        st.write("⏳ Extraction pending")

    if st.session_state.extraction_result:
        st.write("👁️ Review available")
    else:
        st.write("⏳ Review pending")

    if st.session_state.invoice_fields:

        validation_state, _ = validate_invoice(
            st.session_state.invoice_fields
        )

        if validation_state:
            st.write("✅ Validation passed")
        else:
            st.write("⚠️ Validation needs attention")

    else:

        st.write("⏳ Validation pending")

    if st.session_state.review_saved:
        st.write("✅ Review saved")
    else:
        st.write("⏳ Review not saved")

    if st.session_state.verified:
        st.write("✅ Human verified")
    else:
        st.write("⏳ Human verification pending")

    if st.session_state.approved:
        st.write("✅ Approved")
    else:
        st.write("🔒 Approval locked")

    st.divider()

    st.subheader("Privacy")

    st.caption(
        "This prototype is designed for local document "
        "processing. During development/testing, avoid "
        "uploading real confidential financial documents."
    )

    st.divider()

    if st.button(
        "🔄 Start New Invoice",
        use_container_width=True,
    ):

        reset_application()
        st.rerun()

    st.divider()

    st.caption(
        f"{APP_NAME} • {APP_VERSION}"
    )


# ============================================================
# MAIN HEADER
# ============================================================

st.markdown(
    '<div class="main-title">📄 FieldExtract AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-subtitle">'
    "Intelligent Invoice Extraction & "
    "Human-Verified Accuracy"
    "</div>",
    unsafe_allow_html=True,
)

st.write(
    "Turn invoice documents into structured data "
    "with evidence, validation, human review, "
    "controlled approval, and export."
)


# ============================================================
# STATUS BANNER
# ============================================================

if st.session_state.approved:

    st.success(
        "🟢 READY — Invoice has been human-verified "
        "and approved for export."
    )

elif st.session_state.verified:

    st.info(
        "🔵 VERIFIED — Human verification is complete. "
        "Final approval is still required."
    )

elif st.session_state.extraction_result:

    st.warning(
        "🟡 REVIEW — Extraction is complete. "
        "Review, save, and validate the data "
        "before approval."
    )

else:

    st.info(
        "🔵 READY — Upload an invoice to begin."
    )


st.divider()


# ============================================================
# WORKFLOW BAR
# ============================================================

st.header("🔄 Processing Workflow")

workflow_cols = st.columns(5)

workflow_items = [
    ("1️⃣", "Extract"),
    ("2️⃣", "Review"),
    ("3️⃣", "Validate"),
    ("4️⃣", "Approve"),
    ("5️⃣", "Export"),
]

for column, item in zip(
    workflow_cols,
    workflow_items,
):

    with column:

        st.markdown(
            '<div class="workflow-card">',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="workflow-number">'
            f"{item[0]}"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="workflow-label">'
            f"{item[1]}"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )


st.divider()


# ============================================================
# UPLOAD
# ============================================================

st.header("📤 1. Upload Invoice")

uploaded_file = st.file_uploader(
    "Choose an invoice PDF or image",
    type=[
        "pdf",
        "png",
        "jpg",
        "jpeg",
    ],
    help=(
        "Supported formats: PDF, PNG, JPG and JPEG. "
        f"Maximum file size: {MAX_FILE_SIZE_MB} MB."
    ),
)


if uploaded_file is not None:

    valid_file, file_error = validate_uploaded_file(
        uploaded_file
    )

    if not valid_file:

        st.error(file_error)

    else:

        # ----------------------------------------------------
        # DOCUMENT ISOLATION
        # ----------------------------------------------------

        current_signature = get_file_signature(
            uploaded_file
        )

        previous_signature = (
            st.session_state.get(
                "file_signature"
            )
        )

        if (
            previous_signature is not None
            and current_signature
            != previous_signature
        ):

            reset_application()

        st.session_state[
            "file_signature"
        ] = current_signature

        st.success(
            f"Invoice selected: {uploaded_file.name}"
        )

        file_col1, file_col2, file_col3 = (
            st.columns(3)
        )

        with file_col1:

            st.metric(
                "File Type",
                uploaded_file.type
                or "Unknown",
            )

        with file_col2:

            st.metric(
                "File Size",
                f"{uploaded_file.size / 1024:.1f} KB",
            )

        with file_col3:

            st.metric(
                "Status",
                "Ready",
            )

        # ====================================================
        # PREVIEW
        # ====================================================

        with st.expander(
            "👁️ Document Preview",
            expanded=True,
        ):

            filename = uploaded_file.name.lower()

            if filename.endswith(
                (".png", ".jpg", ".jpeg")
            ):

                try:

                    image = Image.open(
                        io.BytesIO(
                            uploaded_file.getvalue()
                        )
                    )

                    st.image(
                        image,
                        caption=uploaded_file.name,
                        use_container_width=True,
                    )

                except Exception as error:

                    st.error(
                        "Unable to preview this image."
                    )

                    st.exception(error)

            else:

                pdf_bytes = (
                    uploaded_file.getvalue()
                )

                document = None

                try:

                    document = fitz.open(
                        stream=pdf_bytes,
                        filetype="pdf",
                    )

                    st.write(
                        f"PDF contains "
                        f"{len(document)} page(s)."
                    )

                    if len(document) > 0:

                        page = document[0]

                        pixmap = page.get_pixmap(
                            matrix=fitz.Matrix(
                                1.5,
                                1.5,
                            ),
                            alpha=False,
                        )

                        preview_image = Image.open(
                            io.BytesIO(
                                pixmap.tobytes("png")
                            )
                        )

                        st.image(
                            preview_image,
                            caption="First page preview",
                            use_container_width=True,
                        )

                except Exception as error:

                    st.error(
                        "Unable to preview this PDF."
                    )

                    st.exception(error)

                finally:

                    if document is not None:
                        document.close()

        # ====================================================
        # PROCESS
        # ====================================================

        if st.button(
            "🚀 Process Invoice",
            type="primary",
            use_container_width=True,
        ):

            # Clear old workflow before processing.
            st.session_state[
                "extraction_result"
            ] = None

            st.session_state[
                "invoice_fields"
            ] = None

            st.session_state[
                "original_fields"
            ] = None

            st.session_state[
                "verified"
            ] = False

            st.session_state[
                "approved"
            ] = False

            st.session_state[
                "review_saved"
            ] = False

            # Clear review widgets.
            for key in list(
                st.session_state.keys()
            ):

                if key.startswith("edit_"):
                    del st.session_state[key]

            with st.spinner(
                "Reading and extracting invoice data..."
            ):

                try:

                    result = process_document(
                        uploaded_file
                    )

                    fields = extract_invoice_fields(
                        result["text"]
                    )

                    st.session_state[
                        "extraction_result"
                    ] = result

                    st.session_state[
                        "invoice_fields"
                    ] = fields.copy()

                    st.session_state[
                        "original_fields"
                    ] = fields.copy()

                    st.session_state[
                        "verified"
                    ] = False

                    st.session_state[
                        "approved"
                    ] = False

                    st.session_state[
                        "review_saved"
                    ] = False

                    st.success(
                        "Invoice processed successfully."
                    )

                    st.rerun()

                except Exception as error:

                    st.error(
                        "Invoice processing failed."
                    )

                    st.exception(error)


# ============================================================
# RESULTS
# ============================================================

if st.session_state.extraction_result:

    result = (
        st.session_state.extraction_result
    )

    fields = (
        st.session_state.invoice_fields
    )

    original_fields = (
        st.session_state.original_fields
    )

    # ========================================================
    # EXTRACTION SUMMARY
    # ========================================================

    st.header(
        "📊 2. Extraction Summary"
    )

    summary_col1, summary_col2, summary_col3 = (
        st.columns(3)
    )

    with summary_col1:

        st.metric(
            "Processing Method",
            result["method"],
        )

    with summary_col2:

        extracted_count = sum(
            1
            for value in fields.values()
            if value
        )

        st.metric(
            "Fields Found",
            f"{extracted_count}/"
            f"{len(FIELD_LABELS)}",
        )

    with summary_col3:

        st.metric(
            "OCR Used",
            "Yes"
            if result["ocr_used"]
            else "No",
        )

    # ========================================================
    # EVIDENCE
    # ========================================================

    st.header(
        "🔎 3. Evidence & Confidence"
    )

    st.info(
        "Confidence is a prototype rule-based estimate. "
        "It helps prioritize human review and is not "
        "a validated probability."
    )

    evidence_table = build_evidence_table(
        fields,
        result["text"],
        result["method"],
    )

    st.dataframe(
        evidence_table,
        use_container_width=True,
        hide_index=True,
    )

    # ========================================================
    # HUMAN REVIEW
    # ========================================================

    st.header(
        "✏️ 4. Human Review"
    )

    st.info(
        "Automated extraction is a draft. "
        "Review every value against the source evidence, "
        "then save the reviewed data."
    )

    edited_fields = {}

    review_col1, review_col2 = (
        st.columns(2)
    )

    for index, (key, label) in enumerate(
        FIELD_LABELS.items()
    ):

        target_column = (
            review_col1
            if index % 2 == 0
            else review_col2
        )

        with target_column:

            edited_fields[key] = st.text_input(
                label,
                value=fields.get(
                    key,
                    "",
                ),
                key=f"edit_{key}",
            )

    # --------------------------------------------------------
    # SAVE REVIEW
    # --------------------------------------------------------

    if st.button(
        "💾 Save Review & Re-Validate",
        use_container_width=True,
    ):

        st.session_state[
            "invoice_fields"
        ] = edited_fields.copy()

        st.session_state[
            "review_saved"
        ] = True

        st.session_state[
            "verified"
        ] = False

        st.session_state[
            "approved"
        ] = False

        st.success(
            "Reviewed values saved. "
            "The data will now be re-validated."
        )

        st.rerun()

    if st.session_state.review_saved:

        st.success(
            "✅ Review saved successfully."
        )

    else:

        st.warning(
            "⚠️ Review has not been saved yet. "
            "Human verification remains locked."
        )

    # ========================================================
    # CORRECTIONS
    # ========================================================

    current_fields = (
        st.session_state.invoice_fields
    )

    changes = []

    for key in FIELD_LABELS:

        original_value = (
            original_fields.get(
                key,
                "",
            )
        )

        current_value = (
            current_fields.get(
                key,
                "",
            )
        )

        if (
            original_value
            != current_value
        ):

            changes.append(
                {
                    "Field":
                        FIELD_LABELS[key],
                    "Original":
                        original_value,
                    "Reviewed":
                        current_value,
                }
            )

    if changes:

        st.subheader(
            "📝 Corrections Detected"
        )

        st.dataframe(
            pd.DataFrame(changes),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.caption(
            "No corrections recorded."
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    st.header(
        "🧮 5. Validation"
    )

    valid, messages = validate_invoice(
        current_fields
    )

    for message in messages:

        if message.startswith("✓"):

            st.success(message)

        else:

            st.warning(message)

    # ========================================================
    # HUMAN VERIFICATION
    # ========================================================

    st.header(
        "👤 Human Verification"
    )

    if not st.session_state.review_saved:

        st.warning(
            "🔒 Human verification is locked. "
            "Save the reviewed values first."
        )

    elif not valid:

        st.warning(
            "🔒 Human verification is locked. "
            "Fix validation issues first."
        )

    else:

        st.success(
            "Validation passed. "
            "The reviewed record is ready for "
            "human verification."
        )

        if st.button(
            "✅ Mark Data as Human Verified",
            type="primary",
            use_container_width=True,
        ):

            st.session_state[
                "verified"
            ] = True

            st.session_state[
                "approved"
            ] = False

            st.success(
                "Data marked as human verified."
            )

    if st.session_state.verified:

        st.success(
            "✅ Human verification completed."
        )

    else:

        st.info(
            "⏳ Human verification pending."
        )

    # ========================================================
    # FINAL APPROVAL
    # ========================================================

    st.header(
        "🔒 6. Final Approval"
    )

    if st.session_state.verified:

        st.write(
            "The record has passed validation "
            "and human review."
        )

        if st.button(
            "🔒 Approve Invoice for Export",
            type="primary",
            use_container_width=True,
        ):

            st.session_state[
                "approved"
            ] = True

            st.success(
                "Invoice approved for export."
            )

    else:

        st.warning(
            "Approval is locked until "
            "human verification is completed."
        )

    if st.session_state.approved:

        st.success(
            "🟢 APPROVED — Invoice is ready for export."
        )

    else:

        st.error(
            "🔴 NOT APPROVED — Export is locked."
        )

    # ========================================================
    # EVALUATION
    # ========================================================

    st.header(
        "📊 7. Prototype Evaluation"
    )

    evaluation = calculate_evaluation(
        original_fields,
        current_fields,
        result["text"],
        valid,
    )

    metric1, metric2, metric3, metric4 = (
        st.columns(4)
    )

    with metric1:

        st.metric(
            "Fields Extracted",
            f"{evaluation['extracted_fields']}/"
            f"{evaluation['total_fields']}",
        )

    with metric2:

        st.metric(
            "Corrections",
            evaluation["corrections"],
        )

    with metric3:

        st.metric(
            "Evidence Coverage",
            f"{evaluation['evidence_coverage'] * 100:.0f}%",
        )

    with metric4:

        st.metric(
            "Validation",
            "PASS"
            if evaluation["validation_passed"]
            else "FAIL",
        )

    st.caption(
        "These metrics describe the current prototype "
        "invoice and are not claims of general accuracy, "
        "productivity improvement, or market performance."
    )

    if evaluation["missing_fields"]:

        st.warning(
            "Missing extracted fields: "
            + ", ".join(
                evaluation["missing_fields"]
            )
        )

    else:

        st.success(
            "All defined invoice fields were extracted."
        )

    # ========================================================
    # CONTROLLED EXPORT
    # ========================================================

    st.header(
        "📥 8. Controlled Export"
    )

    if st.session_state.approved:

        st.success(
            "Export unlocked after validation, "
            "human verification, and final approval."
        )

        try:

            csv_bytes = create_csv_bytes(
                current_fields
            )

            json_bytes = create_json_bytes(
                current_fields
            )

            excel_bytes = create_excel_bytes(
                current_fields
            )

            export_col1, export_col2, export_col3 = (
                st.columns(3)
            )

            with export_col1:

                st.download_button(
                    label="📄 Download CSV",
                    data=csv_bytes,
                    file_name=(
                        "fieldextract_invoice.csv"
                    ),
                    mime="text/csv",
                    use_container_width=True,
                )

            with export_col2:

                st.download_button(
                    label="🧾 Download JSON",
                    data=json_bytes,
                    file_name=(
                        "fieldextract_invoice.json"
                    ),
                    mime="application/json",
                    use_container_width=True,
                )

            with export_col3:

                st.download_button(
                    label="📊 Download Excel",
                    data=excel_bytes,
                    file_name=(
                        "fieldextract_invoice.xlsx"
                    ),
                    mime=(
                        "application/vnd."
                        "openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    use_container_width=True,
                )

        except Exception as error:

            st.error(
                "Export preparation failed."
            )

            st.exception(error)

    else:

        st.warning(
            "🔒 Export is locked. Complete human "
            "verification and final approval first."
        )

    # ========================================================
    # RAW TEXT
    # ========================================================

    with st.expander(
        "📋 View Raw Extracted Text"
    ):

        st.text_area(
            "Document text",
            result["text"],
            height=300,
        )

    # ========================================================
    # STRUCTURED DATA
    # ========================================================

    with st.expander(
        "📄 View Current Structured Data"
    ):

        export_data = pd.DataFrame(
            [current_fields]
        )

        st.dataframe(
            export_data,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# EMPTY STATE
# ============================================================

else:

    st.info(
        "👆 Upload an invoice above to start "
        "the FieldExtract AI workflow."
    )

    st.markdown(
        """
### What FieldExtract AI does

**1. Extract**  
Reads invoice PDFs and images.

**2. Structure**  
Converts invoice information into defined fields.

**3. Evidence**  
Shows source text associated with extracted values.

**4. Review**  
Allows a human to inspect and correct the extraction.

**5. Validate**  
Checks required fields and amount consistency.

**6. Verify**  
Requires explicit human verification.

**7. Approve**  
Requires explicit final approval before export.

**8. Export**  
Produces CSV, JSON and Excel outputs.
        """
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    f"{APP_NAME} • {APP_VERSION} • Prototype"
)