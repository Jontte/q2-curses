import threading
import curses
import re

from IRCState import IRCState
import UIComponents
import UIEngine

class IRCUI:
    def __init__(self):
        self.event = threading.Event()
        self.mutex = threading.RLock()
        self.layout = UIEngine.canvas(self.event, self.mutex)
        self.layout.layout('''
ver(
    hor(
        20 winlist,
        ver(
            1 topic,
            hor(
                channel,
                20 nicklist
            )
        )
    ),
    1 splitter, 
    1 input
)
''')
        self.channel = []
        self.layout.renderFn('winlist', self.renderWinlist)
        self.layout.renderFn('channel', self.renderChannel)
        self.layout.renderFn('nicklist', self.renderNicklist)
        self.layout.renderFn('splitter', self.renderSplitter)
        self.layout.renderFn('topic', self.renderTopic)
        self.layout.renderFn('input', self.renderInput)
        self.layout.metaFn(self.handleMeta)
        
        self.thread = None
        self.networks = []

        # setup windows
        self.status_window = UIComponents.TextWindow('status')
        self.windows = [self.status_window]
        self.current_window_index = 0
        self.input_title = u'> '
        self.layout.submitFn(self.on_submit)

    def run(self):
        self.thread = threading.Thread(target = self.layout.run)
        self.thread.start()

    def stop(self):
        self.layout.stop()
        self.event.set()

    def isRunning(self):
        return self.thread.is_alive()

    def refresh(self):
        self.layout.refresh()

    def renderWinlist(self, screen, panel_id, x, y, w, h):
        for yy in range(len(self.windows)):
            if yy >= h:
                break
            screen.addstr(y+yy, x, str(yy+1))
            if w-2 > 0:
                self.windows[yy].render_tab(screen, x+2, y+yy, w-2, 1, yy == self.current_window_index)

    def renderChannel(self, screen, panel_id, x, y, w, h):
        self.windows[self.current_window_index].render(screen,x,y,w,h)
    def renderNicklist(self, screen, panel_id, x, y, w, h):
        UIEngine.nullRender(screen,panel_id,x,y,w,h)

    def renderTopic(self,screen,panel_id, x, y, w, h):

        text = self.windows[self.current_window_index].name
        text += ' ' * max(0,(w-len(text)))
        text = text[:w]
        screen.addstr(y,x,text, curses.color_pair(3) | curses.A_BOLD)

    def renderInput(self, screen, panel_id, x, y, w, h):

        offset = 0
        msg = self.layout.getInput()
        msglen = len(msg)

        screen.addstr(y,x,self.input_title.encode('utf-8'))

        x += len(self.input_title)
        w -= len(self.input_title)
        if w <= 0:
            return

        if msglen > w-1:
            offset = msglen-(w-1)

        try:
            screen.addstr(y,x,' '*w)
        except: pass

        msg = msg[offset:]
        screen.addstr(y,x,bytes(msg,'utf-8'))

        cursorpos = self.layout.getCursor() - offset
        self.layout.setCursor(x+cursorpos,y)

    def renderSplitter(self, screen, panel_id, x, y, w, h):
        screen.addstr(y,x,' '*w, curses.A_REVERSE)

    def pushStatusMessage(self, msg):
        with self.mutex:
            self.status_window.push_message(msg)
        self.refresh()

    def pushMessage(self, msg):
        with self.mutex:
            self.windows[self.current_window_index].push_message(msg)
        self.refresh()

    def handleMeta(self, char):
        # Alt+number switches windows:

        if char >= ord('0') and char <= ord('9'):
            idx = char-ord('0')-1
            if idx < 0: idx += 10
            if idx < len(self.windows):
                self.current_window_index = idx
                self.refresh()
            return
        self.pushStatusMessage('unhandled meta key: ' + chr(char))

    def repopulate_windows(self):

        self.windows = [self.status_window]

        for network in self.networks:

            bufs = network.buffer_list()

            self.windows.append(UIComponents.NetworkWindow(network))

            for buffer in network.buffer_list():
                self.windows.append(UIComponents.BufferWindow(network, buffer))

    def on_submit(self, line):

        line = line.strip()

        if re.match('^/', line):

            cmd = re.split(' +', line[1:])

            if cmd[0] == 'connect' and len(cmd) > 1:
                self.pushStatusMessage('Connecting to: ' + cmd[1])
                self.state.core_connect(self.networks[0], cmd[1])

    def on_core_connect(self):
        self.pushStatusMessage('Connected to core')

    def on_core_close(self):
        self.pushStatusMessage('Disconnected from core')
        self.state = None
        self.networks = []
        self.repopulate_windows()

    def on_core_networklist(self, networks):
        self.networks = networks
        self.repopulate_windows()

    def on_core_bufferlist(self, network):
        self.repopulate_windows()

    def on_core_newbuffer(self):
        self.repopulate_windows()

    def connect(self, hostport):

        self.state = IRCState(
            hostport,
            callbacks = {
                'logger': self.pushStatusMessage,
                'core_connect': self.on_core_connect,
                'core_close': self.on_core_close,
                'core_networklist': self.on_core_networklist,
                'core_bufferlist': self.on_core_bufferlist,
                'core_newbuffer': self.on_core_newbuffer,
        })

