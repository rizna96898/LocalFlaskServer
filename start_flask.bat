@echo off

"C:\Users\nezar\AppData\Local\Microsoft\WindowsApps\wt.exe" ^
--pos "-1080,10" ^
--size 110,50 ^
new-tab ^
-d E:\LocalFlaskServer ^
cmd.exe /k "title FlaskServer && E:\python\python.exe src\app.py"