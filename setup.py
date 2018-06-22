import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name = "okschema",
    version = "0.1.1",
    author = "Krzysztof Stachlewski",
    author_email = "stach@stachlewski.info",
    description = "Validate JSON data using a schema written in Python",
    license = "BSD",
    url = "https://github.com/okcode-eu/okschema",
    packages=['okschema'],
    install_requires=[
        'pendulum',
    ],
    long_description=read('README.md'),
)
