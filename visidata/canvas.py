
from collections import defaultdict, Counter

# layers:
# - PixelCanvas: the actual pixels on the screen.
#   - width/height are exactly equal to the number of pixels displayable, and can change at any time.
#   - needs to refresh from source on resize.
#   - no cursor

# - UnitCanvas: a virtual display of arbitrary dimensions
#   - uses units convenient to the app
#   - allows zooming in/out
#   - has a cursor, of arbitrary position and width/height (not restricted to current zoom)

#   - 

# - GraphSheet: specific application, draws to UnitCanvas (inverted Y)

# - MapSheet: Units are lat/long?


# pixels covering whole actual terminal
#  all x/y/w/h in PixelCanvas are pixel coordinates
class PixelCanvas(Sheet):
    columns=[Column('')]  # to eliminate errors outside of draw()
    def __init__(self, name, *sources, **kwargs):
        super().__init__(name, *sources, **kwargs)
        self.pixels = defaultdict(lambda: defaultdict(Counter)) # [y][x] = { attr: count, ... }
        self.strings = []  # (x, y, text, attr)
        self.setPixelDimensions()

    def setPixelDimensions(self):
        self.pix_leftx = left_margin_chars*2
        self.pix_rightx = self.pixelWidth-right_margin_chars*2
        self.pix_topy = 0
        self.pix_bottomy = self.pixelHeight-bottom_margin_chars*4

    def plotpixel(self, x, y, attr):
        self.pixels[y][x].append(attr)

    def plotline(self, x1, y1, x2, y2, attr):
        'Draws onscreen segment of line from (x1, y1) to (x2, y2)'
        xdiff = max(x1, x2) - min(x1, x2)
        ydiff = max(y1, y2) - min(y1, y2)
        xdir = 1 if x1 <= x2 else -1
        ydir = 1 if y1 <= y2 else -1

        r = round(max(xdiff, ydiff))

        for i in range(r+1):
            x = x1
            y = y1

            if r:
                y += ydir * (i * ydiff) / r
                x += xdir * (i * xdiff) / r

            self.plotpixel(round(x), round(y), attr)

    def plotlabel(self, x, y, text, attr):
        self.strings.append((x, y, text, attr))

    def withinCursor(self, x, y):
        'No cursor on base PixelCanvas; override in subclass to provide cursor.'
        return False

    @property
    def cursorPixelBounds(self):
        'Returns pixel bounds of cursor as [ left, top, right, bottom ]'
        return [ 0, 0, 0, 0 ]

    def withinBounds(self, x, y, bbox):
        left, top, right, bottom = bbox
        return x >= left and \
               x <= right and \
               y >= top and \
               y <= bottom

    def draw(self, scr):
        scr.erase()

        cursorBBox = self.cursorPixelBounds

        for char_y in range(0, self.nVisibleRows+1):
            for char_x in range(0, vd().windowWidth):
                block_colors = [
                    self.pixels[char_y*4  ].get(char_x*2, None),
                    self.pixels[char_y*4+1].get(char_x*2, None),
                    self.pixels[char_y*4+2].get(char_x*2, None),
                    self.pixels[char_y*4  ].get(char_x*2+1, None),
                    self.pixels[char_y*4+1].get(char_x*2+1, None),
                    self.pixels[char_y*4+2].get(char_x*2+1, None),
                    self.pixels[char_y*4+3].get(char_x*2, None),
                    self.pixels[char_y*4+3].get(char_x*2+1, None)
                ]
                pow2 = 1
                braille_num = 0
                for c in block_colors:
                    if c:
                        braille_num += pow2
                    pow2 *= 2

                if braille_num != 0:
                    only_colors = list(c for c in block_colors if c)
                    attr = Counter(only_colors).most_common(1)[0][0]
                else:
                    attr = 0

                if self.withinBounds(char_x*2, char_y*4, cursorBBox):
                    attr, _ = colors.update(attr, 0, options.color_current_row, 10)

                scr.addstr(char_y, char_x, chr(0x2800+braille_num), attr)

        if options.show_graph_labels:
            for pix_x, pix_y, txt, attr in self.labels:
                clipdraw(scr, int(pix_y/4), int(pix_x/2), txt, attr, len(txt))



# x and y are always in grid units
class GridCanvas(PixelCanvas):
    commands = [
        Command('h', 'sheet.cursorGridLeft -= charGridWidth', ''),
        Command('l', 'sheet.cursorGridLeft += charGridWidth', ''),
        Command('j', 'sheet.cursorGridTop += charGridHeight', ''),
        Command('k', 'sheet.cursorGridTop -= charGridHeight', ''),

        Command('H', 'sheet.cursorGridWidth -= 1', ''),
        Command('L', 'sheet.cursorGridWidth += 1', ''),
        Command('J', 'sheet.cursorGridHeight += 1', ''),
        Command('K', 'sheet.cursorGridHeight -= 1', ''),

        Command('Z', 'zoom()', 'zoom into cursor'),
        Command('+', 'zoom(1.1)', 'zoom in 10%'),
        Command('-', 'zoom(0.9)', 'zoom out 10%'),
    ]
    def __init__(self):
        # bounding box of entire grid, updated when adding point/line/label or recalcBounds
        self.gridLeft, self.gridTop = None, None  # derive first bounds on first draw
        self.gridWidth, self.gridHeight = None, None

        # bounding box of visible grid
        self.visibleGridLeft
        self.visibleGridTop
        self.visibleGridWidth
        self.visibleGridHeight

        # bounding box of cursor (should be contained within visible grid?)
        self.cursorGridLeft, self.cursorTopValue = None, None
        self.cursorGridWidth, self.cursorHeightValue = None, None

        # the width/height (in grid units) of a single character 'cell' in the terminal
        self.charGridWidth, self.charGridHeight = None, None

        self.points = []  # list of (grid_x, grid_y, attr)
        self.lines = []   # list of (grid_x1, grid_y1, grid_x2, grid_y2, attr)
        self.labels = []  # list of (grid_x, grid_y, label, attr)

    @property
    def pixelGridWidth(self):
        'Width in grid units of a single character cell in the terminal'
        return self.visibleGridWidth/self.pixelWidth

    @property
    def pixelGridHeight(self):
        'Height in grid units of a single character cell in the terminal'
        return self.visibleGridHeight/self.pixelHeight

    @property
    def cursorPixelBounds(self):
        return [ self.scaleX(self.cursorGridLeft),
                 self.scaleY(self.cursorGridTop),
                 self.scaleX(self.cursorGridLeft+self.cursorGridWidth),
                 self.scaleY(self.cursorGridTop+self.cursorGridHeight)
        ]

    def checkBounds(self, x, y):
        if self.gridLeft is None or x < self.gridLeft:     self.grifLeft = x
        if self.gridTop is None or y < self.gridTop:       self.gridTop = y
        if self.gridWidth is None or x > self.gridRight:   self.gridWidth = x-self.gridLeft
        if self.gridHeight is None or y > self.gridBottom: self.gridHeight = y-self.gridTop

    def point(self, x, y, colorname):
        checkBounds(x, y)
        self.points.append(x, y, colors[colorname])

    def line(self, x1, y1, x2, y2, colorname):
        checkBounds(x1, y1)
        checkBounds(x2, y2)
        self.lines.append(x1, y1, x2, y2, colors[colorname])

    def label(self, x, y, text, colorname):
        checkBounds(x, y)
        self.labels.append(x, y, text, colors[colorname])

    def zoom(self, amt=None):
        if amt is None:  # zoom to cursor
            self.visibleGridLeft = self.cursorGridLeft
            self.visibleGridTop = self.cursorGridTop
            self.visibleGridWidth = self.cursorGridWidth
            self.visibleGridHeight = self.cursorGridHeight
        else:
            self.visibleGridWidth *= amt
            self.visibleGridHeight *= amt

    def checkCursor(self):
        # scroll if cursor not entirely visible (and scrolling would help)
        return False

    def scaleX(self, x):
        'returns pixel x coordinate on PixelCanvas'
        return (x-self.visibleGridLeft)*self.pixelWidth/(self.visibleGridWidth)

    def scaleY(self, y):
        'returns pixel y coordinate on PixelCanvas'
        return (y-self.visibleGridTop)*self.pixelHeight/(self.visibleGridHeight)

    def refresh(self):
        'plots points and lines and text onto the PixelCanvas'
        for x, y, attr in Progress(self.points):
            self.plotpixel(self.scaleX(x), self.scaleY(y), attr)

        for x1, y1, x2, y2, attr in Progress(self.lines):
            self.plotline(self.scaleX(x1), self.scaleY(y1), self.scaleX(x2), self.scaleY(y2), attr)

        for x, y, text, attr in Progress(self.labels):
            self.plotlabel(self.scaleX(x), self.scaleY(y), text, attr)

