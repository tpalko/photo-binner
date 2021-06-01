import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="photobinner",
    version="0.1",
    author="Tim Palko",
    author_email="tim@palkosoftware.com",
    description="Organize image files by year and date, preserving descriptive text from existing folders",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tpalko/photo-binner",
    packages=setuptools.find_packages(), #['photobinner', 'photobinner.sources'],
    py_modules=['photobinner/source'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU GPLv3 License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    scripts=['photobinner/photobinner'],
 #   entry_points=dict(console_scripts=['photobinner=photobinner:main']),
#    install_requires=['adb==1.3.0','exifread','click','pytz','ConfigParser'],
    # packages=['', 'sources'],
    # package_dir={'': 'bin', 'sources': 'bin/sources'},
 #   license='GNU GPLv3'
)
