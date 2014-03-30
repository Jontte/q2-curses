import curses
import UIEngine
import math
import re
import IRCState

class Window:
    def __init__(self, name):
        self.name = name

    def render(self, screen, x, y, w, h):
        UIEngine.nullRender(screen, self.name, x, y, w, h)

    def render_tab(self, screen, x, y, w, h, selected):

        if selected:
            attr = curses.color_pair(1) | curses.A_UNDERLINE
        else:
            attr = curses.color_pair(2)

        screen.addstr(y, x, self.name[:w], attr)

class TextWindow(Window):
    def __init__(self, name):
        Window.__init__(self, name)
        self.lines = []

    def push_message(self, msg):
        self.lines += re.split('\n', msg)

    def render(self,screen,x,y,w,h):
        # Clear..
        for yy in range(y,y+h):
            screen.addstr(yy,x,' '*w)

        # Whether to draw an extra symbol to help distinguish long messages from each other:
        drawBullet = False

        if drawBullet:
            x += 2
            w -= 2
            if w <= 0:
                return
        # Let's do some wrapping..
        pos = y+h-1
        for i in range(len(self.lines)):
            idx = len(self.lines)-i-1

            thisline = self.lines[idx]

            linecount = int(math.ceil(float(len(thisline))/w))

            if pos-linecount < y:
                break

            if drawBullet:
                screen.addch(y+pos-linecount,x-2, curses.ACS_DIAMOND)
            for a in range(linecount):
                screen.addstr(y+pos-linecount+a, x, thisline[:w].encode('utf-8'))
                thisline = thisline[w:]
            pos -= linecount


class NetworkWindow(Window):

    def __init__(self, network):
        Window.__init__(self, 'Network: ' + str(network.state))
        self.network = network

    def render(self,screen,x,y,w,h):

        UIEngine.clear(screen, x, y, w, h)

        lines = ['']

        net = self.network

        if net.state == IRCState.Network.STATE_CONNECTED:
            lines.append('Status: Connected')
        elif net.state == IRCState.Network.STATE_CONNECTING:
            lines.append('Status: Connecting')
        elif net.state == IRCState.Network.STATE_DISCONNECTED:
            lines.append('Status: Disconnected')

        lines += ['']

        config = net.get_configuration()
        if config is not None:
            lines += ['Server: ' + config.server]
            lines += ['Nickname: ' + config.nickname]
        else:
            lines += ['Waiting for network configuration...']

        lines += ['']



        for i in range(len(lines)):
            if i >= h:
                break

            x_offset = 2
            screen.addstr(y+i, x+x_offset, lines[i][:(w-x_offset)], 0)

class BufferWindow(Window):

    def __init__(self, network, buffer):
        Window.__init__(self, 'Buffer')

