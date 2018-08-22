import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()
short_description = long_description.split('.')[0].split('\n')[-1] + '.'

setuptools.setup(
    name="stateful_registers",
    version="0.0.1dev",
    author="Erik Tollerud",
    author_email="erik.tollerud@gmail.com",
    description=short_description,
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/eteq/stateful_registers",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
