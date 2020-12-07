import setuptools

setuptools.setup(
    name="iptv-plex-tuner",
    description="Application designed to allow you to watch IPTV channels in Plex.",
    packages=setuptools.find_packages(),
    python_requires='>=3.6',
    install_requires=[
        "Flask-RESTful==0.3.8",
        "lxml==4.6.2",
        "python-xmltv==1.4.3",
        "requests==2.24.0"
    ],
    extras_require={
        "dev": [
            "autopep8==1.5.3",
            "flake8==3.8.1",
            "PyInstaller==4.1"
        ]
    }
)
