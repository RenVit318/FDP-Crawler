"""Africa Health Data Space — dataspace configuration."""

SITE_NAME = 'Africa Health Data Space'
SITE_TAGLINE = 'Discover and request access to African health datasets'

DEFAULT_FDPS = [
    'https://fdp.tangaza.ac.ke',
]

# Only these catalogs are shown in this dataspace; any other catalog discovered
# on the registered FDPs is filtered out.
INCLUDE_ONLY_CATALOG_URIS = [
    # COMPASS AfyaKE / Dagoretti
    'https://fdp.tangaza.ac.ke/catalog/218d8f70-f3d9-4860-a07c-b7f56a5c3684',
    # COMPASS TaifaKE (Pumwani, Mathare)
    'https://fdp.tangaza.ac.ke/catalog/67276eac-f216-4055-ab4a-de3eccddbb7b',
]

BRAND_LOGOS = [
    {'file': 'vodan.png', 'alt': 'VODAN Africa Logo'},
]

# TODO: replace with the real contact address.
CONTACT_EMAIL = 'contact@example.org'
