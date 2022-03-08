<<<<<<< HEAD
from datetime import datetime
import unittest
from server.common_helpers import DateTimeHelper, StrHelper


class DateTimeHelperTestCase(unittest.TestCase):
    def test_to_datetime(self):
        _time = datetime(2021, 8, 13, 19, 58, 46)

        self.assertEqual(_time, DateTimeHelper.to_datetime('2021/8/13 19:58:46'))
        self.assertEqual(_time, DateTimeHelper.to_datetime('2021/08/13 19:58:46'))
        self.assertEqual(_time, DateTimeHelper.to_datetime('2021-8-13 19:58:46'))
        self.assertEqual(_time, DateTimeHelper.to_datetime('2021-08-13 19:58:46'))
        self.assertEqual(_time, DateTimeHelper.to_datetime('2021$08$13 19&58&46', '%Y$%m$%d %H&%M&%S'))
        self.assertEqual(_time, datetime(2021, 8, 13, 19, 58, 46))

    def test_to_str(self):
        _time = datetime(2021, 8, 13, 19, 58, 46)
        _time_str = '2021/8/13 19:58:46'

        self.assertEqual('2021/08/13 19:58:46', DateTimeHelper.to_str(_time))
        self.assertEqual('2021/08/13 19:58:46', DateTimeHelper.to_str(_time, '%Y/%m/%d %H:%M:%S'))
        self.assertEqual('2021/08/13 19:58:46', DateTimeHelper.to_str(_time_str, '%Y/%m/%d %H:%M:%S'))
        self.assertEqual('20210813195846', DateTimeHelper.to_str(_time, '%Y%m%d%H%M%S'))
        self.assertEqual('20210813195846', DateTimeHelper.to_str(_time_str, '%Y%m%d%H%M%S'))


class StrHelperTestCase(unittest.TestCase):
    def test_md5(self):
        _time_str = '张三$2021813195846$622211103932112$100'
        self.assertEqual('FB476239B01A4FDE7599DCDE1AAF4661', StrHelper.md5(_time_str))


if __name__ == '__main__':
    unittest.main()
=======
from datetime import datetime
import unittest
from server.common_helpers import DateTimeHelper, StrHelper


class DateTimeHelperTestCase(unittest.TestCase):
    def test_to_datetime(self):
        _time = datetime(2021, 8, 13, 19, 58, 46)

        self.assertEqual(_time, DateTimeHelper.to_datetime('2021/8/13 19:58:46'))
        self.assertEqual(_time, DateTimeHelper.to_datetime('2021/08/13 19:58:46'))
        self.assertEqual(_time, DateTimeHelper.to_datetime('2021-8-13 19:58:46'))
        self.assertEqual(_time, DateTimeHelper.to_datetime('2021-08-13 19:58:46'))
        self.assertEqual(_time, DateTimeHelper.to_datetime('2021$08$13 19&58&46', '%Y$%m$%d %H&%M&%S'))
        self.assertEqual(_time, datetime(2021, 8, 13, 19, 58, 46))

    def test_to_str(self):
        _time = datetime(2021, 8, 13, 19, 58, 46)
        _time_str = '2021/8/13 19:58:46'

        self.assertEqual('2021/08/13 19:58:46', DateTimeHelper.to_str(_time))
        self.assertEqual('2021/08/13 19:58:46', DateTimeHelper.to_str(_time, '%Y/%m/%d %H:%M:%S'))
        self.assertEqual('2021/08/13 19:58:46', DateTimeHelper.to_str(_time_str, '%Y/%m/%d %H:%M:%S'))
        self.assertEqual('20210813195846', DateTimeHelper.to_str(_time, '%Y%m%d%H%M%S'))
        self.assertEqual('20210813195846', DateTimeHelper.to_str(_time_str, '%Y%m%d%H%M%S'))


class StrHelperTestCase(unittest.TestCase):
    def test_md5(self):
        _time_str = '张三$2021813195846$622211103932112$100'
        self.assertEqual('FB476239B01A4FDE7599DCDE1AAF4661', StrHelper.md5(_time_str))


if __name__ == '__main__':
    unittest.main()
>>>>>>> 9106ec0777a2e9e0e3255c47bc883216c62945f8
