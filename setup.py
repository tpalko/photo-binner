from distutils.core import setup

setup(
    name="photobinner",
    version="0.1",
    description="Organize image files by year and date, preserving descriptive text from existing folders",
    author="Tim Palko",
    author_email="tim@palkosoftware.com",
    url="https://github.com/tpalko/photo-binner",
    download_url="http://palkosoftware.ddns.net/scripts/photobinner.tar.gz",
    packages=['photobinner', 'photobinner.sources'],
    scripts=['photobinner/photobinner'],
    # packages=['', 'sources'],
    # package_dir={'': 'bin', 'sources': 'bin/sources'},
    license='MIT'
)
