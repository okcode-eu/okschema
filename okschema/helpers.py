import decimal, re, enum
import pendulum
import math
from .schema import NotValidError, ValidationCode


fmt_uuid = '[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}'
fmt_lang = '[A-Za-z]{1,3}'


def val_datetime(d):
    try:
        return pendulum.from_format(d, "YYYY-MM-DDTHH:mm:ss.SSSSSS")
    except ValueError as e:
        raise NotValidError(ValidationCode.BAD_TYPE, "bad datetime format")


def val_date(d):
    try:
        return pendulum.from_format(d, "YYYY-MM-DD")
    except ValueError as e:
        raise NotValidError(ValidationCode.BAD_TYPE, "bad date format")


def val_isfinite(d):
    return math.isfinite(d)
# postgres: float has inf, nan. numeric has nan.


class AppValidationCode(enum.IntEnum):
    BAD_VALUE = 50  # things like bad password
    DUPLICATE = 51 # duplicate fk
    NOT_FOUND = 52  # fk missing, sth missing in external system
    NOT_ENOUGH = 53  # too few entries, cannot delete sth
