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

PyYAML version 5.4 required by CppBind can create installation errors, I was able to get around this issue by running:

pip3 install wheel -v
pip3 install "cython<3.0.0" pyyaml==5.4 --no-build-isolation -v