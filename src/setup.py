from setuptools import setup

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name='wmts_extractor',
    packages=['wmts_extractor'],
    python_requires='>=3.8, <4',
    install_requires=required,
    entry_points={
        'console_scripts': ['wmts-extractor=wmts_extractor.run:cli'],
    }
)
