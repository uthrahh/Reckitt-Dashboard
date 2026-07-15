import kagglehub
import pandas as pd
from pathlib import Path 
''' 
imports the Path class from Python's built-in pathlib module, 
which provides an object-oriented, cross-platform way to interact with file system paths.
Instead of treating paths as raw strings
'''

def load_reckitt_data():

    path = Path(
        kagglehub.dataset_download(
            "agnimchakraborty/reckitt"
        )
    )

    excel_files = list(path.glob("*.xlsx"))

    if not excel_files:
        raise FileNotFoundError("No Excel file found in dataset.")

    df = pd.read_excel(excel_files[0])

    return df

if __name__ == "__main__":
    load_reckitt_data()