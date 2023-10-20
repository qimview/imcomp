# imcomp.py

GUI that allows to compare series of images
It can be configured to display specific results of an program/algorithm

## Installation on Windows with >= Python 3.9:

Python: 3.9
https://www.python.org/downloads/release/python-390/
https://www.python.org/ftp/python/3.9.0/python-3.9.0-amd64.exe

Set python3.9 in console (adapt to your user path)
set PATH=C:\Users\USERNAME\AppData\Local\Programs\Python\Python39\;C:\Users\kkrissian\AppData\Local\Programs\Python\Python39\Scripts;%PATH%

## Installation issue:

PyYAML version 5.4 required by CppBind can create installation errors, I was enable to get around this issue by running:
pip install PyYAML==5.3.1
pip install -e . --no-deps PyYAML # -e option is for development, it points to the github clone
