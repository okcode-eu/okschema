# Validate JSON data using a schema written in Python

# Examples

```
from okschema import validate, ValidationError, SchemaError

try:
    validated_data = validate(schema, data)
except ValidationError as e:
    print(e.js)  # {'code': ValidationCode.<xxx>}
```

## Validation of a simple form
```
from okschema import validate, fmt_uuid

def val_email(v):
    return v

schema = {
    'my_password':  {'@t': 'string', '@lteq': 100},
    'user_id':      {'@t': 'string', '@regexp': fmt_uuid},
    'new_email':    {'@t': 'string', '@val': val_email},
    'new_password': {'@t': 'string', '@lteq': 100},
}
data = {
    'my_password': 'abc',
    'user_id': 'dbc8911c-92e8-4cdb-85b8-47a7a6a82db1',
    'new_email': 'abc@example.com',
    'new_password': 'abc'
}
validated_data = validate(schema, data)
```

## Potential use in request handling

```
@api_request(schema=lambda m: {
    'email':    {'@t': 'string', '@lteq': m.user.c.email.ui_len},
    'password': {'@t': 'string', '@lteq': m.user.c.password.ui_len},
    'key':      {'@t': 'string', '@lteq': 10240},
    'permission_level': {'@t': 'int', '@in': [PermissionE.ADMIN, PermissionE.USER]},
})
async def add_user_account(request, m):
    ...
```

## Nested structure - error handling
```
schemaA = {
    'outer': {
        'a': 'int',
        'b': {'@t': 'str', '@lt': 2, '@required': False, '@null': True, '@blank': True},
        'c': [{'@t': 'str', '@in': ['x', 'y', 'z']}]
    },
    'is_ok': {'@type': 'bool', '@default': True}
}
data1 = {
}
data2 = {
    'outer': {
        'a': 'xxx',
        'b': '3333',
        'c': ['a', 'x', 12]
    },
    'is_ok': True
}
```

```
>>> validate(schemaA, data1)
ValidationError: ({
    'outer': {'code': ValidationCode.MISSING},
    'is_ok': {'code': ValidationCode.MISSING}
}, schemaA)
```

```
>>> validate(schemaA, data2)
ValidationError: ({
    'outer': {
        'a': {'code': ValidationCode.BAD_TYPE},
        'b': {'code': ValidationCode.NOT_LT, 'details': 2},
        'c': [
            {'code': ValidationCode.NOT_IN},
            None,  # no error here
            {'code': ValidationCode.BAD_TYPE}
        ]
    },
    'is_ok': {'code': ValidationCode.BAD_TYPE}
), schemaA)
```

## Custom validators - error handling

```
def bad_val1_cont(x):
    raise NotValidButContinueError(ValidationCode.BAD_VALUE, 1)

def bad_val2_cont(x):
    raise NotValidButContinueError(ValidationCode.BAD_VALUE, 5)

def bad_val3(x):
    raise NotValidError(ValidationCode.BAD_VALUE)

schemaA = {
    'b':  {'@t': 'int', '@val': [bad_val1_cont, bad_val2_cont]}
}
schemaB = {
    'b':  {'@t': 'int', '@val': [bad_val1_cont, bad_val2_cont, bad_val3]}
}
data1 = {'b': 12}
```

```
>>> validate(schemaA, data1)
ValidationError: ({
    'b': {
        'code': ValidationCode.MANY_ERRORS, 'details': [
            {'code': ValidationCode.BAD_VALUE, 'details': 1},
            {'code': ValidationCode.BAD_VALUE, 'details': 5}
        ]
    }
}, schemaA)

>>> validate(schemaB, data1)
ValidationError: ({
    'b': {
        'code': ValidationCode.MANY_ERRORS, 'details': [
            {'code': ValidationCode.BAD_VALUE, 'details': 1},
            {'code': ValidationCode.BAD_VALUE, 'details': 5},
            {'code': ValidationCode.BAD_VALUE}
        ]
    }
}, schemaA)
```

# ValidationCode enum

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

# Field description
```
"field: "type"
"field": { extended field description }
```

# Extended field description
By default all fields are required and strings must be non-empty. Extra fields in input data are discarded.
```
{
    "@t": "type", # default type is dict
    
    # -- validators --
    
    # Checks that regexp matches - called before other validators.
    "@regexp": "regexp",
    
    # Validator function.
    "@val": val_fun,
    "@val: [val_fun, val_fun2, ...],
    
    # -- options --
    
    # If True and value is missing, it will not be present in result unless
    # default is defined. Makes sense for subfields in dicts.
    "@optional": bool,
    
    # Allows empty strings.
    "@blank": bool,
    
    # Used when value is not present.
    # Default value is never passed to validators.
    "@default": value,
    
    # Allow nulls (None). By default null is not allowed.
    "@null": bool, 
    
    # -- limits --
    # Checked before validators are called.
    # They work for string lengths too.
    # TODO: They work for list lengths too.
    
    "@in": [value1, value2, ...],
    "@gt": value,
    "@gteq": value,
    "@lt": value,
    "@lteq": value,
    "@neq": value,
    
    # Extra fields if type is dict.
    "field1": field description or extended field description,
    ...
}
```

# Lists.

```
"field": [field description]
"field": [{extended field description}]
```

## TODO: Optional lists.

## TODO: List length limits.
```
"field": [
    {
        # field description
    }, {
        # list parameters
        "@optional": True,
        "@gt": val,
    }
]
```

# Available types
## scalar
 - string (str)
 - int
 - decimal
 - float
 - bool

## composite
 - dict

## TODO: Type "any" handles any type of subjson withot further validation

# Validator functions

```
def fun(val):
    return val + 1
```

Should either return validated value or raise NotValidError(code, details).
May also raise NotValidButContinueError to store the error but call the next validator, constructing a list
of errors. 
