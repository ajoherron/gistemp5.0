# GHCN data
GHCN_temp_url = 'https://data.giss.nasa.gov/pub/gistemp/ghcnm.tavg.qcf.dat'
GHCN_meta_url = 'https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt'

# Rules
drop_rules = '''
CHM00052836  omit: 0-1948
CHXLT909860  omit: 0-1950
BL000085365  omit: 0-1930
MXXLT948335  omit: 0-1952
ASN00058012  omit: 0-1899
ASN00084016  omit: 0-1899
ASN00069018  omit: 0-1898
NIXLT013080  omit: 0-1930
NIXLT751359  omit: 0-9999
CHXLT063941  omit: 0-1937
CHM00054843  omit: 0-1937
MXM00076373  omit: 0-9999
USC00044022  omit: 0-9999
USC00044025  omit: 0-9999
CA002402332  omit: 2011-9999
RSM00024266  omit: 2021/09
'''