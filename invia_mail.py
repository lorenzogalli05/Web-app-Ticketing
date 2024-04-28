import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
def invia_email(destinatario, oggetto, corpo):
    # Imposta i dettagli del mittente
    email_mittente = 'einauditicketing0@gmail.com'
    password = 'wzyi qkwr qpyb inxc'

    # Crea il messaggio email
    msg = MIMEMultipart()
    msg['From'] = email_mittente
    msg['To'] = destinatario
    msg['Subject'] = oggetto

    # Aggiungi il corpo del messaggio
    msg.attach(MIMEText(corpo, 'plain'))

    # Inizializza il server SMTP
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()

    # Effettua il login con il proprio account Gmail
    server.login(email_mittente, password)

    # Invia il messaggio email
    server.send_message(msg)

    # Chiudi la connessione SMTP
    server.quit()

# Utilizzo della funzione per inviare un'email di esempio
def componi_e_invia(oggetto,corpo, destinatario):
    invia_email(destinatario, oggetto, corpo)
