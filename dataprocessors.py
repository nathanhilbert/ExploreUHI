
# coding: utf-8

# Prase from HeatIslandsUI in Urbis folder as a working example
# ------------

# In[1]:

# uidata = {'startdate': ['1980/07/01'], 
#           'tmin': ['tmin'], 
#           'impervious': ['impervious'], 
#           'diurnal': ['diurnal'], 
#           'tmax': ['tmax'], 
#           'cityvalue': ['24283', '54322'], 
#           'landscanpopulation': ['landscanpopulation'], 
#           'citiesselect': ['Cleveland, Tennessee'], 
#           'extentbuffer': ['1'], 
#           'grump2015': ['grump2015'], 
#           'fixedbuffer': [''], 
#           'enddate': ['1980/07/15'],
#            'urbandef':['landscan']}

from celery import Celery

app = Celery('dataprocessors', broker='redis://localhost:6379/0')


import os
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

    print "DOING THIS"

    # In[2]:

    POSTGRESURI = os.environ.get("HIPOSTGRES", 'postgresql://urbis:urbis@localhost:5432/urbis')

    APPPOSTGRESURI = os.environ.get("HIPOSTGRESAPP", 'postgresql://urbis:urbis@localhost:5432/urbisapp')
    
    appengine = create_engine(APPPOSTGRESURI)
    jobid = randint(0,9999999)
    sql = """INSERT INTO heatislandui.jobs (id, inputdata, status, starttime) VALUES ({0},'{1}', 'running', now())""".format(jobid, json.dumps(uidata))
    appengine.execute(sql)


    try:


        engine = create_engine(POSTGRESURI)

        sql = "SELECT placeid, label FROM urbanclusters.cityoptions WHERE placeid IN ({0})".format(",".join(uidata['cityvalue[]']))
        results = engine.execute(sql)
        places = [{'placeid': row[0], 'label': row[1]} for row in results]
        print "Looking at {0}".format(str(places))


        # In[3]:

        #set up the datasets required

        EXTENTTABLES = {'landscan':'urbanclusters.landscan_urbannamed',
             'grump':'urbanclusters.grump_urbannamed',
            'naturalearth':'urbanclusters.ne_10m_urbannamed',
            'globcover': 'urbanclusters.globcover_urbannamed',
            'earthenv': 'urbanclusters.earthenv_urbannamed'
            }
        #get the table for the selection of the urban clusters
        urbanextenttable = EXTENTTABLES.get(uidata['urbandef'][0], 'urbanclusters.landscan_urbannamed')



        # In[4]:



        def get_geom_from_postgis(tablename, placeid):

            conn = engine.connect()
            sql = """
            SELECT ST_AsEWKB(geom), ST_AsGeoJson(geom) AS geom, ST_Area(geom) as area FROM {0}
            WHERE placeid={1}
            """.format(tablename, placeid)
            result = conn.execute(sql)
            row = result.first()
            conn.close()
            return wkb.loads(str(row[0])), row[1], row[2] 

        def get_geom_from_postgis_buffer(tablename, placeid, value, fixed=False):

            conn = engine.connect()
            if fixed:
                sql = """
                    SELECT ST_AsEWKB(ST_Difference(
                        ST_Buffer(geom, {0})
                        , geom)) AS geom,
                        ST_AsGeoJson(ST_Difference(
                        ST_Buffer(geom, {0})
                        , geom)) AS geom,
                        ST_Area(ST_Difference(
                        ST_Buffer(geom, {0})
                        , geom)) AS area
                        FROM {1}
                    WHERE placeid={2}
                    """.format(value, tablename, placeid)
            else:
                sql = """
                 SELECT ST_AsEWKB(ST_Difference(ST_Buffer(geom, (sqrt(2*St_Area(geom)/pi())-sqrt(St_Area(geom)/pi()))), geom)) AS geom,
                     ST_AsGeoJson(ST_Difference(ST_Buffer(geom, (sqrt(2*St_Area(geom)/pi())-sqrt(St_Area(geom)/pi()))), geom)) AS geom,
                    ST_Area(ST_Difference(ST_Buffer(geom, (sqrt(2*St_Area(geom)/pi())-sqrt(St_Area(geom)/pi()))), geom)) AS area
                    FROM {1}
                WHERE placeid={2}
            """.format(value, tablename, placeid)
            result = conn.execute(sql)
            row = result.first()
            conn.close()
            return wkb.loads(str(row[0])), row[1], row[2] 
        
        def processplace(placeid, urbanextenttable, uidata):
            BASERASTERPATH = os.environ.get("HIRASTERBASE", '/data/rasterstorage')

            RASTERSETS = {'grump2000': 'grump/population2000.json', 
                          'grump2005': 'grump/population2005.json', 
                          'grump2010': 'grump/population2010.json',
                          'grump2015': 'grump/population2015.json',
                          'grump2020': 'grump/population2020.json',
                          'landscanpopulation': 'landscan/landscan.json',
                          'impervious': 'nlcd/impervious/nlcd_impervious_2011.json',
                          'nlcd': 'nlcd/landcover/nlcd_landcover_2011.json'
                          }
            #               'nlcd/impervious/nlcd_impervious_2001.json',
            #              'nlcd/impervious/nlcd_impervious_2006.json',


            DAYMETSTORAGE = os.environ.get("HIDAYMET", '/Volumes/UrbisBackup/rasterstorage/daymet')
            DAYMETVALS = ['tmin','tmax']

            
            results = get_geom_from_postgis(urbanextenttable, placeid)
            urbanextentgeom = from_series(pd.Series([results[0]]))
            urbanextentgeomjson = results[1]
            urbanextentarea = results[2]


            bufferextentgeom = None
            bufferextentgeomjson = None
            if uidata['extentbuffer']:
                results = get_geom_from_postgis_buffer(urbanextenttable, placeid, float(uidata['extentbuffer'][0]))
                bufferextentgeom = from_series(pd.Series([results[0]]))
                bufferextentgeomjson = results[1]
                bufferextentarea = results[2]
            elif uidata['fixedbuffer']:
                results = get_geom_from_postgis_buffer(urbanextenttable, placeid, int(uidata['fixedbuffer'][0]), True)
                bufferextentgeom = from_series(pd.Series([results[0]]))
                bufferextentgeomjson = results[1]
                bufferextentarea = results[2]

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
                            'std': float(result.values.std()),
                            'weightedsum': float((result.values * result.weights).sum()),
                            'min': float(result.values.min()),
                            'max': float(result.values.max())
    #                         'valuecounts': dict(result.value_counts())
                            }
                        if bufferextentgeomjson:
                            result = tempr.query(bufferextentgeom).next()
                            rasterresults[rasterkey]['bufferextent'] = {
                                'sum': float(result.values.sum()),
                                'mean': float(result.values.mean()),
                                'weightedmean': float((result.values * result.weights).sum() / result.weights.sum()),
                                'std': float(result.values.std()),
                                'weightedsum': float((result.values * result.weights).sum()),
                                'min': float(result.values.min()),
                                'max': float(result.values.max())
    #                             'valuecounts': dict(result.value_counts())
                                }
                    except Exception,e:
                        traceback.print_exc()
                        print e

                        pass


            # In[13]:


            STARTDATE = uidata.get('startdate', [''])[0]
            ENDDATE = uidata.get('enddate', [''])[0]

            starttime = dateparser(STARTDATE)

            numberdays = dateparser(ENDDATE) - starttime

            daymetdaterng = pd.date_range(starttime, periods=numberdays.days+1, freq='D')

            # def get_day_year_from_str(strdate):
            #     startdatetup = dateparser(strdate).timetuple()
            #     return startdatetup.tm_year, startdatetup.tm_yday

            # if STARTDATE and ENDDATE:
            #     startyear, startday = get_day_year_from_str(STARTDATE)
            #     endyear, endday = get_day_year_from_str(ENDDATE)


            # In[18]:
            DAYMETSTORAGE = os.environ.get("HIDAYMET", '/Volumes/UrbisBackup/rasterstorage/daymet')
            DAYMETVALS = ['tmin','tmax']
            # daymetpath = '/Users/nlh/sharedata/rasterstorage/daymet/tmin'
            daymetdates = []

            
            daymetresults = {}
            for measure in DAYMETVALS:
                urbanextentresults = {
                        'std':[],
                        'mean':[],
                        'min':[],
                        'max':[]
                }

                bufferextentresults = {
                        'std':[],
                        'mean':[],
                        'min':[],
                        'max':[]
                }

                if not uidata.get(measure, False):
                    continue
                for daymetdate in daymetdaterng:
                    daymettimetuple = daymetdate.timetuple()
                    year = daymettimetuple.tm_year
                    day = daymettimetuple.tm_yday

                    print "doing {0},{1}".format(year, day)
                    try:
                        raster = read_raster(op.join(DAYMETSTORAGE, measure, \
                                                     "daymet_v3_{0}_{1}_{2}.tif".format(measure, year,day)))
                    except Exception,e:
                        print e
                        print "daymet_v3_{0}_{1}_{2}.tif Does not exist in the file system".format(measure,year,day)
                        continue
                    daymetdates.append("{0}-{1}".format(year,day))
                    result = raster.query(urbanextentgeom).next()

                    urbanextentresults['std'].append(float(result.values.std()))
                    urbanextentresults['mean'].append(float(result.values.mean()))
                    urbanextentresults['min'].append(float(result.values.min()))
                    urbanextentresults['max'].append(float(result.values.max()))

                    if bufferextentgeomjson:
                        result = raster.query(bufferextentgeom).next()
                        bufferextentresults['std'].append(float(result.values.std()))
                        bufferextentresults['mean'].append(float(result.values.mean()))
                        bufferextentresults['min'].append(float(result.values.min()))
                        bufferextentresults['max'].append(float(result.values.max()))
                daymetresults[measure] = {
                    'urbanextentresults': urbanextentresults,
                    'bufferextentresults': bufferextentresults
                }

            results = {}
            results['rasterresults'] = rasterresults

            results['daymetresults'] = {
                'daymetdates': daymetdates,
                'results': daymetresults
            }
            results['info'] = {
                'placeid': placeid,
                'urbangeom': urbanextentgeomjson,
                'buffergeom': bufferextentgeomjson,
                'bufferarea': bufferextentarea,
                'urbanarea': urbanextentarea
            }
            return results

        
        finalresults = {}
        for place in places:
            finalresults[place['placeid']] = {
                'label': place['label'],
                'results': None
            }
            finalresults[place['placeid']]['results'] = processplace(place['placeid'], urbanextenttable, uidata)



        sql = """UPDATE heatislandui.jobs SET results='{0}', status='complete', endtime=now() WHERE id={1}""".format(json.dumps(finalresults), jobid)
        appengine.execute(sql)
    except Exception,e:
        print "ERROR:"
        print e
        sql = """UPDATE heatislandui.jobs SET status='error' WHERE id={0}""".format(jobid)
        appengine.execute(sql)



    # In[ ]:



