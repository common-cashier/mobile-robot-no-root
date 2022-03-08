import re
from typing import Any

from PIL import Image
import pytesseract
from server.bots.verification import get_tessdata_dir

__all__ = ['RecognizeNumber']




class RecognizeNumber:
    def __init__(self, img=None, x=0, y=0, width=0, height=0, letters_len=0):
        self.img = img
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.letters_len = letters_len

    def _get_image(self):
        page_snap_obj = Image.open(self.img)
        left, top = self.x, self.y
        right = left + self.width
        bottom = top + self.height
        image_obj = page_snap_obj.crop((left, top, right, bottom))
        return image_obj

    def _processing_image(self):
        image_obj = self._get_image()
        img = image_obj.convert('L')
        pixel_data: Any = img.load()
        w, h = img.size
        threshold = 120
        for y in range(h):
            for x in range(w):
                if pixel_data[x, y] < threshold:
                    pixel_data[x, y] = 0
                else:
                    pixel_data[x, y] = 255
        return img

    def _delete_spot(self):
        images = self._processing_image()
        data = images.getdata()
        w, h = images.size
        black_point = 0
        for x in range(1, w - 1):
            for y in range(1, h - 1):
                mid_pixel = data[w * y + x]  # 中央像素点像素值
                if mid_pixel < 50:  # 找出上下左右四个方向像素点像素值
                    top_pixel = data[w * (y - 1) + x]
                    left_pixel = data[w * y + (x - 1)]
                    down_pixel = data[w * (y + 1) + x]
                    right_pixel = data[w * y + (x + 1)]
                    if top_pixel < 10:
                        black_point += 1
                    if left_pixel < 10:
                        black_point += 1
                    if down_pixel < 10:
                        black_point += 1
                    if right_pixel < 10:
                        black_point += 1
                    if black_point < 1:
                        images.putpixel((x, y), 255)
                    black_point = 0
        return images

    def image_str(self):
        image = self._delete_spot()


        data_dir = '--tessdata-dir ' + get_tessdata_dir()
        config_str = f'--psm 6 --dpi 300 --oem 3 {data_dir} -c tessedit_char_whitelist=0123456789'  # 0123456789
        result = pytesseract.image_to_string(image, lang='eng', config=config_str)

        results = re.sub(u'([^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a])', '', result)
        res = results[0:self.letters_len]
        return res
