from setuptools import setup, find_packages

setup(
    name="embird-shared",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "sqlalchemy",
        "pgvector",
        "pydantic"
    ],
)
