@echo off
title TIRE-MES 4.0 - Multi-PLC Industrial Pipeline Simulator
color 0A

echo ===============================================================================
echo     TIRE-MES 4.0 - MULTI-PLC INDUSTRIAL PIPELINE SIMULATOR
echo     Mo phong input thoi gian thuc tu cac tram PLC (OPC-UA, Modbus, MQTT)
echo ===============================================================================
echo.
echo Chon che do kich ban van hanh:
echo   [1] NORMAL           - Van hanh chuan ISO/SOP (Takt 45s, 170 C, 21 bar)
echo   [2] TAKT_CREEP       - Troi chu ky TBM do mon dao (Kich hoat AI Tab 9)
echo   [3] BOTTLENECK_SURGE - Song tai don u buong dem (Kich hoat AI Tab 10)
echo   [4] DEFECT_SPIKE     - Tut ap bang bong & qua nhiet (Kich hoat AI Tab 11, 12)
echo.

set /p choice="Nhap lua chon [1-4, mac dinh: 1]: "
if "%choice%"=="" set choice=1

set SCENARIO=NORMAL
if "%choice%"=="2" set SCENARIO=TAKT_CREEP
if "%choice%"=="3" set SCENARIO=BOTTLENECK_SURGE
if "%choice%"=="4" set SCENARIO=DEFECT_SPIKE

echo.
echo Dang khoi dong pipeline voi kich ban: %SCENARIO%...
python scripts\run_plc_pipeline.py --scenario %SCENARIO% --interval 2.0

pause
