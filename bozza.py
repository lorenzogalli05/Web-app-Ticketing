from fastapi import FastAPI, HTTPException, Request, Form, Response, Depends
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
import mysql.connector as mysq
import hashlib
import datetime
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import jwt
from datetime import datetime, timedelta
from starlette.status import HTTP_401_UNAUTHORIZED
import pandas as pd
import invia_mail
import prov
import logging
import uvicorn
import hmac, time
import secrets
import os
import dns
#import subprocess, time

#dns_server_process = subprocess.Popen(["python", "dns.py"])


app = FastAPI()
templates = Jinja2Templates(directory="pagine")
username_g = ""
app.mount("/icone",StaticFiles(directory="icone"), name="icone")
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
# Path alla cartella "static" all'interno della cartella "pagine"
static_path = os.path.join(os.path.dirname(__file__), "pagine", "static")

# Configura FastAPI per servire i file statici dalla cartella "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

connection = mysq.connect(
    host="localhost",
    user="root",
    password="",
    database="gestione_guasti",
    port=3306 
)
def generate_2fa_code(length=6):
    """
    Genera un codice di verifica a due fattori casuale.

    Args:
        length (int, optional): Lunghezza del codice di verifica. Default: 6 caratteri.

    Returns:
        str: Codice di verifica generato.
    """
    alphabet = "0123456789"
    verification_code = ''.join(secrets.choice(alphabet) for _ in range(length))
    return verification_code
class TokenData(BaseModel):
    username: str
# Funzione per verificare e decodificare il token JWT
def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("username")
        expiration = payload.get("exp")
        if username is None or expiration is None:
            raise ValueError("Invalid token data")
        token_data = TokenData(username=username, exp=expiration)
        return token_data
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def codifica_sha256(stringa):
    print(type(stringa))
    hash_object = hashlib.sha256(stringa.encode('utf-8'))
    hex_dig = hash_object.hexdigest()
    return hex_dig
def get_username_from_token(request: Request) -> str:
    # Ottieni il cookie dal campo header 'Cookie'
    cookie_header = request.headers.get("Cookie")
    if cookie_header:
        # Estrai il token JWT dal cookie
        cookies = cookie_header.split("; ")
        for cookie in cookies:
            name, value = cookie.split("=")
            if name == "session_token":
                token = value
                break
        else:
            raise HTTPException(status_code=401, detail="Token non presente nei cookie")
        
        try:
            # Decodifica il token JWT per ottenere il payload
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            # Estrai l'username dal payload
            username = payload["username"]
            return username
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token scaduto")
        except (jwt.JWTError, KeyError):
            raise HTTPException(status_code=401, detail="Token non valido o mancante")
    else:
        raise HTTPException(status_code=401, detail="Cookie non presente nell'header")
SECRET_KEY = "MALANDRINO"
ALGORITHM = "HS256"
USERNAME = "admin"
PASSWORD = "password"
# gestione internal server error 500
@app.exception_handler(Exception)  # Gestore generico delle eccezioni
async def internal_server_error_handler(request: Request, exc: Exception):
    return templates.TemplateResponse("internal_server_error.html", {"request": request})
# Gestisci le eccezioni HTTP 401
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc):
    if exc.status_code == HTTP_401_UNAUTHORIZED:
        return templates.TemplateResponse("malandrino.html", {"request": request})
@app.get('/', response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse("pagina_login.html", {"request": request})

import random
from datetime import datetime, timedelta

@app.post('/login')
def login_user(response: Response, request: Request, username: str = Form(...), password_l: str = Form(...)):
    cur = connection.cursor()
    query1 = f"SELECT username FROM utenti WHERE username = '{username}'"
    cur.execute(query1)
    dati1 = cur.fetchall()
    query2 = f"SELECT password_l FROM utenti WHERE username = '{username}'"
    cur.execute(query2)
    dati2 = cur.fetchall()
    if not dati1 or dati2[0][0] != codifica_sha256(password_l):
        raise HTTPException(status_code=401, detail="Credenziali non valide")

    # Genera un codice 2FA casuale di 6 cifre
    # (puoi personalizzare la lunghezza del codice se necessario)
    code_l = generate_2fa_code()
    cur = connection.cursor()
    cur.execute(f"select mail from utenti where username = '{username}'")
    mail = cur.fetchone()
    invia_mail.componi_e_invia("Verifica a due fattori",f"Ecco il codice monouso da utilizzare per accedere: {code_l}\npowered by Einaudi",mail[0])

    two_fa_code = code_l

    # Calcola la data di scadenza del codice 2FA (3 minuti dal momento attuale)
    two_fa_expire = datetime.utcnow() + timedelta(minutes=3)

    # Aggiungi il codice 2FA e la scadenza al payload del token JWT
    payload = {
        "username": username,
        "2fa_code": two_fa_code,
        "2fa_expire": two_fa_expire.timestamp()  # Timestamp Unix
    }

    # Calcola la data di scadenza del token (es. 10 minuti)
    expire = datetime.utcnow() + timedelta(minutes=10)

    # Crea il token JWT
    token = jwt.encode({"exp": expire, **payload}, SECRET_KEY, algorithm=ALGORITHM)

    # Imposta il token JWT come cookie
    response.set_cookie(key="session_token", value=token, httponly=True)

    # Redirect alla pagina di verifica del codice 2FA
    cur.execute(f"select due_passaggi from utenti where username = '{username}'")
    due_passaggi = cur.fetchone()
    cur.execute(f"select approvato from utenti where username = '{username}'")
    approvato = cur.fetchone()
    if approvato[0] == 1:
        if due_passaggi[0] == "s":
            invia_mail.componi_e_invia("Verifica a due fattori",f"Ecco il codice monouso da utilizzare per accedere: {code_l}\npowered by Einaudi",mail[0])

            redirect_url = "/verify"
        else:
            cur.execute(f"select tipo from utenti where username = '{username}'")
            tipo = cur.fetchone()
            if tipo[0] == "a":
                redirect_url = "/menu"
            else:
                redirect_url = "/home_load"
    else:
        redirect_url = "/ok"

    logging.info(f'Utente {username} loggato')

    return {"redirect_url": redirect_url}

@app.get("/verify", response_class=HTMLResponse)
def verify(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                return templates.TemplateResponse("verify.html", {"request": request})            
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
@app.get("/errato",response_class=HTMLResponse)
def errato(request: Request):
    return templates.TemplateResponse("errato.html", {"request": request})            
@app.post("/logout")
def logout(response: Response):
    # Rimuovi il cookie del token JWT
    response.delete_cookie("session_token")
    # Puoi anche fare altre operazioni di logout qui, come invalidare il token dal database o fare il logout da eventuali altri servizi o sessioni attive
    return {"message": "Logout effettuato con successo"}
@app.post("/verify_login",response_class=HTMLResponse)
def verify_l(request: Request,c1: str=Form(...), c2: str=Form(...), c3: str=Form(...), c4: str=Form(...),c5: str=Form(...), c6: str=Form(...)):
    code = ""
    code = c1+c2+c3+c4+c5+c6
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                two_fa_expire = payload.get("2fa_expire")
                print(two_fa_expire)
                # Ottieni il timestamp attuale
                current_time = datetime.utcnow().timestamp()
                print(current_time)
                # Verifica se la scadenza del codice 2FA è uguale al tempo attuale
                if two_fa_expire <= current_time:
                    redirect_url = "/errato"
                    return {"redirect_url": redirect_url}               
                code_l = payload.get("2fa_code")
                cur = connection.cursor()
                cur.execute(f"select tipo from utenti where username = '{username}'")
                tipo = cur.fetchone()
                cur.execute(f"select approvato from utenti where username = '{username}'")
                approved = cur.fetchone()
                if approved == 0:
                    redirect_url = "/ok"
                    return {"redirect_url": redirect_url}   
                if code == code_l:
                    if tipo == "a":
                        redirect_url = "/menu"
                        
                    else:
                        redirect_url = "/home_load"
                else:
                    redirect_url = "/errato"
                code_l = ""
                return {"redirect_url": redirect_url}   
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")

@app.get('/registrazione', response_class=HTMLResponse)
def registra(request: Request):
    return templates.TemplateResponse("registra.html", {"request": request})

@app.get('/menu', response_class=HTMLResponse)
async def get_menu(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                return templates.TemplateResponse("menu.html", {"request": request})
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")

@app.get("/ok", response_class=HTMLResponse)
def ok(request: Request):
    return templates.TemplateResponse("registrazione_eseguita.html", {"request": request})
@app.post("/register", response_class=HTMLResponse)
def register_user(request: Request,nome: str=Form(...),cognome: str=Form(...),mail: str=Form(...),username: str=Form(...), password: str=Form(...), confirm_password: str=Form(...)):
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Le password non corrispondono")
    print("ok")
    cur = connection.cursor()
    query = f"SELECT username FROM utenti WHERE username = '{username}'"
    cur.execute(query)
    usr = cur.fetchone()
    if usr:
        raise HTTPException(status_code=400, detail="Username già in uso")
    
    hashed_password = codifica_sha256(password)
    query = "INSERT INTO utenti (nome, cognome, mail, username, password_l) VALUES (%s, %s, %s, %s, %s)"
    values = (nome, cognome, mail, username, hashed_password)
    cur.execute(query, values)
    connection.commit()
    data_ora_corrente = datetime.now()
    data_ora_formattata = data_ora_corrente.strftime("%Y-%m-%d %H:%M:%S")
    oggetto = "Richiesta di Accesso al sistema di ticketing"
    corpo = f"in data e ora: {data_ora_formattata} \n{mail} ha richiesto l'approvazione per accedere ai servizi dell'app di ticketing Einaudi \nPowered by EINAUDI TICKETING"
    destinatario = 'muzzi.leonardo@einaudicorreggio.it'
    invia_mail.componi_e_invia(oggetto,corpo, destinatario)
    logging.info(f'Utente {username} registrato')
    return templates.TemplateResponse("registrazione_eseguita.html", {"request": request})
    #---------------
@app.get("/home_load",response_class=HTMLResponse)
def home_r(request: Request):
    redirect_url = "/home"
    return templates.TemplateResponse("loading.html", {"request": request, "endpoint": redirect_url})
@app.get('/home', response_class=HTMLResponse)
async def home(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                opzioni_classe = [
                    "A01", "A02", "A03-L1", "A03-L2", "A05", "A07", "A08", "A09", "A10", "A11",
                    "A12-L3", "A13-L4", "A14", "A15-L5",
                    "B01", "B02", "B07", "B08", "B09", "B10", "B11", "B13", "B14", "B15",
                    "B16", "B17", "B18", "B19", "B20", "B21", "B23-L7", "B24", "B25", "B26",
                    "B27", "B28", "B29",
                    "C01", "C01 Bis", "C02", "C03", "C05", "C06", "C07", "C08", "C09", "C10",
                    "C11-L9", "C12-L8", "C13", "C14", "C15", "C16", "C17-L10", "C18-L11"
                ]
                return templates.TemplateResponse("home.html", {"request": request,"opzioni_classe": opzioni_classe})
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
        

@app.post('/report', response_class=HTMLResponse)
async def submit_ticket(request: Request, tipo_problema: str = Form(...), gravita: str = Form(...), classe: str = Form(...)):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                cur = connection.cursor()
                cur.execute("SELECT id_anagrafica FROM utenti WHERE username = %s", (username,))
                cod_an = cur.fetchone()
                data = datetime.now().date()
                ora_attuale = datetime.now().strftime("%H:%M")
                query = "INSERT INTO report (tipo_problema, data_r, gravita, classe, ora, cod_anagrafica) VALUES (%s, %s, %s, %s, %s, %s)"
                values = (tipo_problema, data, gravita, classe, ora_attuale, cod_an[0])
                cur.execute(query, values)
                connection.commit()
                return templates.TemplateResponse("ringraziamento.html", {"request": request})
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
@app.get("/get_storico",response_class=HTMLResponse)
def getstorico(request: Request):
    redirect_url = "/storico"
    return templates.TemplateResponse("loading.html", {"request": request, "endpoint": redirect_url})
@app.get('/storico', response_class=HTMLResponse)
async def index(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                cur = connection.cursor()
                admin = f"select tipo from utenti where username = '{username}'"
                cur.execute(admin)
                tipo = cur.fetchall()
                print(tipo,username)
                if tipo[0][0] == "a":
                    cur.execute("SELECT report.tipo_problema, report.gravita, report.classe, report.data_r, report.ora, report.stato, utenti.username, utenti.mail, report.id_report FROM report, utenti where report.cod_anagrafica = utenti.id_anagrafica ")
                    tickets = cur.fetchall()

                    # Separare i ticket aperti e chiusi in due liste diverse
                    tickets_aperti = [ticket for ticket in tickets if ticket[5] == 0]
                    tickets_chiusi = [ticket for ticket in tickets if ticket[5] == 1]
                    print(tickets_aperti)
                    print(tickets_chiusi)
                    return templates.TemplateResponse("admin_page.html", {"request": request, "tickets_aperti": tickets_aperti, "tickets_chiusi": tickets_chiusi})
                else:
                    raise HTTPException(status_code=401, detail="Authentication required")
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")




 

@app.get('/flag')
def flag(request: Request,id_report: str):
    cur = connection.cursor()
    print("id-report: ", id_report)
    query = f"update report set stato = 1 where id_report = {id_report}"
    cur.execute(query)
    connection.commit()
    cur.close()
    logging.warning(f"Ticket chiuso")
    return JSONResponse(content={"message": "Ticket approvato con successo."}, status_code=200)


# Endpoint per ottenere il tipo di utente associato al token JWT
@app.get("/get_user_type")
async def get_user_type(request: Request,token_data: TokenData = Depends(verify_token)):
    # Qui inserisci la logica per ottenere il tipo di utente dal database o da altre fonti
    # Per semplicità, restituirò un valore fittizio basato sul nome utente
    session_token = request.cookies.get("session_token")
    payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
    username = payload.get("username")
    cur = connection.cursor()
    query = f"select tipo from utenti where username = '{username}'"
    cur.execute(query)
    dati = cur.fetchall()
    print(dati)
    if dati[0][0] == "a":
        user_type = "admin"
    else:
        user_type = "normal"
    return {"user_type": user_type}
@app.get("/get_approva",response_class=HTMLResponse)
def get_approva(request: Request):
    redirect_url = "/approva"
    return templates.TemplateResponse("loading.html", {"request": request, "endpoint": redirect_url})
@app.get("/approva", response_class= HTMLResponse)
def approva(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                cur = connection.cursor()
                admin = f"select tipo from utenti where username = '{username}'"
                cur.execute(admin)
                tipo = cur.fetchall()
                print(tipo,username)
                if tipo[0][0] == "a":
                    cur.execute("select nome,cognome,username, approvato,id_anagrafica from utenti where approvato = false")
                    tickets_in_sospeso = cur.fetchall()
                    cur.execute("select nome,cognome,username, approvato,id_anagrafica from utenti where approvato = true")
                    tickets_approvati = cur.fetchall()
                    print(type(tickets_approvati[0][3]))

                    
                    return templates.TemplateResponse("approva.html", {"request": request, "tickets_in_sospeso": tickets_in_sospeso, "tickets_approvati": tickets_approvati})
                else:
                    raise HTTPException(status_code=401, detail="Authentication required")
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")

@app.post("/ban")
async def ban(id: str):
    cur = connection.cursor()
    query = f"update utenti set approvato = false where id_anagrafica = {id}"
    cur.execute(query)
    logging.warning(f"utente {id} bannato")
    connection.commit()
@app.post("/approva_u")
async def approva(id: str):
    cur = connection.cursor()
    query = f"update utenti set approvato = true where id_anagrafica = {id}"
    cur.execute(query)
    logging.warning(f"utente {id} approvato")
    connection.commit()
@app.get("/get_impostazioni",response_class=HTMLResponse)
def get_imp(request:Request):
    redirect_url = "/impostazioni"
    return templates.TemplateResponse("loading.html", {"request": request, "endpoint": redirect_url})
@app.get("/impostazioni", response_class=HTMLResponse)
def return_impostazioni(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                return templates.TemplateResponse("imposta_user.html", {"request": request})
            else:
                raise HTTPException(status_code=401, detail="Authentication required")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
@app.get("/profile")
def profile(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                cur = connection.cursor()
                cur.execute(f"select nome,cognome,mail from utenti where username = '{username}'")
                dati = cur.fetchall()
                print(dati)
                return {
                    "nome": dati[0][0],
                    "cognome": dati[0][1],
                    "email": dati[0][2]
                    }       
            else:
                raise HTTPException(status_code=401, detail="Authentication required")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
@app.post("/update_profile")
def update(request: Request, nome: str=Form(...), cognome: str=Form(...), mail: str=Form(...)):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                cur = connection.cursor()
                cur.execute(f"update utenti set nome = '{nome}', cognome = '{cognome}', mail = '{mail}' where username = '{username}'")
                connection.commit()   
            else:
                raise HTTPException(status_code=401, detail="Authentication required")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
@app.get("/modifica_password", response_class=HTMLResponse)
def return_modifica(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                return templates.TemplateResponse("cambia_password.html", {"request": request})
            else:
                raise HTTPException(status_code=401, detail="Authentication required")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")


@app.post("/update_password")
def update_pw(request: Request,newPassword: str=Form(...)):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                cur = connection.cursor()
                password_hashed = codifica_sha256(newPassword)  # Assicurati che questa funzione crei un hash sicuro della password
                cur.execute(f"UPDATE utenti SET password_l = '{password_hashed}' WHERE username = '{username}'")
                connection.commit()
            else:
                raise HTTPException(status_code=401, detail="Authentication required")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
    

@app.get("/chisiamo", response_class=HTMLResponse)
def chi_siamo(request: Request):
    return templates.TemplateResponse("chi_siamo.html", {"request": request})
'''
@app.post("/update_password")
def update_password(new_password: str):
    # Qui puoi aggiornare la password nel tuo database utilizzando new_password
    # Ad esempio, potresti utilizzare SQLAlchemy per aggiornare il record dell'utente nel database
    # In questo esempio, stampiamo semplicemente la nuova password
    print("Nuova password:", new_password)
    return {"message": "Password aggiornata con successo"}
    '''
@app.get("/aiuto", response_class=HTMLResponse)
def aiuto(request: Request):
    return templates.TemplateResponse("help.html", {"request": request})
@app.post("/help")
async def help(name: str=Form(...),email: str=Form(...),problem: str=Form(...)):
    print("")
    oggetto = "Segnalazione problema web app"
    data_ora_corrente = datetime.now()
    data_ora_formattata = data_ora_corrente.strftime("%Y-%m-%d %H:%M:%S")
    corpo = f"Si è riscontrato un problema alla web app segnalato da: {email} | ({name}), alle {data_ora_formattata}:\n{problem}\nPowered by EINAUDI TICKETING"
    invia_mail.componi_e_invia(oggetto,corpo)
@app.get("/get_hystogram",response_class=HTMLResponse)
def hysto(request:Request):
    redirect_url = "/hystogram"
    return templates.TemplateResponse("loading.html", {"request": request, "endpoint": redirect_url})
@app.get("/hystogram", response_class=HTMLResponse)
def hystogram(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                prov.home(connection)
                return templates.TemplateResponse("istogramma_guasti.html", {"request": request})
            else:
                raise HTTPException(status_code=401, detail="Authentication required")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
@app.get("/get_excel",response_class=HTMLResponse)
def excel_get(request: Request):
    redirect_url = "/excel"
    return templates.TemplateResponse("loading.html", {"request": request, "endpoint": redirect_url})
@app.get("/excel",response_class=HTMLResponse)
def excel_v(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                return templates.TemplateResponse("excel.html", {"request": request})            
            else:
                raise HTTPException(status_code=401, detail="Authentication required")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")

@app.get("/create_excel")
async def excel(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        try:
            payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("username")
            if username:
                cur = connection.cursor()
                cur.execute("SELECT id_anagrafica, nome, cognome,mail FROM utenti")  # Seleziona tutte le colonne necessarie in una singola query
                user_data = cur.fetchall()
                print(user_data)
                # Creazione di un DataFrame pandas dai dati degli utenti
                df = pd.DataFrame(user_data, columns=['ID', 'NOME', 'COGNOME', 'MAIL'])

                # Specifica il percorso e il nome del file Excel da salvare
                excel_file_path = "excel/users.xlsx"

                # Salvataggio del DataFrame come file Excel
                df.to_excel(excel_file_path, index=False)

                # Ritorna il file Excel come risposta
                return FileResponse(excel_file_path, filename="users.xlsx")  
            else:
                raise HTTPException(status_code=401, detail="Authentication required")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Token decoding error")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
'''
if __name__ == "__main__":
    # Avvia il server FastAPI utilizzando uvicorn
    uvicorn.run(app, host="0.0.0.0",port=8000)
'''