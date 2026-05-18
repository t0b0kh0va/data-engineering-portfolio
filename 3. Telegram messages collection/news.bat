@echo off
set CHATS=https://t.me/DataInsight,https://t.me/blueteamalerts
set OUTPUT=../news/news

echo Collecting from: %CHATS%
echo Saving to: %OUTPUT%

cd compose

python HR.py --config config.ini --chats %CHATS% --output %OUTPUT%  --timestamps ../news/news_timestamps.json --format csv
echo.
echo Done! Saved to %OUTPUT%
pause