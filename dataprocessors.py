
# coding: utf-8

# Prase from HeatIslandsUI in Urbis folder as a working example
# ------------

# In[1]:

# uidata = {'startdate': ['1980/07/01'], 
#           'tmin': ['tmin'], 
#           'impervious': ['impervious'], 
#           'diurnal': ['diurnal'], 
#           'tmax': ['tmax'], 
#           'cityvalue': '24283', 
#           'landscanpopulation': ['landscanpopulation'], 
#           'citiesselect': ['Cleveland, Tennessee'], 
#           'extentbuffer': ['1'], 
#           'grump2015': ['grump2015'], 
#           'fixedbuffer': [''], 
#           'enddate': ['1980/07/15'],
#            'urbandef':['landscan']}

from celery import Celery

app = Celery('dataprocessors', broker='redis://localhost:6379/0')



from sqlalchemy import create_engine
from shapely import wkb
from pyspatial.vector import from_series
import pandas as pd
import os.path as op
import json
from pyspatial.raster import read_catalog, read_raster
import traceback
from dateutil.parser import parse as dateparser

from random import randint

@app.task
def processor(uidata):

    # In[2]:

    POSTGRESURI = 'postgresql://urbis:urbis@localhost:5432/urbis'
    

    APPPOSTGRESURI = 'postgresql://urbis:urbis@localhost:5432/urbisapp'

    appengine = create_engine(APPPOSTGRESURI)
    jobid = randint(0,9999999)
    sql = """INSERT INTO jobs (id, inputdata, status) VALUES ({0},'{1}', 'running')""".format(jobid, json.dumps(uidata))
    appengine.execute(sql)





    engine = create_engine(POSTGRESURI)

    sql = "SELECT placeid, label FROM urbanclusters.cityoptions WHERE placeid = {0}".format(uidata['cityvalue'][0])
    results = engine.execute(sql)
    placeid, label = results.first()
    print "Looking at {0} with id {1}".format(label, placeid)


    # In[3]:

    #set up the datasets required

    EXTENTTABLES = {'landscan':'urbanclusters.landscan_urbannamed',
         'grump':'urbanclusters.grump_urbannamed',
        'naturalearth':'urbanclusters.ne_10m_urbannamed'
        }
    urbanextenttable = EXTENTTABLES.get(uidata['cityvalue'][0], 'urbanclusters.landscan_urbannamed')
            
            



    BASERASTERPATH = '/data/rasterstorage'

    RASTERSETS = {'grump2000': 'grump/population2000.json', 
                  'grump2005': 'grump/population2005.json', 
                  'grump2010': 'grump/population2010.json',
                  'grump2015': 'grump/population2015.json',
                  'grump2020': 'grump/population2020.json',
                  'landscanpopulation': 'landscan/landscan.json',
                  'impervious': 'nlcd/impervious/nlcd_impervious_2011.json'
                  }
    #               'nlcd/impervious/nlcd_impervious_2001.json',
    #              'nlcd/impervious/nlcd_impervious_2006.json',
                 

    DAYMETSTORAGE = '/Volumes/UrbisBackup/rasterstorage/daymet'
    DAYMETVALS = ['tmin','tmax']


    # In[4]:



    def get_geom_from_postgis(tablename, placeid):

        conn = engine.connect()
        sql = """
        SELECT ST_AsEWKB(geom), ST_AsGeoJson(geom) AS geom FROM {0}
        WHERE placeid={1}
        """.format(tablename, placeid)
        result = conn.execute(sql)
        row = result.first()
        conn.close()
        return wkb.loads(str(row[0])), row[1] 

    def get_geom_from_postgis_buffer(tablename, placeid, value, fixed=False):

        conn = engine.connect()
        if fixed:
            sql = """
                SELECT ST_AsEWKB(ST_Difference(
                    ST_Buffer(geom, {0})
                    , geom)) AS geom,
                    ST_AsGeoJson(ST_Difference(
                    ST_Buffer(geom, {1})
                    , geom)) AS geom
                    FROM {2}
                WHERE placeid={3}
                """.format(value, value, tablename, placeid)
        else:
            sql = """
            SELECT ST_AsEWKB(ST_Difference(
                ST_Buffer(geom, (sqrt(St_Area(geom)/pi())* {0}))
                , geom)) AS geom,
                ST_AsGeoJson(ST_Difference(
                ST_Buffer(geom, (sqrt(St_Area(geom)/pi())* {1}))
                , geom)) AS geom
                FROM {2}
            WHERE placeid={3}
        """.format(value, value, tablename, placeid)
        result = conn.execute(sql)
        row = result.first()
        conn.close()
        return wkb.loads(str(row[0])), row[1] 



    results = get_geom_from_postgis(urbanextenttable, placeid)
    urbanextentgeom = from_series(pd.Series([results[0]]))
    urbanextentgeomjson = results[1]


    bufferextentgeom = None
    bufferextentgeomjson = None
    if uidata['extentbuffer']:
        results = get_geom_from_postgis_buffer(urbanextenttable, placeid, float(uidata['extentbuffer'][0]))
        bufferextentgeom = from_series(pd.Series([results[0]]))
        bufferextentgeomjson = results[1]
    elif uidata['fixedbuffer']:
        results = get_geom_from_postgis_buffer(urbanextenttable, placeid, int(uidata['fixedbuffer'][0]), True)
        bufferextentgeom = from_series(pd.Series([results[0]]))
        bufferextentgeomjson = results[1]
        

            


    # In[11]:


    rasterresults = {}


    print bufferextentgeom
    for rasterkey in RASTERSETS.keys():
        if uidata.get(rasterkey, None):
            try:
                tempr = read_catalog(op.join(BASERASTERPATH, RASTERSETS[rasterkey]))
                rasterresults[rasterkey] = {}
                result = tempr.query(urbanextentgeom).next()
                rasterresults[rasterkey]['urbanextent'] = {
                    'sum': float(result.values.sum()),
                    'mean': float(result.values.mean()),
                    'weightedmean': float((result.values * result.weights).sum() / result.weights.sum()),
                    'std': float(result.values.std())
                    }
                if bufferextentgeomjson:
                    result = tempr.query(bufferextentgeom).next()
                    rasterresults[rasterkey]['bufferextent'] = {
                        'sum': float(result.values.sum()),
                        'mean': float(result.values.mean()),
                        'weightedmean': float((result.values * result.weights).sum() / result.weights.sum()),
                        'std': float(result.values.std())
                        }
            except Exception,e:
                traceback.print_exc()
                print e
                
                pass


    # In[13]:

    
    STARTDATE = uidata.get('startdate', [''])[0]
    ENDDATE = uidata.get('enddate', [''])[0]

    def get_day_year_from_str(strdate):
        startdatetup = dateparser(strdate).timetuple()
        return startdatetup.tm_year, startdatetup.tm_yday

    if STARTDATE and ENDDATE:
        startyear, startday = get_day_year_from_str(STARTDATE)
        endyear, endday = get_day_year_from_str(ENDDATE)

    print startyear, startday
    print endyear, endday


    # In[18]:



    DAYMETSTORAGE = '/Volumes/UrbisBackup/rasterstorage/daymet'
    DAYMETVALS = ['tmin','tmax', 'diurnal']
    # daymetpath = '/Users/nlh/sharedata/rasterstorage/daymet/tmin'
    daymetdates = []
    urbanextentresults = {
        'tmin':{
            'std':[],
            'mean':[],
            'min':[],
            'max':[]
        },
        'tmax':{
            'std':[],
            'mean':[],
            'min':[],
            'max':[]
        },
        'diurnal':{
            'std':[],
            'mean':[],
            'min':[],
            'max':[]
        }
    }

    bufferextentresults = {
        'tmin':{
            'std':[],
            'mean':[],
            'min':[],
            'max':[]
        },
        'tmax':{
            'std':[],
            'mean':[],
            'min':[],
            'max':[]
        },
        'diurnal':{
            'std':[],
            'mean':[],
            'min':[],
            'max':[]
        }
    }


    # daymet_v3_tmin_1980_1.tif
    for year in range(startyear, endyear+1):
        for day in range(startday, endday):
            print "doing {0},{1}".format(year, day)
            raster = read_raster(op.join(DAYMETSTORAGE, 'tmin', "daymet_v3_tmin_{0}_{1}.tif".format(year,day)))
            daymetdates.append("{0}-{1}".format(year,day))
            result = raster.query(urbanextentgeom).next()
            urbanextentresults['tmin']['std'].append(float(result.values.std()))
            urbanextentresults['tmin']['mean'].append(float(result.values.mean()))
            urbanextentresults['tmin']['min'].append(float(result.values.min()))
            urbanextentresults['tmin']['max'].append(float(result.values.max()))
            
            if bufferextentgeomjson:
                result = raster.query(bufferextentgeom).next()
                bufferextentresults['tmin']['std'].append(float(result.values.std()))
                bufferextentresults['tmin']['mean'].append(float(result.values.mean()))
                bufferextentresults['tmin']['min'].append(float(result.values.min()))
                bufferextentresults['tmin']['max'].append(float(result.values.max()))

    results = {}
    results['rasterresults'] = rasterresults

    results['daymetresults'] = {
        'daymetdates': daymetdates,
        'urbanextentresults': urbanextentresults,
        'bufferextentresults': bufferextentresults
    }
    results['info'] = {
        'label': label,
        'placeid': placeid,
        'urbangeom': urbanextentgeomjson,
        'buffergeom': bufferextentgeomjson
    }



    sql = """UPDATE jobs SET results='{0}', status='complete' WHERE id={1}""".format(json.dumps(results), jobid)
    appengine.execute(sql)


    # In[ ]:



