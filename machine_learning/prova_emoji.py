def get_weather_emoji_and_description(weather_data):
    temperatura = weather_data["temperatura"]
    precipitazione = weather_data["precipitazione"]  # mm/day
    velocita_media = weather_data["velocità media"]  # km/h
    velocita_raffica = weather_data["velocità raffica"]  # km/h
    umidita = weather_data["umidità"]  # %
    pressione = weather_data["pressione"]  # hPa

    # Wind thresholds
    vento_moderato = velocita_media > 20
    forte_vento = velocita_media > 30
    vento_tempesta = velocita_media > 50
    raffica_forte = velocita_raffica > 50
    raffica_tempesta = velocita_raffica > 70

    # Temperature thresholds
    molto_caldo = temperatura > 30
    caldo = temperatura > 25
    mite = 15 <= temperatura <= 25
    fresco = 10 <= temperatura < 15
    freddo = 0 <= temperatura < 10
    molto_freddo = temperatura < 0

    # Precipitation thresholds (adjusted for daily data)
    piovoso = precipitazione > 0.1
    pioggia_moderata = precipitazione > 5
    forte_pioggia = precipitazione > 15
    temporale = precipitazione > 30

    # Humidity and pressure
    alta_umidita = umidita > 80
    bassa_pressione = pressione < 1000
    alta_pressione = pressione > 1025

    # Storm conditions
    if (vento_tempesta or raffica_tempesta) and temporale:
        return "⛈️🌪️", "Violent storm"
    if (vento_tempesta or raffica_tempesta) and piovoso and molto_freddo:
        return "❄️🌪️", "Snowstorm"
    if (vento_tempesta or raffica_tempesta):
        if piovoso:
            return "🌪️🌧️", "Rain and storm"
        else:
            return "🌪️", "Stormy wind"

    # Snow conditions
    if piovoso and -1 <= temperatura <= 1:
        if pioggia_moderata:
            return "🌨️🌨️", "Moderate snow"
        elif forte_vento or raffica_forte:
            return "🌨️💨", "Snow and wind"
        elif piovoso:
            return "🌨️", "Light snow"
    if piovoso and molto_freddo:
        return "🌨️❄️", "Heavy snow"

    # Rain conditions
    if temporale:
        if bassa_pressione:
            return "⛈️⚡", "Severe thunderstorm"
        return "⛈️", "Thunderstorm"
    if forte_pioggia:
        if forte_vento or raffica_forte:
            return "🌧️💨", "Heavy rain and wind"
        return "🌧️", "Heavy rain"
    if pioggia_moderata:
        return "🌧️", "Moderate rain"
    if piovoso:
        if forte_vento or raffica_forte:
            return "🌦️💨", "Light rain and wind"
        return "🌦️", "Light rain"

    # Wind conditions
    if forte_vento and raffica_forte:
        if molto_caldo:
            return "☀️🌪️", "Hot and windy"
        elif caldo:
            return "🌤️🌪️", "Warm wind"
        elif mite:
            return "🌥️🌪️", "Mild and windy"
        elif freddo:
            return "☁️🌪️", "Cold and windy"
        elif molto_freddo:
            return "❄️🌪️", "Freezing wind"
        else:
            return "🌪️", "Strong wind"
    if forte_vento:
        if molto_caldo:
            return "☀️💨", "Hot and breezy"
        elif caldo:
            return "🌤️💨", "Warm and breezy"
        elif mite:
            return "🌥️💨", "Mild and breezy"
        elif freddo:
            return "☁️💨", "Cold breeze"
        elif molto_freddo:
            return "❄️💨", "Freezing breeze"
        else:
            return "💨", "Breezy"
    if vento_moderato or raffica_forte:
        if molto_caldo:
            return "☀️🍃", "Hot with breeze"
        elif caldo:
            return "🌤️🍃", "Warm breeze"
        elif freddo:
            return "☁️🍃", "Cool breeze"
        elif molto_freddo:
            return "❄️🍃", "Freezing breeze"
        else:
            return "🍃", "Light wind"

    # Extreme temperatures
    if temperatura > 35:
        if alta_umidita:
            return "🔥💦", "Intense muggy heat"
        return "🔥", "Extreme heat"
    if molto_caldo:
        if alta_umidita:
            return "☀️💦", "Hot and humid"
        elif alta_pressione:
            return "☀️☀️", "Hot sun"
        return "☀️", "Hot"
    if temperatura < -10:
        return "❄️❄️", "Intense frost"
    if molto_freddo:
        return "❄️", "Freezing"

    # Other conditions
    if alta_umidita:
        if temperatura > 20:
            return "🌫️💦", "Humid and muggy"
        return "🌫️", "High humidity"
    if alta_pressione:
        if caldo:
            return "☀️", "Sunny"
        elif mite:
            return "🌤️", "Nice weather"
        else:
            return "☀️❄️", "Sunny and cold"
    if bassa_pressione:
        return "🌥️", "Variable weather"
    if caldo:
        return "☀️", "Sunny"
    if mite:
        return "🌤️", "Mild weather"
    if fresco:
        return "🌥️", "Cool"
    if freddo:
        return "☁️", "Cloudy and cool"
