#!/usr/bin/evn python
# coding: utf-8

import os
import base64
from struct import pack, unpack, calcsize

class DownloadRecord(object):
    def __init__(self, url):
        self.url = url
        self.filename = base64.b64encode(self.url)
        self.bulk_size = 65536
        self.url_length = len(self.url)

        # url_size, url, content_size, bulk_size, (seq, status), (seq, status) ...
        # no alignment, [unsigned short] [string] [unsigned long] [unsigned int]
        self.header_format = "=H%ssQI" % self.url_length
        self.header_size = calcsize(self.header_format)
        if os.path.exists(self.filename):
            self.f = open(self.filename, "rb+")
        else:
            self.f = open(self.filename, "wb+")

    def get_record_filename(self):
        return self.filename

    def _validate(self):
        """校验是否是一个合法的record文件
           判断各个字段是否正常，大小是否正确
        """
        return True

    def is_downloading(self):
        return os.path.exists(self.filename)

    def clear(self):
        self.f.truncate()

    def create_record(self, content_size, bulk_size=65536):
        self.content_size = content_size
        self.bulk_size = bulk_size

        header = pack(self.header_format, self.url_length, self.url, self.content_size, self.bulk_size)
        bulk_num = self._get_bulk_num()
        bulk_format = self._get_bulk_format(bulk_num)
        bulk_data = [[seq, False] for seq in range(bulk_num)]
        bulks = pack(bulk_format, *[element for lst in bulk_data for element in lst])

        self.f.write(header)
        self.f.write(bulks)

    def recover(self):
        header_data = self.f.read(self.header_size)
        header = unpack(self.header_format, header_data)
        _, url, self.content_size, self.bulk_size = header
        assert(url == self.url)

    def close(self):
        self.f.close()

    def _get_all_completed_seqs(self):
        bulk_status = self._get_all_bulks()
        completed_bulks = filter(lambda status: status[1], bulk_status)
        return map(lambda bulk: bulk[0], completed_bulks)

    def get_bulk_range(self, seq):
        bulk_num = self._get_bulk_num()
        if seq < bulk_num - 1:
            return (self.bulk_size * seq, self.bulk_size * (seq + 1))
        elif seq == bulk_num - 1:
            return (self.bulk_size * seq, self.content_size - 1)

        assert(0)

    def get_all_uncompleted_seqs(self):
        bulk_status = self._get_all_bulks()
        uncompleted_bulks = filter(lambda status: not status[1], bulk_status)
        return map(lambda bulk: bulk[0], uncompleted_bulks)

    def _get_all_bulks(self):
        bulk_num = self._get_bulk_num()
        bulk_format = self._get_bulk_format(bulk_num)
        bulk_size = calcsize(bulk_format)

        self.f.seek(self.header_size)
        bulk_data = self.f.read(bulk_size)
        bulks = unpack(bulk_format, bulk_data)
        return [(bulks[i], bulks[i+1]) for i in range(0, len(bulks), 2)]

    def set_bulk_completed(self, seq):
        pos = self.header_size + 5 * seq
        bulk = pack("=I?", seq, True)
        self.f.seek(pos)
        self.f.write(bulk)

    def delete(self):
        os.remove(self.filename)

    def _get_bulk_num(self):
        return (self.content_size + self.bulk_size - 1) / self.bulk_size

    def _get_bulk_format(self, bulk_num):
        return "=" + "I?" * bulk_num


if __name__ == "__main__":
    record = DownloadRecord("http://dldir1.qq.com/qqfile/QQforMac/QQ_V4.1.1.dmg")
    #record.create_record(1000, 12)
    record.recover()
    uncompleted_seqs = record.get_all_uncompleted_seqs()
    size = len(uncompleted_seqs)
    print size
    if size > 0:
        print uncompleted_seqs[0]
        print uncompleted_seqs[size-1]

    record.close()
    #record.delete()
