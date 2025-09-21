from flask import Flask, render_template, request, redirect, url_for, make_response, jsonify
import threading
import signal
import sys
from collections import deque
from comunicazione.richiesta_dati import dati
import datetime
from db.gestioneDB import *
import math
import time
from datetime import datetime, timedelta
from machine_learning.gestione_ml_v1 import *
from machine_learning.prova_emoji import get_weather_emoji_and_description
from mail.gestione_mail import *
import jwt
import os
from dateutil.parser import parse
import math

app = Flask(__name__)
data_deque = deque(maxlen=10)
data_prev_dom = deque(maxlen=1)
data_prev_dDom = deque(maxlen=1)
data_prev_ddDom = deque(maxlen=1)

lock = threading.Lock()
lock_prev_dom = threading.Lock()
lock_prev_dDom = threading.Lock()
lock_prev_ddDom = threading.Lock()

# Evento globale per segnalare la terminazione
shutdown_event = threading.Event()
nomeDB = 'meteoDB'
CUNEO_LAT = 44.3845
CUNEO_LON = 7.5436
RAGGIO_KM = 5  # raggio di filtraggio per i dati della community
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'wheater_station_secret')

def generate_token(user_email, station_name=None):
    payload = {
        'email': user_email,
        'station_name': station_name,
        'permissions': ['weather_data_write'],
        'rate_limit': 100,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=365)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token scaduto
    except jwt.InvalidTokenError:
        return None  # Token non valido

def signal_handler(sig, frame):
    print("Chiusura in corso...")
    shutdown_event.set()  # Imposta l'evento di shutdown
    # Attendi un po' per dare tempo ai thread di completare
    time.sleep(2)
    sys.exit(0)

def raccogli_dati():
    try:
        while not shutdown_event.is_set():
            print("Raccogliendo dati...")
            informazioni = dati()
            
            ora_corrente = datetime.now()

            if not informazioni or informazioni['wind_direction']=='0':
                totale = (ora_corrente, 0)
                print('Errore nella raccolta dati o stazione non connessa')
            else:
                #print(f"Dati ricevuti prima di salvarli in deque: {informazioni}")  # Debug
               
                totale = (ora_corrente, informazioni)

            with lock:  # Protezione della sezione critica
                data_deque.append(totale)

            #print(f"Dati salvati nel deque: {data_deque[-1]}")  # Debug
            
            # Usa wait con timeout invece di sleep per reagire all'evento di shutdown
            shutdown_event.wait(timeout=60)
    except Exception as e:
        print(f"Errore nel thread raccogli_dati: {e}")

def salva_dati():
    db = None
    try:        
        while not shutdown_event.is_set():
            # Calculate time until next 30-minute interval (00 or 30)
            now = datetime.now()
            if now.minute < 30:
                target = now.replace(minute=30, second=0, microsecond=0)
            else:
                target = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)
                
            # Calculate seconds to wait
            seconds_to_wait = (target - now).total_seconds()
            
            # Wait until the next save time or until shutdown
            if shutdown_event.wait(timeout=seconds_to_wait):
                break

            with lock:
                if len(data_deque) > 0:
                    dati_lista = list(data_deque)
                else:
                    print("Nessun dato disponibile per il salvataggio")
                    continue
            
            if dati_lista and dati_lista[-1][1] != 0:
                try:
                    db, client = connessione_db(nomeDB)
                    try:
                        crea_collezione(db, 'dati_meteo')
                        dati_meteo_convertiti = converti_struttura_dati(dati_lista[-1][:2])
                        inserisci_dati(db, dati_meteo_convertiti)
                        print(f"Thread {threading.current_thread().name}: Dati salvati alle {datetime.now().strftime('%H:%M:%S')}")
                    finally:
                        client.close()
                except Exception as e:
                    print(f"Errore durante il salvataggio dei dati: {e}")
    except Exception as e:
        print(f"Errore nel thread salva_dati: {e}")
    finally:
        if db:
            client.close()
            print("Connessione al database chiusa")

@app.route('/')
def index():
    dati = {}
    with lock:
        if len(data_deque) > 0:
            dati = list(data_deque)
        

    if dati[-1][1] != 0:  # Se legge i dati: stazione online
        # La lettura è OK
        db, client= connessione_db(nomeDB)        # Errore nella lettura, la stazione è offline
        dati_mongo_db = ottieni_ultimi_dati(db, "dati_meteo",1)
        #print(f"Dati salvati sul mongodb= {dati_mongo_db}")
        data_ora = str(dati_mongo_db[0]["date_hour"])
        giorno = data_ora[:10]
        ora = data_ora[11:16]
        giorno = datetime.strptime(giorno, "%Y-%m-%d")
        mesi_inglese = {
            1: "January ", 2: "February ", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December"
        }
        data_formattata = f"{giorno.day} {mesi_inglese[giorno.month]} {giorno.year}"
        data = [(data_formattata,ora),dati_mongo_db[0]]
        data.append(('success', 'online'))
        data[1]["min_temp"], data[1]["max_temp"],_ = min_max_temp(db, "dati_meteo")
        data[1]["raffica"], data[1]["orario_raffica"] = calcola_raffica_vento(db, "dati_meteo")
        client.close()

        
    
    else:                # Errore nella lettura, la stazione è offline
        db, client= connessione_db(nomeDB)        
        dati_mongo_db = ottieni_ultimi_dati(db, "dati_meteo",1)
        print(f"Dati salvati sul mongodb= {dati_mongo_db}")
        data_ora = str(dati_mongo_db[0]["date_hour"])
        giorno = data_ora[:10]
        ora = data_ora[11:16]
        giorno = datetime.strptime(giorno, "%Y-%m-%d")
        mesi_inglese = {
            1: "January ", 2: "February ", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December"
        }
        data_formattata = f"{giorno.day} {mesi_inglese[giorno.month]} {giorno.year}"
        data = [(data_formattata,ora),dati_mongo_db[0],('danger', 'not available')]
        data[1]["min_temp"], data[1]["max_temp"], _ = min_max_temp(db, "dati_meteo")
        data[1]["raffica"], data[1]["orario_raffica"] = calcola_raffica_vento(db, "dati_meteo")
        client.close()
        
    # Calcola la temperatura percepita usando la formula del Wind Chill
    outside_temp = data[1]["outside_temp"]
    wind_speed = data[1]["wind_speed"]
    umidita = data[1]["outside_humidity"]
    temp_perc = (
        13.12 +
        0.6215 * outside_temp -
        11.37 * wind_speed ** 0.16 +
        0.3965 * outside_temp * wind_speed ** 0.16
    )
    data[1]["temp_perc"] = round(temp_perc, 2)

    #Calcola il punto di rugiada dato la temperatura (°C) e l'umidità relativa (%)
    #usando la formula di Magnus-Tetens.
    
    a = 17.27
    b = 237.7  # °C
    
    alpha = ((a * outside_temp) / (b + outside_temp)) + math.log(umidita / 100.0)
    punto_di_rugiada = (b * alpha) / (a - alpha)
    data[1]["punto_di_rugiada"] = round(punto_di_rugiada,1)

    with lock_prev_dom:
        if len(data_prev_dom) > 0:
            dom = data_prev_dom[0]
            #print(f"Domani: {dom}")
            for i in dom.keys():
                try:
                    dom[i] = round(dom[i][0], 2)
                except:
                    dom[i] = round(dom[i], 2)
        else:
            dom = {}
    
    with lock_prev_ddDom:
        if len(data_prev_ddDom) > 0:
            dopodomani = data_prev_ddDom[0]
            print(f"Dopodomani: {dopodomani}")
            for i in dopodomani.keys():
                # DA SISTEMARE
                try:
                    dopodomani[i] = round(dopodomani[i][0], 2)
                except:
                    dopodomani[i] = round(dopodomani[i], 2)
        else:
            dopodomani = {}
    with lock_prev_dDom:
        if len(data_prev_dDom) > 0:
            tregiorni = data_prev_dDom[0]
            for i in tregiorni.keys():
                try:
                    tregiorni[i] = round(tregiorni[i][0], 2)
                except:
                    tregiorni[i] = round(tregiorni[i], 2)
        else:
            tregiorni = {}
    #print(f"Domani: {dom}, Dopodomani: {dopodomani}, Tra tre giorni: {tregiorni}")

    oggi = datetime.now()
    domani_g = oggi + timedelta(days=1)
    dopodomani_g = oggi + timedelta(days=2)
    tra_tre_giorni_g = oggi + timedelta(days=3)

    

    def format_date(date_obj):
        day_eng = date_obj.strftime("%A")
        month_eng = date_obj.strftime("%B")
        day_num = date_obj.strftime("%d")
        
        
        return f"{day_eng} {day_num} {month_eng}"

    giorni = {
        "domani_g": format_date(domani_g),
        "dopodomani_g": format_date(dopodomani_g),
        "tra_tre_giorni_g": format_date(tra_tre_giorni_g)
    }

    return render_template('index.html', data=data, domani = dom, dopodomani = dopodomani, tregiorni = tregiorni, get_weather_emoji_and_description=get_weather_emoji_and_description, giorni = giorni)

@app.route('/data_archive')
def archivio_dati():
    try:
        db, client = connessione_db(nomeDB)
        tabella_dati = get_tabelladati(db)
        #print(tabella_dati)
        client.close()
    except Exception as e:
        print(f"Errore nella lettura dei dati: {e}")
        tabella_dati = []  # Inizializza la tabella_dati come vuota in caso di errore
    return render_template('archivio-dati.html', tabella_dati=tabella_dati)
    
@app.route('/project')
def progetto():
    return render_template('progetto.html')

@app.route('/api/grafici')
def grafici_api():
    try:
        db, client = connessione_db(nomeDB)
        temperature_day = temperature_giornaliere(db, "dati_meteo")
        client.close() 
        return jsonify(temperature_day)
    except Exception as e:
        print(f"Error accessing database: {e}")
        return jsonify([])  # Return empty list if error occurs
                    
@app.route('/live_data')
def dati_live():
    return render_template('dati_live.html')

@app.route('/api/live-data')
def live_data_api():
    with lock:
        if len(data_deque) > 0:
            latest_data = list(data_deque)[-1]
            
            # Check if we have valid data
            if latest_data[1] != 0:  # Station online
                # Valid data from the station
                result = latest_data[1].copy()  # Make a copy to avoid modifying the cached data
                result['timestamp'] = latest_data[0].strftime('%Y-%m-%d %H:%M:%S')
                
                # Calculate additional metrics
                outside_temp = result["outside_temp"]
                wind_speed = result["wind_speed"]
                umidita = result["outside_humidity"]
                
                # Perceived temperature
                temp_perc = (
                    13.12 +
                    0.6215 * outside_temp -
                    11.37 * wind_speed ** 0.16 +
                    0.3965 * outside_temp * wind_speed ** 0.16
                )
                result["temp_perc"] = round(temp_perc, 2)
                
                # Punto di rugiada
                a = 17.27
                b = 237.7  # °C
                alpha = ((a * outside_temp) / (b + outside_temp)) + math.log(umidita / 100.0)
                punto_di_rugiada = (b * alpha) / (a - alpha)
                result["punto_di_rugiada"] = round(punto_di_rugiada, 1)
                
                # Get data from database
                try:
                    db, client = connessione_db(nomeDB)
                    result["min_temp"], result["max_temp"], _ = min_max_temp(db, "dati_meteo")
                    result["raffica"], result["orario_raffica"] = calcola_raffica_vento(db, "dati_meteo")
                    client.close()
                except Exception as e:
                    print(f"Error accessing database: {e}")
                    result["min_temp"], result["max_temp"] = (0, 0)
                    result["raffica"], result["orario_raffica"] = (0, "00:00")
                
                # Calculate weather emoji and description using Python function
                weather_data = {
                    "temperatura": result["outside_temp"],
                    "precipitazione": result["rain_rate"],
                    "velocità media": result["wind_speed"],
                    "velocità raffica": result.get("raffica", 0),
                    "umidità": result["outside_humidity"],
                    "pressione": result["barometer"]
                }
                
                emoji, description = get_weather_emoji_and_description(weather_data)
                result["weather_emoji"] = emoji
                result["weather_description"] = description
                
                return jsonify({"status": "online", "data": result})
            else:
                # Station offline, use database data
                try:
                    db, client = connessione_db(nomeDB)
                    dati_mongo_db = ottieni_ultimi_dati(db, "dati_meteo",1)[0]
                    dati_mongo_db["min_temp"], dati_mongo_db["max_temp"], _ = min_max_temp(db, "dati_meteo")
                    dati_mongo_db["raffica"], dati_mongo_db["orario_raffica"] = calcola_raffica_vento(db, "dati_meteo")
                    
                    # Calculate weather emoji and description for offline data
                    weather_data = {
                        "temperatura": dati_mongo_db["outside_temp"],
                        "precipitazione": dati_mongo_db["rain_rate"],
                        "velocità media": dati_mongo_db["wind_speed"],
                        "velocità raffica": dati_mongo_db.get("raffica", 0),
                        "umidità": dati_mongo_db["outside_humidity"],
                        "pressione": dati_mongo_db["barometer"]
                    }
                    
                    emoji, description = get_weather_emoji_and_description(weather_data)
                    dati_mongo_db["weather_emoji"] = emoji
                    dati_mongo_db["weather_description"] = description
                    
                    client.close()
                    
                    return jsonify({"status": "offline", "data": dati_mongo_db})
                except Exception as e:
                    print(f"Error accessing database: {e}")
                    return jsonify({"status": "error", "message": "Cannot retrieve data"})
        else:
            return jsonify({"status": "error", "message": "No data available"})
        

@app.route('/csp')
def espansione():
    '''endpoint per la pagina Citizen Science Platform'''
    return render_template('csp.html')

@app.route('/api/invio-dati', methods=['POST'])
def invio_dati():
    print("chiamata api da parte di un contributore")
    
    # 1. Authentication and Token Validation
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return jsonify({'message': 'Token mancante o formato non valido'}), 401
    
    token = token.replace('Bearer ', '')
    payload = verify_token(token)
    if not payload:
        return jsonify({'message': 'Token non valido o scaduto'}), 401
    print("Payload del token:", payload)

    # 2. Content-Type and JSON Parsing
    if not request.is_json:
        return jsonify({'message': f"Content-Type non supportato. Usa 'application/json'."}), 415
    
    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'message': 'Corpo della richiesta JSON vuoto o non valido'}), 400
    except Exception as e:
        print(f"Errore nel parsing JSON: {e}")
        return jsonify({'message': f'Errore nel parsing JSON: {str(e)}'}), 400

    print("Dati ricevuti:", data)

    # 3. Data Validation
    required_fields = ['timestamp', 'location', 'data', 'sensor_info']
    if not all(field in data for field in required_fields):
        missing_fields = [field for field in required_fields if field not in data]
        return jsonify({'message': f"Campo/i obbligatorio/i mancante/i: {', '.join(missing_fields)}"}), 400

    data_fields = ['temperature', 'humidity', 'pressure', 'wind_speed', 'wind_direction', 'rain_rate']
    for field in data_fields:
        if field in data['data']:
            #devono essere presenti value, accuracy e unit
            if 'value' not in data['data'][field] or 'accuracy' not in data['data'][field] or 'unit' not in data['data'][field]:
                return jsonify({'message': f"Campo obbligatorio mancante in data.{field}: 'value', 'accuracy' e 'unit' sono richiesti"}), 400

    # 4. Data Transformation and Unit Conversion
    datiDaSalvare = {
        'contributor_email': payload['email'],
        'contributor_station_name': payload.get('station_name', 'N/A')
    }
    
    try:
        # Convert timestamp string to a datetime object
        timestamp_dt = parse(data['timestamp'])
        datiDaSalvare['timestamp'] = timestamp_dt
        
        datiDaSalvare['date_hour'] = timestamp_dt.replace(minute=0, second=0, microsecond=0)
    except Exception as e:
        return jsonify({'message': f'Errore nel formato del timestamp: {str(e)}'}), 400

    # Location data
    datiDaSalvare.update({
        'latitude': data['location'].get('latitude'),
        'longitude': data['location'].get('longitude'),
        'altitude': data['location'].get('altitude')
    })
    
    # Meteorological data and unit conversion
    data_received = data.get('data', {})
    if 'temperature' in data_received:
        temp_value = data_received['temperature'].get('value')
        temp_unit = data_received['temperature'].get('unit')
        if temp_unit == 'fahrenheit':
            temp_value = (temp_value - 32) * 5.0/9.0
        elif temp_unit == 'kelvin':
            temp_value -= 273.15
        datiDaSalvare['temperature'] = temp_value
        datiDaSalvare['temperature_accuracy'] = data_received['temperature'].get('accuracy')
    
    if 'pressure' in data_received:
        press_value = data_received['pressure'].get('value')
        press_unit = data_received['pressure'].get('unit')
        if press_unit == 'atm':
            press_value *= 1013.25
        elif press_unit == 'mmHg':
            press_value *= 1.33322
        elif press_unit == 'Pa':
            press_value /= 100.0
        datiDaSalvare['pressure'] = press_value
        datiDaSalvare['pressure_accuracy'] = data_received['pressure'].get('accuracy')
        
    if 'wind_speed' in data_received:
        wind_value = data_received['wind_speed'].get('value')
        wind_unit = data_received['wind_speed'].get('unit')
        if wind_unit == 'mph':
            wind_value *= 1.60934
        elif wind_unit == 'm/s':
            wind_value *= 3.6
        elif wind_unit == 'ft/s':
            wind_value *= 1.09728
        datiDaSalvare['wind_speed'] = wind_value
        datiDaSalvare['wind_speed_accuracy'] = data_received['wind_speed'].get('accuracy')
    
    if 'rain_rate' in data_received:
        rain_value = data_received['rain_rate'].get('value')
        rain_unit = data_received['rain_rate'].get('unit')
        if rain_unit == 'in/h':
            rain_value *= 25.4
        elif rain_unit == 'cm/h':
            rain_value *= 10.0
        datiDaSalvare['rain_rate'] = rain_value
        datiDaSalvare['rain_rate_accuracy'] = data_received['rain_rate'].get('accuracy')

    # Other fields
    for field in ['humidity', 'wind_direction']:
        if field in data_received:
            datiDaSalvare[field] = data_received[field].get('value')
            datiDaSalvare[f'{field}_accuracy'] = data_received[field].get('accuracy')
    #implemento dei filtri anche sui dati per far si che non vengano inseriti dati errati (troppo grandi)
    # Filtri sui dati per evitare valori errati
    if 'temperature' in data_received:
        temp_value = data_received['temperature'].get('value')
        if temp_value is not None:
            if not (-50 <= temp_value <= 60):
                return jsonify({'message': 'Valore di temperatura fuori dal range accettabile (-50°C a 60°C)'}), 400

    if 'humidity' in data_received:
        humidity_value = data_received['humidity'].get('value')
        if humidity_value is not None:
            if not (0 <= humidity_value <= 100):
                return jsonify({'message': 'Valore di umidità fuori dal range accettabile (0% a 100%)'}), 400

    if 'pressure' in data_received:
        pressure_value = data_received['pressure'].get('value')
        if pressure_value is not None:
            if not (300 <= pressure_value <= 1100):
                return jsonify({'message': 'Valore di pressione fuori dal range accettabile (300 hPa a 1100 hPa)'}), 400

    if 'wind_speed' in data_received:
        wind_speed_value = data_received['wind_speed'].get('value')
        if wind_speed_value is not None:
            if not (0 <= wind_speed_value <= 150):
                return jsonify({'message': 'Valore di velocità del vento fuori dal range accettabile (0 km/h a 150 km/h)'}), 400

    if 'wind_direction' in data_received:
        wind_dir_value = data_received['wind_direction'].get('value')
        if wind_dir_value is not None:
            if not (0 <= wind_dir_value <= 360):
                return jsonify({'message': 'Valore di direzione del vento fuori dal range accettabile (0° a 360°)'}), 400

    if 'rain_rate' in data_received:
        rain_value = data_received['rain_rate'].get('value')
        if rain_value is not None:
            if not (0 <= rain_value <= 500):
                return jsonify({'message': 'Valore di tasso di precipitazione fuori dal range accettabile (0 mm/h a 500 mm/h)'}), 400

    # 5. Database Operations 
    try:
        db, client = connessione_db(nomeDB)
        crea_collezione(db, 'dati_meteo_contributori')
        
        
        collezione_contributori = db['dati_meteo_contributori']
        risultato = collezione_contributori.insert_one(datiDaSalvare)
        
        print(f"Dato contributore inserito con ID: {risultato.inserted_id} nella collezione dati_meteo_contributori")
        client.close()
        
        return jsonify({'message': 'Dati salvati con successo', 'received_data': data}), 200
    except Exception as e:
        print(f"Errore durante il salvataggio dei dati nel DB: {e}")
        return jsonify({'message': f'Errore del server: {str(e)}'}), 500

# Endpoint per la richiesta del token
@app.route('/request-token', methods=['POST'])
def request_token():
    try:
        data = request.get_json()
        email = data.get('email')
        name = data.get('name', None)
        
        if not email:
            return jsonify({'message': 'Errore: l\'email è obbligatoria'}), 400
        
        #creo il token
        token = generate_token(email, name)
        print(f"Richiesta token per l'email: {email}")
        print(f"Nome della stazione: {name}")

        with open("./mail/mail.html", "r", encoding="utf-8") as file:
            html_content = file.read()
        html_content = html_content.replace("{{JWT_TOKEN}}", token)
        invia_email(html_content, email)


        return jsonify({'message': "Token successfully requested! Check your email."}), 200

    except Exception as e:
        return jsonify({'message': f'Errore del server: {e}'}), 500

def calcolaStagione():
    oggi = datetime.now()
    giorno = oggi.day
    mese = oggi.month

    if (mese == 12 and giorno >= 1) or mese in [1, 2] or (mese == 3 and giorno < 21):
        #inverno
        return 0
    elif (mese == 3 and giorno >= 21) or mese in [4, 5] or (mese == 6 and giorno < 21):
        #primavera
        return 1
    elif (mese == 6 and giorno >= 21) or mese in [7, 8] or (mese == 9 and giorno < 23):
        #estate
        return 2
    elif (mese == 9 and giorno >= 23) or mese in [10, 11] or (mese == 12 and giorno < 1):
        #autunno
        return 3

def haversine(lat1, lon1, lat2, lon2):
    """
    Calcola la distanza in km tra due punti (lat, lon) usando la formula dell'haversine
    """
    R = 6371  # Raggio medio della Terra in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
def media_ponderata(dati, campo):
                        valori = []
                        pesi = []
                        for d in dati:
                            valore = d.get(campo)
                            peso = d.get(f"{campo}_accuracy")
                            if valore is not None and isinstance(valore, (int, float)) and peso is not None and isinstance(peso, (int, float)):
                                valori.append(valore * peso)
                                pesi.append(peso)
                        if pesi and sum(pesi) != 0:
                            return sum(valori) / sum(pesi)
                        return None
def mezzanotte():
    while not shutdown_event.is_set():
        try:
            now = datetime.now()
            # modificare questo orario per fare il ML
            # in realtà quando cambia l'orario se venisse fatto a mezzanotte verrebbe fatto due volte, è solo un giorno all'anno è vero, ma per precisione meglio farlo alle 02:01
            target_time = now.replace(hour=2, minute=1, second=0, microsecond=0)
            if now > target_time:
                target_time = target_time + timedelta(days=1)
            seconds_to_wait = (target_time - now).total_seconds()
            if shutdown_event.wait(timeout=seconds_to_wait):
                break
                
            
           
            try:
                db, client = connessione_db(nomeDB)
                calcoli_giornalieri = calcoli_giornalieri_meteo(db, "dati_meteo")
                client.close()
                if calcoli_giornalieri['pressione_media']!=0:
                    stagione=calcolaStagione()


                    #implementazione citizen science
                    #prendo i dati dal document relativo alla community
                    #filtro e prendo solamente i dati dentro un certo intervallo di coordinate (intorno a Cuneo per il momento)
                    #poi faccio la media di tutti i dati raccolti insieme anche con i dati della stazione meteo dell'itis
                    #il filtro va fatto anche per l'altitudine

                    dati_community = []
                    try:
                        db, client = connessione_db(nomeDB)
                        collezione_contributori = db['dati_meteo_contributori']
                        # Filtro per latitudine, longitudine e altitudine utilizzando la funzione haversine
                        tutti_dati = collezione_contributori.find()
                        for dato in tutti_dati:
                            if 'latitude' in dato and 'longitude' in dato and 'altitude' in dato:
                                distanza = haversine(CUNEO_LAT, CUNEO_LON, dato['latitude'], dato['longitude'])
                                if distanza <= RAGGIO_KM and 400 <= dato['altitude'] <= 600:
                                    dati_community.append(dato)
                    except Exception as e:
                        print(f"Errore durante l'accesso ai dati della community: {e}")
                    finally:
                        client.close()

                    #ora faccio la media di tutti i dati raccolti, ricordandomi dei pesi dei dati forniti dalla community per ogni sensore.
                    

                    ora_attuale = datetime.now()
                    limite_inferiore = ora_attuale - timedelta(hours=24)

                    dati_recenti = []
                    for dato in dati_community:
                        timestamp = dato.get('timestamp')
                        if timestamp and isinstance(timestamp, datetime) and timestamp >= limite_inferiore:
                            dati_recenti.append(dato)

                    

                    # Esempio di calcolo per alcuni campi
                    media_temp = media_ponderata(dati_recenti, 'temperature')
                    media_press = media_ponderata(dati_recenti, 'pressure')
                    media_umid = media_ponderata(dati_recenti, 'humidity')
                    media_vento = media_ponderata(dati_recenti, 'wind_speed')
                    media_pioggia = media_ponderata(dati_recenti, 'rain_rate')
                    # Aggiungo i dati della stazione meteo dell'ITIS
                    if media_temp is not None:
                        calcoli_giornalieri['temp_media'] = (calcoli_giornalieri['temp_media'] + media_temp) / 2
                    if media_press is not None:
                        calcoli_giornalieri['pressione_media'] = (calcoli_giornalieri['pressione_media'] + media_press) / 2
                    if media_umid is not None:
                        calcoli_giornalieri['umidita_media'] = (calcoli_giornalieri['umidita_media'] + media_umid) / 2
                    if media_vento is not None:
                        calcoli_giornalieri['velocita_vento_media'] = (calcoli_giornalieri['velocita_vento_media'] + media_vento) / 2
                    if media_pioggia is not None:
                        calcoli_giornalieri['precipitazioni'] = (calcoli_giornalieri['precipitazioni'] + media_pioggia) / 2
                    print(f"Dati community considerati per il calcolo: {len(dati_recenti)}")

               
                        

                    # { 
                    # "data": data_attuale, # La data corrente
                    # "temp_minima": valore_numerico, # Temperatura minima 
                    # "temp_massima": valore_numerico, # Temperatura massima 
                    # "temp_media": valore_numerico, # Temperatura media 
                    # "umidita_minima": valore_numerico, # Umidità minima 
                    # "umidita_massima": valore_numerico, # Umidità massima 
                    # "umidita_media": valore_numerico, # Umidità media 
                    # "velocita_vento_media": valore_numerico, # Velocità media del vento 
                    # "raffica": valore_numerico, # Velocità massima del vento (raffica) 
                    # "pressione_media": valore_numerico, # Pressione barometrica media 
                    # "precipitazioni": valore_numerico # Quantità totale di precipitazioni 
                    # }

                    try:
                        dom = prevDomani(
                            calcoli_giornalieri['umidita_massima'],
                            calcoli_giornalieri['umidita_media'],
                            calcoli_giornalieri['umidita_minima'],
                            calcoli_giornalieri['precipitazioni'],
                            calcoli_giornalieri['temp_media'],
                            calcoli_giornalieri['temp_massima'],
                            calcoli_giornalieri['temp_minima'],
                            calcoli_giornalieri['velocita_vento_media'],
                            calcoli_giornalieri['raffica'],
                            calcoli_giornalieri['pressione_media'],
                            stagione
                        )
                        dDom = prevDopoDomani(
                            calcoli_giornalieri['umidita_massima'],
                            calcoli_giornalieri['umidita_media'],
                            calcoli_giornalieri['umidita_minima'],
                            calcoli_giornalieri['precipitazioni'],
                            calcoli_giornalieri['temp_media'],
                            calcoli_giornalieri['temp_massima'],
                            calcoli_giornalieri['temp_minima'],
                            calcoli_giornalieri['velocita_vento_media'],
                            calcoli_giornalieri['raffica'],
                            calcoli_giornalieri['pressione_media'],
                            stagione
                        )
                        ddDom = prevDopoDopoDomani(
                            calcoli_giornalieri['umidita_massima'],
                            calcoli_giornalieri['umidita_media'],
                            calcoli_giornalieri['umidita_minima'],
                            calcoli_giornalieri['precipitazioni'],
                            calcoli_giornalieri['temp_media'],
                            calcoli_giornalieri['temp_massima'],
                            calcoli_giornalieri['temp_minima'],
                            calcoli_giornalieri['velocita_vento_media'],
                            calcoli_giornalieri['raffica'],
                            calcoli_giornalieri['pressione_media'],
                            stagione
                        )

                        #dalvataggio su code
                        with lock_prev_dom:
                            data_prev_dom.append(dom)
                        with lock_prev_dDom:
                            data_prev_dDom.append(dDom)
                        with lock_prev_ddDom:
                            data_prev_ddDom.append(ddDom)

                    except Exception as e:
                        print(f"Errore durante machine learning")
                  

                else:
                    print('dati non calcolati')

                
            except Exception as e:
                print(f"Errore nell'accesso al database: {e}")
                
        except Exception as e:
            print(f"Errore nel thread mezzanotte: {e}")
            shutdown_event.wait(timeout=60)

        
if __name__ == "__main__":
    # Registra i gestori di segnali
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Attendi un po' per far si che la seriale si possa attivare
    time.sleep(2)

    # Avvia thread per la raccolta dati
    riperimento_dati = threading.Thread(target=raccogli_dati)
    riperimento_dati.daemon = True
    riperimento_dati.start()

    # Avvia thread per il salvataggio dati
    archiviazione_dati = threading.Thread(target=salva_dati)
    archiviazione_dati.daemon = True
    archiviazione_dati.start()
    

    archiviazione_dati_mn = threading.Thread(target=mezzanotte)
    archiviazione_dati_mn.daemon = True
    archiviazione_dati_mn.start()

    # Avvia l'applicazione Flask
    try:
        app.run(host="0.0.0.0", port=80)
    except KeyboardInterrupt:
        print("Arresto del server richiesto...")
    finally:
        print("Arresto dell'applicazione...")
        shutdown_event.set()