"""
Setup configuration for interactivePCA package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="interactive-pca",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Interactive PCA visualization with Dash",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/interactive-pca",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pandas>=1.3.0",
        "numpy>=1.20.0",
        "plotly>=5.0.0",
        "dash>=2.0.0",
        "dash-bootstrap-components>=1.0.0",
        "dash-ag-grid>=2.0.0",
        "dash-daq>=0.5.0",
        "dash-mantine-components>=0.12.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.12.0",
            "black>=21.0",
            "flake8>=3.9.0",
            "isort>=5.9.0",
        ],
    },
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "interactive-pca=interactive_pca.cli:main",
        ],
    },
)
