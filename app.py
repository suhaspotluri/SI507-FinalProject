from flask import Flask, render_template, flash, redirect, request, session, url_for
from flask_session import Session
import json
import requests
from config import Config
import mysql.connector
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests_cache
import time
import folium
from datetime import datetime
import openrouteservice
from openrouteservice import convert
import secrets

osr_key=secrets.osr_key
owm_key=secrets.owm_key
db_user=secrets.db_user
db_pw=secrets.db_pw
db_host=secrets.db_host

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config.from_object(__name__)
#Setup caching of requests
requests_cache.install_cache(cache_name='search_cache', backend='sqlite', expire_after=180)

Session(app)
#Setup rate limitter
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
#Function to connect to database
def connect():
    cnx = mysql.connector.connect(user=db_user, password=db_pw,host=db_host,database='tripweather')
    cursor=cnx.cursor(dictionary=True)
    return cnx,cursor

#Funciton to convert time to human readable time
def ctime(time):
    hours = time // 3600
    minutes = time % 60
    return f"{hours}h:{minutes}m"
#Flask Routes:

#Home page, check for login and return users trips 
@app.route("/", methods=['GET', 'POST'])
def home():
    if session.get('login','False')=='True':
        cnx,cursor=connect()
        username=session['username']
        uid=session['user']
        q=f"SELECT * FROM `trips` WHERE `uid`={uid}"
        cursor.execute(q)
        trips=cursor.fetchall()
        print(trips)
        return render_template("home.html", username=username,trips=trips)
    else:
        return redirect(url_for('login'))

#Trip page either delete create or view a trip
@app.route("/trip/<string:action>/<int:tid>", methods=['GET','POST'])
def trip(action,tid):
    if session.get('login','False')=='True':
        username=session['username']
        uid=session['user']
        cnx,cursor=connect()
        if action=='create':
            if request.method == 'POST':
                tname=request.values.get('tname')
                q=f"INSERT INTO `trips` (`tname`, `sdate`, `uid`) VALUES ('{tname}', '{None}', '{uid}')"
                cursor.execute(q)
                cnx.commit()
                tid=cursor.lastrowid
                cnx.close()
                return redirect(f'/trip/view/{tid}')
            else:
                return render_template("trip.html", username=username)
        elif action=='delete':
            q=f"DELETE `trips` FROM `trips` JOIN `users` ON uid=users.id WHERE trips.id={tid} AND users.id={uid}"
            cursor.execute(q)
            cnx.commit()
            cnx.close()
            return redirect(url_for('home'))
        elif action=='view':
            if request.method == 'POST':
                tname=request.values.get('tname')
                sdate=request.values.get('sdate')
                q=f"UPDATE `trips` SET tname='{tname}', sdate='{sdate}' WHERE id={tid}"
                print(q)
                cursor.execute(q)
                cnx.commit()
            q=f"SELECT * FROM `trips` WHERE `id`={tid}"
            cursor.execute(q)
            trip=cursor.fetchone()
            print(trip)
            if trip['sdate'] != None:
                trip['sdate']=trip['sdate'].strftime("%Y-%m-%dT%H:%M:%S")
            q=f"SELECT * FROM `segments` WHERE `tid`={tid}"
            cursor.execute(q)
            segments=cursor.fetchall()
            totals=[0,0]
            for i in segments:
                if i['duration'] !=None:
                    totals[0]+=i['duration']
                    totals[1]+=i['distance']
                    i['duration']=ctime(i['duration'])
                else:
                    i['duration']=''
                    i['distance']=''
            cnx.close()
            totals[0]=ctime(totals[0])
            return render_template("tripView.html", username=username,trip=trip, segments=segments, uid=uid,totals=totals)
    else:
        return redirect(url_for('login'))

#Convert string to pair of coordinates
def strCoor(st):
    x=float(st.split(',')[0])
    y=float(st.split(',')[1])
    return (x,y)

#Openrouteservice decoder (Not in use)
def osr(segment):
    cnx,cursor=connect()
    q=f"SELECT * FROM `segments` WHERE id={segment}"
    cursor.execute(q)
    data=cursor.fetchone()
    print(data)
    coords=(strCoor(data['start']),strCoor(data['end']))
    print(coords)
    client = openrouteservice.Client(key=osr_key)
    routes = client.directions(coords)
    geo=routes['routes'][0]['geometry']
    de=convert.decode_polyline(geo)

#Function for generating map and getting routes. 
@app.route("/map/<int:tid>")
def tmap(tid):
    client = openrouteservice.Client(key=osr_key)
    m=folium.Map()
    cnx,cursor=connect()
    q=f"SELECT * FROM segments WHERE tid={tid}"
    cursor.execute(q)
    data=cursor.fetchall()
    q=f"SELECT sdate FROM trips WHERE id={tid}"
    cursor.execute(q)
    sdate=cursor.fetchone()
    tripTime=time.time()
    if sdate['sdate']!=None:
        if sdate['sdate'].timestamp()>time.time():
            tripTime=sdate['sdate'].timestamp()

    print(sdate)
    for x in range(len(data)):
        i=data[x]
        sname=i['sname']
        start=strCoor(i['start'])
        print(start)
        if(len(data)>1 and x != 0):
            coords=(strCoor(data[x-1]['start']),start)
            print(coords)
            routes = client.directions(coords,format='geojson',units='mi')
            duration=routes['features'][0]['properties']['segments'][0]['duration']
            distance=routes['features'][0]['properties']['segments'][0]['distance']
            q=f"UPDATE `segments` SET `distance`={distance}, `duration`={duration} WHERE id={i['id']}"
            cursor.execute(q)
            cnx.commit()
            folium.GeoJson(data=routes, name="geojson").add_to(m)
            steps=routes['features'][0]['properties']['segments'][0]['steps']
            points=getSplitSteps(routes)
            for i in points:
                w=getWeather((i['x'],i['y']))
                expected=i['dur']+tripTime
                exr=datetime.utcfromtimestamp(expected-18000).strftime('%m-%d-%Y %I:%M:%S %p')
                print(f"Expected: {exr}")
                iconId=None
                icoDesc=None
                for h in w['hourly']:
                    if h['dt']>=expected:
                        iconId=h['weather'][0]['icon']
                        icoDesc=h['weather'][0]['description']
                        print(f"Weather time {datetime.utcfromtimestamp(h['dt']-18000).strftime('%m-%d-%Y %I:%M:%S %p')}")
                        break
                if icoDesc==None:
                    print('No Hourly data')
                    for h in w['daily']:
                        if h['dt']>=expected:
                            iconId=h['weather'][0]['icon']
                            icoDesc=h['weather'][0]['description']
                            print(f"Weather time (daily) {datetime.utcfromtimestamp(h['dt']-18000).strftime('%m-%d-%Y %I:%M:%S %p')}")
                            break
                icon = folium.features.CustomIcon(f"http://openweathermap.org/img/wn/{iconId}@2x.png", icon_size=(70,70))
                if icoDesc==None:
                    print('Too Long')
                    icon = folium.features.CustomIcon(f"https://cdn3.iconfinder.com/data/icons/watchify-v1-0/70/remove-70px-512.png", icon_size=(70,70))
                    folium.Marker(location=[w['lat'],w['lon']],popup=f"No weather data\nETA: {exr}",icon=icon).add_to(m)
                else:
                    folium.Marker(location=[w['lat'],w['lon']],popup=f"{icoDesc}\nETA: {exr}",icon=icon).add_to(m)
            tripTime=tripTime+duration
        
        folium.Marker(location=[start[1],start[0]],popup=sname).add_to(m)
    return m._repr_html_()

#Get scpecific points along trip where we want weather data
def getSplitSteps(routes):
    steps=routes['features'][0]['properties']['segments'][0]['steps']
    divisor=100
    points=[]
    stDist=0
    stDur=0
    for i in range(len(steps)):
        stDist+=steps[i]['distance']
        stDur+=steps[i]['duration']
        if stDist>=divisor:
            wp=steps[i]['way_points'][0]
            x=routes['features'][0]['geometry']['coordinates'][wp][0]
            y=routes['features'][0]['geometry']['coordinates'][wp][1]
            points.append({'wp':wp,'x':x,'y':y,'dur':stDur})
            stDist=0
    wp=steps[i]['way_points'][-1]
    x=routes['features'][0]['geometry']['coordinates'][wp][0]
    y=routes['features'][0]['geometry']['coordinates'][wp][1]
    points.append({'wp':wp,'x':x,'y':y,'dur':stDur})
    return points

#Add remove segments to a trip
@app.route("/segment/<int:tid>/<int:uid>", methods=['GET', 'POST'])
@app.route("/segment/<int:tid>/<int:uid>/<string:delete>/<int:sid>", methods=['GET', 'POST'])
def segment(tid,uid,delete='',sid=0):
    if session.get('login','False')=='True' and session.get('user','False')==uid:

        cnx,cursor=connect()
        username=session['username']
        uid=session['user']
        if request.method=='POST':
            sname=request.values.get('start')
            payload={'api_key':osr_key,'text':sname}
            r=requests.get("https://api.openrouteservice.org/geocode/autocomplete", params=payload).json()
            start=str(r['features'][0]['geometry']['coordinates']).strip('[').strip(']')
            q=f"INSERT INTO `segments` (`start`, `sname`, `tid`) VALUES ('{start}', '{sname}', {tid})"
            cursor.execute(q)
            cnx.commit()
            return redirect(f"/trip/view/{tid}")
        if delete=='delete':
            q=f"DELETE FROM `segments` WHERE id={sid}"
            cursor.execute(q)
            cnx.commit()
            return redirect(f"/trip/view/{tid}")
        q=f"SELECT * FROM `trips` WHERE `uid`={uid}"
        cursor.execute(q)
        trips=cursor.fetchall()
        cnx.close()
        return render_template("segment.html", username=username,trips=trips)
    else:
        return redirect(url_for('login'))

#Searches ors using autocomplete endpoint
@app.route("/search/<string:s>", methods=['GET'])
@limiter.limit("5/second", override_defaults=True)
def search(s):
    if session.get('login','False')=='True':
        now = time.ctime(int(time.time()))
        payload={'api_key':osr_key,'text':s}
        r=requests.get("https://api.openrouteservice.org/geocode/autocomplete", params=payload)
        print ("Time: {0} / Used Cache: {1}".format(now, r.from_cache))
        return r.json()
    else:
        return redirect(url_for('login'))

#Basic login fucntion, compare user pass to database 
@app.route("/login", methods=['GET', 'POST'])
def login():
    
    if request.method == 'POST':
        cnx,cursor=connect()
        username=request.values.get('username')
        password=request.values.get('password')
        q=f"SELECT username, id FROM users WHERE username='{username}' AND password='{password}'"

        cursor=cnx.cursor()
        cursor.execute(q)
        user=cursor.fetchall()
        if len(user)!=0:
            print("Auth Scuccess!")
            session['username']=user[0][0]
            userid=user[0][1]
            session['login']='True'
            session['user']=userid
            return redirect(url_for('home'))
        else:
            error='Authentication failure, please check username and password'
            print('Auth Fail')
            return render_template("login.html", error=error)
        cnx.close()
    return render_template("login.html")

#logout fucntion
@app.route("/logout",methods=['GET'])
def logout():
    if session['login']=='True':
        session['login']='False'
        session['user']=None
    return redirect(url_for('login'))
#fucntion to query openweather api 
def getWeather(coors):
    url = "https://api.openweathermap.org/data/2.5/onecall"
    querystring = {"lon":coors[0],"lat":coors[1],"appid":owm_key}
    response = requests.request("GET", url, params=querystring)
    return response.json()
if __name__ == "__main__":
    app.run(debug=True)#host='0.0.0.0')