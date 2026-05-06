from setuptools import setup, find_packages

setup(
    name="credit-memo",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=1.4.0",
    ],
    extras_require={
        "docx": ["python-docx>=0.8.11"],
    },
)
