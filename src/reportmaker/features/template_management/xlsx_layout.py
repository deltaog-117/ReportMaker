"""Defines the layout of the Excel template spreadsheet."""

# Sheet names
SHEET_REPORT = "Report"
SHEET_CHART = "Chart"
SHEET_TRANSFORM = "Transform"
SHEET_AGGREGATIONS = "Aggregations"
SHEET_PARAMETERS = "Parameters"

# Field names (for the key/value sheets)
# --- Report sheet ---
FIELD_REPORT_NAME = "Report Name"
FIELD_DESCRIPTION = "Description"
FIELD_DATABASE_URL = "Database URL"
FIELD_SQL_QUERY = "SQL Query"
FIELD_OUTPUT_FORMAT = "Output Format"
FIELD_SCHEDULE = "Schedule"

# --- Chart sheet ---
FIELD_CHART_KIND = "Kind"
FIELD_CHART_X_COLUMN = "X Column"
FIELD_CHART_Y_COLUMN = "Y Column"
FIELD_CHART_TITLE = "Title"
FIELD_CHART_X_LABEL = "X Label"
FIELD_CHART_Y_LABEL = "Y Label"

# --- Transform sheet ---
FIELD_TRANSFORM_GROUP_BY = "Group By"
FIELD_TRANSFORM_PIVOT_INDEX = "Pivot Index"
FIELD_TRANSFORM_PIVOT_COLUMNS = "Pivot Columns"
FIELD_TRANSFORM_PIVOT_VALUES = "Pivot Values"

# --- Aggregations sheet ---
AGG_HEADER_COLUMN = "Column"
AGG_HEADER_FUNCTION = "Function"

# --- Parameters sheet ---
PARAM_HEADER_NAME = "Name"
PARAM_HEADER_TYPE = "Type"
PARAM_HEADER_REQUIRED = "Required"
PARAM_HEADER_DEFAULT = "Default"
PARAM_HEADER_DESCRIPTION = "Description"


# --- Example rows for the blank template ---
EXAMPLE_REPORT_ROWS = [
    (FIELD_REPORT_NAME, "Daily Sales Report"),
    (FIELD_DESCRIPTION, "Sales by product for the last 7 days"),
    (FIELD_DATABASE_URL, "sqlite:///sales.db"),
    (FIELD_SQL_QUERY, "SELECT product, revenue FROM sales WHERE date >= date('now', '-7 days')"),
    (FIELD_OUTPUT_FORMAT, "pdf"),
    (FIELD_SCHEDULE, ""),
]

EXAMPLE_CHART_ROWS = [
    (FIELD_CHART_KIND, "bar"),
    (FIELD_CHART_X_COLUMN, "product"),
    (FIELD_CHART_Y_COLUMN, "revenue"),
    (FIELD_CHART_TITLE, "Revenue by Product"),
    (FIELD_CHART_X_LABEL, "Product"),
    (FIELD_CHART_Y_LABEL, "Revenue (USD)"),
]

EXAMPLE_TRANSFORM_ROWS = [
    (FIELD_TRANSFORM_GROUP_BY, "product"),
    (FIELD_TRANSFORM_PIVOT_INDEX, ""),
    (FIELD_TRANSFORM_PIVOT_COLUMNS, ""),
    (FIELD_TRANSFORM_PIVOT_VALUES, ""),
]

EXAMPLE_AGGREGATION_ROWS = [
    ("revenue", "sum"),
]

EXAMPLE_PARAMETER_ROWS = [
    ("start_date", "date", "false", "2026-09-01", "Start date for the report"),
    ("product", "string", "false", "Widget", "Product name to filter"),
]
