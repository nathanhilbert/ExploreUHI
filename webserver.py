
# coding: utf-8

# In[1]:

import os

import tornado.ioloop
import tornado.web
import tornado.concurrent
import tornado.autoreload

from bokeh.plotting import figure
from bokeh.embed import components

from dateutil.parser import parse as dateparser
from datetime import timedelta


import psycopg2

import json

from time import time

# from sockjs.tornado import SockJSConnection, SockJSRouter, proto

import urllib



class IndexHandler(tornado.web.RequestHandler):
    """Regular HTTP handler to serve the ping page"""
    def get(self):
        self.render('index.html')

class SearchCitiesHandler(tornado.web.RequestHandler):
    def get(self):
        q = self.get_argument('term') 
        q = "%%" + q.lower() + "%%"
        db = psycopg2.connect(dbname="urbis", user="postgres", password="postgres", host="localhost")
        cursor = db.cursor()
        cursor.execute("""SELECT 
              neurban.id as urbanid, 
                (array_agg(
                  tplace.name || ', ' || tstates.name order by St_Area(tplace.geom) desc
                ))[1] as placename
            FROM 
              public.natearth_urbanareas_10m as neurban, 
              public.tigerlineplaces as tplace,
              public.tigerlinestates as tstates
             WHERE St_Intersects(neurban.geom, tplace.geom) AND tplace.statefp=tstates.statefp AND 
             LOWER(tplace.name) LIKE %s
             GROUP BY neurban.id ORDER BY placename LIMIT 20""", (q,))

        result = {'data': []}
        for r in cursor:
            result['data'].append({'value': r[0], 'text': r[1]})
            # result[r[1]] = r[0]
        cursor.close()
        self.write(result) 


class GetUrbanGeojson(tornado.web.RequestHandler):
    def get(self):
        q = self.get_argument('id') 
        db = psycopg2.connect(dbname="urbis", user="postgres", password="postgres", host="localhost")
        cursor = db.cursor()
        cursor.execute("""SELECT 
          neurban.id, 
          ST_AsGeoJSON(neurban.geom) as urban,
          ST_AsGeoJSON(ST_Difference(ST_Buffer(neurban.geom, sqrt(St_Area(neurban.geom)/pi())), neurban.geom)) as buffer
        FROM 
          public.natearth_urbanareas_10m as neurban
        WHERE neurban.id=%s LIMIT 1;""", (int(q),))

        template =   { "type": "FeatureCollection",
                    "features": [
                       ]
                     }
        obj = cursor.next()
        urbangeo = json.loads(obj[1])
        urbangeo['properties'] = {
            'id': obj[0],
            'urbanmean': 7.34,
            'type': 'urban'
        }
        buffergeo = json.loads(obj[2])
        buffergeo['properties'] = {
            'id': obj[0],
            'buffermean': 5.65,
            'type': 'buffer'
        }
        template['features'].append(urbangeo)
        template['features'].append(buffergeo)


        self.write(template)
        cursor.close()
        # result = {'data': []}
        # for r in cursor:
        #     result['data'].append({'value': r[0], 'text': r[1]})
        #     # result[r[1]] = r[0]
        # cursor.close()
        # self.write(result) 


class GetBokeh(tornado.web.RequestHandler):
    """docstring for ClassName"""
    def get(self):
        q = self.get_argument('id') 
        db = psycopg2.connect(dbname="urbis", user="postgres", password="postgres", host="localhost")
        cursor = db.cursor()
        cursor.execute("""SELECT 
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
        WHERE urbid=%s AND datatype='tmin' ORDER BY year,day""", (int(q),))
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
        for r in cursor:
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
        




if __name__ == "__main__":
    import logging
    logging.getLogger().setLevel(logging.DEBUG)

    # Create application
    app = tornado.web.Application(
            [(r"/", IndexHandler),
            (r"/searchcities", SearchCitiesHandler),
            (r"/geturban", GetUrbanGeojson),
            (r"/getbokeh", GetBokeh),
            (r'/bower_components/(.*)', tornado.web.StaticFileHandler, {'path': os.path.join(os.path.dirname(__file__), "bower_components"),}),]
        )
    app.listen(9999)

    print 'Listening on 0.0.0.0:9999'

    tornado.autoreload.start(io_loop=None, check_time=500)
    tornado.autoreload.watch('index.html')

    tornado.ioloop.IOLoop.instance().start()


# In[ ]:



