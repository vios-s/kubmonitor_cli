from setuptools import setup, find_packages
from version import __version__

setup(
    name="kubmonitor-cli",
    version=__version__,
    description="A rich CLI Kubernetes monitor",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="yyx",
    url="https://github.com/yyx/kubmonitor-cli",
    packages=find_packages(),
    py_modules=["monitor"],
    install_requires=[
        "rich",
        "psutil"
    ],
    entry_points={
        "console_scripts": [
            "kubmonitor=monitor:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
