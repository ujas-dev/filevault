from setuptools import setup, find_packages

setup(
    name="filevault",
    version="4.0.0",
    author="Ujas J. Dubal",
    author_email="ujasdevelopment@gmail.com",
    description="Intelligent file organizer, deduplicator & secure shredder with GUI",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/YOUR_USERNAME/filevault",
    py_modules=["filevault", "filevault_gui"],
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[],                # zero hard deps — all optional
    extras_require={
        "full": [
            "blake3", "pymupdf", "pypdf", "pikepdf",
            "python-docx", "openpyxl", "python-pptx",
            "Pillow", "imagehash", "piexif",
            "watchdog", "PyYAML", "customtkinter",
        ],
        "gui": ["customtkinter"],
        "pdf": ["pymupdf", "pypdf", "pikepdf"],
        "office": ["python-docx", "openpyxl", "python-pptx"],
        "image": ["Pillow", "imagehash", "piexif"],
        "watch": ["watchdog"],
    },
    entry_points={
        "console_scripts": [
            "filevault=filevault:cli",
            "filevault-gui=filevault_gui:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.14",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Utilities",
        "Topic :: Desktop Environment :: File Managers",
        "Environment :: Console",
        "Environment :: X11 Applications",
    ],
    keywords="file organizer deduplicator secure shred rename exif pdf ebook gui cli",
    project_urls={
        "Bug Tracker":  "https://github.com/YOUR_USERNAME/filevault/issues",
        "Changelog":    "https://github.com/YOUR_USERNAME/filevault/releases",
        "Discussions":  "https://github.com/YOUR_USERNAME/filevault/discussions",
    },
)
