import os
import unittest

# use root
os.chdir('../../')

from server.bots.bank_util.BCM.recognize import RecognizeNumber
from server.bots.verification import get_tessdata_dir


def _get_img_path(file_name):
    _base_dir = os.path.dirname(__file__)
    return os.path.join(_base_dir, 'moq', file_name)


class BCMRecognizeTestCase(unittest.TestCase):

    def test_pwd_number(self):
        img_path = _get_img_path('test_img_trans_pay_pwd.png')
        a = RecognizeNumber(img_path, 18, 1188, 1062, 615, 10)
        self.assertEqual('9548726130', a.image_str())

        img_path = _get_img_path('test_img_bcm_kb.png')
        a = RecognizeNumber(img_path, 18, 1188, 1062, 615, 10)
        self.assertEqual('4673185092', a.image_str())

    def test_tessdata_path(self):
        img_path = get_tessdata_dir()
        self.assertIn('server/bots/verification/tessdata', img_path)
