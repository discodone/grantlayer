"""GrantLayer MVP — GL-114 String-length validation helpers."""

MAX_SHORT_ID_LENGTH = 128
MAX_ROLE_LENGTH = 64
MAX_LABEL_LENGTH = 128
MAX_NAME_LENGTH = 256
MAX_URL_LENGTH = 2048
MAX_DESCRIPTION_LENGTH = 1000
MAX_REASON_LENGTH = 1000
MAX_METADATA_STRING_LENGTH = 1000


class ValidationError(ValueError):
    """Project-consistent validation exception."""
    pass


def validate_string_length(value, field_name: str, max_length: int) -> None:
    """Validate that *value* is a string and does not exceed *max_length*.

    Raises ValidationError with a safe message containing *field_name* and
    *max_length*.  The full offending value is never echoed.
    """
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")
    if len(value) > max_length:
        raise ValidationError(
            f"{field_name} exceeds maximum length of {max_length} characters."
        )


def validate_optional_string_length(value, field_name: str, max_length: int) -> None:
    """Validate that an optional string *value* does not exceed *max_length*.

    None is accepted.  Raises ValidationError on overlong or non-string values.
    """
    if value is None:
        return
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")
    if len(value) > max_length:
        raise ValidationError(
            f"{field_name} exceeds maximum length of {max_length} characters."
        )
