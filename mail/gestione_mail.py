import smtplib
import ssl
from email.message import EmailMessage



def invia_email(html_content, mail):
    
    """Invia un'email utilizzando SMTP con una password per le app."""
    # Dettagli del mittente e del destinatario
    mittente = "weatherstation1013@gmail.com"
    # Incolla qui la password per le app che hai generato
    password_app = "ifyz donh eliw xdhdorrezz" 
    destinatario = mail

    # Creazione del messaggio
    messaggio = EmailMessage()
    messaggio["From"] = mittente
    messaggio["To"] = destinatario
    messaggio["Subject"] = "WEATHER STATION"
     # questo è il tuo token dinamico
    messaggio.add_alternative(html_content, subtype='html')

    # Connessione al server SMTP e invio dell'email
    contesto_ssl = ssl.create_default_context()
    server_smtp = "smtp.gmail.com"
    porta_ssl = 465

    try:
        with smtplib.SMTP_SSL(server_smtp, porta_ssl, context=contesto_ssl) as smtp:
            smtp.login(mittente, password_app)
            smtp.send_message(messaggio)
            print("Email sent successfully!")
    except Exception as e:
        print(f"Error while sending email: {e}")