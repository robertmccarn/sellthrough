"""SellThrough market intelligence pipeline.

The package is intentionally organized as a small layered application rather
than a single script. Importable modules make the behavior easier to test and
let future interfaces reuse the same services without copying command-line code.
"""

__all__ = ["__version__"]

# Keep the version in one importable place for packaging metadata, diagnostics,
# and future `sellthrough --version` support.
__version__ = "0.1.0"
