<<<<<<< HEAD
from server import settings
from server.settings import get_md5, log, Level


def update_init():
    file_path = r'./bots/boc.py'
    md5_01 = get_md5(file_path)
    file_path = r'./bots/ccb.py'
    md5_02 = get_md5(file_path)
    settings.md5_json = {
        "boc": md5_01,
        "ccb": md5_02
    }
    log(str(settings.md5_json), Level.X_LOG, True)
=======
from server import settings
from server.settings import get_md5, log, Level


def update_init():
    file_path = r'./bots/boc.py'
    md5_01 = get_md5(file_path)
    file_path = r'./bots/ccb.py'
    md5_02 = get_md5(file_path)
    settings.md5_json = {
        "boc": md5_01,
        "ccb": md5_02
    }
    log(str(settings.md5_json), Level.X_LOG, True)
>>>>>>> 9106ec0777a2e9e0e3255c47bc883216c62945f8
