import SimpleHTTPServer
import SocketServer
import os,pwd,subprocess
import json
import logging
import time
import re
import datetime
import pymongo
from bson.objectid import ObjectId

class HTTPFileServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    def do_POST(self):
        '''
        Serve a Post request for curl.
        post parameter: {"fileserver":"http://192.168.0.1/data/","task":"","testcase":"","ver1":"","ver2":"","ver1_logicdbfile":"","ver2_logicdbfile":"","xodrfile":"","paramfile":""}
        for example:curl -d '{"fileserver":"http://10.69.144.124:8000/data/","task":"QI_testtask","testcase":"QI_testcase","ver1":"2.4.0.1","ver2":"2.3.1.5"}' http://10.69.144.159:8000
        '''
        datas = self.rfile.read(int(self.headers['content-length']))
        print 'post datas: ',datas
        if not self.is_json(datas):
            self.send_error(400, "Please use post agrs as JSON_STR.  eg:\'{\"fileserver\":\"http://192.168.0.1/data/\",\"task\":"",\"testcase\":"",\"ver1\":\"2.4.0.1\",\"ver2\":\"2.3.1.5\"}\'")
        else:
            datas = json.loads(datas)
            #post request is call QI Worker to execute QI test
            if ('fileserver' in datas):
                try:
                    datas['QI_status'] = 'submit'
                    mongodb_insert(datas)
                    self.send_response(200, "QI Worker run success.")
                    self.send_header('Content-type', 'text/html')

                    self.end_headers()
                    self.wfile.write("QI worker is submitted to QI server, please waiting for executed result.")
                except Exception as e:
                    self.send_response(500, "QI Worker run fail.")
                    self.send_header('Content-type', 'text/html')

                    self.end_headers()
                    self.wfile.write("QI worker fail to submitt to QI server, please try it sometime later.")
            #post request is to query QI test execute result: submit/waiting/running/done/error
            #curl -d '{"task":"QI_testtask","testcase":"QI_testcase","ver1":"2.4.0.1","ver2":"2.3.1.5"}'
            else:
                qi_result_cursor = mongodb_find(datas)
                qi_result = []
                for i in qi_result_cursor:
                    qi_result.append(i)
                self.send_response(200)
                self.send_header('Content-type', 'text/html')

                self.end_headers()
                self.wfile.write(qi_result)

    def is_json(self,myjson):
        try:
            json.loads(myjson)
        except ValueError:
            return False
        return True

class XForkingMixIn(SocketServer.ForkingMixIn):
    timeout = 300
    max_children = 30

class XForkingTCPServer(XForkingMixIn, SocketServer.TCPServer): pass
                
def mongodb_find(mongodb_sql):
    '''
    select function in mongodb
    '''
    client = pymongo.MongoClient()
    db = client.QIWorker #connect to QIWorker db
    collection = db.postdata #connect to table postdata
    result = collection.find(mongodb_sql) #result is class 'pymongo.cursor.Cursor' list
    return result

def mongodb_insert(data):
    '''
    insert function in mongodb
    '''
    client = pymongo.MongoClient()
    db = client.QIWorker #connect to QIWorker db
    collection = db.postdata #connect to table postdata
    result = collection.insert(data) #insert function return mongodb data _id
    return result

def mongodb_collection():
    '''
    return mongdb collection
    '''
    client = pymongo.MongoClient()
    db = client.QIWorker #connect to QIWorker db
    collection = db.postdata #connect to table postdata
    return collection

if __name__ == '__main__':
    PORT = 8002
    Handler = HTTPFileServerHandler
    #httpd = SocketServer.ThreadingTCPServer(("", PORT), Handler)
    httpd = XForkingTCPServer(("", PORT), Handler)
    print "Starting HTTP File Server on port", PORT
    httpd.serve_forever()
