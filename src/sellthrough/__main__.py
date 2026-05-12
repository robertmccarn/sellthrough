"""Support `python -m sellthrough`.

Python executes a package's `__main__.py` when the package is run with `-m`.
Keeping this file as a tiny delegation layer means module execution and the
installed console script both reach the same `sellthrough.cli.main()` function.
"""

from sellthrough.cli import main


if __name__ == "__main__":
    # Raising `SystemExit` is the standard way for a Python CLI to turn a return
    # code from `main()` into the process exit status observed by the shell.
    raise SystemExit(main())
