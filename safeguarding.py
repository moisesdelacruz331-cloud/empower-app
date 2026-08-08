import hashlib
import re

# Persistent salt for cryptographic hashing (Store securely in st.secrets)
SALT_KEY = "EMPOWER_2026_SECURE_SALT"

# Define Regex Patterns for Profanity and Malicious Code Injections
PROFANITY_REGEX = r"(?i)\b(gago|tanga|bobo|tangina|penta|pUTA|ulol|fuck|shit|bitch|asshole|bastard)\b"
MALICIOUS_INPUT_REGEX = (
    r"(?i)(<script.*?>.*?</script>|<[^>]+>|SELECT\s+.*?\s+FROM|DROP\s+TABLE|OR\s+1=1)"
)


def generate_anonymous_id(lrn: str, salt: str = SALT_KEY) -> str:
    """Converts a raw Learner Reference Number (LRN) into a salted SHA-256 unique anonymous ID (e.g., STU-8A2F).

    Ensures LRNs are never stored in plain text on cloud databases.
    """
    if not lrn or str(lrn).strip() == "":
        return "STU-ANON"

    clean_lrn = str(lrn).strip()
    salted_bytes = f"{clean_lrn}{salt}".encode("utf-8")
    hash_digest = hashlib.sha256(salted_bytes).hexdigest()

    # Generate a deterministic 4-character alphanumeric identifier suffix
    short_id = hash_digest[:4].upper()
    return f"STU-{short_id}"


def sanitize_input(text: str) -> str:
    """Filters profane language and strips XSS/injection vectors before saving to Google Sheets."""
    if not text or not isinstance(text, str):
        return ""

    # 1. Neutralize malicious code & HTML script tags
    sanitized = re.sub(
        MALICIOUS_INPUT_REGEX, "[BLOCKED_INPUT]", text, flags=re.IGNORECASE
    )

    # 2. Mask profane/abusive content
    sanitized = re.sub(
        PROFANITY_REGEX, "*****", sanitized, flags=re.IGNORECASE
    )

    return sanitized.strip()


def validate_and_format_submission(payload: dict) -> dict:
    """Processes incoming student payload through privacy and sanitization filters."""
    return {
        "Timestamp": payload.get("Timestamp", ""),
        "Class/Section": payload.get("Class/Section", ""),
        # Store LRN exclusively as salted anonymized ID
        "Student LRN": generate_anonymous_id(payload.get("Student LRN", "")),
        "Mood": sanitize_input(payload.get("Mood", "")),
        "Kind Peer": generate_anonymous_id(payload.get("Kind Peer", "")),
        "Preferred Groupmate": generate_anonymous_id(
            payload.get("Preferred Groupmate", "")
        ),
        "Isolated Peer": generate_anonymous_id(
            payload.get("Isolated Peer", "")
        ),
        "Counselor Request": sanitize_input(
            payload.get("Counselor Request", "")
        ),
    }
