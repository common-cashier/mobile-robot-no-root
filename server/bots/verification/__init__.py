import os


def get_tessdata_dir():
    """
    获取 tessdata 绝对路径
    """
    # 根据当前文件路径，组装 tessdata 绝对路径
    dir_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'tessdata'))
    return dir_path
