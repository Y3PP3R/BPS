#!/usr/bin/env python
from miniboa import TelnetServer
import urllib2, time, socket, json, httplib
from datetime import datetime, timedelta

from notification import mailer


#globals
JSON_DOMAIN = "www.batavierenrace.nl"
JSON_PATH = "/cdb/gpsdata/rvd2011.php"
GEONAMES_USERNAME = "batapositioning"
CLIENT_LIST = []
MAILER = None

#read config file
def load_configuration(self, config_file):
    file = open(config_file)
    config = json.load(file)
    file.close()

    return config

# gps checksum calc
def chk_chksum(gprmc_str):
  chk = ''
  ref = "0x%s" % gprmc_str[-2:]
  
  for c in gprmc_str:
    if c == '*':
      break
    elif chk == '':
      chk = ord(c)
    else:
      chk = chk ^ ord(c)
  
  return hex(chk).lower() == ref.lower()


def my_on_connect(client):
  print "client connected: %s" % client.address
  CLIENT_LIST.append(client)

def my_on_disconnect(client):
  print "client disconnected: %s" % client.address
  CLIENT_LIST.remove(client)
    
def process_clients():
  for client in CLIENT_LIST:
    if client.active and client.cmd_ready:
      data = client.get_command()
      message = data.split(',')
      str = ','.join(message[2:15])

      print "%s: IMEI = %s" % (time.strftime("%Y-%m-%d %H:%M%S", time.localtime()), message[17][6:])
      if chk_chksum(str):
        print "GPS Data OK"
        
        #===============
        # begin country retrieval      
        url = "http://api.geonames.org/countryCode?lat=%f&lng=%f&username=%s" % (float(message[5])/100,float(message[7])/100, GEONAMES_USERNAME)
        response = urllib2.urlopen(url) 
        country = response.read().strip()
        print "Countrycode = %s" % country
        # end country retrieval
        #===============
        
        
        #===============
        # begin battery calculation
        bat =  float(message[20][2:6]) - 3.65
        rest = bat / (4.15 - 3.65) * 100

        print "battery = %.1f%%" % rest

        if rest < 200:
          MAILER.low_battery(message[17][6:])
        
        # end battery calculation
        #===============
        
        #================
        # start json object building    
        delta = timedelta(minutes=1)
        timestamp = (datetime.utcnow()-delta).isoformat()
        print "timestamp = %s" % timestamp

        lat = float(message[5])
        lon = float(message[7])

        lat = int(lat / 100) + ((lat - (int((lat / 100)) * 100)) / 60)
        lon = int(lon / 100) + ((lon - (int((lon / 100)) * 100)) / 60)
        speed = 1.85 * float(message[9])

        output = {}
        output['id'] = message[17][6:]
        output['timestamp'] = timestamp
        output['latitude'] = "%f" % lat
        output['longitude'] = "%f" % lon
        output['speed'] = "%f" % speed
        output['direction'] = message[10]

        enc = json.JSONEncoder(indent = 4)
        json_out = enc.encode(output)
           
        headers = {"Content-type": "application/json", "Accept": "application/json; charset=utf8"}
        conn = httplib.HTTPConnection(JSON_DOMAIN)
        conn.request("POST", JSON_PATH, json_out, headers)
        response = conn.getresponse()
        print "%s %s" %(response.status, response.reason)

        # end json
        #===============
        
      else:
        print "GPS Data Error"
#===============================================================

if __name__ == "__main__":
  config = load_configuration(os.path.dirname(__file__) + os.sep + 'config.json')
  MAILER = mailer(config['from_address'], config['notify'])
  server = TelnetServer(port=config['port'], address=socket.gethostbyname(socket.gethostname()), on_connect=my_on_connect, on_disconnect=my_on_disconnect)
  #server = TelnetServer(port=9999, address='192.168.2.137', on_connect=my_on_connect, on_disconnect=my_on_disconnect)
  
  print "\n\nStarting server on port %d.  CTRL-C to interrupt.\n" % server.port
  while True:
      server.poll()
      process_clients()
