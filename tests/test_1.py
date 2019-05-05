from okschema import NotValidError, NotValidButContinueError, ValidationCode, \
    ValidationError, validate, NotHere, Engine
from okschema.helpers import val_date, val_datetime, fmt_uuid, AppValidationCode
import decimal
import pendulum as dt
import pytest
import enum


class FakeEnumE(enum.IntEnum):
    A = 1
    B = 2


def val_err(x):
    raise NotValidError(AppValidationCode.BAD_VALUE)


def dict_lteq_12(d):
    suma = d['a'] + d['b']
    if not suma <= 12:
        raise NotValidError(ValidationCode.OUT_OF_BOUNDS)
    d['sum'] = suma
    return d


def bad_val1_cont(x):
    raise NotValidButContinueError(AppValidationCode.BAD_VALUE, 1)


def bad_val2_cont(x):
    raise NotValidButContinueError(AppValidationCode.BAD_VALUE, 5)


ok_tests = [
    ('int', 12),
    ('string', 'aaa'),
    ('float', 121.12, 121.12),
    ('decimal', '121.1222222', decimal.Decimal('121.1222222')),
    ('bool', False),
    ({'@t': 'int'}, 12),
    ({'@t': 'bool'}, True),
    (
         {
            'a': {'@t': 'int', '@val': [lambda x: x*2, lambda x: x+1]},
            'b': {
                'ba': {
                    '@t': 'int',
                    '@lteq': 15,
                    '@val': lambda x: x+1
                }
            },
            'c': 'int'
        }, {  # input
            'a': 12,
            'b': {
                'ba': 15
            },
            'c': 0
        }, {  # expected result
            'a': 25,
            'b': {
                'ba': 16
            },
            'c': 0
        },

    ), (
        {
            'a': 'string',
            'b': 'decimal',
        }, {
            'a': '123123',
            'b': '12.12',
        },
        {
            'a': '123123',
            'b': decimal.Decimal('12.12'),
        }
    ), (
        {
            'a': {'@t': 'string', '@lteq': 7}
        }, {
            'a': '123123',
        }
    ),
    (
        # dict validator
        {
            'a': 'int',
            'b': 'int',
            '@val': lambda d: d['a'] + d['b']
        },
        {
            'a': 10,
            'b': 2
        },
        12
    ),
    (
        # dict validator, extra field
        {
            'a': 'int',
            'b': 'int',
            '@val': dict_lteq_12,
        },
        {
            'a': 10,
            'b': 2
        },
        {
            'a': 10,
            'b': 2,
            'sum': 12
        }
    ),
    # Blank strings
    (
        {'a': {'@t': 'str', '@blank': True}},
        {'a': ''}
    ),
    # Dates
    (
        {'a': {'@t': 'str', '@val': val_date}},
        {'a': '2018-03-12'},
        {'a': dt.datetime(2018, 3, 12)}
    ),
    (
        {'a': {'@t': 'str', '@val': val_datetime}},
        {'a': '2018-03-28T10:29:32.358Z'},
        {'a': dt.datetime(2018, 3, 28, 10, 29, 32, 358)}
    ),
    # Extra dict fields must be ignored
    (
        {
            'a': 'int',
            'b': {'x': 'int'},
        },
        {
            'a': 10,
            'b': {'x': 5, 'y': '21212'},
            'extra_c': [],
            'extra_d': 'ooops'
        },
        {
            'a': 10,
            'b': {'x': 5},
        }
    ),
    (
        {
            'a': 'int',
            'b': {'@t': 'int', '@optional': True},
        },
        {
            'a': 10,
        },
        {
            'a': 10
        }
    ),
    (
        {
            'a': 'int',
            'b': {'@t': 'int', '@optional': True, '@default': 5},
        },
        {
            'a': 10,
        },
        {
            'a': 10,
            'b': 5
        }
    ),
    # @in
    (
        {
            'a': {'@t': 'int', '@in': [1, 2, 3]}
        },
        {
            'a': 1
        }
    ),
    # more data then needed
    (
        {'a': 'int', 'b': 'int'},
        {'a': 10, 'b': 20, 'c': 30},
        {'a': 10, 'b': 20}
    ),
    # regexp TODO:
    # enum
    (
        {'a': {'@t': 'int', '@in': FakeEnumE}},
        {'a': 1}
    )
]

bad_tests = [
    (
        'int', '123', {'code': ValidationCode.BAD_TYPE}
    ),
    (
        'float', '123.1', {'code': ValidationCode.BAD_TYPE}
    ),
    (
        {'@t': 'string', '@val': val_err}, 'abc', {'code': AppValidationCode.BAD_VALUE}
    ),
    (
        {'a': {'@t': 'string', '@val': val_err}}, {'a': 'abc'}, {'a': {'code': AppValidationCode.BAD_VALUE}}
    ),
    # Fields missing, constraint errors
    (
        {
            'a': {'@t': 'string', '@val': val_err},
            'b': {'@t': 'string'},
            'sub1': {
                'c': {'@t': 'int', '@lt': 10, '@gt': 5},
            },
            'sub2': {
                'c': 'int',
            }
        }, {
            'a': 'abc',
            'sub1': {
                'c': 3
            }
        }, {
            'a': {'code': AppValidationCode.BAD_VALUE},
            'b': {'code': ValidationCode.MISSING},
            'sub1': {
                'c': {'code': ValidationCode.NOT_GT, 'details': 5}
            },
            'sub2': {'code': ValidationCode.MISSING}
        }
    ),
    # missing simple value
    (
        'int',
        NotHere,
        {'code': ValidationCode.MISSING}
    ),
    # dict validator
    (
        {
            'a': 'int',
            'b': 'int',
            '@val': dict_lteq_12
        },
        {
            'a': 10,
            'b': 3
        },
        {'code': ValidationCode.OUT_OF_BOUNDS}
    ),
    # Stacked validators with continuation
    (
        {'a': {'b':  {'@t': 'int', '@val': [bad_val1_cont, bad_val2_cont]}}},
        {'a': {'b': 12}},
        {'a': {'b': {'code': ValidationCode.MANY_ERRORS, 'details': [
            {'code': AppValidationCode.BAD_VALUE, 'details': 1}, {'code': AppValidationCode.BAD_VALUE, 'details': 5}
        ]}}}
    ),
    # Validators with continuation and normal
    (
        {'b':  {'@t': 'int', '@val': [bad_val1_cont, bad_val2_cont, val_err]}},
        {'b': 12},
        {'b': {'code': ValidationCode.MANY_ERRORS, 'details': [
            {'code': AppValidationCode.BAD_VALUE, 'details': 1}, {'code': AppValidationCode.BAD_VALUE, 'details': 5},
            {'code': AppValidationCode.BAD_VALUE}
        ]}}
    ),
    # TODO: test MANY_ERRORS with lists of validators when only one returns an error
    # GT
    (
        {'a': {'@t': 'str'}},
        {'a': ''},
        {'a': {'code': ValidationCode.NOT_GT, 'details': 0}}
    ),
    # None not allowed
    (
        {'b': {'@t': 'int', '@null': False}},
        {'b': None},
        {'b': {'code': ValidationCode.NULL}}
    ),
    # Nothing
    (
        {'b': 'int'},
        {},
        {'b': {'code': ValidationCode.MISSING}}
    ),
    # Totally bad types
    (
        {'b': 'int'},
        [],
        {'code': ValidationCode.BAD_TYPE}
    ),
    (
        ['int'],
        {'a': 12},
        {'code': ValidationCode.BAD_TYPE}
    ),
    # Garbage
    (
        {'a': {'b': 'int'}},
        {'dadas': {}, 12: '2222', None: '121'},
        ({'a': {'code': ValidationCode.MISSING}})
    ),
    # Enum
    (
        {'a': {'@t': 'int', '@in': FakeEnumE}},
        {'a': 3},
        {'a': {'code': ValidationCode.NOT_IN}}
    )
]

ok_list_tests = [
    (
        ['int'],
        [1, 2, 3]
    ),
    (
        [{'@t': 'int', '@lt': 4}],
        [1, 2, 3]
    ),
    (
        {
            'm': [{
                    'a': {'@t': 'int', '@lt': 4},
                    'b': {'@t': 'int', '@lt': 5},
                    'c': 'str'
                }
            ]
        },
        {'m': [{'a': 1, 'b': 2, 'c': 'x'}, {'a': 1, 'b': 2, 'c': 'y'}]},
    ),
    (
        [['int']],
        [[1, 1, 2]]
    ),
    # Empty lists
    (
        {
            'a': ['int']
        },
        {
            'a': []
        }
    ),
    (
        ['int'],
        []
    ),
    # Optional lists.
    (
        {
            'a': ['int', {'@optional': True}]
        },
        {
        },
    ),
    (
        {
            'a': [{'@t': 'int'}, {'@optional': True}]
        },
        {
        },
    ),
    (
        {
            'a': [{'@t': 'int'}, {'@optional': True}]
        },
        {
            'a': []
        },
    ),
    (
        {
            'a': [{'@t': 'int'}, {'@optional': True}]
        },
        {
            'a': [1, 3]
        },
    )
]

bad_list_tests = [
    (
        ['int'],
        [1, 2, 'x'],
        [None, None, {'code': ValidationCode.BAD_TYPE}]
    ),
    (
        [{'@t': 'int', '@lt': 4}],
        [1, 7, 6],
        [None, {'code': ValidationCode.NOT_LT, 'details': 4}, {'code': ValidationCode.NOT_LT, 'details': 4}]
    ),
    (
        {
            'm': [{
                    'a': {'@t': 'int', '@lt': 4},
                    'b': {'@t': 'int', '@lt': 5},
                    'c': 'str'
                }
            ]
        },
        {'m': [{'a': 1, 'b': 7, 'c': 12}, {'a': -1, 'b': 10, 'c': 'y'}]},
        {'m': [
            {'b': {'code': ValidationCode.NOT_LT, 'details': 5}, 'c': {'code': ValidationCode.BAD_TYPE}},
            {'b': {'code': ValidationCode.NOT_LT, 'details': 5}}
        ]}
    ),
    (
        {'li': [{'@t': 'str'}]},
        {'li': 12},
        # this time the error is not a list but just a dict, it refers to the list as a whole
        {'li': {'code': ValidationCode.BAD_TYPE}}
    ),
    (
        {'li': [{'@t': 'str'}]},
        {},
        # this time the error is not a list but just a dict, it refers to the list as a whole
        {'li': {'code': ValidationCode.MISSING}}
    ),
    # Missing list
    (
        {
            'a': ['int']
        },
        {
        },
        {'a': {'code': ValidationCode.MISSING}}
    ),
    # List length (not implemented)
    # (
    #     {'a': ['int', {'@gt': 2}]},
    #     {'a': [1]},
    #     {'a': {'code': ValidationCode.NOT_GT, 'details': 2}}
    # )
]

ok_cast_str_tests = [
    ('decimal', '121.1222222', decimal.Decimal('121.1222222')),
    ('float', '121.1222222', 121.1222222),
    ('int', '121', 121),
    ('bool', 'true', True),
    ('bool', 'false', False),
]

# No cast from string.
bad_cast_str_tests = [
    ('float', '121.1222222', {'code': ValidationCode.BAD_TYPE}),
    ('int', '121', {'code': ValidationCode.BAD_TYPE}),
    ('bool', 'true', {'code': ValidationCode.BAD_TYPE}),
    ('bool', 'false', {'code': ValidationCode.BAD_TYPE}),
]

ok_strict_types_tests = [
    ('decimal', decimal.Decimal('121.1222222'), decimal.Decimal('121.1222222')),
    ('float', 121.1222222, 121.1222222),
    ('int', 121, 121),
    ('bool', True, True),
    ('bool', False, False),
]

# Strict types on, but failures.
bad_strict_types_tests = [
    ('decimal', 121, {'code': ValidationCode.BAD_TYPE}),
    ('decimal', 121.12, {'code': ValidationCode.BAD_TYPE}),
    ('decimal', '121.12', {'code': ValidationCode.BAD_TYPE}),
    ('float', 121, {'code': ValidationCode.BAD_TYPE}),
    ('bool', 'true', {'code': ValidationCode.BAD_TYPE}),
    ('bool', 'false', {'code': ValidationCode.BAD_TYPE}),
]


class TestSchema:

    def one_test_ok(self, test, **kwargs):
        if len(test) == 2:
            assert validate(test[0], test[1], **kwargs) == test[1]
        else:
            assert validate(test[0], test[1], **kwargs) == test[2]

    def one_test_bad(self, test, **kwargs):
        try:
            result = validate(test[0], test[1], **kwargs)
            assert False
        except ValidationError as e:
            assert e.js == test[2]

    def test_ok(self):
        for i, test in enumerate(ok_tests):
            self.one_test_ok(test)

    def test_ok_lists(self):
        for i, test in enumerate(ok_list_tests):
            self.one_test_ok(test)

    def test_bad(self):
        for i, test in enumerate(bad_tests):
            self.one_test_bad(test)

    def test_bad_lists(self):
        for i, test in enumerate(bad_list_tests):
            self.one_test_bad(test)

    def test_ok_cast_str(self):
        kwargs = dict(cast_from_string=True)
        for i, test in enumerate(ok_cast_str_tests):
            self.one_test_ok(test, **kwargs)

    def test_bad_cast_str(self):
        kwargs = dict(cast_from_string=False)
        for i, test in enumerate(bad_cast_str_tests):
            self.one_test_bad(test, **kwargs)

    def test_ok_strict_types(self):
        kwargs = dict(strict_types=True)
        for i, test in enumerate(ok_strict_types_tests):
            self.one_test_ok(test, **kwargs)

    def test_bad_strict_types(self):
        kwargs = dict(strict_types=True)
        for i, test in enumerate(bad_strict_types_tests):
            self.one_test_bad(test, **kwargs)
