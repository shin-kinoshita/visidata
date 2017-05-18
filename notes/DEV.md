## General notes to aid development

### debugging

- `^E` pushes a stack trace sheet for the most recent exception.
- `^Q` quits immediately, dumping the last stack trace if there is one.  It is the only keystroke handled explicitly in the event loop, useful when the command system itself is broken.
- `^O` pushes the result of an eval, evaluated in the same context as commands and column eval expressions.  This is the raw Python object, and ENTER will push new object sheet for the current attribute.

## Adding a new command

Just add a `command()` call at the toplevel of an addon:

        command('N', 'notes.rows.append(cursorValue)', 'append value in cell at cursor to notes sheet')

The first argument is the keystroke(s) needed to invoke the command.  This must be the exact string
returned by `curses.keyname` for the keystroke (this is what is displayed in the lower right corner after every command).  A prefix (only 1 for now) may be included before the main keystroke.

The code in the `execstr` (second argument) is exec()ed with the visadata module globals (including all previously exec()ed .py files), and the current sheet as locals.
In addition, `sheet` is mapped to itself, and `vd` is mapped to the singleton VisiData object.
In the visidata module namespace there are a few global functions for convenience:

    - `input(prompt, type="")`: reads a string from the bottom line, using history of the given type.
    - `status(msg)`: shows the given msg on the bottom row.
    - `error(msg)`: raises an Exception with the given msg.  Useful for lambda functions since `raise` is a statement.


Notes and gotchas:
- generator expressions don't work in command execstrs.  I've preferred using lambda functions but then you have to remember to bind the variables manually.

## Loaders

Two methods:

### 1. open_<ext> function returning Sheet().

If the source is simple and doesn't allow any further interaction (like csv), then `def`ine an `open_` and a `load_` function that take a Path object and return a Sheet.  This function opens a fictional .foo format:

        def open_foo(path):
            vs = Sheet(path.name, path)
            vs.loader = lambda vs=vs: load_foo(vs)
            return vs

load_foo takes a sheet to load into, and knows that the .source member variable contains a Path.

        def load_foo(vs):
            with self.source.open_text() as fp:
                ncols, nrows = fp.readline().split()
                vs.columns = ArrayColumns(int(ncols))
                vs.progressTotal = int(nrows)
                vs.rows = []
                for i in range(int(nrows)):
                    vs.progressMade = i
                    vs.rows.append([x for x in fp.readline().split('bar')])

            status('finished loading')

* add the @async decorator to any loaders which can be run asynchronously:
    * Set .columns before adding rows.  So that rows are shown properly during loading.
    * Set .rows = [] (empty list) at outset and add rows one at a time with .append(), so that the rows can be viewed and rearranged while still loading.
    * do not depend on the rows list staying in the same order.  i.e. only use .append().  If you want to modify the rows after adding them, store a ref to the row itself elsewhere and modify the row object through that.
    * Set .progressTotal to some reasonable estimate of the total, and increment .progressMade during the loop.  Make sure .progressTotal and .progressMade are equal at the end of the load or the progress indicator will never go away.
    * show some status (like `status('loaded')`) when done
* Use options.headerlines to use the first few rows as column names, if applicable.

* Loaders can provide sheet-specific commands by calling `self.command`

use self.command in __init__ or reload() to create sheet-specific commands.  Define ENTER to create a more detailed sheet from the cursorRow.

        self.command(ENTER, 'vd.push(DivingSheet(self.name+"_dive", cursorRow))', 'dive into this row')

### 2. Sheet subclass

        class DivingSheet(Sheet):
            # The default Sheet.__init__(self, name, *sources) will work for many types of sheets
            @async
            def reload(self):
                # just like the load_foo function above, but using self.source
                ...

# make a test

create the essential input files (foo1.csv/tsv with headers)
use vd to create the command history foo.vd file (includes 'o' foo1.csv etc)
save foo_output.csv

'foo' should be unique prefix.

