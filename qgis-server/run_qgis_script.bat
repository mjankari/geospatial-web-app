@echo off 

:: 1. SET THE CORRECT ROOT PATH
set OSGEO4W_ROOT=C:\Program Files\QGIS 3.40.10

:: 2. CALL THE ENVIRONMENT BOOTSTRAPPER
call "%OSGEO4W_ROOT%\bin\o4w_env.bat" 

:: 3. SET QGIS PATHS
:: We MUST add the /plugins folder to find 'processing'
set QGIS_PREFIX_PATH=%OSGEO4W_ROOT%\apps\qgis-ltr
set PATH=%OSGEO4W_ROOT%\bin;%OSGEO4W_ROOT%\apps\qgis-ltr\bin;%PATH%

:: CRITICAL LINE: Add both the python and the plugins folder
set PYTHONPATH=%OSGEO4W_ROOT%\apps\qgis-ltr\python;%OSGEO4W_ROOT%\apps\qgis-ltr\python\plugins;%PYTHONPATH%

:: --- AWS CREDENTIALS ---
set AWS_ACCESS_KEY_ID=###
set AWS_SECRET_ACCESS_KEY=###
set AWS_DEFAULT_REGION=###
set MY_S3_BUCKET_NAME=###

:: 4. RUN YOUR SCRIPT
"%OSGEO4W_ROOT%\bin\python.exe" qgis-ml-server-flask.py

pause