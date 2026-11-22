@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  ERA5 download + processing + model run (Windows, one click)
REM  Usage: double-click, or from a terminal:
REM      scripts\era5_windows.bat            (1950-2025, full run)
REM      scripts\era5_windows.bat 2009 2009  (quick test, one year)
REM ============================================================
cd /d "%~dp0\.."

set START=%1
set END=%2
if "%START%"=="" set START=1950
if "%END%"=="" set END=2025

where python >nul 2>nul
if errorlevel 1 (
  echo [HATA] Python bulunamadi. https://www.python.org/downloads/ adresinden kurun
  echo        ve kurulumda "Add python.exe to PATH" kutusunu isaretleyin.
  pause
  exit /b 1
)

echo [1/4] Paketler kuruluyor...
python -m pip install --quiet --upgrade cdsapi xarray netCDF4 dask numpy pandas matplotlib
if errorlevel 1 (
  echo [HATA] Paket kurulumu basarisiz.
  pause
  exit /b 1
)

if not exist "%USERPROFILE%\.cdsapirc" if exist "..\cds_key.txt" (
  set /p CDSKEY=<"..\cds_key.txt"
  >"%USERPROFILE%\.cdsapirc" echo url: https://cds.climate.copernicus.eu/api
  >>"%USERPROFILE%\.cdsapirc" echo key: !CDSKEY!
  echo [2/4] CDS anahtari ..\cds_key.txt dosyasindan okundu ve kaydedildi.
)
if not exist "%USERPROFILE%\.cdsapirc" (
  echo.
  echo [2/4] Copernicus CDS anahtari gerekli.
  echo       cds.climate.copernicus.eu - profil sayfasindaki "Personal Access Token"
  set /p CDSKEY=Token'i buraya yapistirin ve Enter'a basin:
  >"%USERPROFILE%\.cdsapirc" echo url: https://cds.climate.copernicus.eu/api
  >>"%USERPROFILE%\.cdsapirc" echo key: !CDSKEY!
  echo       Anahtar %USERPROFILE%\.cdsapirc dosyasina kaydedildi.
) else (
  echo [2/4] CDS anahtari bulundu.
)

echo.
echo [3/4] ERA5 indiriliyor: %START%-%END%  (her yil ayri istek, kuyruga gore saatler surebilir)
echo       Yarida kesilirse tekrar calistirin: inen yillar atlanir.
python scripts\download_era5.py --start %START% --end %END%
if errorlevel 1 (
  echo [HATA] Indirme basarisiz. ERA5 lisansini kabul ettiniz mi?
  echo        ERA5 hourly data on single levels sayfasi - Download sekmesi - Terms of use
  pause
  exit /b 1
)

echo.
echo [4/4] Yillik maksimumlar hesaplaniyor ve model calistiriliyor...
python scripts\process_era5.py
python run_model.py

echo.
echo Bitti. Sonuclar: outputs\  (grafiklerde artik "DEMO DATA" yazmamali)
pause
