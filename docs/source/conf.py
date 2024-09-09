# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "castep_outputs_tools"
copyright = "2024, Jacob Wilkins"
author = "Jacob Wilkins"

# The full version, including alpha/beta/rc tags
release = "0.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.mathjax",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    # "numpydoc",
    # "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = []

autosectionlabel_prefix_document = True

autosummary_generate = True

napoleon_use_ivar = True
napoleon_use_param = False
napoleon_use_admonition_for_notes = True

numpydoc_validation_checks = {"all", "ES01", "EX01", "SA01"}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_book_theme"
html_theme_options = {}
html_static_path = ["_static"]
