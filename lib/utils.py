"""Utility functions"""


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human-readable size"""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_mb_size(mb_value: float) -> str:
    """Format MB to appropriate unit (MB, GB, TB)"""
    if mb_value < 1024:
        return f"{mb_value:,.2f} MB"
    elif mb_value < 1024 * 1024:
        return f"{mb_value / 1024:.2f} GB"
    else:
        return f"{mb_value / (1024 * 1024):.2f} TB"


def format_number(value: str) -> str:
    """Format number with thousands separator"""
    if value == 'N/A':
        return value
    try:
        num = float(value)
        if num == int(num):
            # Integer - add thousands separator
            return f"{int(num):,}"
        else:
            # Float - round to 2 decimals and add separator
            return f"{num:,.2f}"
    except:
        return value
