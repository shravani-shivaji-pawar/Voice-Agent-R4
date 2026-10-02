import os
import sys
import py_compile
import glob

def check_python_files(root_dir):
    errors = []
    for filepath in glob.glob(os.path.join(root_dir, "**", "*.py"), recursive=True):
        if "venv" in filepath or ".venv" in filepath or "__pycache__" in filepath:
            continue
        try:
            py_compile.compile(filepath, doraise=True)
        except py_compile.PyCompileError as e:
            errors.append((filepath, str(e)))
    return errors

if __name__ == "__main__":
    backend_dir = os.path.abspath("Backend")
    print(f"Checking Python files in {backend_dir}...")
    errs = check_python_files(backend_dir)
    print(f"Found {len(errs)} compilation errors.")
    for path, err in errs:
        print(f"Error in {path}:\n{err}\n")
