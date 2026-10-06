@echo off
chcp 65001 >nul
echo ========================================================
echo  Đang đẩy code MiniMES lên GitHub...
echo  Repo: https://github.com/duchoa56819/MiniMES2
echo ========================================================
echo.

git push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo  [THÀNH CÔNG] Đã đẩy toàn bộ source code lên GitHub!
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo  [THẤT BẠI] Không thể đẩy code. Vui lòng kiểm tra kết nối mạng hoặc quyền truy cập GitHub.
    echo ========================================================
)

pause
