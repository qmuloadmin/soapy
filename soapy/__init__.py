#!/usr/bin/python3

import time


class Log:
    """ Basic trace-level based logging class """

    trace_level_map = {
        0: "FATAL",
        1: "ERROR",
        2: "WARN",
        3: "NOTICE",
        4: "INFO",
        5: "DEBUG"
    }

    def __init__(self, tl):

        """ Provide tracelevel of -1 to not log anything """

        self.tl = tl
        self.log("Set instance tracelevel to {0}".format(tl), 5)

    def log(self, message, tl):

        if self.tl == -1:
            return

        if tl <= self.tl:
            prefix = "{}".format(self.trace_level_map[tl]+":")
            message = message.replace("\n", "")
            print("{:7}{} | {}: {} |".format(
                prefix,
                time.ctime(),
                self.__class__.__name__.lower(),
                message))
