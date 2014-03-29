#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import locale
import asyncore
import UI
import sys

class Application:

    def __init__(self):
        self.ui = UI.IRCUI()

    def run(self, hostport):

        self.ui.connect(hostport)
        self.ui.run()

        try:
            while self.ui.isRunning():
                asyncore.loop(timeout=1, count=1)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.ui.pushMessage('Exception in main loop: ' + str(e))
        self.ui.stop()

if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL,"")

    if len(sys.argv) < 3:
        print('Usage: %s core-host core-port' % sys.argv[0])
        sys.exit(1)

    app = Application()
    app.run((sys.argv[1], int(sys.argv[2])))

