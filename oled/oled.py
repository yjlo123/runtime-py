#!/usr/bin/python
# -*- coding:utf-8 -*-

from . import SH1106
import time
from PIL import Image,ImageDraw,ImageFont

class Display:
    def __init__(self):
        self.width = 21
        self.height = 7

        self.buffer = [' ' * self.width] * self.height
        self.disp = SH1106.SH1106()
        self.disp.Init()
        self.cur_row = 0
        self.cur_col = 0

        self.disp.clear()

    def show(self):
        image1 = Image.new('1', (self.disp.width, self.disp.height), "WHITE")
        draw = ImageDraw.Draw(image1)
        font_d = ImageFont.truetype('DejaVuSansMono.ttf', 10)
        for i in range(self.height):
            draw.text((0, 9 * i), self.buffer[i], font=font_d, fill=0)
        self.disp.ShowImage(self.disp.getbuffer(image1))

    def clear(self):
        self.disp.clear()

    def print(self, text, end=None):
        text += '\n' if end is None else end
        for c in text:
            if c == '\n':
                self.cur_row += 1
                self.cur_col = 0
                if self.cur_row == len(self.buffer):
                    self.buffer.append(' ' * self.width)
            else:
                if self.cur_col == self.width:
                    self.cur_row += 1
                    self.cur_col = 0
                if self.cur_row == len(self.buffer):
                    self.buffer.append(' ' * self.width)
                line = self.buffer[self.cur_row]
                self.buffer[self.cur_row] = line[:self.cur_col] + c + line[self.cur_col+1:]
                self.cur_col += 1
        if self.cur_row >= self.height:
            cur_buffer_height = len(self.buffer)
            self.buffer = self.buffer[cur_buffer_height - self.height:]
            self.cur_row = self.height - 1
        #self._log_buffer()
        self.show()

    def _log_buffer(self):
        print('-----')
        for row in self.buffer:
            print(row + '|')


'''
try:
    disp = SH1106.SH1106()

    disp.Init()
    disp.clear()

    image1 = Image.new('1', (disp.width, disp.height), "WHITE")
    draw = ImageDraw.Draw(image1)

    # ~ font = ImageFont.truetype('Font.ttf', 20)
    # ~ draw.text((28,20), u'微雪电子 ', font=font, fill=0)

    font_d = ImageFont.truetype('DejaVuSansMono.ttf', 10)
    draw.text((0,0), 'Moon OS  v1.19 (build', font=font_d, fill=0)
    draw.text((0,9), 'Copyright (c) 1992 Ru', font=font_d, fill=0)
    draw.text((0,18), 'All rights reserved.', font=font_d, fill=0)
    draw.text((0,27), '', font=font_d, fill=0)
    draw.text((0,36), 'Welcome', font=font_d, fill=0)
    draw.text((0,45), '1234567890abcdefghijk', font=font_d, fill=0)
    draw.text((0,54), 'ABCDEFGHIJKLMNOPQRSTU', font=font_d, fill=0)

    disp.ShowImage(disp.getbuffer(image1))

    time.sleep(15)
    disp.clear()

except IOError as e:
    print(e)

except KeyboardInterrupt:    
    print("ctrl + c:")
    epdconfig.module_exit()
    exit()
'''


