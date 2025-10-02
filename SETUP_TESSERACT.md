# Tesseract OCR Setup for headline-reactor

## Windows Installation

1. **Download Tesseract**
   - Go to: https://github.com/UB-Mannheim/tesseract/wiki
   - Download the latest Windows installer (tesseract-ocr-w64-setup-vX.X.X.XXXXX.exe)

2. **Install Tesseract**
   - Run the installer
   - **Important**: During installation, note the installation path (default: `C:\Program Files\Tesseract-OCR`)

3. **Add to PATH**
   - Open System Properties → Advanced → Environment Variables
   - Under System Variables, find `Path` and click Edit
   - Click New and add: `C:\Program Files\Tesseract-OCR`
   - Click OK on all dialogs

4. **Verify Installation**
   ```powershell
   tesseract --version
   ```
   You should see version information if installed correctly.

## Testing headline-reactor

Once Tesseract is installed, you can test the full OCR pipeline:

```powershell
# Test single headline
python test_capture_simple.py

# Start watch mode (requires Bloomberg Alert Catcher window to be visible)
python -m headline_reactor.cli watch --llm
```

## Troubleshooting

If you get `TesseractNotFoundError`:
- Verify Tesseract is in your PATH
- Try restarting your terminal/PowerShell
- Manually specify Tesseract location in `ocr.py`:
  ```python
  pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
  ```

