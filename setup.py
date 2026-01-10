from setuptools import setup
import os

readme_path = "scripts/MCJAR_README.md"
if not os.path.exists(readme_path):
    readme_path = "MCJAR_README.md"

long_description = ""
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="mcjar",
    version="0.0.2",
    py_modules=["mcjar"],
    package_dir={"": "scripts"},
    packages=[],
    include_package_data=True, # Changed to True
    long_description=long_description,
    long_description_content_type="text/markdown",
    # This ensures the file is included in the source distribution
    data_files=[("", [readme_path])],
    entry_points={
        "console_scripts": [
            "mcjar=mcjar:main",
        ],
    },
)
