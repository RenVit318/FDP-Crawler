"""Humanitarian Data Space — sandbox instance.

Same FDPs and branding as the `humanitarian` dataspace, deployed separately (e.g.
at sandbox.humanitariandataspace.com) with AUTO_LOGIN_USERNAME=sandbox_query so
every visitor is signed in as the sandbox user. That is what makes the sandbox
datasets and their preset queries visible — see the gate in
app/routes/datasets.py and app/routes/sparql.py.

Values are re-exported from the humanitarian dataspace by path rather than by
import, because dataspace configs are loaded as standalone files (see
app/__init__.py::_load_dataspace) and are not importable as a package.
"""

import importlib.util
import os

_BASE_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'humanitarian',
    'config.py',
)

_spec = importlib.util.spec_from_file_location('dataspace_humanitarian_base', _BASE_CONFIG)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

# Re-export every setting from the humanitarian dataspace (DEFAULT_FDPS,
# BRAND_LOGOS, CONTACT_EMAIL, ...), then override what differs below.
globals().update({k: getattr(_base, k) for k in dir(_base) if k.isupper()})

SITE_NAME = 'Humanitarian Data Space (Sandbox)'
SITE_TAGLINE = 'Sandbox instance — synthetic data for demonstration purposes'

# Rendered as a strip above the header on every page, so the sandbox instance is
# never mistaken for the public one.
SITE_BANNER = 'Sandbox environment — synthetic data'
