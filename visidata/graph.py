from visidata import *

option('color_graph_axis', 'white', 'color for graph axis labels')

globalCommand('m', 'vd.push(GraphSheet(sheet.name+"_graph", selectedRows or rows, keyCols and keyCols[0] or None, cursorCol))', 'graph the current column vs the first key column (or row number)')
globalCommand('gm', 'vd.push(GraphSheet(sheet.name+"_graph", selectedRows or rows, keyCols and keyCols[0], *numericCols(nonKeyVisibleCols)))', 'graph all numeric columns vs the first key column (or row number)')

graphColors = 'green red yellow cyan magenta white 38 136 168'.split()


def numericCols(cols):
    # isNumeric from describe.py
    return [c for c in cols if isNumeric(c)]


# provides unit->pixel conversion, axis labels, legend
class GraphSheet(GridCanvas):
    def __init__(self, name, rows, xcol, *ycols, **kwargs):
        super().__init__(name, rows, **kwargs)
        self.xcol = xcol
        self.ycols = ycols
        if xcol:
            isNumeric(self.xcol) or error('%s type is non-numeric' % xcol.name)
        for col in ycols:
            isNumeric(col) or error('%s type is non-numeric' % col.name)

    def legend(self, i, txt, colorname):
        self.plotlabel(self.canvasRight-30, self.canvasTop+i*4, txt, colors[colorname])

    def scaleY(self, grid_y):
        'returns canvas y coordinate, with y-axis inverted'
        canvas_y = super().scaleY(grid_y)
        return (self.gridCanvasBottom-canvas_y)

    @async
    def reload(self):
        nerrors = 0
        nplotted = 0

        self.gridpoints.clear()

        for i, ycol in enumerate(self.ycols):
            colorname = graphColors[i % len(graphColors)]
            attr = colors[colorname]

            for rownum, row in enumerate(Progress(self.source)):
                try:
                    graph_x = self.xcol.getTypedValue(row) if self.xcol else rownum
                    graph_y = ycol.getTypedValue(row)
                    self.point(graph_x, graph_y, colorname)
                    nplotted += 1
                except EscapeException:
                    raise
                except Exception:
                    exceptionCaught()
                    nerrors += 1

        status('plotted %d points (%d errors)' % (nplotted, nerrors))

        self.refresh()

    def add_y_axis_label(self, frac):
        amt = self.visibleGridTop + frac*(self.visibleGridHeight)
        if isinstance(self.visibleGridTop, int):
            txt = '%d' % amt
        elif isinstance(self.visibleGridTop, float):
            txt = '%.02f' % amt
        else:
            txt = str(frac)

        # plot y-axis labels on the far left of the canvas, but within the gridCanvas height-wise
        self.plotlabel(0, self.gridCanvasTop + (1.0-frac)*self.gridCanvasHeight, txt, colors[options.color_graph_axis])

    def add_x_axis_label(self, frac):
        amt = self.visibleGridLeft + frac*self.visibleGridWidth
        if isinstance(self.visibleGridLeft, int):
            txt = '%d' % round(amt)
        elif isinstance(self.visibleGridLeft, float):
            txt = '%.02f' % amt
        else:
            txt = str(amt)

        # plot x-axis labels below the gridCanvasBottom, but within the gridCanvas width-wise
        self.plotlabel(self.gridCanvasLeft+frac*self.gridCanvasWidth, self.gridCanvasBottom+4, txt, colors[options.color_graph_axis])

    @async
    def refresh(self):
        super().refresh()
        self.create_labels()

    def create_labels(self):
        self.gridlabels = []

        # y-axis
        self.add_y_axis_label(1.00)
        self.add_y_axis_label(0.75)
        self.add_y_axis_label(0.50)
        self.add_y_axis_label(0.25)
        self.add_y_axis_label(0.00)

        # x-axis
        self.add_x_axis_label(1.00)
        self.add_x_axis_label(0.75)
        self.add_x_axis_label(0.50)
        self.add_x_axis_label(0.25)
        self.add_x_axis_label(0.00)

        xname = self.xcol.name if self.xcol else 'row#'
        self.plotlabel(0, self.gridCanvasBottom+4, '%*s»' % (int(self.leftMarginPixels/2-2), xname), colors[options.color_graph_axis])

        for i, ycol in enumerate(self.ycols):
            colorname = graphColors[i]
            self.legend(i, ycol.name, colorname)
