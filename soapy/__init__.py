#!/usr/bin/python3

import time
import os
from bs4 import BeautifulSoup
from bs4.element import Tag
import requests


class Log:
    """ Basic trace-level based logging class """

    def __init__(self, tl):

        """ Provide tracelevel of -1 to not log anything """

        self.tl = tl
        self._log("Set instance tracelevel to {0}".format(tl), 5)

    def _log(self, message, tl):

        prefix = str()

        if self.tl == -1: return
        if tl <= self.tl:
            if tl == 0:
                prefix = "FATAL:	"
            elif tl == 1:
                prefix = "ERROR:	"
            elif tl == 2:
                prefix = "WARN:	"
            elif tl == 3:
                prefix = "NOTICE: "
            elif tl == 4:
                prefix = "INFO:	"
            elif tl == 5:
                prefix = "DEBUG:	"

            print(prefix + str(time.ctime()) + " | " + message + " |")

