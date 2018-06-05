from okschema import NotValidError, NotValidButContinueError, ValidationCode, \
    ValidationError, validate, val_date, val_datetime, NotHere, fmt_uuid
import decimal
import datetime as dt
import unittest


def val_err(x):
    raise NotValidError(ValidationCode.BAD_VALUE)


def dict_lteq_12(d):
    suma = d['a'] + d['b']
    if not suma <= 12:
        raise NotValidError(ValidationCode.OUT_OF_BOUNDS)
    d['sum'] = suma
    return d


def bad_val1_cont(x):
    raise NotValidButContinueError(ValidationCode.BAD_VALUE, 1)


def bad_val2_cont(x):
    raise NotValidButContinueError(ValidationCode.BAD_VALUE, 5)


ok_tests = [
    ('int', 12),
    ('string', 'aaa'),
    ('float', '121.12', 121.12),
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
    # (
    #     {
    #         'a': ['int', {'@required': False}]
    #     },
    #     {
    #     },
    # ),
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
        {'a': dt.datetime(2018, 3, 28, 10, 29, 32, 358000)}
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
    )
]

bad_tests = [
    (
        {'@t': 'string', '@val': val_err}, 'abc', {'code': ValidationCode.BAD_VALUE}
    ),
    (
        {'a': {'@t': 'string', '@val': val_err}}, {'a': 'abc'}, {'a': {'code': ValidationCode.BAD_VALUE}}
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
            'a': {'code': ValidationCode.BAD_VALUE},
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
            {'code': ValidationCode.BAD_VALUE, 'details': 1}, {'code': ValidationCode.BAD_VALUE, 'details': 5}
        ]}}}
    ),
    # Validators with continuation and normal
    (
        {'b':  {'@t': 'int', '@val': [bad_val1_cont, bad_val2_cont, val_err]}},
        {'b': 12},
        {'b': {'code': ValidationCode.MANY_ERRORS, 'details': [
            {'code': ValidationCode.BAD_VALUE, 'details': 1}, {'code': ValidationCode.BAD_VALUE, 'details': 5},
            {'code': ValidationCode.BAD_VALUE}
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

class TestSchema(unittest.TestCase):

    def test_ok(self):
        try:
            for i, test in enumerate(ok_tests):
                if len(test) == 2:
                    self.assertEqual(validate(test[0], test[1]), test[1])
                else:
                    self.assertEqual(validate(test[0], test[1]), test[2])
        except Exception as e:
            print("Failed test_ok @%d iteration: %s" % (i, test))
            raise

    def test_bad(self):
        try:
            for i, test in enumerate(bad_tests):
                try:
                    result = validate(test[0], test[1])
                    self.fail("should raise")
                except ValidationError as e:
                    #print(e.js)
                    self.assertEqual(e.js, test[2])
        except Exception as e:
            print("Failed test_bad @%d iteration: %s" % (i, test))
            raise


    def test_bad_lists(self):
        try:
            for i, test in enumerate(bad_list_tests):
                try:
                    result = validate(test[0], test[1])
                    self.fail("should raise")
                except ValidationError as e:
                    #print(e.js)
                    self.assertEqual(e.js, test[2])
        except Exception as e:
            print("Failed test_bad_lists @%d iteration: %s" % (i, test))
            raise

unittest.main()
