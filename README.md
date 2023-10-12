# imcomp.py

GUI that allows to compare series of images
It can be configured to display specific results of an program/algorithm

## Installation on Windows with >= Python 3.9:

Python: 3.9
https://www.python.org/downloads/release/python-390/
https://www.python.org/ftp/python/3.9.0/python-3.9.0-amd64.exe

Set python3.9 in console (adapt to your user path)
set PATH=C:\Users\USERNAME\AppData\Local\Programs\Python\Python39\;C:\Users\kkrissian\AppData\Local\Programs\Python\Python39\Scripts;%PATH%

## Installation
check requirements.txt

## cppimport
When displaying images with Qt, C++ code is used to speed-up the processing.
The code is compiled and bound to Python using pybind11 and the module cppimport.
However, the first time you use it, it may not be able to compile the code automatically (I don't know why).
In this case, you can run manually:

  python -m cppimport build ./qimview/CppBind

from the qimview folder. Even of the command ends up with the error 'No module named wrap_numpy', it has probably built the library correctly.
