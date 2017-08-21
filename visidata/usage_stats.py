from visidata import Path

fnUsageStats = '~/.visidata_usage'
#POST_SERVER = 'usage.vd.saul.pw'
POST_URL = 'https://hooks.zapier.com/hooks/catch/2262717/r2qo88/'

def saveUsageData(editlog):
    fn = Path(fnUsageStats).resolve()
    import json
    try:
        counts = json.load(open(fn, 'r'))
    except:
        counts = { 'commands': {} }

    try:
        cmds = counts.get('commands', {})
        for _, k, _, _, _ in editlog.rows:
            cmds[k] = cmds.get(k, 0) + 1
        counts['commands'] = cmds
        json.dump(counts, open(fn, 'w'))
    except:
        raise
        pass


def sendUsageData():
    from urllib.request import urlopen
    import datetime
    import json
    data = {
            'date': datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
        'content': str(json.loads(Path(fnUsageStats).read_text()))
    }
    urlopen(POST_URL, data=json.dumps(data).encode('utf-8'))

if __name__ == '__main__':
    sendUsageData()
