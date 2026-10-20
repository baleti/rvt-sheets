#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
bash tools/pdf_text_regress.sh update > ~/pdf_update.log 2>&1; echo DONE >> ~/pdf_update.log
