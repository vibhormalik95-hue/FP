"""Label-only printable policy; never rewrite labels or source evidence."""
import unicodedata


def is_printable_label(value):
    """Use the confirmed-target Cc/Cf/Cs policy before any caller trimming.

    Callers retain their existing length/byte limits and stored-label handling.
    Do not use this validator for verbatim source or evidence quotation fields.
    """
    return (isinstance(value, str) and bool(value.strip())
            and not any(unicodedata.category(char) in {"Cc", "Cf", "Cs"}
                        for char in value))
