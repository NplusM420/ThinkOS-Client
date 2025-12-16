"""PyInstaller hook for sqlite_vec package.

sqlite_vec loads a native DLL (vec0.dll on Windows, vec0.so on Linux, vec0.dylib on macOS)
that needs to be bundled with the application.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Collect the native extension DLL
datas = collect_data_files('sqlite_vec')
binaries = collect_dynamic_libs('sqlite_vec')
