
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
        Command('w', 'options.show_graph_labels = not options.show_graph_labels', 'toggle show_graph_labels'),
        Command('KEY_RESIZE', 'refresh()', ''),
    ]
    def __init__(self, name, *sources, **kwargs):
        super().__init__(name, *sources, **kwargs)
        self.pixels = defaultdict(lambda: defaultdict(Counter)) # [y][x] = { attr: count, ... }
        self.labels = []  # (x, y, text, attr)
        self.rows = [1]  # something for cursorRowIndex
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
               x < right and \
               y >= top and \
               y < bottom

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

                    if self.withinBounds(char_x*2, char_y*4, cursorBBox) or \
                       self.withinBounds(char_x*2+1, char_y*4+3, cursorBBox):
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
        Command('h', 'sheet.cursorGridLeft -= cursorGridWidth', ''),
        Command('l', 'sheet.cursorGridLeft += cursorGridWidth', ''),
        Command('j', 'sheet.cursorGridTop += cursorGridHeight', ''),
        Command('k', 'sheet.cursorGridTop -= cursorGridHeight', ''),

        Command('zh', 'sheet.cursorGridLeft -= charGridWidth', ''),
        Command('zl', 'sheet.cursorGridLeft += charGridWidth', ''),
        Command('zj', 'sheet.cursorGridTop += charGridHeight', ''),
        Command('zk', 'sheet.cursorGridTop -= charGridHeight', ''),

        Command('gH', 'sheet.cursorGridWidth /= 2', ''),
        Command('gL', 'sheet.cursorGridWidth *= 2', ''),
        Command('gJ', 'sheet.cursorGridHeight /= 2', ''),
        Command('gK', 'sheet.cursorGridHeight *= 2', ''),

        Command('H', 'sheet.cursorGridWidth -= charGridWidth', ''),
        Command('L', 'sheet.cursorGridWidth += charGridWidth', ''),
        Command('J', 'sheet.cursorGridHeight += charGridHeight', ''),
        Command('K', 'sheet.cursorGridHeight -= charGridHeight', ''),

        Command('Z', 'zoom()', 'zoom into cursor'),
        Command('+', 'sheet.zoomlevel *= 1/1.2; resetVisibleGrid()', 'zoom in 20%'),
        Command('-', 'sheet.zoomlevel *= 1.2; resetVisibleGrid()', 'zoom out 20%'),
        Command('0', 'sheet.zoomlevel = 1.0; resetVisibleGrid()', 'zoom to fit full extent'),

        Command('BUTTON1_PRESSED', 'sheet.cursorGridLeft, sheet.cursorGridTop = gridMouse', ''),
        Command('BUTTON1_CLICKED', 'BUTTON1_PRESSED', ''),
        Command('BUTTON1_RELEASED', 'setCursorSize(*gridMouse)', ''),
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

        self.zoomlevel = 1.0

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
    def gridMouse(self):
        gridX = self.visibleGridLeft + (self.mouseX-self.gridCanvasLeft/2)*2*self.visibleGridWidth/self.gridCanvasWidth
        gridY = self.visibleGridTop + (self.gridCanvasBottom/4-self.mouseY-1)*4*self.visibleGridHeight/self.gridCanvasHeight
        return gridX, gridY

    def setCursorSize(self, gridX, gridY):
        'sets width based on other side x and y'
        if gridX > self.cursorGridLeft:
            self.cursorGridWidth = gridX - self.cursorGridLeft
        else:
            self.cursorGridWidth = self.cursorGridLeft - gridX
            self.cursorGridLeft = gridX

        if gridY > self.cursorGridTop:
            self.cursorGridHeight = gridY - self.cursorGridTop
        else:
            self.cursorGridHeight = self.cursorGridTop - gridY
            self.cursorGridTop = gridY

    @property
    def charGridWidth(self):
        'Width in grid units of a single char in the terminal'
        return self.visibleGridWidth*2/self.gridCanvasWidth

    @property
    def charGridHeight(self):
        'Height in grid units of a single char in the terminal'
        return self.visibleGridHeight*4/self.gridCanvasHeight

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

    def resetVisibleGrid(self):
        # point to zoom in closer to
        centerx = self.cursorGridLeft + self.cursorGridWidth/2
        centery = self.cursorGridTop + self.cursorGridHeight/2

        self.visibleGridWidth = self.gridWidth*self.zoomlevel
        self.visibleGridHeight = self.gridHeight*self.zoomlevel
        self.visibleGridLeft = centerx - self.visibleGridWidth/2
        self.visibleGridTop = centery - self.visibleGridHeight/2

        self.refresh()

    def checkCursor(self):
        'scroll to make cursor visible'
        return False

    def scaleX(self, x):
        'returns canvas x coordinate'
        return round(self.gridCanvasLeft+(x-self.visibleGridLeft)*self.gridCanvasWidth/self.visibleGridWidth)

    def scaleY(self, y):
        'returns canvas y coordinate'
        return round(self.gridCanvasTop+(y-self.visibleGridTop)*self.gridCanvasHeight/self.visibleGridHeight)

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

            self.cursorGridLeft = self.visibleGridLeft
            self.cursorGridTop = self.visibleGridTop
            self.cursorGridWidth = self.charGridWidth
            self.cursorGridHeight = self.charGridHeight

        for x, y, attr in Progress(self.gridpoints):
            self.plotpixel(self.scaleX(x), self.scaleY(y), attr)

        for x1, y1, x2, y2, attr in Progress(self.gridlines):
            self.plotline(self.scaleX(x1), self.scaleY(y1), self.scaleX(x2), self.scaleY(y2), attr)

        for x, y, text, attr in Progress(self.gridlabels):
            self.plotlabel(self.scaleX(x), self.scaleY(y), text, attr)

