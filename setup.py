import os
from setuptools import find_packages, setup


# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name="now-payments",
    version="0.9.3",
    packages=find_packages(),
    include_package_data=True,
    license="MIT License",  # example license
    description="Payments hosted on now.sh",
    url="https://www.example.com/",
    author="Biola Oyeniyi",
    # dependency_links=[
        # "http://github.com/SergeySatskiy/cdm-pythonparser/archive/v2.0.1.tar.gz"
    # ],
    classifiers=[
        # Replace these appropriately if you are stuck on Python 2.
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 2",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
)
