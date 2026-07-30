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

# FDPs that stay connected in every visitor's session, re-added on each request
# (see app/__init__.py::init_session) so sessions created before an FDP was
# pinned pick it up too. The sandbox demo FDP hosts the datasets the preset
# query below runs against, so the instance is never an empty shell.
PINNED_FDPS = [
    'https://fdp.renskievit.com',
]

# Listed as a default so the cache prefetches it at startup and keeps it warm
# in the background refresh, exactly like the inherited FDPs.
DEFAULT_FDPS = list(_base.DEFAULT_FDPS) + PINNED_FDPS

# Pre-filled in the SPARQL editor whenever the query box would otherwise be
# empty, so a visitor can hit Execute without writing SPARQL first. Only the
# sandbox defines this; the public instances keep their empty editor.
with open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 'queries', 'grp_a17_where_active.sparql'),
    encoding='utf-8',
) as _query_file:
    DEFAULT_SPARQL_QUERY = _query_file.read()
