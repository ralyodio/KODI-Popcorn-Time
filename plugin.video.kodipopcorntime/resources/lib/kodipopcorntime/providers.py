import os, glob
from kodipopcorntime.common import RESOURCES_PATH

def get_providers():
    providers = {'movies':[],'meta':[],'sub':[]}
    for f in glob.glob(os.path.join(RESOURCES_PATH, 'lib', 'kodipopcorntime', 'providers', 'movie.*')):
        t = os.path.basename(f).split('.')
        if not len(t) == 3 or t[0] not in ['movies', 'meta', 'sub']:
            continue
        providers[t[0]].append('%s.%s' %(t[0], t[1]))
    return providers

PROVIDERS = get_providers()