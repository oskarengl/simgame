# Download Python 3.11 Windows Installer

## Direct Download Links

**Python 3.11.14 Windows 64-bit Installer:**
- https://www.python.org/ftp/python/3.11.14/python-3.11.14-amd64.exe

**Python 3.11.14 Windows 32-bit Installer:**
- https://www.python.org/ftp/python/3.11.14/python-3.11.14.exe

## Installation Steps

1. **Download** one of the installers above (use 64-bit if unsure)

2. **Run the installer** and:
   - ✅ **Check "Add Python to PATH"** (very important!)
   - ✅ Choose "Install Now" or customize location
   - ✅ Note the installation path (usually `C:\Users\YourName\AppData\Local\Programs\Python\Python311\`)

3. **Verify installation:**
   ```powershell
   py -3.11 --version
   ```
   Should show: `Python 3.11.14`

4. **Run setup script:**
   ```powershell
   .\setup_gpu_env.bat
   ```
   When prompted, enter the path to python.exe (usually `C:\Users\YourName\AppData\Local\Programs\Python\Python311\python.exe`)

## Alternative: Use Python Launcher

If you install with "Add to PATH" checked, you can also use:
```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main_gpu.py
```

