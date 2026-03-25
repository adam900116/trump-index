@echo off
cd /d C:\Users\吴方杰\.qclaw\workspace\trump-index
python tvi_engine.py
git add index.html tvi_data.json
git commit -m "update: TVI %date% %time%"
git push origin main
echo [TVI] Updated at %date% %time% >> tvi_update.log
