# GPU Version Setup Guide

## Python Version Requirement

The GPU-accelerated version requires **Python 3.11 or 3.12** (Python 3.14 is not yet supported by `arcade` and `taichi`).

## Quick Setup

### Step 1: Install Python 3.11 or 3.12

1. Download from: https://www.python.org/downloads/
2. **Important**: During installation, check **"Add Python to PATH"**
3. Verify installation:
   ```powershell
   py -3.11 --version
   # or
   py -3.12 --version
   ```

### Step 2: Create Virtual Environment

```powershell
# Navigate to project directory
cd "C:\projects\simgame - Copy"

# Create venv with Python 3.11
py -3.11 -m venv .venv

# Activate it
.venv\Scripts\activate
```

### Step 3: Install Dependencies

```powershell
# Upgrade pip
python -m pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt
```

### Step 4: Run GPU Version

```powershell
python main_gpu.py
```

## Troubleshooting

### "No module named 'arcade'"
- Make sure you activated the virtual environment: `.venv\Scripts\activate`
- Verify Python version: `python --version` (should be 3.11.x or 3.12.x)
- Reinstall: `pip install -r requirements.txt`

### "Python 3.14+ is not yet supported"
- You need Python 3.11 or 3.12 (see Step 1 above)
- The `py` launcher can help: `py -3.11 -m venv .venv`

### Using Multiple Python Versions
- Python 3.14 can stay for other projects
- Use the `.venv` only for the GPU simulation
- The legacy Pygame version (`main.py`) works with any Python 3.x

## Running Both Versions

- **Legacy (Pygame)**: `python main.py` (works with Python 3.14)
- **GPU (Arcade)**: `python main_gpu.py` (requires Python 3.11/3.12 in `.venv`)

