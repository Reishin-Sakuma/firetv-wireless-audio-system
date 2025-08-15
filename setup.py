"""
AudioBridge-Pi セットアップスクリプト
"""

from setuptools import setup, find_packages
from pathlib import Path

# README読み込み
README = Path("README.md")
long_description = README.read_text() if README.exists() else ""

setup(
    name="audio-bridge-pi",
    version="1.0.0",
    description="Bluetooth A2DP to WiFi HTTP Audio Streaming Bridge for Raspberry Pi",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Audio Bridge Project",
    author_email="audiobridge@example.com",
    url="https://github.com/your-username/audio-bridge-pi",
    
    packages=find_packages(),
    python_requires=">=3.7",
    
    install_requires=[
        "flask>=2.0.0",
        "pulsectl>=22.0.0",
        "dbus-python>=1.2.0",
        "PyGObject>=3.40.0",
        "psutil>=5.8.0",
        "netifaces>=0.11.0",
        "pyyaml>=5.4.0"
    ],
    
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-mock>=3.6.0",
            "pytest-cov>=3.0.0"
        ]
    },
    
    entry_points={
        "console_scripts": [
            "audio-bridge=audio_bridge.main:main",
        ]
    },
    
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: System :: Networking",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: POSIX :: Linux",
    ],
    
    keywords="bluetooth a2dp wifi streaming raspberry-pi audio fire-tv",
    
    include_package_data=True,
    package_data={
        "audio_bridge": ["config/**/*"],
    },
)