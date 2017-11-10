
from collections import defaultdict, Counter
from visidata import *

# The Canvas covers the entire terminal (minus the status line).
# The Grid is arbitrarily large (a virtual cartesian coordinate system).
# The visibleGrid is what is actively drawn onto the terminal.
# The gridCanvas is the area of the canvas that contains that visibleGrid.
# The gridAxes are drawn outside the gridCanvas, on the left and bottom.

# Canvas and gridCanvas coordinates are pixels at the same scale (gridCanvas are offset to leave room for axes).
# Grid and visibleGrid coordinates are app-specific units.

# plotpixel()/plotline()/plotlabel() take Canvas pixel coordinates
# point()/line()/label() take Grid coordinates

option('show_graph_labels', True, 'show axes and legend on graph')


# pixels covering whole actual terminal
#  - width/height are exactly equal to the number of pixels displayable, and can change at any time.
#  - needs to refresh from source on resize
#  - all x/y/w/h in PixelCanvas are pixel coordinates
#  - override cursorPixelBounds to specify a cursor (none by default)
class PixelCanvas(Sheet):
    columns=[Column('')]  # to eliminate errors outside of draw()
    commands=[
        Command('^L', 'refresh()', 'redraw all pixels on canvas'),
        Command('KEY_RESIZE', 'resetCanvasDimensions(); refresh()', 'redraw all pixels on canvas'),
        Command('w', 'options.show_graph_labels = not options.show_graph_labels', 'toggle show_graph_labels')
    ]
    def __init__(self, name, *sources, **kwargs):
        super().__init__(name, *sources, **kwargs)
        self.pixels = defaultdict(lambda: defaultdict(Counter)) # [y][x] = { attr: count, ... }
        self.labels = []  # (x, y, text, attr)
        self.resetCanvasDimensions()

    def resetCanvasDimensions(self):
        'sets total available canvas dimensions'
        self.canvasTop = 0
        self.canvasLeft = 0
        self.canvasWidth = vd().windowWidth*2
        self.canvasHeight = (vd().windowHeight-1)*4  # exclude status line

    def plotpixel(self, x, y, attr):
        self.pixels[round(y)][round(x)][attr] += 1

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
        self.labels.append((x, y, text, attr))

    @property
    def canvasBottom(self):
        return self.canvasTop+self.canvasHeight

    @property
    def canvasRight(self):
        return self.canvasLeft+self.canvasWidth

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

    def getPixelAttr(self, x, y):
        r = self.pixels[y].get(x, None)
        if r is None:
            return 0
        else:
            return r.most_common(1)[0][0]

    def draw(self, scr):
        scr.erase()

        if self.pixels:
            cursorBBox = self.cursorPixelBounds

            for char_y in range(0, self.nVisibleRows+1):
                for char_x in range(0, vd().windowWidth):
                    block_attrs = [
                        self.getPixelAttr(char_x*2  , char_y*4  ),
                        self.getPixelAttr(char_x*2  , char_y*4+1),
                        self.getPixelAttr(char_x*2  , char_y*4+2),
                        self.getPixelAttr(char_x*2+1, char_y*4  ),
                        self.getPixelAttr(char_x*2+1, char_y*4+1),
                        self.getPixelAttr(char_x*2+1, char_y*4+2),
                        self.getPixelAttr(char_x*2  , char_y*4+3),
                        self.getPixelAttr(char_x*2+1, char_y*4+3),
                    ]

                    pow2 = 1
                    braille_num = 0
                    for c in block_attrs:
                        if c:
                            braille_num += pow2
                        pow2 *= 2

                    if braille_num != 0:
                        attr = Counter(c for c in block_attrs if c).most_common(1)[0][0]
                    else:
                        attr = 0

                    if self.withinBounds(char_x*2, char_y*4, cursorBBox):
                        attr, _ = colors.update(attr, 0, options.color_current_row, 10)

                    scr.addstr(char_y, char_x, chr(0x2800+braille_num), attr)

        if options.show_graph_labels:
            for pix_x, pix_y, txt, attr in self.labels:
                clipdraw(scr, int(pix_y/4), int(pix_x/2), txt, attr, len(txt))


# virtual display of arbitrary dimensions
# - x/y/w/h are always in grid units (units convenient to the app)
# - allows zooming in/out
# - has a cursor, of arbitrary position and width/height (not restricted to current zoom)
class GridCanvas(PixelCanvas):
    leftMarginPixels = 10*2
    rightMarginPixels = 6*2
    topMarginPixels = 0
    bottomMarginPixels = 2*4  # reserve bottom line for x axis

    commands = PixelCanvas.commands + [
        Command('h', 'sheet.cursorGridLeft -= pixelGridWidth', ''),
        Command('l', 'sheet.cursorGridLeft += pixelGridWidth', ''),
        Command('j', 'sheet.cursorGridTop += pixelGridHeight', ''),
        Command('k', 'sheet.cursorGridTop -= pixelGridHeight', ''),

        Command('H', 'sheet.cursorGridWidth -= 1', ''),
        Command('L', 'sheet.cursorGridWidth += 1', ''),
        Command('J', 'sheet.cursorGridHeight += 1', ''),
        Command('K', 'sheet.cursorGridHeight -= 1', ''),

        Command('Z', 'zoom()', 'zoom into cursor'),
        Command('+', 'zoom(zoomlevel*1.1)', 'zoom in 10%'),
        Command('-', 'zoom(zoomlevel*0.9)', 'zoom out 10%'),
        Command('0', 'zoom(1.0)', 'zoom to fit full extent'),
    ]

    def __init__(self, name, *sources, **kwargs):
        super().__init__(name, *sources, **kwargs)

        # bounding box of entire grid in grid units, updated when adding point/line/label or recalcBounds
        self.gridLeft, self.gridTop = None, None  # derive first bounds on first draw
        self.gridWidth, self.gridHeight = None, None

        # bounding box of visible grid, in grid units
        self.visibleGridLeft = None
        self.visibleGridTop = None
        self.visibleGridWidth = None
        self.visibleGridHeight = None

        # bounding box of cursor (should be contained within visible grid?)
        self.cursorGridLeft, self.cursorGridTop = 0, 0
        self.cursorGridWidth, self.cursorGridHeight = None, None

        # bounding box of gridCanvas, in pixels
        self.gridpoints = []  # list of (grid_x, grid_y, attr)
        self.gridlines = []   # list of (grid_x1, grid_y1, grid_x2, grid_y2, attr)
        self.gridlabels = []  # list of (grid_x, grid_y, label, attr)

    def resetCanvasDimensions(self):
        super().resetCanvasDimensions()
        self.gridCanvasLeft = self.leftMarginPixels
        self.gridCanvasTop = self.topMarginPixels
        self.gridCanvasWidth = self.canvasWidth - self.rightMarginPixels - self.leftMarginPixels
        self.gridCanvasHeight = self.canvasHeight - self.bottomMarginPixels - self.topMarginPixels

    @property
    def pixelGridWidth(self):
        'Width in grid units of a single pixel in the terminal'
        return self.visibleGridWidth/self.gridCanvasWidth

    @property
    def pixelGridHeight(self):
        'Height in grid units of a single pixel in the terminal'
        return self.visibleGridHeight/self.gridCanvasHeight

    @property
    def gridRight(self):
        return self.gridLeft + self.gridWidth

    @property
    def gridBottom(self):
        return self.gridTop + self.gridHeight

    @property
    def visibleGridBottom(self):
        return self.visibleGridTop + self.visibleGridHeight

    @property
    def gridCanvasBottom(self):
        return self.gridCanvasTop + self.gridCanvasHeight

    @property
    def gridCanvasRight(self):
        return self.gridCanvasLeft + self.gridCanvasWidth

    @property
    def cursorPixelBounds(self):
        return [ self.scaleX(self.cursorGridLeft),
                 self.scaleY(self.cursorGridTop),
                 self.scaleX(self.cursorGridLeft+self.cursorGridWidth),
                 self.scaleY(self.cursorGridTop+self.cursorGridHeight)
        ]

    def checkBounds(self, x, y):
        if self.gridLeft is None or x < self.gridLeft:     self.gridLeft = x
        if self.gridTop is None or y < self.gridTop:       self.gridTop = y
        if self.gridWidth is None or x > self.gridRight:   self.gridWidth = x-self.gridLeft
        if self.gridHeight is None or y > self.gridBottom: self.gridHeight = y-self.gridTop

    def point(self, x, y, colorname):
        self.checkBounds(x, y)
        self.gridpoints.append((x, y, colors[colorname]))

    def line(self, x1, y1, x2, y2, colorname):
        self.checkBounds(x1, y1)
        self.checkBounds(x2, y2)
        self.gridlines.append((x1, y1, x2, y2, colors[colorname]))

    def label(self, x, y, text, colorname):
        self.checkBounds(x, y)
        self.gridlabels.append((x, y, text, colors[colorname]))

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
        'scroll to make cursor visible'
        return False

    def scaleX(self, x):
        'returns canvas x coordinate'
        return self.gridCanvasLeft+(x-self.visibleGridLeft)*self.gridCanvasWidth/self.visibleGridWidth

    def scaleY(self, y):
        'returns canvas y coordinate'
        return self.gridCanvasTop+(y-self.visibleGridTop)*self.gridCanvasHeight/self.visibleGridHeight

    @async
    def refresh(self):
        'plots points and lines and text onto the PixelCanvas'
        self.resetCanvasDimensions()
        self.pixels.clear()
        self.labels.clear()

        if self.visibleGridLeft is None:
            self.visibleGridLeft = self.gridLeft
            self.visibleGridWidth = self.gridWidth
            self.visibleGridTop = self.gridTop
            self.visibleGridHeight = self.gridHeight

            self.cursorGridWidth = self.pixelGridWidth
            self.cursorGridHeight = self.pixelGridHeight

        for x, y, attr in Progress(self.gridpoints):
            self.plotpixel(self.scaleX(x), self.scaleY(y), attr)

        for x1, y1, x2, y2, attr in Progress(self.gridlines):
            self.plotline(self.scaleX(x1), self.scaleY(y1), self.scaleX(x2), self.scaleY(y2), attr)

        for x, y, text, attr in Progress(self.gridlabels):
            self.plotlabel(self.scaleX(x), self.scaleY(y), text, attr)

