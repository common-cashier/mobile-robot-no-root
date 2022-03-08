import os


def get_tessdata_dir():
    dir_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'tessdata'))
    return dir_path
