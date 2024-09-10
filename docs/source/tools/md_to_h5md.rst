``md_to_h5md``
==============

Tool for converting castep .md files to h5md format [1]_.

Installation
------------

To install `md_to_h5md` and depedencies, use:

.. code-block::

   pip install "castep_outputs_tools[md_to_h5md]"

This adds a script which can be run from the command line:

.. code-block::

   > md_to_h5md.py -h

   usage: md_to_h5md [-h] -o OUTPUT [-a AUTHOR] [-e EMAIL] [-V] source

   Convert a castep .md file to .h5md format.

   positional arguments:
     source                .md file to parse

   options:
     -h, --help            show this help message and exit
     -o OUTPUT, --output OUTPUT
                           File to write output.
     -a AUTHOR, --author AUTHOR
                           Author for metadata.
     -e EMAIL, --email EMAIL
                           Email for metadata.
     -V, --version         show program's version number and exit

   See https://www.nongnu.org/h5md/ for more info on h5md.


Limitations
-----------

h5md cannot handle variable atom count calculations, and so
attempting to convert a ̆μVT calculation may fail.

Dependencies
------------

`h5py <https://www.h5py.org/>`__


.. [1] https://www.nongnu.org/h5md/
