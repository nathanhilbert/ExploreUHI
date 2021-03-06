
# coding: utf-8

# In[1]:

import os

import tornado.ioloop
import tornado.web
import tornado.concurrent
import tornado.autoreload

from bokeh.plotting import figure
from bokeh.embed import components
from sqlalchemy import create_engine

import numpy as np


from dateutil.parser import parse as dateparser
from datetime import timedelta, datetime

import json

from time import time

# from sockjs.tornado import SockJSConnection, SockJSRouter, proto

import urllib


import random


from dataprocessors import processor

APPPOSTGRESURI = os.environ.get("HIPOSTGRESAPP", 'postgresql://urbis:urbis@localhost:5432/urbisapp')
POSTGRESURI = os.environ.get("HIPOSTGRES", 'postgresql://urbis:urbis@localhost:5432/urbis')

class IndexHandler(tornado.web.RequestHandler):
    """Regular HTTP handler to serve the ping page"""
    def get(self):
        self.render('index.html')

class DaymetMap(tornado.web.RequestHandler):
    """Regular HTTP handler to serve the ping page"""
    def get(self):
        self.render('daymetmap.html')


class JobSubmit(tornado.web.RequestHandler):
    def post(self):
        theargs = self.request.arguments
        print theargs
        processor.apply_async(args=(theargs,))
        # print self.get_body_argument("data")
        # mydata = self.get_arguments("data")
        self.write(theargs)
    def get(self):
        self.write({"jobs": {}})

class JobReSubmit(tornado.web.RequestHandler):
    def post(self):
        jobid = self.get_argument('jobid')
        appengine = create_engine(APPPOSTGRESURI)
        sql = """SELECT inputdata FROM heatislandui.jobs WHERE id={0}""".format(jobid)
        rowresult = appengine.execute(sql)
        for r in rowresult:
            inputdata = r[0]
            break
        processor.apply_async(args=(inputdata,jobid,))
        self.write("success")


class SearchCitiesHandler(tornado.web.RequestHandler):
    def get(self):
        q = self.get_argument('term') 
        q = q.lower()
        appengine = create_engine(POSTGRESURI)

        rowresult = appengine.execute("""
            SELECT placeid, label FROM urbanclusters.cityoptions WHERE LOWER(label) LIKE '%%{0}%%' LIMIT 20""".format(q))

        result = {'data': []}
        for r in rowresult:
            result['data'].append({'id': r[0], 'text': r[1]})
            # result[r[1]] = r[0]
        # cursor.close()
        self.write(result) 


# class GetUrbanGeojson(tornado.web.RequestHandler):
#     def get(self):
#         q = self.get_argument('id') 
#         appengine = create_engine(POSTGRESURI)

#         rowresult = appengine.execute("""SELECT 
#           neurban.id, 
#           ST_AsGeoJSON(neurban.geom) as urban,
#           ST_AsGeoJSON(ST_Difference(ST_Buffer(neurban.geom, sqrt(St_Area(neurban.geom)/pi())), neurban.geom)) as buffer
#         FROM 
#           public.natearth_urbanareas_10m as neurban
#         WHERE neurban.id={0} LIMIT 1;""".format(int(q)))

#         template =   { "type": "FeatureCollection",
#                     "features": [
#                        ]
#                      }
#         obj = rowresult.next()
#         urbangeo = json.loads(obj[1])
#         urbangeo['properties'] = {
#             'id': obj[0],
#             'urbanmean': 7.34,
#             'type': 'urban'
#         }
#         buffergeo = json.loads(obj[2])
#         buffergeo['properties'] = {
#             'id': obj[0],
#             'buffermean': 5.65,
#             'type': 'buffer'
#         }
#         template['features'].append(urbangeo)
#         template['features'].append(buffergeo)


#         self.write(template)
#         # cursor.close()
#         # result = {'data': []}
#         # for r in cursor:
#         #     result['data'].append({'value': r[0], 'text': r[1]})
#         #     # result[r[1]] = r[0]
#         # cursor.close()
#         # self.write(result) 


class GetBokeh(tornado.web.RequestHandler):
    """docstring for ClassName"""
    def get(self):
        q = self.get_argument('id') 
        appengine = create_engine(POSTGRESURI)

        rowresult = appengine.execute("""SELECT 
          urbanareas_daymet.id, 
          urbanareas_daymet.placename, 
          urbanareas_daymet.urbanmean, 
          urbanareas_daymet.buffermean, 
          urbanareas_daymet.urbanstdev, 
          urbanareas_daymet.bufferstdev, 
          urbanareas_daymet.urbancount, 
          urbanareas_daymet.buffercount, 
          urbanareas_daymet.datatype, 
          urbanareas_daymet.year, 
          urbanareas_daymet.day, 
          urbanareas_daymet.urbid
        FROM 
          public.urbanareas_daymet
        WHERE urbid={0} AND datatype='tmin' ORDER BY year,day""".format(int(q)))
        xdata = []
        uydata = []
        bydata = []
        ustdmin = []
        ustdmax = []
        bstdmin = []
        bstdmax = []
        cityname = None

        firstdataday = dateparser("1980-01-01")
        counter = 0
        for r in rowresult:
            cityname = r[1]
            xdata.append(firstdataday + timedelta(days=counter))
            counter +=1


            # xdata.append(int(str(r[9])[2:] + str(r[10]).zfill(3)))
            uydata.append(r[2])
            ustdmin.append(r[2] - r[4])
            ustdmax.append(r[2] + r[4])
            bydata.append(r[3])
            bstdmin.append(r[3] - r[5])
            bstdmax.append(r[3] + r[5])
            
        # uydatadf = pd.DataFrame(uydata)
        # bydatadf = pd.DataFrame(bydata)

        # umean = uydatadf.rolling(window=7,center=False).mean()
        # bmean = bydatadf.rolling(window=7, center=False).mean()

        p1 = figure(title="TempMin for {0} of Daymet".format(cityname), 
                    x_axis_type="datetime",
                     plot_width=1200, 
                     plot_height=500)
        p1.xaxis.axis_label = 'Date'
        p1.yaxis.axis_label = 'MinDailyTemp'

        p1.line(xdata, uydata, color='#A6CEE3', legend='Urban')
        p1.line(xdata, bydata, color='#B2DF8A', legend='Buffer')
        p1.rect(xdata, ustdmax, 0.2, 0.01, line_color="black")
        p1.rect(xdata, ustdmin, 0.2, 0.01, line_color="black")
        # p1.segment(xdata, ustdmax, xdata, uydata, line_width=2, line_color="black")
        # p1.segment(xdata, ustdmin, xdata, uydata, line_width=2, line_color="black")
        # p1.line(datetime(IBM['date']), IBM['adj_close'], color='#33A02C', legend='IBM')
        # p1.line(datetime(MSFT['date']), MSFT['adj_close'], color='#FB9A99', legend='MSFT')

        p1.legend.location = "top_left"

        # output_notebook()


        script, div = components(p1)

        self.write({
            'div': div,
            'script': script
            })


from osgeo import gdal, gdalnumeric, ogr, osr
from PIL import Image, ImageDraw
import os, sys
import os.path as op
from pyproj import Proj, transform
def clipper(raster_file, bbox):
    DAYMETSTORAGE = '/Volumes/UrbisBackup/rasterstorage/daymet'
    measure = 'tmin'

    def world2Pixel(geoMatrix, x, y):
      """
      Uses a gdal geomatrix (gdal.GetGeoTransform()) to calculate
      the pixel location of a geospatial coordinate
      """
      ulX = geoMatrix[0]
      ulY = geoMatrix[3]
      xDist = geoMatrix[1]
      yDist = geoMatrix[5]
      rtnX = geoMatrix[2]
      rtnY = geoMatrix[4]
      pixel = int((x - ulX) / xDist)
      line = int((ulY - y) / xDist)
      return (pixel, line)

    # Also load as a gdal image to get geotransform
    # (world file) info
    raster_path = op.join(DAYMETSTORAGE, measure, \
                                 raster_file)
    srcArray = gdalnumeric.LoadFile(raster_path)

    srcImage = gdal.Open(raster_path)
    geoTrans = srcImage.GetGeoTransform()


    # Convert the layer extent to image pixel coordinates
    tminX, tmaxX, tminY, tmaxY = bbox

    outProj = Proj(init='epsg:3857')
    inProj = Proj(init='epsg:4326')

    minX,minY = transform(inProj,outProj,tminX,tminY)
    maxX,maxY = transform(inProj,outProj,tmaxX,tmaxY)



    ulX, ulY = world2Pixel(geoTrans, minX, maxY)
    lrX, lrY = world2Pixel(geoTrans, maxX, minY)

    # Calculate the pixel size of the new image
    pxWidth = int(lrX - ulX)
    pxHeight = int(lrY - ulY)


    clip = srcArray[ulY:lrY, ulX:lrX]
    img = Image.new('RGBA',(len(clip), len(clip[0])))


    minval= np.min(clip)
    maxval= np.max(clip)

    newarray = np.uint8((clip/np.max(clip)) * 255)
    # inverted_im = Image.fromarray(newarray, mode='L')

    rgbArray = np.zeros((len(clip), len(clip[0]),3), 'uint8')

    minimum, maximum = float(np.min(clip)), float(np.max(clip))
    ratio = (clip - minimum) / (maximum-minimum)
    print ratio
    b = 255*(1 - ratio)
    r = 255*(ratio - 1)
    # g = 255 - abs(b - r)
    rgbArray[..., 0] = r
    # rgbArray[..., 1] = g
    rgbArray[..., 2] = b

    img2 = Image.fromarray(rgbArray)
    return img2

from StringIO import StringIO

class TileViewer(tornado.web.RequestHandler):
    def get(self):

        q = self.get_argument('bbox')
        dater = dateparser(self.get_argument('daymetdate'))
        daymettimetuple = dater.timetuple()
        year = daymettimetuple.tm_year
        day = daymettimetuple.tm_yday
        raster_filename = "daymet_v3_{0}_{1}_{2}.tif".format('tmin', year,day)

        bboxarray = q.split(",")
        self.set_header("Content-Type", 'image/png')
        img = clipper(raster_filename, bboxarray)
        zdata = StringIO()

        img.save(zdata, 'PNG')
        self.write(zdata.getvalue())
        self.finish()
        

class JobsViewer(tornado.web.RequestHandler):
    """docstring for ClassName"""

    def get(self):
        self.render('jobs.html')
    def post(self):
        appengine = create_engine(APPPOSTGRESURI)
        sql = """SELECT id, status, starttime, endtime FROM heatislandui.jobs"""
        result = appengine.execute(sql)
        setresult = []
        for r in result:
            setresult.append({'id':r[0], 'status':r[1], 'starttime':str(r[2]), 'endtime':str(r[3])})
        self.write({'data':setresult})




class ResultViewer(tornado.web.RequestHandler):
    """docstring for ClassName"""
    def get(self):
        self.render('results.html')

    def post(self):
        jobid = self.get_argument('jobid') 

        appengine = create_engine(APPPOSTGRESURI)
        sql = """SELECT id, inputdata, results  FROM heatislandui.jobs WHERE id={0}""".format(jobid)
        result = appengine.execute(sql)
        resultrow = result.first()
        resultobj = resultrow[2]
        # resultobj = json.loads(resultrow[2])
        # print resultobj

        features = []
        for placeresult in resultobj.values():
            features.append(json.loads(placeresult['results']['info']['urbangeom']))
            features.append(json.loads(placeresult['results']['info']['buffergeom']))

        geojson =   { "type": "FeatureCollection",
            "features": features,
                'crs': {
                  'type': 'name',
                  'properties': {
                      'name': 'urn:ogc:def:crs:EPSG::3857'
                    }
                  }
             }

        #get a temp first place value to find rasterkeys
        tempp = resultobj.values()[0]

        bokehvizes = []
        #result types for the temporal rasters
        rastertypes = [x for x in tempp['results'].keys() if x in ('prismresults', 'daymetresults',)]
        measurekeys = [x for x in tempp['results'][rastertypes[0]]['results'].keys()]

        for measure in tempp['results'][rastertypes[0]]['results'].keys():

            p1 = figure(title=measure, 
                     x_axis_type="datetime",
                      plot_width=1200, 
                      plot_height=500)
            p1.xaxis.axis_label = 'Date'
            p1.yaxis.axis_label = 'DiffDailyTemp'

            datearray = []
            for d in tempp['results'][rastertypes[0]]['dates']:
                ds = d.split("-")
                datearray.append(datetime(int(ds[0]), 1, 1) + timedelta(int(ds[1]) - 1))


            for placeresult in resultobj.values():
                daymetresults = placeresult['results']['daymetresults']
                prismresults = placeresult['results']['prismresults']

                umeanfloat = [float(x) for x in daymetresults['results'][measure]["urbanextentresults"]['mean']]
                bmeanfloat = [float(x) for x in daymetresults['results'][measure]["bufferextentresults"]['mean']]

                uhivaluedaymet = np.array(umeanfloat) - np.array(bmeanfloat)

                try:

                    umeanfloat = [float(x) for x in prismresults['results']["prism" + measure]["urbanextentresults"]['mean']]
                    bmeanfloat = [float(x) for x in prismresults['results']["prism" + measure]["bufferextentresults"]['mean']]

                    uhivalueprism = np.array(umeanfloat) - np.array(bmeanfloat)
                except:
                    uhivalueprism = None


                r = lambda: random.randint(0,255)
                randomcolor = '#%02X%02X%02X' % (r(),r(),r())
                p1.line(datearray, uhivaluedaymet , color=randomcolor, legend=placeresult['label'] + "-daymet")
                if uhivalueprism != None:
                    randomcolor = '#%02X%02X%02X' % (r(),r(),r())
                    p1.line(datearray, uhivalueprism , color=randomcolor, legend=placeresult['label'] + "-prism")
                # p1.rect(resultobj["daymetresults"]['daymetdates'], ustdmax, 0.2, 0.01, line_color="black")
                # p1.rect(resultobj["daymetresults"]['daymetdates'], ustdmin, 0.2, 0.01, line_color="black")
                # p1.segment(xdata, ustdmax, xdata, uydata, line_width=2, line_color="black")
                # p1.segment(xdata, ustdmin, xdata, uydata, line_width=2, line_color="black")
                # p1.line(datetime(IBM['date']), IBM['adj_close'], color='#33A02C', legend='IBM')
                # p1.line(datetime(MSFT['date']), MSFT['adj_close'], color='#FB9A99', legend='MSFT')

            p1.legend.location = "top_left"

            script, div = components(p1)

            bokehvizes.append({
                'script': script,
                'div': div
                })

        rasterdatastring = ""
        for placeresult in resultobj.values():
            rasterdatastring += "<h5>" + placeresult['label'] + "</h5><br/>" + \
                "<h5>Urban Area: " + str(placeresult['results']['info']['urbanarea']) + "</h5><br/>" + \
                "<h5>Buffer Area: " + str(placeresult['results']['info']['bufferarea']) + "</h5><br/>" +\
            json.dumps(placeresult['results']["rasterresults"], indent=4, sort_keys=True)\
            .replace("\n", "<br>").replace('\r', '&nbsp;&nbsp;')


        self.write({'inputdata':resultrow[1],
                    'geojson':geojson,
                    'rasterresults': rasterdatastring,
                    'bokeh':bokehvizes
                    })




if __name__ == "__main__":
    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    APPPOSTGRESURI = os.environ.get("HIPOSTGRESAPP", 'postgresql://urbis:urbis@localhost:5432/urbisapp')
    POSTGRESURI = os.environ.get("HIPOSTGRES", 'postgresql://urbis:urbis@localhost:5432/urbis')

    # Create application
    app = tornado.web.Application(
            [(r"/", IndexHandler),
            (r"/daymetmap", DaymetMap),
            (r"/searchcities", SearchCitiesHandler),
            (r"/jobsubmit", JobSubmit),
            (r"/jobresubmit", JobReSubmit),
            (r"/jobs", JobsViewer),
            (r"/job", ResultViewer),
            (r"/tiler", TileViewer),
            (r"/getbokeh", GetBokeh),
            (r'/bower_components/(.*)', tornado.web.StaticFileHandler, {'path': os.path.join(os.path.dirname(__file__), "bower_components"),}),]
        )
    app.listen(9999)

    print 'Listening on 0.0.0.0:9999'

    tornado.autoreload.start(io_loop=None, check_time=500)
    tornado.autoreload.watch('index.html')
    tornado.autoreload.watch('jobs.html')
    tornado.autoreload.watch('results.html')

    tornado.ioloop.IOLoop.instance().start()


# In[ ]:



