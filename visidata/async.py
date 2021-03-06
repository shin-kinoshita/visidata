import ctypes
import threading
import pstats
import cProfile

from .vdtui import *

min_task_time_s = 0.10 # only keep tasks that take longer than this number of seconds

option('profile_tasks', True, 'profile async tasks')
option('min_memory_mb', 0, 'minimum memory to continue loading and async processing')

globalCommand('^C', 'cancelThread(*sheet.currentThreads or error("no active threads on this sheet"))', 'abort all tasks on current sheet')
globalCommand('g^C', 'cancelThread(*vd.threads or error("no threads"))', 'abort all secondary tasks')
globalCommand('^T', 'vd.push(vd.tasksSheet)', 'open Tasks Sheet')
globalCommand('^_', 'toggleProfiling(threading.current_thread())', 'turn profiling on for main process')

class ProfileSheet(TextSheet):
    commands = TextSheet.commands + [
        Command('z^S', 'profile.dump_stats(input("save profile to: ", value=name+".prof"))', 'save profile'),
    ]
    def __init__(self, name, pr):
        super().__init__(name, getProfileResults(pr).splitlines())
        self.profile = pr

def toggleProfiling(t):
    if not t.profile:
        t.profile = cProfile.Profile()
        t.profile.enable()
        status('profiling of main task enabled')
    else:
        t.profile.disable()
        status('profiling of main task disabled')


# define @async for potentially long-running functions
#   when function is called, instead launches a thread
#   ENTER on that row pushes a profile of the thread

class ThreadProfiler:
    def __init__(self, thread):
        self.thread = thread
        if options.profile_tasks:
            self.thread.profile = cProfile.Profile()
        else:
            self.thread.profile = None

    def __enter__(self):
        if self.thread.profile:
            self.thread.profile.enable()
        return self

    def __exit__(self, exc_type, exc_val, tb):
        if self.thread.profile:
            self.thread.profile.disable()

        # remove very-short-lived async actions
        if elapsed_s(self.thread) < min_task_time_s:
            vd().threads.remove(self.thread)


@functools.wraps(vd().toplevelTryFunc)
def threadProfileCode(vdself, func, *args, **kwargs):
    'Profile @async tasks if `options.profile_tasks` is set.'
    with ThreadProfiler(threading.current_thread()) as prof:
        try:
            prof.thread.status = threadProfileCode.__wrapped__(vdself, func, *args, **kwargs)
        except EscapeException as e:
            prof.thread.status = e

def getProfileResults(pr):
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s)
    ps.strip_dirs()
    ps.sort_stats('cumulative')
    ps.print_stats()
    return s.getvalue()

def cancelThread(*threads, exception=EscapeException):
    'Raise exception on another thread.'
    for t in threads:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(t.ident), ctypes.py_object(exception))


SheetsSheet.commands += [
    Command('^C', 'cancelThread(*cursorRow.currentThreads)', 'abort all threads on sheet at cursor'),
]

SheetsSheet.columns += [
    ColumnAttr('threads', 'currentThreads', type=len),
]

# each row is an augmented threading.Thread object
class TasksSheet(Sheet):
    rowtype = 'threads'
    commands = [
        Command('d', 'cancelThread(cursorRow)', 'abort task at current row'),
        Command('^C', 'd'),
        Command(ENTER, 'vd.push(ProfileSheet(cursorRow.name+"_profile", cursorRow.profile))', 'push profile sheet for this action'),
    ]
    columns = [
        ColumnAttr('name'),
        Column('process_time', type=float, getter=lambda col,row: elapsed_s(row)),
        ColumnAttr('profile'),
        ColumnAttr('status'),
    ]
    def reload(self):
        self.rows = vd().threads

def elapsed_s(t):
    return (t.endTime or time.process_time())-t.startTime

def checkMemoryUsage(vs):
    min_mem = options.min_memory_mb
    if min_mem and vd().unfinishedThreads:
        tot_m, used_m, free_m = map(int, os.popen('free --total --mega').readlines()[-1].split()[1:])
        ret = '[%dMB]' % free_m
        if free_m < min_mem:
            attr = 'red'
            status('%dMB free < %dMB minimum, stopping threads' % (free_m, min_mem))
            cancelThread(*vd().unfinishedThreads)
            curses.flash()
        else:
            attr = 'green'
        return ret, attr

vd().tasksSheet = TasksSheet('task_history')
vd().toplevelTryFunc = threadProfileCode
vd().addHook('rstatus', checkMemoryUsage)

