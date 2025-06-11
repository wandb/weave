# PowerShell script to run Weave smoke tests on Windows
# This script can be used for local testing on Windows machines

param(
    [switch]$UseContainer,
    [switch]$BuildContainer,
    [switch]$Verbose,
    [string]$PythonVersion = "3.11"
)

Write-Host "=== Weave Windows Smoke Test Runner ===" -ForegroundColor Cyan

# Check if running on Windows
if ($env:OS -ne "Windows_NT") {
    Write-Error "This script must be run on Windows!"
    exit 1
}

# Function to run tests natively
function Run-NativeTests {
    Write-Host "`nRunning tests natively with Python..." -ForegroundColor Green
    
    # Check if Python is installed
    try {
        $pythonVer = python --version 2>&1
        Write-Host "Found $pythonVer" -ForegroundColor Yellow
    } catch {
        Write-Error "Python is not installed or not in PATH!"
        exit 1
    }
    
    # Install dependencies
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    python -m pip install --upgrade pip
    python -m pip install -e ../..
    python -m pip install pytest
    
    # Set environment variables
    $env:WEAVE_SMOKE_TEST = "1"
    $env:PYTHONUNBUFFERED = "1"
    
    # Run tests
    Write-Host "`nRunning smoke tests..." -ForegroundColor Green
    if ($Verbose) {
        python -m pytest test_windows_smoke.py -v -s
    } else {
        python -m pytest test_windows_smoke.py
    }
}

# Function to run tests in container
function Run-ContainerTests {
    Write-Host "`nRunning tests in Windows container..." -ForegroundColor Green
    
    # Check if Docker is installed
    try {
        docker --version | Out-Null
    } catch {
        Write-Error "Docker is not installed or not running!"
        exit 1
    }
    
    # Change to repository root
    Push-Location ../..
    
    try {
        # Build container if requested
        if ($BuildContainer) {
            Write-Host "Building Windows container..." -ForegroundColor Yellow
            docker build -f Dockerfile.windows -t weave-windows-test:latest .
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Failed to build container!"
                exit 1
            }
        }
        
        # Run tests in container
        Write-Host "Running tests in container..." -ForegroundColor Yellow
        docker run --rm `
            -e WEAVE_SMOKE_TEST=1 `
            -e PYTHONUNBUFFERED=1 `
            weave-windows-test:latest
            
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Tests failed in container!"
            exit 1
        }
    } finally {
        Pop-Location
    }
}

# Main execution
try {
    if ($UseContainer) {
        Run-ContainerTests
    } else {
        Run-NativeTests
    }
    
    Write-Host "`n✓ All tests passed!" -ForegroundColor Green
} catch {
    Write-Host "`n✗ Tests failed!" -ForegroundColor Red
    Write-Error $_
    exit 1
} 