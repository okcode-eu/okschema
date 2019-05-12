from decimal import Decimal
import decimal
import re
import enum
import math
from typing import Any
import inspect


class NotHereClass:
    pass
NotHere = NotHereClass()


class SchemaCode(enum.IntEnum):
    UNKNOWN_TYPE = 1000
    ILLEGAL_COMPARISON = 1001
    VAL_NOT_CALLABLE = 1002
    BAD_REGEXP = 1003


class ValidationCode(enum.IntEnum):
    GENERAL = 0
    # Validation errors
    BAD_TYPE = 1
    NOT_IN = 2
    NULL = 3
    MISSING = 4
    OUT_OF_BOUNDS = 5  # for use by validators
    REGEXP = 6
    MANY_ERRORS = 8  # list of errors for a single field
    NOT_GT = 9
    NOT_GTEQ = 10
    NOT_LT = 11
    NOT_LTEQ = 12
    NOT_NEQ = 13
    NOT_EQ = 14


class SchemaError(Exception):
    def __init__(self, code: SchemaCode, details=None):
        self.code: SchemaCode = code
        self.details = details


class ValidationError(Exception):
    def __init__(self, js: dict, schema):
        self.js: dict = js
        self.schema = schema


class NotValidError(Exception):
    """Thrown by validators."""

    def __init__(self, code, details=None):
        self.code = code
        self.details = details

    def jsonize(self):
        if self.code in [_StructureCode.DICT, _StructureCode.LIST]:
            return self.details
        else:
            if self.details is not None:
                if isinstance(self.code, enum.IntEnum):
                    return {'code': self.code.value, 'details': self.details}
                else:
                    return {'code': self.code, 'details': self.details}
            else:
                return {'code': self.code.value}


class NotValidButContinueError(NotValidError):
    pass


class _StructureCode(enum.IntEnum):
    DICT = -1
    LIST = -2


def validate(schema, data, **kwargs):
    """Validates data according to the schema."""
    try:
        e = Engine(**kwargs)
        data = e.validate(schema, data)
    except NotValidError as e:
        raise ValidationError(e.jsonize(), schema) # from None (TODO)
    return data


# TODO: design a schema to validate any possible schema

class Engine:
    def __init__(self, cast_from_string=False, allow_not_finite=False, strict_types=False):
        # cast bool and int from strings
        self.cast_from_string = cast_from_string  # floats, ints, decimals
        self.allow_not_finite = allow_not_finite  # decimals
        self.strict_types = strict_types  # for validating generated data
        if self.cast_from_string:
            self.strict_types = False

    def validate(self, schema, data):
        """
        Validates a single json value.
        :param schema: description of the expected value
        :param data: the value to validate
        :return: validated_value
        :raises: ValidationError, SchemaError
        """
        if isinstance(schema, list):
            return self.handle_list(schema, data)

        ftype = self.determine_field_type(schema)

        # Preparse and handle edge cases.
        if data is NotHere:
            return self.handle_optional_and_default_when_data_nothere(schema)
        else:
            if data is not None:
                data = self.cast_data(ftype, data)  # raises NotValidError, SchemaError
            else:
                # Handle nulls.
                allow_null = self.get_bool_opt_from_schema(schema, '@null')
                if not allow_null:
                    raise NotValidError(ValidationCode.NULL)
                return None  # Data is None and it is allowed.

        if ftype == 'dict':
            # Parse subfields of dictionary.
            error_details = {}
            rc_data = {}
            for fieldname, subschema in schema.items():  # iterate expected keys
                if fieldname[0] != '@':
                    try:
                        subdata = data[fieldname]
                    except KeyError:
                        subdata = NotHere  # pass NotHere to inform us recursively that there is no data for this key
                    try:
                        # Validate recursively.
                        rc_subdata = self.validate(subschema, subdata)
                        if rc_subdata is not NotHere:
                            rc_data[fieldname] = rc_subdata
                    except NotValidError as e:
                        error_details[fieldname] = e.jsonize()
            if error_details:
                raise NotValidError(_StructureCode.DICT, error_details)

            if '@val' in schema:
                # Whole-dict validator.
                rc_data = self.call_validators(schema['@val'], rc_data)
        else:
            # Data is expected to be a scalar value.
            if isinstance(schema, dict):
                # The value of data has further constraints and options specified in schema.
                rc_data = self.verify_value_options(schema, ftype, data)
            else:
                rc_data = data
        return rc_data

    def handle_optional_and_default_when_data_nothere(self, schema):
        # No value supplied in json. Check if it's allowed and if there is a default value.
        optional = self.get_bool_opt_from_schema(schema, '@optional')
        if not optional:
            raise NotValidError(ValidationCode.MISSING)
        try:
            default = schema['@default']
            if callable(default):
                default = default()
        except KeyError:
            return NotHere  # Optional field has no default.
        return default  # Default is returned as is, no validators are run.

    def handle_list(self, schema, data):
        list_opts = {}
        if len(schema) == 2:
            list_opts = schema[1]  # must be a dict
        item_schema = schema[0]
        error_list = []
        has_errors = False
        result_data = []
        if data is NotHere:
            return self.handle_optional_and_default_when_data_nothere(list_opts)
        if not isinstance(data, (list, tuple)):
            raise NotValidError(ValidationCode.BAD_TYPE)
        # TODO: handle list length opts
        # TODO: handle list-level validators
        # Validate each list item.
        for data_item in data:
            try:
                item_result_data = self.validate(item_schema, data_item)
                result_data.append(item_result_data)
                error_list.append(None)
            except NotValidError as e:
                error_list.append(e.jsonize())
                has_errors = True
        if has_errors:
            # Errors in list items.
            raise NotValidError(_StructureCode.LIST, error_list)
        return result_data

    def determine_field_type(self, schema):
        ftype = 'dict'
        if isinstance(schema, dict):
            try:
                ftype = schema['@t']
            except KeyError:
                pass
        elif isinstance(schema, str):
            ftype = schema.split(',')[0]
        return ftype

    def cast_data(self, ftype, data):
        """Cast data to given ftype or raise BAD_TYPE."""
        if ftype == 'dict':
            if not isinstance(data, dict):
                raise NotValidError(ValidationCode.BAD_TYPE)
        elif ftype in ['string', 'str']:
            if not isinstance(data, str):
                raise NotValidError(ValidationCode.BAD_TYPE)
        elif ftype == 'decimal':
            # Decimals are always good as strings.
            allowed_types = (Decimal,) if self.strict_types else (Decimal, int, float, str)
            if not isinstance(data, allowed_types):
                # Don't allow tuple as constructor's argument.
                raise NotValidError(ValidationCode.BAD_TYPE)
            try:
                data = Decimal(data)
                if not self.allow_not_finite and not math.isfinite(data):
                    raise NotValidError(ValidationCode.BAD_TYPE, "infinite decimal")
            except (decimal.InvalidOperation, TypeError, ValueError):
                raise NotValidError(ValidationCode.BAD_TYPE)
        elif ftype == 'float':
            # Floats must be given as numbers unless cast_from_string is True.
            allowed_types = (float,) if self.strict_types else (int, float)
            if not isinstance(data, allowed_types):
                if isinstance(data, str) and self.cast_from_string:
                    try:
                        data = float(data)
                    except (ValueError, TypeError):
                        raise NotValidError(ValidationCode.BAD_TYPE)
                else:
                    raise NotValidError(ValidationCode.BAD_TYPE)
        elif ftype == 'bool':
            if not isinstance(data, bool):
                if self.strict_types:
                    raise NotValidError(ValidationCode.BAD_TYPE)
                if isinstance(data, str) and self.cast_from_string:
                    if data.lower() == "false":
                        data = False
                    elif data.lower() == "true":
                        data = True
                    else:
                        raise NotValidError(ValidationCode.BAD_TYPE)
                else:
                    raise NotValidError(ValidationCode.BAD_TYPE)
        elif ftype == 'int':
            if not isinstance(data, int):
                if isinstance(data, str) and self.cast_from_string:
                    try:
                        data = int(data)
                    except ValueError:
                        raise NotValidError(ValidationCode.BAD_TYPE)
                else:
                    raise NotValidError(ValidationCode.BAD_TYPE)
        else:
            raise SchemaError(SchemaCode.UNKNOWN_TYPE)
        return data

    def verify_value_options(self, schema, ftype, data):
        """Checks if scalar data holds constraints specified in schema."""
        try:
            regexp = schema['@regexp']
        except KeyError:
            pass
        else:
            if not isinstance(regexp, str):
                raise SchemaError(SchemaCode.BAD_REGEXP)
            try:
                if not re.match(regexp, data):
                    raise NotValidError(ValidationCode.REGEXP)
            except TypeError:
                # Some really bad value instead of string.
                raise NotValidError(ValidationCode.REGEXP)

        # Other conditions.
        blank_string_allowed = self.get_bool_opt_from_schema(schema, "@blank")
        if ftype in ['str', 'string'] and not blank_string_allowed and not len(data):
            raise NotValidError(ValidationCode.NOT_GT, 0)
        for optname, optval in schema.items():
            if optname[0] == '@':
                optname = optname[1:]
                if optname == 'in':
                    if inspect.isclass(optval) and issubclass(optval, enum.Enum):
                        optval = set(optval)
                    if data not in optval:
                        raise NotValidError(ValidationCode.NOT_IN)
                elif optname in ['gt', 'gteq', 'lt', 'lteq', 'neq', 'eq']:
                    if ftype not in ['int', 'float', 'decimal', 'string', 'str']:
                        raise SchemaError(SchemaCode.ILLEGAL_COMPARISON)
                    if ftype in ['string', 'str']:
                        xdata = len(data)  # Length validators check string lengths.
                    else:
                        xdata = data

                    if optname == 'gt':
                        if not xdata > optval:
                            raise NotValidError(ValidationCode.NOT_GT, optval)
                    elif optname == 'gteq':
                        if not xdata >= optval:
                            raise NotValidError(ValidationCode.NOT_GTEQ, optval)
                    elif optname == 'lt':
                        if not xdata < optval:
                            raise NotValidError(ValidationCode.NOT_LT, optval)
                    elif optname == 'lteq':
                        if not xdata <= optval:
                            raise NotValidError(ValidationCode.NOT_LTEQ, optval)
                    elif optname == 'neq':
                        if not xdata != optval:
                            raise NotValidError(ValidationCode.NOT_NEQ, optval)
                    elif optname == 'eq':
                        if not xdata == optval:
                            raise NotValidError(ValidationCode.NOT_EQ, optval)
                elif optname == 'val':
                    data = self.call_validators(optval, data)
        return data

    def get_bool_opt_from_schema(self, schema, opt):
        """None, False, True"""
        rc = None
        if isinstance(schema, dict):
            rc = False
            try:
                rc = schema[opt]
            except KeyError:
                pass
        return rc

    def call_validators(self, validators, data):
        """Call validators on data."""
        if callable(validators):
            data = validators(data)
        elif isinstance(validators, list):
            error_collection = []
            try:
                for val_fun in validators:
                    if callable(val_fun):
                        try:
                            data = val_fun(data)
                        except NotValidButContinueError as e:
                            # Continue calling next validators with the same input.
                            error_collection.append(e)
                            continue
                    else:
                        raise SchemaError(SchemaCode.VAL_NOT_CALLABLE)
            except NotValidError as e:
                error_collection.append(e)

            if error_collection:
                if len(error_collection) == 1:
                    raise error_collection[0]
                else:
                    jsonized_errors = [e.jsonize() for e in error_collection]
                    raise NotValidError(ValidationCode.MANY_ERRORS, jsonized_errors)
        else:
            raise SchemaError(SchemaCode.VAL_NOT_CALLABLE)
        return data
