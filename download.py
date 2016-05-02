#!/usr/bin/env python
# coding: utf-8

import sys
import threading
import time
import argparse
import logging
import os.path
from Queue import Queue

import requests

from download_record import DownloadRecord

class Downloader(object):
    def __init__(self, url, thread_num=3):
        self.url = url
        self.filename = self._get_file_name()
        self.thread_num = thread_num
        self.bulk_size = 2 ** 16
        self.record = DownloadRecord(self.url)

    def start(self):
        start_time = time.time()

        head = self._get_head()
        length = self._get_content_length(head)
        target_exists = os.path.exists(self.filename)
        if not target_exists:
            self._create_download_file()

        if self._can_segment_download(head) and length != -1:
            # download file and record file are all ok
            if target_exists and self.record.is_downloading():
                logging.info("downloading from last download")
                self.record.recover()
            else:
                self.record.clear()
                self.record.create_record(length)
            self._use_multi_segment_download()
        else:
            logging.info("server does not support partial download, download file at once.")
            content = self._get_content_at_once()
            self._write_to_file(content, 0, len(content)-1)

        self.record.delete()

        end_time = time.time()
        logging.info("download spend %s seconds" % (end_time - start_time))

    def _use_multi_segment_download(self):
        queue = Queue()
        for seq in self.record.get_all_uncompleted_seqs():
            queue.put(seq)
        for i in range(self.thread_num):
            thread = threading.Thread(target = self._download_worker, args=(queue, ))
            thread.daemon = True
            thread.start()

        queue.join()

    def _download_worker(self, queue):
        while True:
            seq = queue.get()
            start, end = self.record.get_bulk_range(seq)
            self._download_segment_and_write(start, end)
            self.record.set_bulk_completed(seq)
            queue.task_done()

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
        headers = {"Range": "Bytes=0-"}
        return requests.head(self.url, headers=headers)

    def _can_segment_download(self, head):
        return head.status_code == 206

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

    logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    loader = Downloader(args.url, args.thread_num)
    loader.start()
