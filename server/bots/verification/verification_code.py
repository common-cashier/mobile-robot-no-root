<<<<<<< HEAD
import re  # 用于正则
import time

from PIL import Image  # 用于打开图片和对图片处理
import pytesseract  # 用于图片转文字

from server.ocr_api import ocr_img

Image.LOAD_TRUNCATED_IMAGES = True


class VerificationCode:
    def __init__(self, x=None, y=None, width=None, height=None, img=None, bank=None, letters_len=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.img = img
        self.bank = bank
        self.letters_len = letters_len

    def get_pictures(self):
        page_snap_obj = Image.open(self.img)
        time.sleep(1)
        left = self.x
        top = self.y
        right = left + self.width
        bottom = top + self.height
        image_obj = page_snap_obj.crop((left, top, right, bottom))  # 按照验证码的长宽，切割验证码
        return image_obj

    def processing_image(self):
        image_obj = self.get_pictures()  # 获取验证码
        img = image_obj.convert("L")  # 转灰度
        Bigdata = img.load()
        w, h = img.size
        threshold = 120
        for y in range(h):
            for x in range(w):
                if Bigdata[x, y] < threshold:
                    Bigdata[x, y] = 0
                else:
                    Bigdata[x, y] = 255
        return img

    def delete_spot(self):
        images = self.processing_image()
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

    def image_str(self, deluxe=False):

        image = self.delete_spot()
        image.save(self.img)

        if deluxe:
            try:
                res = ocr_img(self.img, self.letters_len)
            except Exception as ext:
                res = ''
                print(ext)
        else:
            result = pytesseract.image_to_string(image, lang='eng', config="--psm 6 --tessdata-dir "
                                                                           "bots/verification/tessdata "
                                                                           "--oem 3 -c tessedit_char_whitelist=0123456789")  # 图片转文字
            results = re.sub(u"([^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a])", "", result)  # 去除识别出来的特殊字符
            res = results[0:self.letters_len]  # 只获取前self.letters_len个字符
        return res


if __name__ == '__main__':
    a = VerificationCode(0, 0, 1080, 430, 'verification.jpg', "boc", 10)
    code = a.image_str()
    print("img_read: " + code)
=======
import re  # 用于正则
import time

from PIL import Image  # 用于打开图片和对图片处理
import pytesseract  # 用于图片转文字

from server.ocr_api import ocr_img

Image.LOAD_TRUNCATED_IMAGES = True


class VerificationCode:
    def __init__(self, x=None, y=None, width=None, height=None, img=None, bank=None, letters_len=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.img = img
        self.bank = bank
        self.letters_len = letters_len

    def get_pictures(self):
        page_snap_obj = Image.open(self.img)
        time.sleep(1)
        left = self.x
        top = self.y
        right = left + self.width
        bottom = top + self.height
        image_obj = page_snap_obj.crop((left, top, right, bottom))  # 按照验证码的长宽，切割验证码
        return image_obj

    def processing_image(self):
        image_obj = self.get_pictures()  # 获取验证码
        img = image_obj.convert("L")  # 转灰度
        Bigdata = img.load()
        w, h = img.size
        threshold = 120
        for y in range(h):
            for x in range(w):
                if Bigdata[x, y] < threshold:
                    Bigdata[x, y] = 0
                else:
                    Bigdata[x, y] = 255
        return img

    def delete_spot(self):
        images = self.processing_image()
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

    def image_str(self, deluxe=False):

        image = self.delete_spot()
        image.save(self.img)

        if deluxe:
            try:
                res = ocr_img(self.img, self.letters_len)
            except Exception as ext:
                res = ''
                print(ext)
        else:
            result = pytesseract.image_to_string(image, lang='eng', config="--psm 6 --tessdata-dir "
                                                                           "bots/verification/tessdata "
                                                                           "--oem 3 -c tessedit_char_whitelist=0123456789")  # 图片转文字
            results = re.sub(u"([^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a])", "", result)  # 去除识别出来的特殊字符
            res = results[0:self.letters_len]  # 只获取前self.letters_len个字符
        return res


if __name__ == '__main__':
    a = VerificationCode(0, 0, 1080, 430, 'verification.jpg', "boc", 10)
    code = a.image_str()
    print("img_read: " + code)
>>>>>>> 9106ec0777a2e9e0e3255c47bc883216c62945f8
