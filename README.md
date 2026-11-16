# MCD_Randomizer5e2024_web
Random character creation for D&amp;D 5e 2024

# For users
The software can be run from either the github address, or locally if the index.html file is downloaded.
It is recommended to save a copy of the character log file so that it can be reloaded/modified at a later date if required.

# Developer Workflow : notes on how to change CSV input files and update the index.html
As of V1.1, all character option data is stored in CSV files that can be updated.

Edit the CSVs in the data folder, then run python build.py. It rebuilds index.html, and template.html holds the app code.
Weights/probabilities of each character options are relative, so you can add rows without rebalancing to 100. You can also add extra columns.
Save CSVs as “CSV UTF-8” so the accents survive.
For GitHub, upload index.html for the live app, and also template.html, build.py and the data folder so everything is versioned together.
