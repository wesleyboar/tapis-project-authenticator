"""
Configuration data e.g. for tenant-specific UI customizations.
"""

TENANT_UI = {
  "default": {
    "branding": [{
        "src": "authorize/tapis.jpg",
        "alt": "Tapis"
    }],
    "login": {
        "register_url": "https://accounts.tacc.utexas.edu/register",
        "help_links": [{
            "url": "https://tacc.utexas.edu/about/help/",
            "text": "Account Help"
        }]
    }
  },
  "jupyter-tacc-dev": {
    "branding": [{
        "src": "authorize/icicle-logo.png",
        "alt": "Icicle"
    }],
    "login": {
        "register_url": "https://accounts.tacc.utexas.edu/register",
        "help_links": [{
            "url": "https://tacc.utexas.edu/about/help/",
            "text": "Account Help"
        }]
    }
  },
  "designsafe": {
    "branding": [{
        "src": "authorize/designsafe.svg",
        "alt": "DesignSafe"
    }, {
        "src": "authorize/tacc.jpg",
        "alt": "TACC"
    }],
    "login": {
        "register_url": "https://accounts.tacc.utexas.edu/register",
        "help_links": [{
            "url": "https://tacc.utexas.edu/about/help/",
            "text": "Account Help"
        }]
    }
  },
  "icicle": {
    "branding": [{
        "src": "authorize/icicle-logo.png",
        "alt": "Icicle"
    }],
    "login": {
        "register_url": "https://accounts.tacc.utexas.edu/register",
        "help_links": [{
            "url": "https://tacc.utexas.edu/about/help/",
            "text": "Account Help"
        }]
    }
  },
  "dev": {
    "branding": [{
        "src": "authorize/dev.jpeg",
        "alt": "Dev"
    }],
    "login": {
        "register_url": "https://accounts.tacc.utexas.edu/register",
        "help_links": [{
            "url": "https://tacc.utexas.edu/about/help/",
            "text": "Account Help"
        }]
    }
  },
  "apcd": {
    "branding": [{
        "src": "authorize/tapis.jpg",
        "alt": "Tapis"
    }],
    "login": {
        "register_url": "https://accounts.tacc.utexas.edu/apcd/register",
        "help_links": [{
            "url": "mailto:support@tickets.txapcd.org",
            "text": "For help, email support@tickets.txapcd.org"
        }]
    }
  },
  "tacc": {
    "branding": [{
        "src": "authorize/tacc-formal.svg",
        "alt": "TACC"
    }],
    "login": {
        "register_url": "https://accounts.tacc.utexas.edu/register",
        "help_links": [{
            "url": "https://tacc.utexas.edu/about/help/",
            "text": "Account Help"
        }]
    }
  }
}
