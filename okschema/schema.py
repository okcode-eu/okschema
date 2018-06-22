import decimal, re, enum
import pendulum


fmt_uuid = '[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}'
fmt_lang = '[A-Za-z]{1,3}'


def val_datetime(val):
    try:
        return pendulum.from_format(val, "YYYY-MM-DDTHH:mm:ss.SSSSSS")
    except ValueError as e:
        raise NotValidError(ValidationCode.BAD_TYPE, "bad datetime format")


def val_date(val):
    try:
        return pendulum.from_format(val, "YYYY-MM-DD")
    except ValueError as e:
        raise NotValidError(ValidationCode.BAD_TYPE, "bad date format")


class NotHereClass:
    pass
NotHere = NotHereClass()


class SchemaError(Exception):
    pass


class SchemaCode(enum.IntEnum):
    UNKNOWN_OPTION = 1000
    ILLEGAL_COMPARISON = 2000
    VAL_NOT_CALLABLE = 3000


class ValidationError(Exception):

    def __init__(self, js, schema):
        self.js, schema = js, schema


class NotValidError(Exception):

    def __init__(self, code, details=None):
        self.code, self.details = code, details

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
    NOT_EQ = 13

    # Application dependent, not generated here but could be used by validators or some other code
    BAD_VALUE = 50  # things like bad password
    DUPLICATE_VALUE = 51 # duplicate fk
    NOT_FOUND = 52  # fk missing, sth missing in external system
    NOT_ENOUGH = 53  # too few entries, cannot delete sth


class _StructureCode(enum.IntEnum):
    DICT = -1
    LIST = -2


def validate(schema, data):
    """Validates data according to the schema."""
    try:
        data = _validate(schema, data)
    except NotValidError as e:
        raise ValidationError(e.jsonize(), schema) # from None
    return data


def _validate(schema, data):
    """
    Validates a single json value.
    :param schema: description of the expected value
    :param data: the value to validate
    :return: validated_value
    :raises: ValidationError, SchemaError
    """
    if isinstance(schema, list):
        # Handle lists of values.
        if len(schema) == 2:
            list_opts = schema[1]
            # TODO: validate list opts
        item_schema = schema[0]
        error_list = []
        has_errors = False
        result_data = []
        if data is NotHere:
            raise NotValidError(ValidationCode.MISSING)
            # TODO: handle list opts, check list's '@required' opt.
        if not isinstance(data, list):
            raise NotValidError(ValidationCode.BAD_TYPE)
        for data_item in data:
            try:
                item_result_data = _validate(item_schema, data_item)
                result_data.append(item_result_data)
                error_list.append(None)
            except NotValidError as e:
                error_list.append(e.jsonize())
                has_errors = True
        if has_errors:
            # Errors in list items.
            raise NotValidError(_StructureCode.LIST, error_list)
        return result_data

    ftype = determine_field_type(schema)

    # Preparse and handle edge cases.
    if data is NotHere:
        # No value supplied in json. Check if it's allowed and if there is a default value.
        optional = get_bool_opt_from_schema(schema, '@optional')
        if not optional:
            raise NotValidError(ValidationCode.MISSING)
        try:
            default = schema['@default']
            if callable(default):
                default = default()
        except KeyError:
            return NotHere  # Optional field has no default.
        return default  # Default is returned as is, no validators are runned.
    else:
        if data is not None:
            data = cast_data(ftype, data)  # raises InternalValidationError, SchemaError
        else:
            # Handle nulls.
            allow_null = get_bool_opt_from_schema(schema, '@null')
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
                    rc_subdata = _validate(subschema, subdata)
                    if rc_subdata is not NotHere:
                        rc_data[fieldname] = rc_subdata
                except NotValidError as e:
                    error_details[fieldname] = e.jsonize()
        if error_details:
            raise NotValidError(_StructureCode.DICT, error_details)

        if '@val' in schema:
            # Whole-dict validator.
            rc_data = call_validators(schema['@val'], rc_data)
    else:
        # Data is expected to be a scalar value.
        if isinstance(schema, dict):
            # The value of data has further constraints and options specified in schema.
            rc_data = verify_value_options(schema, ftype, data)
        else:
            rc_data = data
    return rc_data


def determine_field_type(schema):
    ftype = 'dict'
    if isinstance(schema, dict):
        try:
            ftype = schema['@t']
        except KeyError:
            pass
    elif isinstance(schema, str):
        ftype = schema.split(',')[0]
    return ftype


def cast_data(ftype, data):
    """Cast data to given ftype or raise BAD_TYPE."""
    if ftype == 'dict':
        if not isinstance(data, dict):
            raise NotValidError(ValidationCode.BAD_TYPE)
    elif ftype in ['string', 'str', 'decimal', 'float']:
        if not isinstance(data, str):
            raise NotValidError(ValidationCode.BAD_TYPE)
        if ftype == 'decimal':
            try:
                data = decimal.Decimal(data)
            except (decimal.InvalidOperation, TypeError):
                raise NotValidError(ValidationCode.BAD_TYPE)
        elif ftype == 'float':
            try:
                data = float(data)
            except (ValueError, TypeError):
                raise NotValidError(ValidationCode.BAD_TYPE)
    elif ftype == 'bool':
        data = bool(data)
    elif ftype == 'int':
        if not isinstance(data, int):
            raise NotValidError(ValidationCode.BAD_TYPE)
    else:
        raise SchemaError(ValidationCode.BAD_TYPE)
    return data


def verify_value_options(schema, ftype, data):
    """Checks if scalar data holds constraints specified in schema."""
    if '@regexp' in schema:
        regexp = schema['@regexp']
        if not re.match(regexp, data):
            raise NotValidError(ValidationCode.REGEXP)

    # Limits
    blank_string_allowed = get_bool_opt_from_schema(schema, "@blank")
    if ftype in ['str', 'string'] and not blank_string_allowed and not len(data):
        raise NotValidError(ValidationCode.NOT_GT, 0)
    for optname, optval in schema.items():
        if optname[0] == '@':
            optname = optname[1:]
            if optname == 'in':
               if data not in optval:
                    raise NotValidError(ValidationCode.NOT_IN)
            elif optname in ['gt', 'gteq', 'lt', 'lteq', 'neq']:
                if ftype not in ['int', 'float', 'decimal', 'string', 'str']:
                    raise SchemaError(ValidationCode.ILLEGAL_COMPARISON)
                if ftype in ['string', 'str']:
                    xdata = len(data)  # Length validators check lists lengths
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
                        raise NotValidError(ValidationCode.NOT_EQ, optval)
            elif optname == 'val':
                data = call_validators(optval, data)
    return data


def get_bool_opt_from_schema(schema, opt):
    rc = None
    if isinstance(schema, str):
        # TODO: remove the string parsing
        # Look for option in the string.
        opts = schema.split(',')[1:]
        rc = opt in opts
    elif isinstance(schema, dict):
        rc = False
        try:
            rc = schema[opt]
        except KeyError:
            pass
    return rc


def call_validators(validators, data):
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
                    raise SchemaError(ValidationCode.VAL_NOT_CALLABLE)
        except NotValidError as e:
            error_collection.append(e)

        if error_collection:
            if len(error_collection) == 1:
                raise error_collection[0]
            else:
                jsonized_errors = [e.jsonize() for e in error_collection]
                raise NotValidError(ValidationCode.MANY_ERRORS, jsonized_errors)
    else:
        raise SchemaError(ValidationCode.VAL_NOT_CALLABLE)
    return data
