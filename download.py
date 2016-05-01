#!/usr/bin/env python

import sys
import threading
import time
import argparse
import logging

import requests

class Downloader(object):
    def __init__(self, url, thread_num=3):
        self.url = url
        self.filename = self._get_file_name()
        self.thread_num = thread_num

    def start(self):
        self._create_download_file()
        head = self._get_head()
        length = self._get_content_length(head)

        start_time = time.time()
        if self._can_segment_download(head):
            if length == -1:
                logging.warn("can not get content-length for url %s" % self.url)
            else:
                self._use_multi_segment_download(length)
        else:
            content = self._get_content_at_once()
            self._write_to_file(content, 0, len(content)-1)

        end_time = time.time()
        print "download spend %s seconds" % (end_time - start_time)

    def _use_multi_segment_download(self, length):
        file_ranges = self._segment_length(length)
        thread_list = []
        for i in range(self.thread_num):
            start, end = file_ranges[i]
            thread = threading.Thread(target = self._download_segment_and_write, args = (start, end))
            thread_list.append(thread)

        for thread in thread_list:
            thread.start()
        for thread in thread_list:
            thread.join()

    def _download_segment_and_write(self, start, end):
        content = self._get_segment_content(start, end)
        self._write_to_file(content, start, end)

    def _create_download_file(self):
        f = open(self.filename, "w")
        f.close()

    def _segment_length(self, length):
        avg = (length + self.thread_num - 1) / self.thread_num
        result = [(avg*i, avg*(i+1)-1) for i in range(self.thread_num-1)]
        last = (avg * (self.thread_num-1), length-1)
        result.append(last)
        return result

    def _get_file_name(self):
        splits = self.url.split("/")
        return splits[len(splits)-1]

    def _get_head(self):
        return requests.head(self.url)

    def _can_segment_download(self, head):
        if "accept-ranges" in head.headers:
            if head.headers["accept-ranges"] == "bytes":
                return True
            else:
                logging.warn("unknown accept-ranges, %s" % head.headers["accept-ranges"])

        return False

    def _get_content_length(self, head):
        length = int(head.headers.get("content-length", -1))
        return length;

    def _get_content_at_once(self):
        res = requests.get(self.url)
        return res.content

    def _get_segment_content(self, start, end):
        headers = {"Range": "Bytes=%s-%s" % (start, end), "Accept-Encoding": "*"}
        res = requests.get(self.url, headers=headers)
        assert(len(res.content) == end - start + 1)
        return res.content

    def _write_to_file(self, content, start, end):
        assert(len(content) == end - start + 1)
        with open(self.filename, "r+") as f:
            f.seek(start)
            f.write(content)


def add_args(parser):
    parser.add_argument("-u", "--url", type=str, required=True, help="url to download")
    parser.add_argument("-t", "--thread_num", type=int, default=3, help="thread number to download")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_args(parser)
    args = parser.parse_args(sys.argv[1:])

    loader = Downloader(args.url, args.thread_num)
    loader.start()
