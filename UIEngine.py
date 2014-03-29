#!/usr/bin/env python3 
# -*- coding: utf-8 -*- 

import curses 
import re

def splitparts(string, parts):
    if len(parts) == 0:
        return ''

    ret = []

    ret.append(string[:parts[0]])
    for i in range(len(parts)-1):
        ret.append(string[parts[i]+1:parts[i+1]])
    ret.append(string[parts[-1]+1:])
    return ret

def nullRender(screen, panel_id, x, y, w, h):
    attr = curses.A_DIM
    for yy in range(1, h-1):
        for xx in range(1, w-1):
            screen.addch(y+yy,x+xx,' ', attr)
    msg = panel_id
    for i in range(len(msg)):
        pos = x+w/2+i - len(msg)/2
        if pos >= x+w:
            break
        if pos <= x:
            continue
        screen.addch(int(y+h/2), int(pos), msg[i], attr)

    screen.addch(y,x,'+', attr)
    screen.addch(y,x+w-1,'+', attr)
    screen.addch(y+h-1,x,'+', attr)
    try:
        screen.addch(y+h-1,x+w-1,'+', attr)
    except curses.error: pass
    for i in range(1,w-1):
        screen.addch(y,x+i, '-', attr)
        screen.addch(y+h-1,x+i, '-', attr)
    for i in range(1,h-1):
        screen.addch(y+i,x, '|', attr)
        screen.addch(y+i,x+w-1, '|', attr)


class panel:
    def __init__(self):
        self._children = []
        self._layout = ''
        self._renderFn = nullRender
        self._id = None

    def setDimensions(self, x, y, w, h):
        self._x = x
        self._y = y
        self._w = w
        self._h = h

    def renderFn(self, panel_id, func):
        if len(self._children) > 0:
            for child in self._children:
                child.renderFn(panel_id, func)
        elif self._id == panel_id:
            self._renderFn = func

    def render(self, screen):
        # Update child status
        self._doLayout()
        if len(self._children) == 0:
            if self._w <= 0 or self._h <= 0:
                return
            try:
                self._renderFn(screen,self._id,self._x,self._y,self._w,self._h)
            except curses.error: pass
            except UnicodeEncodeError: pass
            except UnicodeDecodeError: pass
        else:
            # Recursively redraw.
            for child in self._children:
                child.render(screen);

    def layout(self, data):
        if not isinstance(data, str):
            return
        self._layout = data
        self._parseLayoutString()

    def _parseLayoutString(self):
        # Parse self._layout... 

        self._layout = self._layout.strip()
        l = self._layout

        # Begin with a size descriptor such as 100% or 5
        match = re.match('(0|([1-9][0-9]*))%?',l) # note, only looks at beginning of string
        if match == None:
            self.size = 'x' # 'fill the rest'
            rest = l
        else:
            self.size = match.group(0)
            rest = l[len(self.size):].strip()
       
        match = re.match('[a-zA-Z]+',rest)
        if match == None:
            op = ''
        else:
            op = match.group(0)
        
        # Leaf node?
        self._id = op
        if op != 'ver' and op != 'hor':
            return

        rest = rest[len(op):]
       
        # Parse parentheses...
        if rest[0] != '(' or rest[-1] != ')':
            return

        rest = rest[1:-1]
        # Find splitting commas..

        par = 0
        commas = []
        for i in range(len(rest)):
            c = rest[i]
            if c == ',' and par == 0:
                commas.append(i)
            elif c == '(':
                par += 1
            elif c == ')':
                par -= 1

        parts = splitparts(rest, commas)

        childcount = len(parts)

        while len(self._children) < childcount:
            self._children.append(panel())
        while len(self._children) > childcount:
            self._children.pop()

        for i in range(len(self._children)):
            self._children[i].layout(parts[i])

    def _doLayout(self):

        if len(self._children) == 0:
            return
        
        # Calculate amount of solid grid units..

        childParams = list(map(lambda x: x.size, self._children))
        
        solids = 0
        percentages = 0
        for var in childParams:
            var = str(var)
            if var == 'x':
                continue
            elif var[-1] != '%':
                solids += int(var)
            else:
                percentages += int(var[:-1])
        
        horstack = self._id == 'hor'
        maxwidth = self._w if horstack else self._h
        position = self._x if horstack else self._y
        freespace = maxwidth-solids
       
        lastpindex = -1
        for i in range(len(childParams)):
            var = childParams[i]
            #'x' stands for fill-all:
            if var == 'x':
                childParams[i] = int(float(100-percentages) * freespace / 100)
                percentages = 100
                lastpindex = i
            elif var[-1] == '%':
                childParams[i] = int(float(var[:-1]) * freespace / 100)
                lastpindex = i
            else:
                childParams[i] = int(var)

        # If percentages add up to 100%, make the last percentage value take the rounding error:
        if percentages == 100 and lastpindex != -1:
            solids = sum(childParams)
            diff = maxwidth - solids
            childParams[lastpindex] += diff

        for i in range(len(childParams)):
            c = self._children[i]
            if horstack:
                c._y = self._y
                c._h = self._h
                c._x = position
                c._w = childParams[i]
                position += c._w
                if position > self._x+maxwidth:
                    c._w = maxwidth - c._x
            else:
                c._x = self._x
                c._w = self._w
                c._y = position
                c._h = childParams[i]
                position += c._h
                if position > self._y+maxwidth:
                    c._h = maxwidth - c._y

class canvas:

    def __init__(self, event, mutex):
        self._root = panel()
        self._event = event
        self._mutex = mutex
        self._halt = False

        self._onSubmit = None # function callback to be called when the user presses enter
        self._onMeta = None # function callback for meta-characters
        self._inbuffer = bytearray() # user-written text, raw. When conversion to utf8 succeeds, dump to self._input
        self._input = '' # user-written text, utf8
        self._cursorPos = 0 # position of cursor in self._input

        self._cursorXY = (0,0)
        self._screen = None

    def refresh(self):

        with self._mutex:
            if self._screen == None:
                return

            size = self._screen.getmaxyx()
            self._root.setDimensions(0,0,size[1],size[0])
            self._root.render(self._screen)
            self._screen.move(self._cursorXY[1], self._cursorXY[0])
            self._screen.refresh()

    def _run(self, screen):
        curses.noecho() 
        curses.curs_set(2)
        curses.nonl() # leave newline mode
        curses.cbreak()
        curses.halfdelay(10)
        screen.leaveok(0)
        screen.scrollok(0)
        screen.keypad(1)

        screen.timeout(100) # 100ms

        if curses.has_colors():
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_RED)

        escape = False # Whether an escape character was read from getch() previously

        with self._mutex:
            self._screen = screen
            self.refresh()

        try:
            while not self._halt:

                if self._event.is_set():
                    self._event.clear()
                    self.refresh()

                event = screen.getch()

                with self._mutex:
                    if event == 27: #Escape!
                        escape = True
                    elif escape:
                        if self._onMeta != None:
                            self._onMeta(event)
                        escape = False
                    elif event == curses.KEY_RESIZE:
                        # on resize we clear the whole screen
                        screen.clear()
                    elif event == curses.KEY_LEFT:
                        self._cursorPos = max(0, self._cursorPos-1)
                    elif event == curses.KEY_RIGHT:
                        self._cursorPos = min(len(self._input), self._cursorPos+1)
                    elif event == curses.KEY_BACKSPACE or event == 8 or event == 127: # backspace
                        s = self._input
                        p = self._cursorPos
                        self._input = s[:max(0,p-1)] + s[p:]
                        self._cursorPos = max(0, self._cursorPos-1)
                    elif event == curses.KEY_DC: # delete-key
                        s = self._input
                        p = self._cursorPos
                        self._input = s[:max(0,p)] + s[p+1:]
                    elif event == curses.KEY_HOME:
                        self._cursorPos = 0
                    elif event == curses.KEY_END:
                        self._cursorPos = len(self._input)
                    elif event == curses.KEY_ENTER or event == 13: #newline
                        self._cursorPos = 0
                        if len(self._input) > 0 and self._onSubmit != None:
                            self._onSubmit(self._input)
                        self._input = ''
                    elif event == 10: # linefeed
                        pass
                    elif event > 0 and event < 256:
                        p = self._cursorPos
                        self._inbuffer.append(event)
                        try:
                            buf = str(self._inbuffer, 'utf-8')
                            self._input = self._input[:p] + buf + self._input[p:]
                            self._cursorPos += 1
                            self._inbuffer = bytearray()
                        except UnicodeDecodeError: pass

                    if event != -1:
                        self.refresh()
        except KeyboardInterrupt:
            return

    def layout(self, string):
        self._root.layout(string)

    def renderFn(self, panel_id, fn):
        # wrap the given function inside a mutex lock:
        def func(screen, panel_id, x, y, w, h):
            with self._mutex:
                fn(screen, panel_id, x, y, w, h)
        self._root.renderFn(panel_id, func)

    def run(self):
        curses.wrapper(self._run)

    def stop(self):
        self._halt = True

    def getInput(self):
        return self._input

    # get cursor position (index in a line)
    def getCursor(self):
        return self._cursorPos
    
    # set cursor position (screen coordinates)
    def setCursor(self, x, y):
        self._cursorXY = (x,y)

    def submitFn(self, fn):
        self._onSubmit = fn

    def metaFn(self, fn):
        self._onMeta = fn

