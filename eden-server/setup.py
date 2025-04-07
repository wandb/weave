from setuptools import setup, find_packages

setup(
    name="eden-server",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "pydantic>=2.4.2",
        "python-dotenv>=1.0.0",
        "websockets>=12.0",
        "aiofiles>=24.1.0",
        "typer>=0.9.0",
        "rich>=13.7.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "black>=25.1.0",
            "isort>=5.12.0",
            "mypy>=1.6.1",
        ],
    },
    entry_points={
        "console_scripts": [
            "eden=eden.cli:app",
        ],
    },
    python_requires=">=3.9",
) 