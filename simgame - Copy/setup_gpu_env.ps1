# GPU Environment Setup Script
# This script helps find and set up Python 3.11/3.12 for the GPU simulation

Write-Host "=" * 70
Write-Host "GPU Simulation Environment Setup"
Write-Host "=" * 70
Write-Host ""

# Check for Python 3.11/3.12 in common locations
$pythonPaths = @(
    "C:\Python311\python.exe",
    "C:\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:ProgramFiles\Python311\python.exe",
    "$env:ProgramFiles\Python312\python.exe",
    "$env:ProgramFiles(x86)\Python311\python.exe",
    "$env:ProgramFiles(x86)\Python312\python.exe"
)

$foundPython = $null
$pythonVersion = $null

Write-Host "Searching for Python 3.11 or 3.12..."
foreach ($path in $pythonPaths) {
    if (Test-Path $path) {
        try {
            $version = & $path --version 2>&1
            if ($version -match "Python 3\.(11|12)") {
                $foundPython = $path
                $pythonVersion = $version
                Write-Host "✓ Found: $path"
                Write-Host "  Version: $version"
                break
            }
        } catch {
            # Skip if can't execute
        }
    }
}

if (-not $foundPython) {
    Write-Host ""
    Write-Host "✗ Python 3.11 or 3.12 not found automatically."
    Write-Host ""
    Write-Host "Please provide the full path to your Python 3.11 or 3.12 installation:"
    Write-Host "  (e.g., C:\Python311\python.exe or C:\Users\YourName\AppData\Local\Programs\Python\Python311\python.exe)"
    Write-Host ""
    $manualPath = Read-Host "Enter Python path (or press Enter to download)"
    
    if ($manualPath -and (Test-Path $manualPath)) {
        try {
            $version = & $manualPath --version 2>&1
            if ($version -match "Python 3\.(11|12)") {
                $foundPython = $manualPath
                $pythonVersion = $version
                Write-Host "✓ Using: $foundPython"
            } else {
                Write-Host "✗ That Python version is not 3.11 or 3.12"
                $foundPython = $null
            }
        } catch {
            Write-Host "✗ Could not execute that Python"
            $foundPython = $null
        }
    }
}

if (-not $foundPython) {
    Write-Host ""
    Write-Host "=" * 70
    Write-Host "SETUP INSTRUCTIONS:"
    Write-Host "=" * 70
    Write-Host ""
    Write-Host "1. Download Python 3.11 or 3.12 from:"
    Write-Host "   https://www.python.org/downloads/"
    Write-Host ""
    Write-Host "2. During installation:"
    Write-Host "   ✓ Check 'Add Python to PATH'"
    Write-Host "   ✓ Note the installation path"
    Write-Host ""
    Write-Host "3. Run this script again after installation"
    Write-Host ""
    Write-Host "=" * 70
    exit 1
}

Write-Host ""
Write-Host "=" * 70
Write-Host "Setting up virtual environment..."
Write-Host "=" * 70
Write-Host ""

# Get the directory containing python.exe
$pythonDir = Split-Path $foundPython -Parent
$pythonExe = Split-Path $foundPython -Leaf

# Create venv
Write-Host "Creating virtual environment..."
& $foundPython -m venv .venv

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to create virtual environment"
    exit 1
}

Write-Host "✓ Virtual environment created"
Write-Host ""

# Activate and install dependencies
Write-Host "Installing dependencies..."
$activateScript = ".\venv\Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    $activateScript = ".\venv\Scripts\activate.bat"
}

& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Failed to install dependencies"
    Write-Host "You may need to run: .venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

Write-Host ""
Write-Host "=" * 70
Write-Host "✓ Setup Complete!"
Write-Host "=" * 70
Write-Host ""
Write-Host "To run the GPU simulation:"
Write-Host "  1. Activate the environment:"
Write-Host "     .venv\Scripts\activate"
Write-Host ""
Write-Host "  2. Run the simulation:"
Write-Host "     python main_gpu.py"
Write-Host ""
Write-Host "=" * 70

