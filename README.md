# Json API data validation

# Examples

TODO:

See tests.

# Field description
```
"field: "type"
"field": { extended field description }
```

# Extended field description
By default all fields are required and strings must be non-empty.

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
    "field1": "type1",
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
