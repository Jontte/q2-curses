import curses
import UIEngine
import math
import re
import IRCState

class Window:
    def __init__(self, name):
        self.name = name

    def get_layout(self):
        return 'status'

    def render(self, screen, widget_context, x, y, w, h):
        UIEngine.nullRender(screen, self.name, x, y, w, h)

    def render_tab(self, screen, widget_context, x, y, w, h, selected):

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

    def render(self, screen, widget_context, x, y, w, h):
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


class Text:
    def __init__(self, text):
        self.text = text

    def render(self, screen, widget_context, x, y, w, h):
        screen.addstr(y, x, self.text[:w], 0)
        return len(self.text), 1

class TextInput:
    def __init__(self, name, focus):
        self.name = name
        self.focus = focus

    def render(self, screen, widget_context, x, y, w, h):
        widget_context.render_text_input(self.name, screen, x, y, w, h, self.focus)
        return len(widget_context.get_text(self.name)), 1

class Spacing:
    def __init__(self, count):
        self.count = count

    def render(self, screen, widget_context, x, y, w, h):
        return self.count, self.count

class Horizontal:
    def __init__(self, items):
        self.items = items

    def render(self, screen, widget_context, x, y, w, h):
        step = [0, 0]
        minh = 0
        for item in self.items:
            size = item.render(screen, widget_context, x+step[0], y+step[1], w-step[0], h-step[1])
            step[0] += min(size[0], w-step[0])
            minh = max(minh, size[1])
        return w, minh

class Vertical:
    def __init__(self, items):
        self.items = items

    def render(self, screen, widget_context, x, y, w, h):
        step = [0, 0]
        minw = 0
        for item in self.items:
            size = item.render(screen, widget_context, x+step[0], y+step[1], w-step[0], h-step[1])
            step[1] += min(size[1], h-step[1])
            minw = max(minw, size[0])
        return minw, h

class NetworkWindow(Window):

    def __init__(self, network):
        Window.__init__(self, 'Network: ' + str(network.state))
        self.network = network

    def get_layout(self):
        return 'network'

    def render(self, screen, widget_context, x, y, w, h):

        UIEngine.clear(screen, x, y, w, h)

        items = []

        net = self.network

        items.append(Spacing(1))

        if net.state == IRCState.Network.STATE_CONNECTED:
            items.append(Text('Status: Connected'))
        elif net.state == IRCState.Network.STATE_CONNECTING:
            items.append(Text('Status: Connecting'))
        elif net.state == IRCState.Network.STATE_DISCONNECTED:
            items.append(Text('Status: Disconnected'))

        items.append(Spacing(1))

        config = net.get_configuration()
        if config is None:
            items.append(Text('Waiting for network configuration...'))
        else:

            if config is False:
                items.append(Text('The network is *not* configured'))
            else:
                widget_context.set_text_default_value('config_server', config.server)
                widget_context.set_text_default_value('config_nickname', config.nickname)

            items.append(Horizontal([Text('Server   : '), TextInput('config_server', focus=1)]))
            items.append(Horizontal([Text('Nickname : '), TextInput('config_nickname', focus=2)]))

        items.append(Spacing(1))

        Vertical(items).render(screen, widget_context, x, y, w, h)

class BufferWindow(Window):

    def __init__(self, network, buffer):
        Window.__init__(self, 'Buffer')

