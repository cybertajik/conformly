from enum import StrEnum


class DataClassification(StrEnum):
    PUBLIC = "Public"
    INTERNAL = "Internal"
    CONFIDENTIAL = "Confidential"
    RESTRICTED = "Restricted"


def requires_application_encryption(
    classification: DataClassification,
    *,
    is_file: bool = False,
    confidential_field_selected: bool = False,
) -> bool:
    return (
        is_file
        or classification is DataClassification.RESTRICTED
        or (classification is DataClassification.CONFIDENTIAL and confidential_field_selected)
    )
