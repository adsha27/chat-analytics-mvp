import pytest
from datetime import datetime
import sys
import os
from pathlib import Path

# Fix import path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import normalize_phone_number, parse_wati_line, ChatSource

def test_normalize_phone_number():
    assert normalize_phone_number("9876543210") == "919876543210"
    assert normalize_phone_number("+91 98765-43210") == "919876543210"
    assert normalize_phone_number("123") == "123"

def test_parse_wati_line_valid():
    line = "24/10/23, 10:30 AM - +91 9876543210: Hello World"
    result = parse_wati_line(line)
    assert result is not None
    assert result['phone_number'] == "919876543210"
    assert result['message_text'] == "Hello World"
    assert result['source'] == ChatSource.WATI
    # Check datetime: 24th Oct 2023
    assert result['timestamp'].day == 24
    assert result['timestamp'].month == 10

def test_parse_wati_line_ambiguous_date():
    # 01/02/23 -> Should prefer Day First -> 1st Feb
    line = "01/02/23, 10:30 AM - Name: Msg"
    result = parse_wati_line(line)
    assert result['timestamp'].day == 1
    assert result['timestamp'].month == 2

def test_parse_wati_line_invalid():
    assert parse_wati_line("Invalid Line") is None
    # Malformed timestamp
    assert parse_wati_line("99/99/99, 10:30 AM - Sender: Msg") is None
