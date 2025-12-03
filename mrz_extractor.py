# mrz_extractor.py

import re
from typing import List, Dict, Any


# ============================================================
#  ICAO CHECK DIGIT HELPERS
# ============================================================
def mrz_char_value(c: str) -> int:
    if c.isdigit():
        return int(c)
    if "A" <= c <= "Z":
        return ord(c) - ord("A") + 10
    if c == "<":
        return 0
    return 0


def mrz_check_digit(field: str) -> str:
    weights = [7, 3, 1]
    total = 0
    for i, ch in enumerate(field):
        total += mrz_char_value(ch) * weights[i % 3]
    return str(total % 10)


# ============================================================
#  OCR AUTO-CORRECTION FOR MRZ LINES
# ============================================================
def normalize_mrz_line(line: str) -> str:
    """
    Apply light OCR corrections without being too aggressive.
    Common MRZ OCR mistakes: O↔0, I↔1, B↔8, S↔5.
    Only applied where it makes sense (digits vs letters).
    """
    # Remove spaces and weird chars first
    line = re.sub(r"[^A-Z0-9<]", "", line.upper())

    # Heuristic: in numeric-heavy segments, fix letters that look like digits
    def smart_fix(s: str) -> str:
        s_list = list(s)
        for i, ch in enumerate(s_list):
            # Digit context → force to digit
            if ch in "O" and (i > 0 and s_list[i-1].isdigit()):
                s_list[i] = "0"
            elif ch in "I" and (i > 0 and s_list[i-1].isdigit()):
                s_list[i] = "1"
            elif ch == "B" and (i > 0 and s_list[i-1].isdigit()):
                s_list[i] = "8"
            elif ch == "S" and (i > 0 and s_list[i-1].isdigit()):
                s_list[i] = "5"
        return "".join(s_list)

    line = smart_fix(line)
    return line


# ============================================================
#  EXTRACT MRZ LINES FROM RAW OCR TEXT
# ============================================================
def extract_mrz_from_ocr_text(text: str) -> List[str]:
    """
    Takes raw OCR text and returns MRZ lines (TD1, TD2, or TD3).
    """
    raw_lines = text.splitlines()
    candidates = []

    for ln in raw_lines:
        ln = ln.strip()
        if not ln:
            continue
        ln = normalize_mrz_line(ln)
        if ln.count("<") >= 2 and len(ln) >= 25:
            candidates.append(ln)

    if not candidates:
        raise ValueError("Could not detect MRZ-like lines in OCR output.")

    # --- TD1: 3 lines, ~30 chars ---
    td1 = [c for c in candidates if 28 <= len(c) <= 36]
    if len(td1) >= 3:
        return td1[:3]

    # --- TD3 / TD2: 2 lines ---
    # Prefer TD3: line 1 starts with P<
    line1 = next((c for c in candidates if c.startswith("P<")), None)
    others = [c for c in candidates if c != line1]

    if line1 and others:
        line2 = sorted(others, key=lambda x: -len(x))[0]
        return [line1, line2]

    # If we can't find a P< line, treat the two longest as TD2
    if len(candidates) >= 2:
        top2 = sorted(candidates, key=lambda x: -len(x))[:2]
        return top2

    raise ValueError("Not enough MRZ lines found.")


# ============================================================
#  TD3 — PASSPORT (2 lines, 44 chars)
# ============================================================
def parse_td3(lines: List[str]) -> Dict[str, Any]:
    line1 = lines[0].ljust(44, "<")
    line2 = lines[1].ljust(44, "<")

    document_type = line1[0]
    issuing_country = line1[2:5]

    name_section = line1[5:]
    parts = name_section.split("<<", 1)
    surname = parts[0].replace("<", " ").strip()
    given_names = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""

    passport_num = line2[0:9]
    passport_cd = line2[9]

    nationality = line2[10:13]

    dob = line2[13:19]
    dob_cd = line2[19]

    sex = line2[20]

    expiry = line2[21:27]
    expiry_cd = line2[27]

    optional = line2[28:42]
    optional_cd = line2[42]

    composite_cd = line2[43]

    def convert(d: str):
        if not re.match(r"^\d{6}$", d):
            return None
        yy = int(d[:2])
        mm = d[2:4]
        dd = d[4:6]
        year = 2000 + yy if yy < 30 else 1900 + yy
        return f"{year}-{mm}-{dd}"

    fields = {
        "document_type": document_type,
        "issuing_country": issuing_country,
        "surname": surname,
        "given_names": given_names,
        "passport_number": passport_num.replace("<", ""),
        "nationality": nationality,
        "date_of_birth": convert(dob),
        "sex": sex,
        "date_of_expiry": convert(expiry),
        "optional_data": optional.replace("<", ""),
    }

    check_digits = {
        "passport_valid": mrz_check_digit(passport_num) == passport_cd,
        "dob_valid": mrz_check_digit(dob) == dob_cd,
        "expiry_valid": mrz_check_digit(expiry) == expiry_cd,
        "optional_valid": mrz_check_digit(optional) == optional_cd,
        "composite_valid": mrz_check_digit(
            passport_num + passport_cd +
            nationality + dob + dob_cd +
            sex + expiry + expiry_cd +
            optional + optional_cd
        ) == composite_cd,
    }

    return {
        "mrz_type": "TD3 (Passport)",
        "fields": fields,
        "check_digits": check_digits,
    }


# ============================================================
#  TD1 — ID CARD (3 lines)
# ============================================================
def parse_td1(lines: List[str]) -> Dict[str, Any]:
    l1, l2, l3 = [ln.ljust(30, "<") for ln in lines]

    doc_type = l1[0:2]
    issuing_country = l1[2:5]
    doc_num = l1[5:14]
    doc_cd = l1[14]
    optional1 = l1[15:30]

    dob = l2[0:6]
    dob_cd = l2[6]
    sex = l2[7]
    exp = l2[8:14]
    exp_cd = l2[14]
    nationality = l2[15:18]
    optional2 = l2[18:29]
    optional2_cd = l2[29]

    name_parts = l3.split("<<")
    surname = name_parts[0].replace("<", " ").strip()
    given_names = name_parts[1].replace("<", " ").strip() if len(name_parts) > 1 else ""

    def convert(d: str):
        if not re.match(r"^\d{6}$", d):
            return None
        yy = int(d[:2])
        mm = d[2:4]
        dd = d[4:6]
        year = 2000 + yy if yy < 30 else 1900 + yy
        return f"{year}-{mm}-{dd}"

    fields = {
        "document_type": doc_type,
        "issuing_country": issuing_country,
        "document_number": doc_num.replace("<", ""),
        "surname": surname,
        "given_names": given_names,
        "sex": sex,
        "nationality": nationality,
        "date_of_birth": convert(dob),
        "date_of_expiry": convert(exp),
        "optional_data": (optional1 + optional2).replace("<", ""),
    }

    check_digits = {
        "document_number_valid": mrz_check_digit(doc_num) == doc_cd,
        "dob_valid": mrz_check_digit(dob) == dob_cd,
        "expiry_valid": mrz_check_digit(exp) == exp_cd,
        "optional2_valid": mrz_check_digit(optional2) == optional2_cd,
    }

    return {
        "mrz_type": "TD1 (ID Card)",
        "fields": fields,
        "check_digits": check_digits,
    }


# ============================================================
#  TD2 — VISA (2 lines)
# ============================================================
def parse_td2(lines: List[str]) -> Dict[str, Any]:
    l1, l2 = [ln.ljust(36, "<") for ln in lines]

    doc_type = l1[0]
    issuing_country = l1[2:5]

    name_parts = l1[5:].split("<<")
    surname = name_parts[0].replace("<", " ").strip()
    given_names = name_parts[1].replace("<", " ").strip() if len(name_parts) > 1 else ""

    passport_num = l2[0:9]
    passport_cd = l2[9]

    nationality = l2[10:13]

    dob = l2[13:19]
    dob_cd = l2[19]

    sex = l2[20]

    expiry = l2[21:27]
    expiry_cd = l2[27]

    optional = l2[28:35]
    optional_cd = l2[35]

    def convert(d: str):
        if not re.match(r"^\d{6}$", d):
            return None
        yy = int(d[:2])
        mm = d[2:4]
        dd = d[4:6]
        year = 2000 + yy if yy < 30 else 1900 + yy
        return f"{year}-{mm}-{dd}"

    fields = {
        "document_type": doc_type,
        "issuing_country": issuing_country,
        "surname": surname,
        "given_names": given_names,
        "passport_number": passport_num.replace("<", ""),
        "nationality": nationality,
        "sex": sex,
        "date_of_birth": convert(dob),
        "date_of_expiry": convert(expiry),
        "optional_data": optional.replace("<", ""),
    }

    check_digits = {
        "passport_valid": mrz_check_digit(passport_num) == passport_cd,
        "dob_valid": mrz_check_digit(dob) == dob_cd,
        "expiry_valid": mrz_check_digit(expiry) == expiry_cd,
        "optional_valid": mrz_check_digit(optional) == optional_cd,
    }

    return {
        "mrz_type": "TD2 (Visa)",
        "fields": fields,
        "check_digits": check_digits,
    }


# ============================================================
#  CONFIDENCE SCORING
# ============================================================
def compute_confidence(parsed: Dict[str, Any]) -> float:
    cd = parsed.get("check_digits", {})
    if not cd:
        return 0.3

    bools = []
    for v in cd.values():
        if isinstance(v, bool):
            bools.append(v)
    if not bools:
        return 0.4

    base = sum(1 for x in bools if x) / len(bools)  # 0–1

    # Light bonus if MRZ type is known & fields look good
    if parsed.get("mrz_type", "").startswith("TD"):
        base += 0.1

    return max(0.0, min(1.0, base))


# ============================================================
#  MAIN DISPATCH
# ============================================================
def parse_mrz(mrz_lines: List[str]) -> Dict[str, Any]:
    if len(mrz_lines) == 3:
        parsed = parse_td1(mrz_lines)
    elif len(mrz_lines) == 2:
        # If starts with P< or very long → TD3
        if mrz_lines[0].startswith("P<") or len(mrz_lines[0]) >= 40:
            parsed = parse_td3(mrz_lines)
        else:
            parsed = parse_td2(mrz_lines)
    else:
        raise ValueError("Unsupported MRZ layout.")

    parsed["confidence"] = compute_confidence(parsed)
    return parsed
