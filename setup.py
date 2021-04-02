# -*- coding: utf-8 -*-
import os
from setuptools import setup, find_packages

long_desc = '''
sphinx_probs_rdf is a sphinx extension which outputs RDF describing Processes and Objects using the PRObs ontology.
'''

def get_version():
    """Get version number of the package from version.py without importing core module."""
    package_dir = os.path.abspath(os.path.dirname(__file__))
    version_file = os.path.join(package_dir, 'src/sphinx_probs_rdf/version.py')

    namespace = {}
    with open(version_file, 'rt') as f:
        exec(f.read(), namespace)

    return namespace['__version__']


setup(
    version=get_version(),
    url='https://github.com/ricklupton/sphinx_probs_rdf',
    download_url='https://pypi.org/project/sphinx_probs_rdf/',
    license='BSD',
    author='Rick Lupton',
    author_email='mail@ricklupton.name',
    description=long_desc.strip().replace('\n', ' '),
    long_description=long_desc,
    zip_safe=False, # XXX what does this mean?
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Framework :: Sphinx',
        'Framework :: Sphinx :: Extension',
        'Topic :: Documentation',
        'Topic :: Documentation :: Sphinx',
        'Topic :: Text Processing',
        'Topic :: Utilities',
    ],
    platforms='any',
    python_requires=">=3.7",
    include_package_data=True,
)
