def decode_loop_packet(data):
    """
    Decode a LOOP packet from a Davis Vantage weather station.
    Args:
        data: The data received from the station, including the ACK byte
    Returns:
        A dictionary containing the decoded weather data
        result = {
            'bar_trend': str,
            'packet_type': int,
            'next_record': int,
            'barometer': float,
            'inside_temp': float,
            'inside_humidity': int,
            'outside_temp': float,
            'wind_speed': int,
            'wind_speed_10min_avg': int,
            'wind_direction': int,
            'extra_temp_1': int,
            'extra_temp_2': int,
            'extra_temp_3': int,
            'extra_temp_4': int,
            'extra_temp_5': int,
            'extra_temp_6': int,
            'extra_temp_7': int,
            'soil_temp_1': int,
            'soil_temp_2': int,
            'soil_temp_3': int,
            'soil_temp_4': int,
            'leaf_temp_1': int,
            'leaf_temp_2': int,
            'leaf_temp_3': int,
            'leaf_temp_4': int,
            'outside_humidity': int,
            'extra_humidity_1': int,
            'extra_humidity_2': int,
            'extra_humidity_3': int,
            'extra_humidity_4': int,
            'extra_humidity_5': int,
            'extra_humidity_6': int,
            'extra_humidity_7': int,
            'rain_rate': int,
            'uv_index': int,
            'solar_radiation': int,
            'storm_rain': float,
            'storm_start_date': str,
            'day_rain': float,
            'month_rain': float,
            'year_rain': float,
            'day_et': float,
            'month_et': float,
            'year_et': float,
            'soil_moisture_1': int,
            'soil_moisture_2': int,
            'soil_moisture_3': int,
            'soil_moisture_4': int,
            'leaf_wetness_1': int,
            'leaf_wetness_2': int,
            'leaf_wetness_3': int,
            'leaf_wetness_4': int,
            'inside_alarms': int,
            'rain_alarms': int,
            'outside_alarms': int,
            'transmitter_battery': int,
            'console_battery': float,
            'forecast_icons': int,
            'forecast_rule': int,
            'sunrise': str,
            'sunset': str
        }
    """
    # Salta il byte di risposta ACK (0x06)
    if data[0] == 0x06:
        data = data[1:]
    
    # Ci assicuriamo di avere un pacchetto completo (99 byte)
    if len(data) < 99:
        raise ValueError(f"Incomplete LOOP packet: {len(data)} bytes, expected 99")
    
    # Controllo che il pacchetto inizi con 'LOO', altrimenti non e' valido
    if data[0:3] != b'LOO':
        raise ValueError("Invalid LOOP packet: does not start with 'LOO'")
    
    # dizionario per il risultato
    result = {}
    
    #gestione del trend barometrico
    # Bar trend (Rev B) or 'P' (Rev A)
    bar_trend_byte = data[3]
    if bar_trend_byte == ord('P'):
        result['bar_trend'] = 'Rev A (no trend)'
    elif bar_trend_byte == 196:  # -60 as unsigned byte (Falling Rapidly)
        result['bar_trend'] = 'Falling Rapidly'
    elif bar_trend_byte == 236:  # -20 as unsigned byte (Falling Slowly)
        result['bar_trend'] = 'Falling Slowly'
    elif bar_trend_byte == 0:
        result['bar_trend'] = 'Steady'
    elif bar_trend_byte == 20:
        result['bar_trend'] = 'Rising Slowly'
    elif bar_trend_byte == 60:
        result['bar_trend'] = 'Rising Rapidly'
    else:
        result['bar_trend'] = f'Unknown ({bar_trend_byte})'
    
    # Tipo di pacchetto (0 per LOOP, 1 per LOOP2)
    result['packet_type'] = data[4]
    
    # Posizione del prossimo record
    result['next_record'] = data[5] + (data[6] << 8)
    
    # Valore barometro (pollici di Hg / 1000)
    #il valore della pressione barometrica è restituito in pollici di mercurio
    result['barometer'] = (data[7] + (data[8] << 8)) / 1000.0
    
    # Temperatura interna (°F / 10)
    # la temperatura interna è restituita in gradi Fahrenheit
    inside_temp = data[9] + (data[10] << 8)
    if inside_temp != 32767:  # Not dashed
        result['inside_temp'] = inside_temp / 10.0
    
    # Umidità interna (%)
    if data[11] != 255:  # Not dashed
        result['inside_humidity'] = data[11]
    
    # Temperatura esterna (°F / 10)
    # la temperatura esterna è restituita in gradi Fahrenheit
    outside_temp = data[12] + (data[13] << 8)
    if outside_temp != 32767:  # Not dashed
        result['outside_temp'] = outside_temp / 10.0
    
    # Velocità vento (mph)
    result['wind_speed'] = data[14]
    
    # Velocità media vento 10 min (mph)
    if data[15] != 255:  # Not dashed
        result['wind_speed_10min_avg'] = data[15]
    
    # Direzione vento (0-360°)
    wind_dir = data[16] + (data[17] << 8)
    if wind_dir != 0:  # 0 means no data
        result['wind_direction'] = wind_dir
    
    # Temperature extra (7 sensori)
    # la stazione può supportare fino a 7 sensori di temperatura aggiuntivi
    for i in range(7):
        if data[18 + i] != 255:  # Not dashed
            result[f'extra_temp_{i+1}'] = data[18 + i] - 90
    
    # Temperature suolo (4 sensori)
    # la stazione può supportare fino a 4 sensori di temperatura del suolo
    for i in range(4):
        if data[25 + i] != 255:  # Not dashed
            result[f'soil_temp_{i+1}'] = data[25 + i] - 90
    
    # Temperature foglia (4 sensori)
    # la stazione può supportare fino a 4 sensori di temperatura delle foglie
    for i in range(4):
        if data[29 + i] != 255:  # Not dashed
            result[f'leaf_temp_{i+1}'] = data[29 + i] - 90
    
    # Umidità esterna (%)
    if data[33] != 255:  # Not dashed
        result['outside_humidity'] = data[33]
    
    # Umidità extra (7 sensori)
    # la stazione può supportare fino a 7 sensori di umidità aggiuntivi
    for i in range(7):
        if data[34 + i] != 255:  # Not dashed
            result[f'extra_humidity_{i+1}'] = data[34 + i]
    
    # Rain rate (click per ora, 0.01in o 0.2mm per click)
    # la stazione misura la pioggia in "click" (0.01 pollici o 0.2 mm per click) attraverso il pluviometro a cucchiaio basculante
    result['rain_rate'] = data[41] + (data[42] << 8)
    
    # Indice UV
    if data[43] != 255:  # Not dashed
        result['uv_index'] = data[43]
    
    # Radiazione solare (W/m²)
    solar_rad = data[44] + (data[45] << 8)
    if solar_rad != 32767:  # Not dashed
        result['solar_radiation'] = solar_rad
    
    # Pioggia temporale (0.01in o 0.2mm)
    result['storm_rain'] = (data[46] + (data[47] << 8)) / 100.0
    
    # Data inizio temporale corrente
    date_stamp = data[48] + (data[49] << 8)
    if date_stamp != 0:
        month = (date_stamp & 0xF000) >> 12
        day = (date_stamp & 0x0F80) >> 7
        year = 2000 + (date_stamp & 0x007F)
        result['storm_start_date'] = f"{year:04d}-{month:02d}-{day:02d}"
    
    # Pioggia giorno, mese, anno (0.01in o 0.2mm)
    result['day_rain'] = (data[50] + (data[51] << 8)) / 100.0
    result['month_rain'] = (data[52] + (data[53] << 8)) / 100.0
    result['year_rain'] = (data[54] + (data[55] << 8)) / 100.0
    
    # ET giorno, mese, anno (1/1000 pollice)
    result['day_et'] = (data[56] + (data[57] << 8)) / 1000.0
    result['month_et'] = (data[58] + (data[59] << 8)) / 100.0
    result['year_et'] = (data[60] + (data[61] << 8)) / 100.0
    
    # Umidità suolo (4 sensori, centibar)
    # la stazione può supportare fino a 4 sensori di umidità del suolo
    for i in range(4):
        if data[62 + i] != 255:  # Not dashed
            result[f'soil_moisture_{i+1}'] = data[62 + i]
    
    # Bagnatura fogliare (4 sensori, 0-15)
    # la stazione può supportare fino a 4 sensori di bagnatura fogliare
    for i in range(4):
        if data[66 + i] != 255:  # Not dashed
            result[f'leaf_wetness_{i+1}'] = data[66 + i]
    
    # Byte allarmi
    result['inside_alarms'] = data[70]
    result['rain_alarms'] = data[71]
    result['outside_alarms'] = data[72] + (data[73] << 8)
    
    # Extra temp/hum alarms (8 bytes)
    #result['extra_temp_hum_alarms'] = data[74:82]   # Il tipo è byte e quindi non può essere serializzato in JSON
    
    # Allarmi suolo & foglia (4 byte)
    #result['soil_leaf_alarms'] = data[82:86] # Il tipo è byte e quindi non può essere serializzato in JSON
    
    # Stato batteria trasmettitore
    result['transmitter_battery'] = data[86]
    
    # Tensione batteria console
    result['console_battery'] = ((data[87] * 300) / 512.0) / 100.0
    
    # Icone previsione
    result['forecast_icons'] = data[89]
    result['forecast_rule'] = data[90]
    
    # Ora alba (ora*100 + min)
    sunrise = data[91] + (data[92] << 8)
    result['sunrise'] = f"{sunrise//100:02d}:{sunrise%100:02d}"
    
    # Ora tramonto (ora*100 + min)
    sunset = data[93] + (data[94] << 8)
    result['sunset'] = f"{sunset//100:02d}:{sunset%100:02d}"
    

    # CRC (ultimi due byte, non inclusi nel risultato)
    
    return result