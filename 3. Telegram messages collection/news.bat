@echo off
set CHATS=https://t.me/DataInsight,https://t.me/blueteamalerts,https://t.me/hack_less
set OUTPUT=../YOUT_PATH/OUTPUT_FILE.json

echo Collecting from: %CHATS%
echo Saving to: %OUTPUT%

cd compose

python HR.py --config config.ini --chats %CHATS% --output %OUTPUT%  --timestamps ../YOUT_PATH/OUTPUT_TIMESTAMPS.json
echo.
echo Done! Saved to %OUTPUT%
pause